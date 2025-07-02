#!/usr/bin/env python3
"""
Batch Processing System for SubsAI
Handles multiple file processing with progress tracking and per-file configuration
"""

import uuid
import time
import threading
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import os
from pathlib import Path
import logging

from subsai import SubsAI, Tools
from .analytics import AnalyticsService


class JobStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


@dataclass
class JobConfig:
    """Configuration for a single batch job"""
    file_id: str
    file_path: str
    file_name: str
    file_size: int
    source_language: str = 'auto'
    target_languages: List[str] = field(default_factory=lambda: ['transcribe'])
    output_formats: List[str] = field(default_factory=lambda: ['srt'])
    export_options: Dict[str, Any] = field(default_factory=dict)
    status: JobStatus = JobStatus.PENDING
    progress: float = 0.0
    current_task: str = ""
    results: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


class ProgressTracker:
    """Tracks progress for batch processing jobs"""
    
    def __init__(self):
        self.job_progress: Dict[str, JobConfig] = {}
        self._lock = threading.Lock()
    
    def add_job(self, job_config: JobConfig):
        """Add a new job to track"""
        with self._lock:
            self.job_progress[job_config.file_id] = job_config
    
    def update_job_progress(self, job_id: str, progress: float, status: JobStatus = None, current_task: str = None, error_message: str = None):
        """Update progress for a specific job"""
        with self._lock:
            if job_id in self.job_progress:
                job = self.job_progress[job_id]
                job.progress = max(0.0, min(1.0, progress))  # Clamp between 0 and 1
                
                if status:
                    job.status = status
                    if status == JobStatus.PROCESSING and job.started_at is None:
                        job.started_at = time.time()
                    elif status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                        job.completed_at = time.time()
                
                if current_task:
                    job.current_task = current_task
                
                if error_message:
                    job.error_message = error_message
    
    def get_job_progress(self, job_id: str) -> Optional[JobConfig]:
        """Get progress for a specific job"""
        with self._lock:
            return self.job_progress.get(job_id)
    
    def get_overall_progress(self) -> Dict[str, Any]:
        """Calculate overall batch progress"""
        with self._lock:
            if not self.job_progress:
                return {
                    'overall_progress': 0.0,
                    'completed_jobs': 0,
                    'total_jobs': 0,
                    'failed_jobs': 0,
                    'processing_jobs': 0,
                    'pending_jobs': 0
                }
            
            total_jobs = len(self.job_progress)
            completed_jobs = sum(1 for job in self.job_progress.values() if job.status == JobStatus.COMPLETED)
            failed_jobs = sum(1 for job in self.job_progress.values() if job.status == JobStatus.FAILED)
            processing_jobs = sum(1 for job in self.job_progress.values() if job.status == JobStatus.PROCESSING)
            pending_jobs = sum(1 for job in self.job_progress.values() if job.status == JobStatus.PENDING)
            
            overall_progress = sum(job.progress for job in self.job_progress.values()) / total_jobs if total_jobs > 0 else 0.0
            
            return {
                'overall_progress': overall_progress,
                'completed_jobs': completed_jobs,
                'total_jobs': total_jobs,
                'failed_jobs': failed_jobs,
                'processing_jobs': processing_jobs,
                'pending_jobs': pending_jobs
            }
    
    def get_all_jobs(self) -> List[JobConfig]:
        """Get all jobs sorted by creation time"""
        with self._lock:
            return sorted(self.job_progress.values(), key=lambda x: x.created_at)
    
    def clear_completed_jobs(self):
        """Remove completed and failed jobs from tracking"""
        with self._lock:
            self.job_progress = {
                job_id: job for job_id, job in self.job_progress.items()
                if job.status not in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]
            }


