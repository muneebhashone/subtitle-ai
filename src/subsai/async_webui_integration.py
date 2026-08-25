#!/usr/bin/env python3
"""
Async WebUI Integration for SubsAI
Bridges async processing capabilities with the existing Streamlit webui
"""

import asyncio
import logging
import time
import threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import streamlit as st

# Import async components
from subsai.async_model_manager import AsyncModelManager
from subsai.async_batch_processor import AsyncBatchProcessor
from subsai.smart_batch_translator import SmartBatchTranslator, get_global_batch_translator
from subsai.async_api_client import cleanup_global_clients
from subsai.analytics import AnalyticsService
from subsai.performance_monitor import get_performance_monitor


@dataclass
class AsyncProcessingResult:
    """Result from async processing operations"""
    success: bool
    results: List[Dict[str, Any]] = None
    error_message: Optional[str] = None
    processing_time: float = 0.0
    performance_stats: Dict[str, Any] = None


class AsyncWebUIManager:
    """
    Manages async operations within the Streamlit webui context
    """
    
    def __init__(self):
        """Initialize the async webui manager"""
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="AsyncWebUI")
        self.logger = logging.getLogger(__name__)
        
        # Async components (initialized on demand)
        self._model_manager: Optional[AsyncModelManager] = None
        self._batch_processor: Optional[AsyncBatchProcessor] = None
        self._batch_translator: Optional[SmartBatchTranslator] = None
        
        # Performance monitoring
        self.performance_monitor = get_performance_monitor()
        
        # Initialize async loop in background thread
        self._setup_async_loop()
    
    def _setup_async_loop(self):
        """Setup async event loop in background thread"""
        def run_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            try:
                self.loop.run_forever()
            except Exception as e:
                self.logger.error(f"Async loop error: {e}")
            finally:
                self.loop.close()
        
        thread = threading.Thread(target=run_loop, daemon=True)
        thread.start()
        
        # Wait for loop to be ready
        while self.loop is None:
            time.sleep(0.01)
        
        self.logger.info("Async event loop initialized")
    
    def run_async(self, coro) -> Any:
        """
        Run an async coroutine from sync context
        
        :param coro: Coroutine to run
        :return: Result of the coroutine
        """
        if self.loop is None:
            raise RuntimeError("Async loop not initialized")
        
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result()
    
    async def get_model_manager(self) -> AsyncModelManager:
        """Get or create async model manager"""
        if self._model_manager is None:
            # Get configuration from session state or use defaults
            max_workers = st.session_state.get('async_max_workers', 4)
            memory_limit = st.session_state.get('async_memory_limit', 8.0)
            
            self._model_manager = AsyncModelManager(
                max_workers=max_workers,
                memory_limit_gb=memory_limit
            )
        
        return self._model_manager
    
    async def get_batch_processor(self, user_id: Optional[int] = None) -> AsyncBatchProcessor:
        """Get or create async batch processor"""
        if self._batch_processor is None:
            # Get configuration from session state or use defaults
            max_concurrent = st.session_state.get('async_max_concurrent_jobs', 3)
            enable_caching = st.session_state.get('async_enable_caching', True)
            
            self._batch_processor = AsyncBatchProcessor(
                max_concurrent_jobs=max_concurrent,
                enable_caching=enable_caching,
                user_id=user_id
            )
        
        return self._batch_processor
    
    async def get_batch_translator(self) -> SmartBatchTranslator:
        """Get or create smart batch translator"""
        if self._batch_translator is None:
            self._batch_translator = await get_global_batch_translator()
        
        return self._batch_translator
    
    def process_single_file_async_bridge(self, 
                                       file_path: str, 
                                       filename: str, 
                                       file_size: int,
                                       config: Dict[str, Any],
                                       progress_placeholder=None,
                                       results_placeholder=None,
                                       user=None) -> AsyncProcessingResult:
        """
        Bridge function to process single file using async capabilities
        """
        
        async def _process():
            start_time = time.time()
            
            try:
                # Get async components
                model_manager = await self.get_model_manager()
                batch_translator = await self.get_batch_translator()
                
                # Update progress
                if progress_placeholder:
                    progress_placeholder.info("🔧 Initializing async processing...")
                
                # Extract configuration
                source_language = config.get('source_language', 'auto')
                target_languages = config.get('target_languages', ['transcribe'])
                output_formats = config.get('output_formats', ['srt'])
                device_preference = config.get('device_preference', 'auto')
                translation_model = config.get('translation_model', 'deepseek-r1:1.5b')
                transcription_model = config.get('transcription_model', 'openai/whisper')
                model_config = config.get('model_config', {})
                intermediate_language = config.get('intermediate_language')
                
                # Step 1: Transcribe
                if progress_placeholder:
                    progress_placeholder.info("🎙️ Transcribing audio using async model manager...")
                
                # Prepare transcription config
                final_model_config = model_config.copy()
                final_model_config.update({
                    'source_language': source_language,
                    'target_language': 'transcribe'
                })
                
                # Add device configuration
                if device_preference != 'auto':
                    final_model_config['device'] = device_preference
                
                # Transcribe asynchronously
                base_subs = await model_manager.transcribe_async(
                    media_file=file_path,
                    model_name=transcription_model,
                    config=final_model_config
                )
                
                if progress_placeholder:
                    progress_placeholder.info("✅ Transcription completed")
                
                # Step 2: Process each target language and format
                results = []
                total_tasks = len(target_languages) * len(output_formats)
                completed_tasks = 0
                
                for target_language in target_languages:
                    if target_language == 'transcribe':
                        current_subs = base_subs
                        lang_suffix = source_language if source_language != 'auto' else 'original'
                    else:
                        # Translate using smart batch translator
                        if progress_placeholder:
                            progress_placeholder.info(f"🌐 Translating to {target_language} using smart batching...")
                        
                        # Extract texts for translation
                        texts = [sub.text for sub in base_subs]
                        
                        # Translate using smart batch translator
                        translated_texts = await batch_translator.translate_multiple(
                            texts=texts,
                            source_lang=source_language if source_language != 'auto' else 'auto',
                            target_lang=target_language,
                            context=f"Subtitle translation from {source_language}",
                            priority=5  # High priority for UI requests
                        )
                        
                        # Update subtitles with translations
                        current_subs = base_subs.copy()
                        for i, translated_text in enumerate(translated_texts):
                            if i < len(current_subs):
                                current_subs[i].text = translated_text
                        
                        lang_suffix = target_language
                    
                    # Generate files in each format
                    for output_format in output_formats:
                        if progress_placeholder:
                            progress_placeholder.info(f"📄 Generating {output_format.upper()} for {target_language}...")
                        
                        # Generate filename
                        from pathlib import Path
                        base_name = Path(filename).stem
                        if len(target_languages) > 1 or target_languages[0] != 'transcribe':
                            generated_filename = f"{base_name}-{lang_suffix}.{output_format}"
                        else:
                            generated_filename = f"{base_name}.{output_format}"
                        
                        # Generate content
                        if output_format == 'ooona':
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
                        
                        results.append(result_entry)
                        completed_tasks += 1
                        
                        # Update progress
                        if progress_placeholder:
                            progress_percent = (completed_tasks / total_tasks) * 100
                            progress_placeholder.progress(progress_percent / 100)
                
                # Calculate processing time
                processing_time = time.time() - start_time
                
                # Get performance stats
                model_stats = model_manager.get_stats()
                translator_stats = batch_translator.get_stats()
                
                performance_stats = {
                    'processing_time': processing_time,
                    'model_manager': model_stats,
                    'batch_translator': translator_stats,
                    'files_generated': len(results)
                }
                
                # Record performance metrics
                self.performance_monitor.record_operation_time("single_file_processing", processing_time, True)
                self.performance_monitor.record_metric("files_generated", len(results), "count", "processing")
                
                if progress_placeholder:
                    progress_placeholder.success(f"✅ Async processing completed in {processing_time:.2f}s!")
                
                return AsyncProcessingResult(
                    success=True,
                    results=results,
                    processing_time=processing_time,
                    performance_stats=performance_stats
                )
                
            except Exception as e:
                processing_time = time.time() - start_time
                
                if progress_placeholder:
                    progress_placeholder.error(f"❌ Async processing failed: {str(e)}")
                
                return AsyncProcessingResult(
                    success=False,
                    error_message=str(e),
                    processing_time=processing_time
                )
        
        # Run the async function
        return self.run_async(_process())
    
    def create_async_batch_processor_bridge(self, user_id: Optional[int] = None) -> 'AsyncBatchProcessorBridge':
        """Create a bridge for async batch processing"""
        return AsyncBatchProcessorBridge(self, user_id)
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics from all async components"""
        
        async def _get_metrics():
            metrics = {}
            
            if self._model_manager:
                metrics['model_manager'] = self._model_manager.get_stats()
            
            if self._batch_processor:
                metrics['batch_processor'] = await self._batch_processor.get_performance_stats()
            
            if self._batch_translator:
                metrics['batch_translator'] = self._batch_translator.get_stats()
            
            return metrics
        
        try:
            return self.run_async(_get_metrics())
        except Exception as e:
            self.logger.error(f"Failed to get performance metrics: {e}")
            return {}
    
    def cleanup(self):
        """Cleanup async resources"""
        
        async def _cleanup():
            if self._model_manager:
                await self._model_manager.shutdown()
            
            if self._batch_processor:
                await self._batch_processor.cleanup_async()
            
            if self._batch_translator:
                await self._batch_translator.shutdown()
            
            # Cleanup global clients
            await cleanup_global_clients()
        
        try:
            self.run_async(_cleanup())
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")
        
        # Shutdown executor
        self.executor.shutdown(wait=False)
        
        # Stop async loop
        if self.loop and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self.loop.stop)


class AsyncBatchProcessorBridge:
    """
    Bridge class for async batch processor in Streamlit context
    """
    
    def __init__(self, manager: AsyncWebUIManager, user_id: Optional[int] = None):
        self.manager = manager
        self.user_id = user_id
        self._processor: Optional[AsyncBatchProcessor] = None
    
    def get_processor(self) -> AsyncBatchProcessor:
        """Get the async batch processor (sync wrapper)"""
        
        async def _get():
            if self._processor is None:
                self._processor = await self.manager.get_batch_processor(self.user_id)
            return self._processor
        
        return self.manager.run_async(_get())
    
    def add_job(self, file_path: str, file_name: str, file_size: int, **config_options) -> str:
        """Add job to async batch processor"""
        processor = self.get_processor()
        
        async def _add_job():
            return await processor.add_job_async(file_path, file_name, file_size, **config_options)
        
        return self.manager.run_async(_add_job())
    
    def start_processing(self):
        """Start async batch processing"""
        processor = self.get_processor()
        
        async def _start():
            return await processor.start_processing_async()
        
        return self.manager.run_async(_start())
    
    def stop_processing(self):
        """Stop async batch processing"""
        processor = self.get_processor()
        
        async def _stop():
            return await processor.stop_processing_async()
        
        return self.manager.run_async(_stop())
    
    def is_processing(self) -> bool:
        """Check if processing is active"""
        try:
            processor = self.get_processor()
            return processor.is_processing()
        except:
            return False
    
    def get_all_jobs(self):
        """Get all jobs"""
        processor = self.get_processor()
        return processor.get_all_jobs()
    
    def get_progress(self):
        """Get overall progress"""
        processor = self.get_processor()
        return processor.get_progress()
    
    def get_job_details(self, job_id: str):
        """Get job details"""
        processor = self.get_processor()
        return processor.get_job_details(job_id)
    
    def clear_completed(self):
        """Clear completed jobs"""
        processor = self.get_processor()
        processor.clear_completed()
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job"""
        processor = self.get_processor()
        
        async def _cancel():
            return await processor.cancel_job_async(job_id)
        
        return self.manager.run_async(_cancel())


