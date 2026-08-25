#!/usr/bin/env python3
"""
Async Model Manager for SubsAI
Handles model lifecycle, connection pooling, and resource management for improved performance
"""

import asyncio
import logging
import time
import weakref
from typing import Dict, List, Optional, Any, Union, Set
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
import threading
import gc
from pathlib import Path

# Import SubsAI components
from subsai import SubsAI, Tools
from subsai.models.abstract_model import AbstractModel
from subsai.utils import get_optimal_device, is_cuda_available


@dataclass
class ModelInstance:
    """Represents a model instance with metadata"""
    model: AbstractModel
    model_name: str
    config: Dict[str, Any]
    device: str
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    use_count: int = 0
    is_busy: bool = False
    memory_usage: Optional[int] = None  # Memory usage in bytes


@dataclass
class ModelPool:
    """Pool of model instances for a specific model type"""
    instances: List[ModelInstance] = field(default_factory=list)
    max_instances: int = 3
    max_idle_time: float = 300.0  # 5 minutes
    _lock: threading.Lock = field(default_factory=threading.Lock)


class AsyncModelManager:
    """
    Manages model instances with async capabilities, connection pooling, and resource optimization
    """
    
    def __init__(self, max_workers: int = 4, memory_limit_gb: float = 8.0):
        """
        Initialize the async model manager
        
        :param max_workers: Maximum number of worker threads for model operations
        :param memory_limit_gb: Soft memory limit for model caching
        """
        self.subs_ai = SubsAI()
        self.tools = Tools()
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="ModelWorker")
        self.memory_limit_bytes = int(memory_limit_gb * 1024 * 1024 * 1024)
        
        # Model pools organized by model configuration signature
        self.model_pools: Dict[str, ModelPool] = {}
        self._global_lock = threading.Lock()
        
        # Performance tracking
        self.stats = {
            'model_creations': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'memory_cleanups': 0,
            'total_memory_freed': 0
        }
        
        # Background cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        # Logger
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"AsyncModelManager initialized with {max_workers} workers, {memory_limit_gb}GB memory limit")
        
        # Start background cleanup
        asyncio.create_task(self._start_background_cleanup())
    
    def _create_pool_key(self, model_name: str, config: Dict[str, Any]) -> str:
        """Create a unique key for model configuration"""
        # Sort config items for consistent key generation
        config_str = "|".join(f"{k}:{v}" for k, v in sorted(config.items()))
        return f"{model_name}#{config_str}"
    
    async def _start_background_cleanup(self):
        """Start background cleanup task"""
        try:
            await asyncio.sleep(1)  # Wait for initialization
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        except Exception as e:
            self.logger.error(f"Failed to start background cleanup: {e}")
    
    async def _cleanup_loop(self):
        """Background cleanup loop for idle models"""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(60)  # Cleanup every minute
                await self._cleanup_idle_models()
                await self._manage_memory()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")
    
    async def _cleanup_idle_models(self):
        """Remove idle models that exceed max_idle_time"""
        current_time = time.time()
        cleaned_pools = []
        
        with self._global_lock:
            for pool_key, pool in list(self.model_pools.items()):
                with pool._lock:
                    # Remove idle instances
                    initial_count = len(pool.instances)
                    pool.instances = [
                        instance for instance in pool.instances
                        if (current_time - instance.last_used) < pool.max_idle_time or instance.is_busy
                    ]
                    
                    removed_count = initial_count - len(pool.instances)
                    if removed_count > 0:
                        self.logger.info(f"Cleaned up {removed_count} idle models from pool {pool_key}")
                    
                    # Remove empty pools
                    if not pool.instances:
                        cleaned_pools.append(pool_key)
            
            # Remove empty pools
            for pool_key in cleaned_pools:
                del self.model_pools[pool_key]
                self.logger.info(f"Removed empty model pool: {pool_key}")
    
    async def _manage_memory(self):
        """Manage memory usage by cleaning up least recently used models"""
        try:
            total_memory = self._estimate_total_memory()
            
            if total_memory > self.memory_limit_bytes:
                self.logger.warning(f"Memory usage ({total_memory / 1024**3:.2f}GB) exceeds limit ({self.memory_limit_bytes / 1024**3:.2f}GB)")
                
                # Collect all non-busy instances with their usage info
                all_instances = []
                with self._global_lock:
                    for pool_key, pool in self.model_pools.items():
                        with pool._lock:
                            for instance in pool.instances:
                                if not instance.is_busy:
                                    all_instances.append((pool_key, instance))
                
                # Sort by last used time (LRU)
                all_instances.sort(key=lambda x: x[1].last_used)
                
                # Remove oldest instances until memory is under limit
                freed_memory = 0
                for pool_key, instance in all_instances:
                    if total_memory - freed_memory <= self.memory_limit_bytes:
                        break
                    
                    # Remove instance from pool
                    pool = self.model_pools.get(pool_key)
                    if pool:
                        with pool._lock:
                            if instance in pool.instances:
                                pool.instances.remove(instance)
                                freed_memory += instance.memory_usage or 0
                                self.logger.info(f"Freed {(instance.memory_usage or 0) / 1024**2:.1f}MB from {pool_key}")
                
                # Force garbage collection
                gc.collect()
                
                # Clear CUDA cache if available
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                        torch.cuda.synchronize()
                        self.logger.info("Cleared CUDA cache")
                except ImportError:
                    pass
                
                self.stats['memory_cleanups'] += 1
                self.stats['total_memory_freed'] += freed_memory
                
        except Exception as e:
            self.logger.error(f"Error managing memory: {e}")
    
    def _estimate_total_memory(self) -> int:
        """Estimate total memory usage of all cached models"""
        total = 0
        with self._global_lock:
            for pool in self.model_pools.values():
                with pool._lock:
                    for instance in pool.instances:
                        if instance.memory_usage:
                            total += instance.memory_usage
                        else:
                            # Rough estimate for models without explicit memory tracking
                            total += 500 * 1024 * 1024  # 500MB per model
        return total
    
    async def get_model(self, model_name: str, config: Dict[str, Any] = None) -> ModelInstance:
        """
        Get a model instance from the pool or create a new one
        
        :param model_name: Name of the model
        :param config: Model configuration
        :return: ModelInstance
        """
        if config is None:
            config = {}
        
        pool_key = self._create_pool_key(model_name, config)
        
        # Try to get from pool first
        with self._global_lock:
            if pool_key not in self.model_pools:
                self.model_pools[pool_key] = ModelPool()
            
            pool = self.model_pools[pool_key]
        
        # Look for available instance in pool
        with pool._lock:
            for instance in pool.instances:
                if not instance.is_busy:
                    instance.is_busy = True
                    instance.last_used = time.time()
                    instance.use_count += 1
                    self.stats['cache_hits'] += 1
                    self.logger.debug(f"Cache hit for model {pool_key}")
                    return instance
        
        # No available instance, create new one if pool not full
        with pool._lock:
            if len(pool.instances) < pool.max_instances:
                # Create new instance
                self.stats['cache_misses'] += 1
                instance = await self._create_model_instance(model_name, config)
                instance.is_busy = True
                pool.instances.append(instance)
                self.logger.info(f"Created new model instance for {pool_key} (pool size: {len(pool.instances)})")
                return instance
        
        # Pool is full, wait for an instance to become available
        self.logger.info(f"Pool {pool_key} is full, waiting for available instance...")
        while True:
            await asyncio.sleep(0.1)  # Small delay to avoid busy waiting
            
            with pool._lock:
                for instance in pool.instances:
                    if not instance.is_busy:
                        instance.is_busy = True
                        instance.last_used = time.time()
                        instance.use_count += 1
                        self.logger.debug(f"Got available instance for {pool_key}")
                        return instance
    
    async def _create_model_instance(self, model_name: str, config: Dict[str, Any]) -> ModelInstance:
        """Create a new model instance in a background thread"""
        
        def _create_model():
            # Add device configuration if not specified
            final_config = config.copy()
            if 'device' not in final_config:
                device = get_optimal_device()
                final_config['device'] = device
            else:
                device = final_config['device']
            
            # Create model using existing SubsAI infrastructure
            model = self.subs_ai.create_model(model_name, final_config)
            
            # Estimate memory usage
            memory_usage = self._estimate_model_memory(model, device)
            
            return ModelInstance(
                model=model,
                model_name=model_name,
                config=final_config,
                device=device,
                memory_usage=memory_usage
            )
        
        # Run model creation in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        instance = await loop.run_in_executor(self.executor, _create_model)
        
        self.stats['model_creations'] += 1
        self.logger.info(f"Created model {model_name} on device {instance.device} ({(instance.memory_usage or 0) / 1024**2:.1f}MB)")
        
        return instance
    
    def _estimate_model_memory(self, model: AbstractModel, device: str) -> Optional[int]:
        """Estimate memory usage of a model"""
        try:
            if device.startswith('cuda'):
                import torch
                if torch.cuda.is_available():
                    # Get GPU memory usage (rough estimate)
                    torch.cuda.synchronize()
                    memory_allocated = torch.cuda.memory_allocated()
                    return memory_allocated
            
            # Fallback: rough estimate based on model type
            model_name = model.__class__.__name__.lower()
            if 'whisper' in model_name:
                if 'large' in str(model):
                    return 3 * 1024 * 1024 * 1024  # 3GB for large models
                elif 'medium' in str(model):
                    return 1.5 * 1024 * 1024 * 1024  # 1.5GB for medium models
                else:
                    return 500 * 1024 * 1024  # 500MB for small models
            
            return 100 * 1024 * 1024  # 100MB default
            
        except Exception as e:
            self.logger.warning(f"Failed to estimate model memory: {e}")
            return None
    
    def return_model(self, instance: ModelInstance):
        """Return a model instance to the pool"""
        instance.is_busy = False
        instance.last_used = time.time()
        self.logger.debug(f"Returned model instance {instance.model_name} to pool")
    
    @asynccontextmanager
    async def use_model(self, model_name: str, config: Dict[str, Any] = None):
        """Context manager for using a model instance"""
        instance = await self.get_model(model_name, config)
        try:
            yield instance
        finally:
            self.return_model(instance)
    
    async def transcribe_async(self, media_file: str, model_name: str, config: Dict[str, Any] = None):
        """Async wrapper for transcription"""
        async with self.use_model(model_name, config) as instance:
            loop = asyncio.get_event_loop()
            # Run transcription in thread pool to avoid blocking
            result = await loop.run_in_executor(
                self.executor, 
                lambda: self.subs_ai.transcribe(media_file, instance.model)
            )
            return result
    
    async def translate_async(self, subs, source_language: str, target_language: str, 
                            translation_model: str, intermediate_language: str = None):
        """Async wrapper for translation"""
        
        def _translate():
            return self.tools.translate(
                subs=subs,
                source_language=source_language,
                target_language=target_language,
                model=translation_model,
                intermediate_language=intermediate_language
            )
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(self.executor, _translate)
        return result
    
    async def shutdown(self):
        """Shutdown the model manager and cleanup resources"""
        self.logger.info("Shutting down AsyncModelManager...")
        
        # Signal cleanup task to stop
        self._shutdown_event.set()
        
        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        # Clear all model pools
        with self._global_lock:
            self.model_pools.clear()
        
        # Force garbage collection
        gc.collect()
        
        # Clear CUDA cache
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
        
        self.logger.info("AsyncModelManager shutdown complete")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        with self._global_lock:
            pool_stats = {}
            for pool_key, pool in self.model_pools.items():
                with pool._lock:
                    pool_stats[pool_key] = {
                        'instances': len(pool.instances),
                        'busy_instances': sum(1 for i in pool.instances if i.is_busy),
                        'total_uses': sum(i.use_count for i in pool.instances)
                    }
        
        return {
            **self.stats,
            'pools': pool_stats,
            'total_memory_estimate': f"{self._estimate_total_memory() / 1024**3:.2f}GB"
        }