class BatchProcessor:
    """Main batch processing orchestrator"""
    
    def __init__(self, progress_callback: Optional[Callable] = None, user_id: Optional[int] = None):
        self.progress_tracker = ProgressTracker()
        self.progress_callback = progress_callback
        self.subs_ai = SubsAI()
        self.tools = Tools()
        self._processing = False
        self._should_stop = False
        self._processing_thread = None
        self._current_job_id = None
        self.user_id = user_id
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
        # Initialize analytics service
        self.analytics = AnalyticsService()
        
    def add_job(self, file_path: str, file_name: str, file_size: int, **config_options) -> str:
        """Add a new job to the batch processing queue"""
        job_id = str(uuid.uuid4())
        
        # Create job configuration with defaults
        job_config = JobConfig(
            file_id=job_id,
            file_path=file_path,
            file_name=file_name,
            file_size=file_size,
            source_language=config_options.get('source_language', 'auto'),
            target_languages=config_options.get('target_languages', ['transcribe']),
            output_formats=config_options.get('output_formats', ['srt']),
            export_options=config_options.get('export_options', {})
        )
        
        self.progress_tracker.add_job(job_config)
        self.logger.info(f"Added job {job_id} for file {file_name}")
        
        return job_id
    
    def start_processing(self):
        """Start batch processing in a separate thread"""
        if self._processing:
            self.logger.warning("Batch processing is already running")
            return False
        
        self._should_stop = False
        self._processing_thread = threading.Thread(target=self._process_queue, daemon=True)
        self._processing_thread.start()
        
        self.logger.info("Started batch processing")
        return True
    
    def stop_processing(self):
        """Stop batch processing"""
        self._should_stop = True
        if self._processing_thread and self._processing_thread.is_alive():
            self._processing_thread.join(timeout=5)
        
        self.logger.info("Stopped batch processing")
    
    def pause_processing(self):
        """Pause batch processing (finish current job but don't start new ones)"""
        self._should_stop = True
        self.logger.info("Paused batch processing")
    
    def is_processing(self) -> bool:
        """Check if batch processing is currently active"""
        return self._processing
    
    def get_current_job_id(self) -> Optional[str]:
        """Get the ID of the currently processing job"""
        return self._current_job_id
    
    def _process_queue(self):
        """Main processing loop (runs in separate thread)"""
        self._processing = True
        
        try:
            while not self._should_stop:
                # Get next pending job
                pending_jobs = [
                    job for job in self.progress_tracker.get_all_jobs()
                    if job.status == JobStatus.PENDING
                ]
                
                if not pending_jobs:
                    break  # No more pending jobs
                
                job = pending_jobs[0]
                self._current_job_id = job.file_id
                
                try:
                    self._process_single_job(job)
                except Exception as e:
                    self.logger.error(f"Error processing job {job.file_id}: {e}")
                    self.progress_tracker.update_job_progress(
                        job.file_id,
                        job.progress,
                        JobStatus.FAILED,
                        error_message=str(e)
                    )
                
                self._current_job_id = None
                
                if self.progress_callback:
                    self.progress_callback()
        
        finally:
            self._processing = False
            self._current_job_id = None
    
    def _process_single_job(self, job: JobConfig):
        """Process a single job with all its target languages and formats"""
        self.logger.info(f"Starting processing of job {job.file_id}: {job.file_name}")
        
        # Track transcription start
        if self.user_id and self.analytics.is_enabled():
            self.analytics.track_transcription_start(
                user_id=self.user_id,
                filename=job.file_name,
                model='openai/whisper',
                file_size=job.file_size,
                source_language=job.source_language,
                target_languages=job.target_languages,
                output_formats=job.output_formats
            )
        
        # Update job status to processing
        self.progress_tracker.update_job_progress(
            job.file_id,
            0.0,
            JobStatus.PROCESSING,
            "Initializing transcription model..."
        )
        
        start_time = time.time()
        
        try:
            # Create model
            model_config = {
                'source_language': job.source_language,
                'target_language': 'transcribe'  # Always transcribe first, then translate if needed
            }
            model = self.subs_ai.create_model('openai/whisper', model_config)
            
            # Transcribe the audio
            self.progress_tracker.update_job_progress(
                job.file_id,
                0.1,
                current_task=f"Transcribing audio ({job.source_language})..."
            )
            
            base_subs = self.subs_ai.transcribe(job.file_path, model)
            
            # Process each target language
            total_tasks = len(job.target_languages) * len(job.output_formats)
            completed_tasks = 0
            
            for target_language in job.target_languages:
                # Handle transcription vs translation
                if target_language == 'transcribe':
                    current_subs = base_subs
                    lang_suffix = job.source_language if job.source_language != 'auto' else 'original'
                else:
                    # Translate to target language
                    self.progress_tracker.update_job_progress(
                        job.file_id,
                        0.3 + (completed_tasks / total_tasks) * 0.6,
                        current_task=f"Translating to {target_language}..."
                    )
                    
                    current_subs = self.tools.translate(
                        subs=base_subs,
                        source_language=job.source_language if job.source_language != 'auto' else 'auto',
                        target_language=target_language,
                        model='deepseek-r1:1.5b'
                    )
                    lang_suffix = target_language
                
                # Generate files in each requested format
                for output_format in job.output_formats:
                    self.progress_tracker.update_job_progress(
                        job.file_id,
                        0.3 + (completed_tasks / total_tasks) * 0.6,
                        current_task=f"Generating {output_format.upper()} for {target_language}..."
                    )
                    
                    # Generate filename
                    base_name = Path(job.file_name).stem
                    if len(job.target_languages) > 1 or job.target_languages[0] != 'transcribe':
                        filename = f"{base_name}-{lang_suffix}.{output_format}"
                    else:
                        filename = f"{base_name}.{output_format}"
                    
                    # Save or export based on export options
                    self._export_subtitle_file(
                        current_subs,
                        filename,
                        output_format,
                        job.export_options,
                        job
                    )
                    
                    completed_tasks += 1
            
            # Calculate processing time and track completion
            processing_time = time.time() - start_time
            
            # Track transcription completion
            if self.user_id and self.analytics.is_enabled():
                self.analytics.track_transcription_complete(
                    user_id=self.user_id,
                    filename=job.file_name,
                    model='openai/whisper',
                    processing_time=processing_time,
                    success=True
                )
                
                # Record comprehensive file analytics
                self.analytics.record_file_processing(
                    user_id=self.user_id,
                    filename=job.file_name,
                    file_size=job.file_size,
                    model_used='openai/whisper',
                    processing_time=processing_time,
                    success=True,
                    source_language=job.source_language,
                    target_languages=[lang for lang in job.target_languages if lang != 'transcribe'],
                    output_formats=job.output_formats
                )
                
                # Track translations
                for target_lang in job.target_languages:
                    if target_lang != 'transcribe':
                        self.analytics.track_translation(
                            user_id=self.user_id,
                            filename=job.file_name,
                            source_lang=job.source_language,
                            target_lang=target_lang
                        )
            
            # Mark job as completed
            self.progress_tracker.update_job_progress(
                job.file_id,
                1.0,
                JobStatus.COMPLETED,
                "Processing completed successfully"
            )
            
            self.logger.info(f"Successfully completed job {job.file_id}")
            
        except Exception as e:
            self.logger.error(f"Error processing job {job.file_id}: {e}")
            
            # Track error
            if self.user_id and self.analytics.is_enabled():
                processing_time = time.time() - start_time
                self.analytics.track_transcription_complete(
                    user_id=self.user_id,
                    filename=job.file_name,
                    model='openai/whisper',
                    processing_time=processing_time,
                    success=False,
                    error_message=str(e)
                )
                
                self.analytics.track_error(
                    user_id=self.user_id,
                    error_type='transcription_error',
                    error_message=str(e),
                    filename=job.file_name
                )
                
                # Record file analytics with error
                self.analytics.record_file_processing(
                    user_id=self.user_id,
                    filename=job.file_name,
                    file_size=job.file_size,
                    model_used='openai/whisper',
                    processing_time=processing_time,
                    success=False,
                    source_language=job.source_language,
                    target_languages=[lang for lang in job.target_languages if lang != 'transcribe'],
                    output_formats=job.output_formats,
                    error_message=str(e)
                )
            
            self.progress_tracker.update_job_progress(
                job.file_id,
                job.progress,
                JobStatus.FAILED,
                error_message=str(e)
            )
            raise
    
    def _export_subtitle_file(self, subs, filename: str, format_ext: str, export_options: Dict, job: JobConfig):
        """Export subtitle file based on export options"""
        from pathlib import Path
        import tempfile
        
        # For now, save to temp directory (can be enhanced for S3, local, etc.)
        temp_dir = Path(tempfile.gettempdir()) / "subsai_batch_output" / job.file_id
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        output_path = temp_dir / filename
        
        # Save the subtitle file
        if format_ext == 'ooona':
            # Handle OOONA format conversion
            try:
                from subsai.storage.ooona_converter import create_ooona_converter
                ooona_converter = create_ooona_converter()
                if ooona_converter:
                    input_content = subs.to_string(format_='srt')
                    result = ooona_converter.convert_subtitle(input_content)
                    if result['success']:
                        with open(output_path, 'w', encoding='utf-8') as f:
                            f.write(result['content'])
                    else:
                        raise Exception(f"OOONA conversion failed: {result['message']}")
                else:
                    raise Exception("OOONA converter not available")
            except ImportError:
                raise Exception("OOONA converter not available")
        else:
            # Standard format
            subs.save(str(output_path))
        
        # Add result to job
        result_info = {
            'filename': filename,
            'format': format_ext,
            'path': str(output_path),
            'size': output_path.stat().st_size if output_path.exists() else 0
        }
        
        # Handle S3 upload if enabled
        if export_options.get('s3_upload', False):
            try:
                from subsai.storage.s3_storage import create_s3_storage
                s3_config = export_options.get('s3_config', {})
                s3_storage = create_s3_storage(s3_config)
                if s3_storage:
                    project_folder = export_options.get('s3_project_folder', 'batch-processing')
                    s3_result = s3_storage.upload_file(
                        str(output_path),
                        filename,
                        project_folder
                    )
                    if s3_result['success']:
                        result_info['s3_url'] = s3_result['s3_url']
                        result_info['s3_upload'] = True
                        self.logger.info(f"Uploaded {filename} to S3: {s3_result['s3_url']}")
                        
                        # Track S3 upload
                        if self.user_id and self.analytics.is_enabled():
                            self.analytics.track_upload(
                                user_id=self.user_id,
                                destination='s3',
                                filename=filename,
                                project_folder=project_folder,
                                s3_url=s3_result['s3_url']
                            )
                    else:
                        self.logger.warning(f"S3 upload failed for {filename}: {s3_result['message']}")
                        result_info['s3_error'] = s3_result['message']
                else:
                    self.logger.warning("S3 storage not available")
                    result_info['s3_error'] = "S3 storage not configured"
            except Exception as e:
                self.logger.error(f"S3 upload error for {filename}: {e}")
                result_info['s3_error'] = str(e)
        
        job.results.append(result_info)
        
        # Track download/export
        if self.user_id and self.analytics.is_enabled():
            self.analytics.track_download(
                user_id=self.user_id,
                filename=filename,
                format=format_ext,
                file_size=result_info['size']
            )
        
        self.logger.info(f"Exported {filename} for job {job.file_id}")
    
    def get_progress(self) -> Dict[str, Any]:
        """Get current progress for all jobs"""
        return self.progress_tracker.get_overall_progress()
    
    def get_job_details(self, job_id: str) -> Optional[JobConfig]:
        """Get detailed information about a specific job"""
        return self.progress_tracker.get_job_progress(job_id)
    
    def get_all_jobs(self) -> List[JobConfig]:
        """Get all jobs"""
        return self.progress_tracker.get_all_jobs()
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a specific job"""
        job = self.progress_tracker.get_job_progress(job_id)
        if job and job.status == JobStatus.PENDING:
            self.progress_tracker.update_job_progress(
                job_id,
                job.progress,
                JobStatus.CANCELLED,
                "Job cancelled by user"
            )
            return True
        return False
    
    def clear_completed(self):
        """Clear completed and failed jobs"""
        self.progress_tracker.clear_completed_jobs()
