#!/usr/bin/env python3
"""
Performance Monitor for SubsAI
Comprehensive performance monitoring and metrics collection
"""

import time
import logging
import threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque
import json
import statistics
from datetime import datetime, timedelta

@dataclass
class PerformanceMetric:
    """Individual performance metric"""
    name: str
    value: float
    unit: str
    timestamp: float = field(default_factory=time.time)
    category: str = "general"
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class PerformanceSummary:
    """Summary of performance metrics over a time period"""
    category: str
    start_time: float
    end_time: float
    metrics: Dict[str, Any] = field(default_factory=dict)
    total_operations: int = 0
    success_rate: float = 0.0
    average_response_time: float = 0.0


class PerformanceMonitor:
    """
    Centralized performance monitoring system for all SubsAI components
    """
    
    def __init__(self, max_history_hours: int = 24, collection_interval: float = 30.0):
        """
        Initialize performance monitor
        
        :param max_history_hours: Maximum hours of history to keep
        :param collection_interval: Interval between metric collection in seconds
        """
        self.max_history_hours = max_history_hours
        self.collection_interval = collection_interval
        
        # Metrics storage
        self.metrics_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self.current_metrics: Dict[str, PerformanceMetric] = {}
        
        # Component tracking
        self.component_stats: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self.operation_counts: Dict[str, int] = defaultdict(int)
        self.operation_times: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        
        # Performance thresholds and alerts
        self.thresholds: Dict[str, float] = {
            'transcription_time_warning': 30.0,  # seconds
            'translation_time_warning': 10.0,   # seconds
            'memory_usage_warning': 8.0,        # GB
            'api_response_time_warning': 5.0,   # seconds
            'cache_hit_rate_warning': 0.5,      # 50%
            'error_rate_warning': 0.1           # 10%
        }
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Background collection
        self._collecting = False
        self._collection_thread: Optional[threading.Thread] = None
        
        # Logger
        self.logger = logging.getLogger(__name__)
        self.logger.info("PerformanceMonitor initialized")
    
    def record_metric(self, name: str, value: float, unit: str = "", 
                     category: str = "general", tags: Dict[str, str] = None):
        """Record a performance metric"""
        with self._lock:
            metric = PerformanceMetric(
                name=name,
                value=value,
                unit=unit,
                category=category,
                tags=tags or {}
            )
            
            key = f"{category}.{name}"
            self.current_metrics[key] = metric
            self.metrics_history[key].append(metric)
            
            # Clean old metrics
            self._cleanup_old_metrics(key)
    
    def record_operation_time(self, operation: str, duration: float, success: bool = True):
        """Record operation timing"""
        with self._lock:
            self.operation_counts[operation] += 1
            self.operation_times[operation].append({
                'duration': duration,
                'success': success,
                'timestamp': time.time()
            })
            
            # Record as metric
            self.record_metric(
                f"{operation}_duration",
                duration,
                "seconds",
                "operations",
                {"success": str(success)}
            )
    
    def record_component_stats(self, component: str, stats: Dict[str, Any]):
        """Record stats from a component"""
        with self._lock:
            self.component_stats[component] = {
                **stats,
                'last_updated': time.time()
            }
            
            # Convert stats to individual metrics
            for key, value in stats.items():
                if isinstance(value, (int, float)):
                    self.record_metric(
                        key,
                        float(value),
                        "",
                        component,
                        {"component": component}
                    )
    
    def start_monitoring(self, components: List[Any] = None):
        """Start background monitoring"""
        if self._collecting:
            return
        
        self._collecting = True
        self._collection_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(components,),
            daemon=True
        )
        self._collection_thread.start()
        self.logger.info("Started performance monitoring")
    
    def stop_monitoring(self):
        """Stop background monitoring"""
        self._collecting = False
        if self._collection_thread:
            self._collection_thread.join(timeout=5.0)
        self.logger.info("Stopped performance monitoring")
    
    def _monitoring_loop(self, components: List[Any] = None):
        """Background monitoring loop"""
        while self._collecting:
            try:
                # Collect metrics from components
                if components:
                    for component in components:
                        try:
                            self._collect_from_component(component)
                        except Exception as e:
                            self.logger.error(f"Error collecting from component {type(component).__name__}: {e}")
                
                # System metrics
                self._collect_system_metrics()
                
                # Check thresholds and alerts
                self._check_alerts()
                
                time.sleep(self.collection_interval)
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(5.0)  # Brief pause on error
    
    def _collect_from_component(self, component):
        """Collect metrics from a specific component"""
        component_name = type(component).__name__
        
        # Try to get stats from component
        if hasattr(component, 'get_stats'):
            try:
                stats = component.get_stats()
                if stats:
                    self.record_component_stats(component_name, stats)
            except Exception as e:
                self.logger.debug(f"Failed to get stats from {component_name}: {e}")
        
        # Model manager specific metrics
        if 'ModelManager' in component_name:
            self._collect_model_manager_metrics(component)
        
        # Batch processor specific metrics
        elif 'BatchProcessor' in component_name:
            self._collect_batch_processor_metrics(component)
        
        # API client specific metrics
        elif 'APIClient' in component_name:
            self._collect_api_client_metrics(component)
        
        # Translator specific metrics
        elif 'Translator' in component_name:
            self._collect_translator_metrics(component)
    
    def _collect_model_manager_metrics(self, manager):
        """Collect specific metrics from model manager"""
        try:
            # Memory usage estimation
            if hasattr(manager, '_estimate_total_memory'):
                memory_usage = manager._estimate_total_memory() / (1024**3)  # GB
                self.record_metric("memory_usage", memory_usage, "GB", "model_manager")
            
            # Pool utilization
            if hasattr(manager, 'model_pools'):
                total_instances = 0
                busy_instances = 0
                for pool in manager.model_pools.values():
                    total_instances += len(pool.instances)
                    busy_instances += sum(1 for i in pool.instances if i.is_busy)
                
                if total_instances > 0:
                    utilization = busy_instances / total_instances
                    self.record_metric("pool_utilization", utilization, "ratio", "model_manager")
            
        except Exception as e:
            self.logger.debug(f"Error collecting model manager metrics: {e}")
    
    def _collect_batch_processor_metrics(self, processor):
        """Collect specific metrics from batch processor"""
        try:
            # Queue lengths
            if hasattr(processor, '_active_jobs'):
                active_jobs = len(processor._active_jobs)
                self.record_metric("active_jobs", active_jobs, "count", "batch_processor")
            
            # Processing efficiency
            if hasattr(processor, 'performance_stats'):
                stats = processor.performance_stats
                for key, value in stats.items():
                    if isinstance(value, (int, float)):
                        self.record_metric(key, value, "", "batch_processor")
            
        except Exception as e:
            self.logger.debug(f"Error collecting batch processor metrics: {e}")
    
    def _collect_api_client_metrics(self, client):
        """Collect specific metrics from API client"""
        try:
            if hasattr(client, 'stats'):
                stats = client.stats
                
                # Calculate success rate
                total_requests = stats.get('total_requests', 0)
                successful_requests = stats.get('successful_requests', 0)
                if total_requests > 0:
                    success_rate = successful_requests / total_requests
                    self.record_metric("api_success_rate", success_rate, "ratio", "api_client")
                
                # Average response time
                avg_response_time = stats.get('average_response_time', 0)
                self.record_metric("api_response_time", avg_response_time, "seconds", "api_client")
            
        except Exception as e:
            self.logger.debug(f"Error collecting API client metrics: {e}")
    
    def _collect_translator_metrics(self, translator):
        """Collect specific metrics from translator"""
        try:
            if hasattr(translator, 'get_stats'):
                stats = translator.get_stats()
                
                # Batch efficiency
                total_requests = stats.get('total_requests', 0)
                batched_requests = stats.get('batched_requests', 0)
                if total_requests > 0:
                    batch_efficiency = batched_requests / total_requests
                    self.record_metric("batch_efficiency", batch_efficiency, "ratio", "translator")
                
                # Cache effectiveness
                cache_hits = stats.get('cache_hits', 0)
                if total_requests > 0:
                    cache_hit_rate = cache_hits / total_requests
                    self.record_metric("translation_cache_hit_rate", cache_hit_rate, "ratio", "translator")
            
        except Exception as e:
            self.logger.debug(f"Error collecting translator metrics: {e}")
    
    def _collect_system_metrics(self):
        """Collect system-level metrics"""
        try:
            import psutil
            
            # CPU usage
            cpu_percent = psutil.cpu_percent()
            self.record_metric("cpu_usage", cpu_percent, "percent", "system")
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_usage_gb = memory.used / (1024**3)
            memory_percent = memory.percent
            self.record_metric("system_memory_usage", memory_usage_gb, "GB", "system")
            self.record_metric("system_memory_percent", memory_percent, "percent", "system")
            
            # GPU metrics if available
            try:
                import torch
                if torch.cuda.is_available():
                    for i in range(torch.cuda.device_count()):
                        memory_allocated = torch.cuda.memory_allocated(i) / (1024**3)
                        memory_reserved = torch.cuda.memory_reserved(i) / (1024**3)
                        self.record_metric(f"gpu_{i}_memory_allocated", memory_allocated, "GB", "gpu")
                        self.record_metric(f"gpu_{i}_memory_reserved", memory_reserved, "GB", "gpu")
            except ImportError:
                pass
            
        except ImportError:
            # psutil not available
            pass
        except Exception as e:
            self.logger.debug(f"Error collecting system metrics: {e}")
    
    def _check_alerts(self):
        """Check performance thresholds and generate alerts"""
        alerts = []
        
        with self._lock:
            # Check transcription times
            if 'operations.transcription_duration' in self.metrics_history:
                recent_transcriptions = list(self.metrics_history['operations.transcription_duration'])[-10:]
                if recent_transcriptions:
                    avg_time = statistics.mean(m.value for m in recent_transcriptions)
                    if avg_time > self.thresholds['transcription_time_warning']:
                        alerts.append(f"High transcription time: {avg_time:.2f}s (threshold: {self.thresholds['transcription_time_warning']}s)")
            
            # Check memory usage
            if 'model_manager.memory_usage' in self.current_metrics:
                memory_usage = self.current_metrics['model_manager.memory_usage'].value
                if memory_usage > self.thresholds['memory_usage_warning']:
                    alerts.append(f"High memory usage: {memory_usage:.2f}GB (threshold: {self.thresholds['memory_usage_warning']}GB)")
            
            # Check API response times
            if 'api_client.api_response_time' in self.current_metrics:
                response_time = self.current_metrics['api_client.api_response_time'].value
                if response_time > self.thresholds['api_response_time_warning']:
                    alerts.append(f"High API response time: {response_time:.2f}s (threshold: {self.thresholds['api_response_time_warning']}s)")
            
            # Check cache hit rates
            if 'translator.translation_cache_hit_rate' in self.current_metrics:
                hit_rate = self.current_metrics['translator.translation_cache_hit_rate'].value
                if hit_rate < self.thresholds['cache_hit_rate_warning']:
                    alerts.append(f"Low cache hit rate: {hit_rate:.2%} (threshold: {self.thresholds['cache_hit_rate_warning']:.2%})")
        
        # Log alerts
        for alert in alerts:
            self.logger.warning(f"Performance Alert: {alert}")
    
    def _cleanup_old_metrics(self, key: str):
        """Remove metrics older than max_history_hours"""
        cutoff_time = time.time() - (self.max_history_hours * 3600)
        
        while (self.metrics_history[key] and 
               self.metrics_history[key][0].timestamp < cutoff_time):
            self.metrics_history[key].popleft()
    
    def get_summary(self, category: str = None, hours: int = 1) -> PerformanceSummary:
        """Get performance summary for a time period"""
        end_time = time.time()
        start_time = end_time - (hours * 3600)
        
        with self._lock:
            relevant_metrics = {}
            total_operations = 0
            successful_operations = 0
            response_times = []
            
            for key, metrics_deque in self.metrics_history.items():
                if category and not key.startswith(f"{category}."):
                    continue
                
                # Filter metrics by time period
                period_metrics = [
                    m for m in metrics_deque 
                    if start_time <= m.timestamp <= end_time
                ]
                
                if period_metrics:
                    values = [m.value for m in period_metrics]
                    relevant_metrics[key] = {
                        'count': len(values),
                        'avg': statistics.mean(values),
                        'min': min(values),
                        'max': max(values),
                        'std': statistics.stdev(values) if len(values) > 1 else 0.0
                    }
                    
                    # Track operations for success rate calculation
                    if 'duration' in key:
                        total_operations += len(values)
                        # Assume success if no explicit failure info
                        successful_operations += len(values)
                        response_times.extend(values)
            
            # Calculate overall metrics
            success_rate = (successful_operations / total_operations) if total_operations > 0 else 0.0
            avg_response_time = statistics.mean(response_times) if response_times else 0.0
            
            return PerformanceSummary(
                category=category or "all",
                start_time=start_time,
                end_time=end_time,
                metrics=relevant_metrics,
                total_operations=total_operations,
                success_rate=success_rate,
                average_response_time=avg_response_time
            )
    
    def get_current_metrics(self) -> Dict[str, PerformanceMetric]:
        """Get current metrics snapshot"""
        with self._lock:
            return self.current_metrics.copy()
    
    def get_component_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get latest component statistics"""
        with self._lock:
            return self.component_stats.copy()
    
    def export_metrics(self, format: str = "json", hours: int = 24) -> str:
        """Export metrics in specified format"""
        summary = self.get_summary(hours=hours)
        current = self.get_current_metrics()
        
        data = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'category': summary.category,
                'period_hours': hours,
                'total_operations': summary.total_operations,
                'success_rate': summary.success_rate,
                'average_response_time': summary.average_response_time,
                'metrics': summary.metrics
            },
            'current_metrics': {
                key: {
                    'value': metric.value,
                    'unit': metric.unit,
                    'category': metric.category,
                    'timestamp': metric.timestamp
                }
                for key, metric in current.items()
            },
            'component_stats': self.get_component_stats()
        }
        
        if format.lower() == 'json':
            return json.dumps(data, indent=2)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def get_performance_insights(self) -> List[str]:
        """Get AI-powered performance insights and recommendations"""
        insights = []
        current = self.get_current_metrics()
        
        # Memory insights
        if 'model_manager.memory_usage' in current:
            memory_usage = current['model_manager.memory_usage'].value
            if memory_usage > 6.0:
                insights.append(f"🔶 High memory usage detected ({memory_usage:.1f}GB). Consider reducing model cache size or using smaller models.")
        
        # Cache insights
        if 'translator.translation_cache_hit_rate' in current:
            hit_rate = current['translator.translation_cache_hit_rate'].value
            if hit_rate < 0.3:
                insights.append(f"🔶 Low translation cache hit rate ({hit_rate:.1%}). Consider increasing cache TTL or pre-warming cache.")
        
        # API insights
        if 'api_client.api_response_time' in current:
            response_time = current['api_client.api_response_time'].value
            if response_time > 3.0:
                insights.append(f"🔶 High API response time ({response_time:.2f}s). Consider using batch requests or local models.")
        
        # Batch efficiency insights
        if 'translator.batch_efficiency' in current:
            batch_efficiency = current['translator.batch_efficiency'].value
            if batch_efficiency < 0.5:
                insights.append(f"🔶 Low batch efficiency ({batch_efficiency:.1%}). Consider increasing batch timeout or size.")
        
        # Success insights
        summary = self.get_summary(hours=1)
        if summary.success_rate < 0.9 and summary.total_operations > 10:
            insights.append(f"🔶 Lower success rate ({summary.success_rate:.1%}) detected. Check error logs for issues.")
        
        if not insights:
            insights.append("✅ All performance metrics look good!")
        
        return insights


# Global performance monitor instance
_global_performance_monitor: Optional[PerformanceMonitor] = None

def get_performance_monitor() -> PerformanceMonitor:
    """Get or create global performance monitor"""
    global _global_performance_monitor
    
    if _global_performance_monitor is None:
        _global_performance_monitor = PerformanceMonitor()
    
    return _global_performance_monitor

def cleanup_performance_monitor():
    """Cleanup global performance monitor"""
    global _global_performance_monitor
    
    if _global_performance_monitor is not None:
        _global_performance_monitor.stop_monitoring()
        _global_performance_monitor = None