# Global instance for webui usage
_global_async_webui_manager: Optional[AsyncWebUIManager] = None

def get_async_webui_manager() -> AsyncWebUIManager:
    """Get or create global async webui manager"""
    global _global_async_webui_manager
    
    if _global_async_webui_manager is None:
        _global_async_webui_manager = AsyncWebUIManager()
    
    return _global_async_webui_manager

def cleanup_async_webui_manager():
    """Cleanup global async webui manager"""
    global _global_async_webui_manager
    
    if _global_async_webui_manager is not None:
        _global_async_webui_manager.cleanup()
        _global_async_webui_manager = None


# Streamlit session state helpers
def init_async_webui_in_session():
    """Initialize async webui components in Streamlit session state"""
    if 'async_webui_manager' not in st.session_state:
        st.session_state.async_webui_manager = get_async_webui_manager()
    
    # Initialize async configuration in session state
    if 'async_config' not in st.session_state:
        st.session_state.async_config = {
            'enabled': True,
            'max_workers': 4,
            'memory_limit': 8.0,
            'max_concurrent_jobs': 3,
            'enable_caching': True,
            'batch_translation': True
        }

def render_async_performance_panel():
    """Render async performance monitoring panel in sidebar"""
    with st.sidebar.expander("⚡ Async Performance", expanded=False):
        st.subheader("Performance Dashboard")
        
        try:
            from subsai.performance_monitor import get_performance_monitor
            monitor = get_performance_monitor()
            
            # Get performance insights
            insights = monitor.get_performance_insights()
            st.write("**Performance Insights:**")
            for insight in insights[:3]:  # Show top 3 insights
                st.write(f"• {insight}")
            
            # Component metrics
            manager = st.session_state.get('async_webui_manager')
            if manager:
                metrics = manager.get_performance_metrics()
                
                if 'model_manager' in metrics:
                    st.write("**Model Manager:**")
                    model_stats = metrics['model_manager']
                    st.write(f"- Cache hits: {model_stats.get('cache_hits', 0)}")
                    st.write(f"- Total memory: {model_stats.get('total_memory_estimate', 'N/A')}")
                
                if 'batch_translator' in metrics:
                    st.write("**Batch Translator:**")
                    translator_stats = metrics['batch_translator']
                    st.write(f"- API calls saved: {translator_stats.get('api_calls_saved', 0)}")
                    st.write(f"- Cache hits: {translator_stats.get('cache_hits', 0)}")
                    st.write(f"- Avg batch size: {translator_stats.get('average_batch_size', 0):.1f}")
                
                if 'batch_processor' in metrics:
                    st.write("**Batch Processor:**")
                    batch_stats = metrics['batch_processor']
                    st.write(f"- Jobs processed: {batch_stats.get('total_jobs_processed', 0)}")
                    st.write(f"- Avg job time: {batch_stats.get('average_job_time', 0):.2f}s")
                    st.write(f"- Active jobs: {batch_stats.get('active_jobs', 0)}")
                
                # Start monitoring if enabled
                if st.session_state.get('async_config', {}).get('enabled', False):
                    components = []
                    if manager._model_manager:
                        components.append(manager._model_manager)
                    if manager._batch_processor:
                        components.append(manager._batch_processor)
                    if manager._batch_translator:
                        components.append(manager._batch_translator)
                    
                    if components and not monitor._collecting:
                        monitor.start_monitoring(components)
            else:
                st.info("Async manager not initialized")
                
        except Exception as e:
            st.error(f"Error loading performance metrics: {e}")

