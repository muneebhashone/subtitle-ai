#!/usr/bin/env python3
"""
Async Batch Processor for SubsAI
Enhanced batch processing with concurrent job execution and async capabilities
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import os
from pathlib import Path
import tempfile
import gc

# Import SubsAI components
from subsai.batch_processor import JobStatus, JobConfig, ProgressTracker
from subsai.async_model_manager import AsyncModelManager
from subsai.async_api_client import DeepSeekAPIClient, get_or_create_client
from subsai.analytics import AnalyticsService
from subsai.utils.file_manager import cleanup_batch_output_dir
from subsai.utils import get_optimal_device, is_cuda_available


@dataclass
class AsyncJobResult:
    """Enhanced job result with async processing metadata"""
    job_id: str
    success: bool
    results: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None
    processing_time: float = 0.0
    device_used: Optional[str] = None
    cache_hits: int = 0
    api_calls: int = 0


class AsyncBatchProcessor:
    """
    Enhanced batch processor with async capabilities and concurrent job execution
    """
    
    def __init__(self, 
                 max_concurrent_jobs: int = 3,
                 max_workers_per_job: int = 2,
                 memory_limit_gb: float = 8.0,
                 enable_caching: bool = True,
                 user_id: Optional[int] = None):
        """
        Initialize the async batch processor
        
        :param max_concurrent_jobs: Maximum number of jobs to process concurrently
        :param max_workers_per_job: Maximum workers per individual job
        :param memory_limit_gb: Memory limit for model caching
        :param enable_caching: Whether to enable result caching
        :param user_id: User ID for analytics tracking
        """
        self.max_concurrent_jobs = max_concurrent_jobs
        self.max_workers_per_job = max_workers_per_job
        self.enable_caching = enable_caching
        self.user_id = user_id
        
        # Core components
        self.progress_tracker = ProgressTracker()
        self.model_manager = AsyncModelManager(
            max_workers=max_workers_per_job * max_concurrent_jobs,
            memory_limit_gb=memory_limit_gb
        )
        self.analytics = AnalyticsService()
        
        # Processing state
        self._processing = False
        self._should_stop = False
        self._processing_task: Optional[asyncio.Task] = None
        self._job_semaphore = asyncio.Semaphore(max_concurrent_jobs)
        self._active_jobs: Dict[str, asyncio.Task] = {}
        
        # Caching
        self.result_cache: Dict[str, Any] = {}
        self.cache_ttl = 3600  # 1 hour
        
        # Performance metrics
        self.performance_stats = {
            'total_jobs_processed': 0,
            'average_job_time': 0.0,
            'total_processing_time': 0.0,
            'concurrent_jobs_peak': 0,
            'cache_hit_rate': 0.0,
            'memory_efficiency': 0.0
        }
        
        # Logger
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"AsyncBatchProcessor initialized with {max_concurrent_jobs} max concurrent jobs")
    
    def _generate_cache_key(self, job: JobConfig) -> str:
        """Generate cache key for job configuration"""
        import hashlib
        cache_data = {
            'file_name': job.file_name,
            'file_size': job.file_size,
            'source_language': job.source_language,
            'target_languages': sorted(job.target_languages),
            'output_formats': sorted(job.output_formats),
            'transcription_model': job.transcription_model,
            'translation_model': job.translation_model,
            'model_variant': job.model_variant
        }
        return hashlib.md5(str(cache_data).encode()).hexdigest()
    
    def _is_cache_valid(self, cache_entry: Dict[str, Any]) -> bool:
        """Check if cache entry is still valid"""
        return time.time() - cache_entry['timestamp'] < self.cache_ttl
    
    async def add_job_async(self, file_path: str, file_name: str, file_size: int, **config_options) -> str:
        """Add a new job to the batch processing queue (async version)"""
        job_id = str(uuid.uuid4())
        
        # Create job configuration
        job_config = JobConfig(
            file_id=job_id,
            file_path=file_path,
            file_name=file_name,
            file_size=file_size,
            source_language=config_options.get('source_language', 'auto'),
            target_languages=config_options.get('target_languages', ['transcribe']),
            output_formats=config_options.get('output_formats', ['srt']),
            intermediate_language=config_options.get('intermediate_language', None),
            export_options=config_options.get('export_options', {}),
            translation_model=config_options.get('translation_model', 'deepseek-r1:1.5b'),
            transcription_model=config_options.get('transcription_model', 'openai/whisper'),
            model_variant=config_options.get('model_variant', None)
        )
        
        # Check cache if enabled
        if self.enable_caching:
            cache_key = self._generate_cache_key(job_config)
            if cache_key in self.result_cache and self._is_cache_valid(self.result_cache[cache_key]):
                # Use cached result
                cached_result = self.result_cache[cache_key]['result']
                job_config.status = JobStatus.COMPLETED
                job_config.progress = 1.0
                job_config.results = cached_result.results
                job_config.completed_at = time.time()
                
                self.performance_stats['cache_hit_rate'] += 1
                self.logger.info(f"Using cached result for job {job_id}")
        
        self.progress_tracker.add_job(job_config)
        self.logger.info(f"Added async job {job_id} for file {file_name}")
        
        return job_id
    
    async def start_processing_async(self):
        """Start async batch processing"""
        if self._processing:
            self.logger.warning("Async batch processing is already running")
            return False
        
        self._should_stop = False
        self._processing_task = asyncio.create_task(self._async_process_queue())
        
        self.logger.info("Started async batch processing")
        return True
    
    async def stop_processing_async(self):
        """Stop async batch processing"""
        self._should_stop = True
        
        # Cancel all active jobs
        for job_id, task in list(self._active_jobs.items()):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # Cancel main processing task
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Stopped async batch processing")
    
    async def _async_process_queue(self):
        """Main async processing loop"""
        self._processing = True
        
        try:
            while not self._should_stop:
                # Get pending jobs
                pending_jobs = [
                    job for job in self.progress_tracker.get_all_jobs()
                    if job.status == JobStatus.PENDING
                ]
                
                if not pending_jobs:
                    # No pending jobs, check if any jobs are still running
                    if not self._active_jobs:
                        break  # No pending or active jobs
                    await asyncio.sleep(1)
                    continue
                
                # Process jobs concurrently up to the limit
                for job in pending_jobs:
                    if len(self._active_jobs) >= self.max_concurrent_jobs:
                        break  # Already at max concurrent jobs
                    
                    if job.file_id not in self._active_jobs:
                        # Start processing this job
                        task = asyncio.create_task(self._process_job_async(job))
                        self._active_jobs[job.file_id] = task
                        
                        # Update peak concurrent jobs stat
                        self.performance_stats['concurrent_jobs_peak'] = max(
                            self.performance_stats['concurrent_jobs_peak'],
                            len(self._active_jobs)
                        )
                
                # Clean up completed jobs
                completed_jobs = []
                for job_id, task in list(self._active_jobs.items()):
                    if task.done():
                        completed_jobs.append(job_id)
                        try:
                            await task  # Get result or exception
                        except Exception as e:
                            self.logger.error(f"Job {job_id} failed: {e}")
                
                for job_id in completed_jobs:
                    del self._active_jobs[job_id]
                
                await asyncio.sleep(0.5)  # Brief pause between iterations
        
        finally:
            self._processing = False
            self._active_jobs.clear()
    
    async def _process_job_async(self, job: JobConfig):
        """Process a single job asynchronously"""
        async with self._job_semaphore:  # Limit concurrent jobs
            start_time = time.time()
            
            try:
                # Update job status
                self.progress_tracker.update_job_progress(
                    job.file_id,
                    0.0,
                    JobStatus.PROCESSING,
                    "Starting async processing..."
                )
                
                # Track analytics
                if self.user_id and self.analytics.is_enabled():
                    self.analytics.track_transcription_start(
                        user_id=self.user_id,
                        filename=job.file_name,
                        model=job.transcription_model,
                        file_size=job.file_size,
                        source_language=job.source_language,
                        target_languages=job.target_languages,
                        output_formats=job.output_formats
                    )
                
                # Process the job
                result = await self._execute_job_async(job)
                
                # Update job with results
                processing_time = time.time() - start_time
                job.results = result.results
                job.progress = 1.0
                job.status = JobStatus.COMPLETED
                job.completed_at = time.time()
                
                # Cache result if enabled
                if self.enable_caching and result.success:
                    cache_key = self._generate_cache_key(job)
                    self.result_cache[cache_key] = {
                        'result': result,
                        'timestamp': time.time()
                    }
                
                # Update performance stats
                self.performance_stats['total_jobs_processed'] += 1
                self.performance_stats['total_processing_time'] += processing_time
                self.performance_stats['average_job_time'] = (
                    self.performance_stats['total_processing_time'] / 
                    self.performance_stats['total_jobs_processed']
                )
                
                # Track analytics completion
                if self.user_id and self.analytics.is_enabled():
                    self.analytics.track_transcription_complete(
                        user_id=self.user_id,
                        filename=job.file_name,
                        model=job.transcription_model,
                        processing_time=processing_time,
                        success=result.success
                    )
                
                self.logger.info(f"Async job {job.file_id} completed in {processing_time:.2f}s")
                
            except Exception as e:
                # Handle job failure
                processing_time = time.time() - start_time
                job.status = JobStatus.FAILED
                job.error_message = str(e)
                job.completed_at = time.time()
                
                # Track analytics failure
                if self.user_id and self.analytics.is_enabled():
                    self.analytics.track_transcription_complete(
                        user_id=self.user_id,
                        filename=job.file_name,
                        model=job.transcription_model,
                        processing_time=processing_time,
                        success=False,
                        error_message=str(e)
                    )
                
                self.logger.error(f"Async job {job.file_id} failed: {e}")
                raise
    
    async def _execute_job_async(self, job: JobConfig) -> AsyncJobResult:
        """Execute a single job with all its processing steps"""
        result = AsyncJobResult(job_id=job.file_id, success=False)
        
        try:
            # Step 1: Transcribe audio
            self.progress_tracker.update_job_progress(
                job.file_id, 0.1, current_task="Transcribing audio..."
            )
            
            # Prepare model config
            model_config = {
                'source_language': job.source_language,
                'target_language': 'transcribe'
            }
            if job.model_variant:
                model_config['model_type'] = job.model_variant
            
            # Transcribe using async model manager
            base_subs = await self.model_manager.transcribe_async(
                media_file=job.file_path,
                model_name=job.transcription_model,
                config=model_config
            )
            
            self.progress_tracker.update_job_progress(
                job.file_id, 0.3, current_task="Transcription completed"
            )
            
            # Step 2: Process each target language
            total_tasks = len(job.target_languages) * len(job.output_formats)
            completed_tasks = 0
            
            for target_language in job.target_languages:
                if target_language == 'transcribe':
                    current_subs = base_subs
                    lang_suffix = job.source_language if job.source_language != 'auto' else 'original'
                else:
                    # Translate asynchronously
                    self.progress_tracker.update_job_progress(
                        job.file_id, 
                        0.3 + (completed_tasks / total_tasks) * 0.5,
                        current_task=f"Translating to {target_language}..."
                    )
                    
                    # Use async API client for API-based models
                    if job.translation_model.startswith('api:'):
                        api_key = os.getenv('DEEPSEEK_API_KEY')
                        if not api_key:
                            raise Exception("DeepSeek API key not found")
                        
                        # Extract texts for batch translation
                        texts = [sub.text for sub in base_subs]
                        
                        # Get async API client
                        client = await get_or_create_client(
                            api_key=api_key,
                            model=job.translation_model.replace('api:', '')
                        )
                        
                        # Translate in batches
                        translated_texts = await client.translate_batch(
                            texts=texts,
                            source_lang=job.source_language,
                            target_lang=target_language
                        )
                        
                        # Update subtitles with translations
                        current_subs = base_subs.copy()
                        for i, translated_text in enumerate(translated_texts):
                            if i < len(current_subs):
                                current_subs[i].text = translated_text
                        
                        result.api_calls += len(texts)
                    else:
                        # Use local translation model
                        current_subs = await self.model_manager.translate_async(
                            subs=base_subs,
                            source_language=job.source_language if job.source_language != 'auto' else 'auto',
                            target_language=target_language,
                            translation_model=job.translation_model,
                            intermediate_language=job.intermediate_language
                        )
                    
                    lang_suffix = target_language
                
                # Generate files in each format
                for output_format in job.output_formats:
                    self.progress_tracker.update_job_progress(
                        job.file_id,
                        0.3 + (completed_tasks / total_tasks) * 0.6,
                        current_task=f"Generating {output_format} for {target_language}..."
                    )
                    
                    # Generate filename
                    base_name = Path(job.file_name).stem
                    if len(job.target_languages) > 1 or job.target_languages[0] != 'transcribe':
                        generated_filename = f"{base_name}-{lang_suffix}.{output_format}"
                    else:
                        generated_filename = f"{base_name}.{output_format}"
                    
                    # Generate content
                    if output_format == 'ooona':
                        # Handle OOONA format
                        try:
                            from subsai.storage.ooona_converter import create_ooona_converter
                            ooona_converter = create_ooona_converter()
                            if ooona_converter:
                                input_content = current_subs.to_string(format_='srt')
                                conversion_result = ooona_converter.convert_subtitle(input_content)
                                if conversion_result['success']:
                                    subtitle_content = conversion_result['content']
                                else:
                                    raise Exception(f"OOONA conversion failed: {conversion_result['message']}")
                            else:
                                raise Exception("OOONA converter not available")
                        except ImportError:
                            raise Exception("OOONA converter not available")
                    else:
                        subtitle_content = current_subs.to_string(format_=output_format)
                    
                    # Create result entry
                    result_entry = {
                        'filename': generated_filename,
                        'format': output_format,
                        'language': target_language,
                        'content': subtitle_content,
                        'size': len(subtitle_content.encode('utf-8'))
                    }
                    
                    # Handle exports (S3, local, etc.)
                    if job.export_options:
                        await self._handle_exports_async(result_entry, job.export_options)
                    
                    result.results.append(result_entry)
                    completed_tasks += 1
            
            self.progress_tracker.update_job_progress(
                job.file_id, 1.0, current_task="Processing completed"
            )
            
            result.success = True
            return result
            
        except Exception as e:
            result.error_message = str(e)
            self.logger.error(f"Job execution failed: {e}")
            raise
    
    async def _handle_exports_async(self, result_entry: Dict[str, Any], export_options: Dict[str, Any]):
        """Handle async export operations (S3, local storage, etc.)"""
        try:
            # S3 export
            if export_options.get('s3_upload', False):
                s3_config = export_options.get('s3_config', {})
                if s3_config.get('enabled', False):
                    from subsai.storage.s3_storage import create_s3_storage
                    
                    s3_storage = create_s3_storage(s3_config)
                    if s3_storage:
                        # Create temp file for upload
                        with tempfile.NamedTemporaryFile(
                            mode='w', 
                            delete=False, 
                            suffix=f".{result_entry['format']}"
                        ) as temp_file:
                            temp_file.write(result_entry['content'])
                            temp_file_path = temp_file.name
                        
                        try:
                            # Upload to S3
                            s3_result = s3_storage.upload_subtitle_file(
                                file_path=temp_file_path,
                                project_name=export_options.get('s3_project_folder', 'async-batch'),
                                custom_filename=result_entry['filename']
                            )
                            
                            if s3_result['success']:
                                result_entry['s3_url'] = s3_result['s3_url']
                                result_entry['s3_upload'] = True
                            else:
                                result_entry['s3_error'] = s3_result['message']
                        
                        finally:
                            # Clean up temp file
                            Path(temp_file_path).unlink(missing_ok=True)
            
            # Add other export handlers here (local storage, etc.)
            
        except Exception as e:
            result_entry['export_error'] = str(e)
            self.logger.error(f"Export failed: {e}")
    
    async def get_job_status_async(self, job_id: str) -> Optional[JobConfig]:
        """Get job status asynchronously"""
        return self.progress_tracker.get_job_progress(job_id)
    
    async def cancel_job_async(self, job_id: str) -> bool:
        """Cancel a job asynchronously"""
        if job_id in self._active_jobs:
            self._active_jobs[job_id].cancel()
            del self._active_jobs[job_id]
        
        self.progress_tracker.update_job_progress(
            job_id, 0.0, JobStatus.CANCELLED, "Job cancelled"
        )
        return True
    
    async def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        # Update cache hit rate
        total_jobs = self.performance_stats['total_jobs_processed']
        if total_jobs > 0:
            self.performance_stats['cache_hit_rate'] = (
                self.performance_stats['cache_hit_rate'] / total_jobs
            ) * 100
        
        # Get model manager stats
        model_stats = self.model_manager.get_stats()
        
        return {
            **self.performance_stats,
            'model_manager': model_stats,
            'active_jobs': len(self._active_jobs),
            'cache_size': len(self.result_cache),
            'is_processing': self._processing
        }
    
    async def cleanup_async(self):
        """Cleanup resources and shutdown"""
        await self.stop_processing_async()
        await self.model_manager.shutdown()
        
        # Clear caches
        self.result_cache.clear()
        
        # Force garbage collection
        gc.collect()
        
        self.logger.info("AsyncBatchProcessor cleanup complete")
    
    # Synchronous wrappers for compatibility
    def add_job(self, file_path: str, file_name: str, file_size: int, **config_options) -> str:
        """Synchronous wrapper for add_job_async"""
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an async context, create a task
            task = asyncio.create_task(
                self.add_job_async(file_path, file_name, file_size, **config_options)
            )
            return task
        else:
            return loop.run_until_complete(
                self.add_job_async(file_path, file_name, file_size, **config_options)
            )
    
    def start_processing(self):
        """Synchronous wrapper for start_processing_async"""
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(self.start_processing_async())
            return True
        else:
            return loop.run_until_complete(self.start_processing_async())
    
    def is_processing(self) -> bool:
        """Check if processing is active"""
        return self._processing
    
    def get_all_jobs(self) -> List[JobConfig]:
        """Get all jobs (synchronous)"""
        return self.progress_tracker.get_all_jobs()
    
    def get_progress(self) -> Dict[str, Any]:
        """Get overall progress (synchronous)"""
        return self.progress_tracker.get_overall_progress()
    
    def get_job_details(self, job_id: str) -> Optional[JobConfig]:
        """Get job details (synchronous)"""
        return self.progress_tracker.get_job_progress(job_id)
    
    def get_current_job_id(self) -> Optional[str]:
        """Get current job ID (may return multiple for concurrent processing)"""
        return list(self._active_jobs.keys())[0] if self._active_jobs else None
    
    def clear_completed(self):
        """Clear completed jobs"""
        self.progress_tracker.clear_completed_jobs()
    
    def cancel_job(self, job_id: str) -> bool:
        """Synchronous wrapper for cancel_job_async"""
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(self.cancel_job_async(job_id))
            return True
        else:
            return loop.run_until_complete(self.cancel_job_async(job_id))