def render_async_config_panel():
    """Render async configuration panel in sidebar"""
    with st.sidebar.expander("⚙️ Async Configuration", expanded=False):
        st.subheader("Performance Settings")
        
        # Get current config
        config = st.session_state.get('async_config', {})
        
        # Async processing toggle
        async_enabled = st.checkbox(
            "Enable Async Processing",
            value=config.get('enabled', True),
            help="Use async processing for improved performance"
        )
        
        if async_enabled:
            # Max workers
            max_workers = st.slider(
                "Max Workers",
                min_value=1,
                max_value=8,
                value=config.get('max_workers', 4),
                help="Maximum number of worker threads"
            )
            
            # Memory limit
            memory_limit = st.slider(
                "Memory Limit (GB)",
                min_value=2.0,
                max_value=16.0,
                value=config.get('memory_limit', 8.0),
                step=0.5,
                help="Memory limit for model caching"
            )
            
            # Max concurrent jobs
            max_concurrent = st.slider(
                "Max Concurrent Jobs",
                min_value=1,
                max_value=8,
                value=config.get('max_concurrent_jobs', 3),
                help="Maximum concurrent batch jobs"
            )
            
            # Caching toggle
            enable_caching = st.checkbox(
                "Enable Result Caching",
                value=config.get('enable_caching', True),
                help="Cache results to avoid redundant processing"
            )
            
            # Batch translation toggle
            batch_translation = st.checkbox(
                "Enable Smart Translation Batching",
                value=config.get('batch_translation', True),
                help="Use smart batching for translation requests"
            )
            
            # Update session state
            st.session_state.async_config = {
                'enabled': async_enabled,
                'max_workers': max_workers,
                'memory_limit': memory_limit,
                'max_concurrent_jobs': max_concurrent,
                'enable_caching': enable_caching,
                'batch_translation': batch_translation
            }
            
            # Update global settings
            st.session_state.async_max_workers = max_workers
            st.session_state.async_memory_limit = memory_limit
            st.session_state.async_max_concurrent_jobs = max_concurrent
            st.session_state.async_enable_caching = enable_caching
        else:
            st.session_state.async_config['enabled'] = False