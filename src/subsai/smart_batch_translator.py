#!/usr/bin/env python3
"""
Smart Batch Translator for SubsAI
Intelligent batching system for translation requests to minimize API calls and improve performance
"""

import asyncio
import logging
import time
import hashlib
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict
import json
import os

from subsai.async_api_client import DeepSeekAPIClient, get_or_create_client


@dataclass
class TranslationRequest:
    """Represents a single translation request"""
    text: str
    source_lang: str
    target_lang: str
    context: Optional[str] = None
    priority: int = 0  # Higher number = higher priority
    request_id: str = field(default_factory=lambda: str(int(time.time() * 1000000)))
    created_at: float = field(default_factory=time.time)
    max_wait_time: float = 5.0  # Maximum wait time before forcing batch processing


@dataclass
class TranslationBatch:
    """Represents a batch of translation requests"""
    requests: List[TranslationRequest] = field(default_factory=list)
    source_lang: str = ""
    target_lang: str = ""
    context: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    batch_id: str = field(default_factory=lambda: str(int(time.time() * 1000000)))


@dataclass
class BatchResult:
    """Result of a batch translation"""
    batch_id: str
    translations: Dict[str, str]  # request_id -> translated_text
    processing_time: float
    api_calls_saved: int
    cache_hits: int


class SmartBatchTranslator:
    """
    Smart batching system for translation requests that optimizes API usage
    """
    
    def __init__(self,
                 max_batch_size: int = 20,
                 batch_timeout: float = 2.0,
                 similarity_threshold: float = 0.85,
                 cache_ttl: int = 3600,
                 max_concurrent_batches: int = 5):
        """
        Initialize the smart batch translator
        
        :param max_batch_size: Maximum number of requests per batch
        :param batch_timeout: Maximum time to wait before processing batch
        :param similarity_threshold: Threshold for text similarity deduplication
        :param cache_ttl: Cache time-to-live in seconds
        :param max_concurrent_batches: Maximum concurrent batch processing
        """
        self.max_batch_size = max_batch_size
        self.batch_timeout = batch_timeout
        self.similarity_threshold = similarity_threshold
        self.cache_ttl = cache_ttl
        self.max_concurrent_batches = max_concurrent_batches
        
        # Request queues organized by language pair and context
        self.request_queues: Dict[str, List[TranslationRequest]] = defaultdict(list)
        self.pending_results: Dict[str, asyncio.Future] = {}
        
        # Translation cache for deduplication
        self.translation_cache: Dict[str, Dict[str, Any]] = {}
        
        # Active batches and processing
        self.active_batches: Dict[str, asyncio.Task] = {}
        self.batch_semaphore = asyncio.Semaphore(max_concurrent_batches)
        
        # Performance metrics
        self.stats = {
            'total_requests': 0,
            'batched_requests': 0,
            'cache_hits': 0,
            'api_calls_saved': 0,
            'average_batch_size': 0.0,
            'total_batches': 0,
            'deduplication_saves': 0
        }
        
        # Background processing
        self._processing = False
        self._batch_processor_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        # Logger
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"SmartBatchTranslator initialized with batch_size={max_batch_size}")
        
        # Start background processing
        asyncio.create_task(self._start_batch_processor())
    
    def _create_queue_key(self, source_lang: str, target_lang: str, context: Optional[str] = None) -> str:
        """Create key for request queue based on language pair and context"""
        context_hash = hashlib.md5((context or "").encode()).hexdigest()[:8]
        return f"{source_lang}->{target_lang}#{context_hash}"
    
    def _create_cache_key(self, text: str, source_lang: str, target_lang: str, context: Optional[str] = None) -> str:
        """Create cache key for translation"""
        cache_data = {
            'text': text.strip().lower(),
            'source': source_lang,
            'target': target_lang,
            'context': context or ""
        }
        return hashlib.md5(json.dumps(cache_data, sort_keys=True).encode()).hexdigest()
    
    def _is_cache_valid(self, cache_entry: Dict[str, Any]) -> bool:
        """Check if cache entry is still valid"""
        return time.time() - cache_entry['timestamp'] < self.cache_ttl
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts (simple approach)"""
        # Simple character-based similarity
        if not text1 or not text2:
            return 0.0
        
        text1_clean = text1.strip().lower()
        text2_clean = text2.strip().lower()
        
        if text1_clean == text2_clean:
            return 1.0
        
        # Calculate Jaccard similarity on character n-grams
        def get_ngrams(text: str, n: int = 3) -> Set[str]:
            return set(text[i:i+n] for i in range(len(text) - n + 1))
        
        ngrams1 = get_ngrams(text1_clean)
        ngrams2 = get_ngrams(text2_clean)
        
        if not ngrams1 or not ngrams2:
            return 0.0
        
        intersection = len(ngrams1 & ngrams2)
        union = len(ngrams1 | ngrams2)
        
        return intersection / union if union > 0 else 0.0
    
    def _find_similar_cached_translation(self, text: str, source_lang: str, target_lang: str, context: Optional[str] = None) -> Optional[str]:
        """Find similar text in cache that can be reused"""
        text_clean = text.strip().lower()
        
        # Look for exact match first
        exact_key = self._create_cache_key(text, source_lang, target_lang, context)
        if exact_key in self.translation_cache and self._is_cache_valid(self.translation_cache[exact_key]):
            return self.translation_cache[exact_key]['translation']
        
        # Look for similar texts
        for cache_key, cache_entry in self.translation_cache.items():
            if not self._is_cache_valid(cache_entry):
                continue
            
            if (cache_entry['source_lang'] == source_lang and 
                cache_entry['target_lang'] == target_lang and
                cache_entry.get('context') == context):
                
                similarity = self._calculate_text_similarity(text_clean, cache_entry['original_text'])
                if similarity >= self.similarity_threshold:
                    self.stats['deduplication_saves'] += 1
                    self.logger.debug(f"Found similar cached translation (similarity: {similarity:.2f})")
                    return cache_entry['translation']
        
        return None
    
    async def _start_batch_processor(self):
        """Start the background batch processor"""
        await asyncio.sleep(0.1)  # Small delay for initialization
        self._batch_processor_task = asyncio.create_task(self._batch_processor_loop())
    
    async def _batch_processor_loop(self):
        """Main batch processing loop"""
        self._processing = True
        
        try:
            while not self._shutdown_event.is_set():
                await asyncio.sleep(0.5)  # Check every 500ms
                
                # Process each queue
                for queue_key, requests in list(self.request_queues.items()):
                    if not requests:
                        continue
                    
                    # Check if batch should be processed
                    should_process = False
                    
                    # Batch size threshold
                    if len(requests) >= self.max_batch_size:
                        should_process = True
                        self.logger.debug(f"Processing batch due to size: {len(requests)}")
                    
                    # Timeout threshold
                    oldest_request = min(requests, key=lambda r: r.created_at)
                    if time.time() - oldest_request.created_at >= self.batch_timeout:
                        should_process = True
                        self.logger.debug(f"Processing batch due to timeout: {time.time() - oldest_request.created_at:.2f}s")
                    
                    # Priority threshold
                    high_priority_requests = [r for r in requests if r.priority > 5]
                    if high_priority_requests:
                        should_process = True
                        self.logger.debug(f"Processing batch due to high priority requests: {len(high_priority_requests)}")
                    
                    # Individual request max wait time
                    for request in requests:
                        if time.time() - request.created_at >= request.max_wait_time:
                            should_process = True
                            self.logger.debug(f"Processing batch due to max wait time exceeded")
                            break
                    
                    if should_process:
                        # Remove requests from queue and create batch
                        batch_requests = requests[:self.max_batch_size]
                        self.request_queues[queue_key] = requests[self.max_batch_size:]
                        
                        if batch_requests:
                            # Create and process batch
                            batch = self._create_batch(batch_requests)
                            await self._process_batch_async(batch)
        
        except Exception as e:
            self.logger.error(f"Error in batch processor loop: {e}")
        finally:
            self._processing = False
    
    def _create_batch(self, requests: List[TranslationRequest]) -> TranslationBatch:
        """Create a translation batch from requests"""
        if not requests:
            raise ValueError("Cannot create batch from empty requests")
        
        # Use the language pair from the first request
        first_request = requests[0]
        
        batch = TranslationBatch(
            requests=requests,
            source_lang=first_request.source_lang,
            target_lang=first_request.target_lang,
            context=first_request.context
        )
        
        return batch
    
    async def _process_batch_async(self, batch: TranslationBatch):
        """Process a batch of translation requests"""
        async with self.batch_semaphore:
            start_time = time.time()
            
            try:
                # Group requests by exact duplicates
                unique_texts = {}
                text_to_requests = defaultdict(list)
                
                for request in batch.requests:
                    text_key = request.text.strip()
                    text_to_requests[text_key].append(request)
                    if text_key not in unique_texts:
                        unique_texts[text_key] = request
                
                # Check cache for each unique text
                cached_translations = {}
                texts_to_translate = []
                
                for text_key, request in unique_texts.items():
                    cached_translation = self._find_similar_cached_translation(
                        request.text, request.source_lang, request.target_lang, request.context
                    )
                    
                    if cached_translation:
                        cached_translations[text_key] = cached_translation
                        self.stats['cache_hits'] += len(text_to_requests[text_key])
                    else:
                        texts_to_translate.append(request)
                
                # Translate uncached texts
                api_translations = {}
                if texts_to_translate:
                    api_translations = await self._translate_batch_via_api(texts_to_translate)
                
                # Combine results and update cache
                all_translations = {}
                for text_key, requests in text_to_requests.items():
                    if text_key in cached_translations:
                        translation = cached_translations[text_key]
                    else:
                        # Find the translation from API results
                        matching_request = unique_texts[text_key]
                        translation = api_translations.get(matching_request.request_id, text_key)
                        
                        # Cache the new translation
                        cache_key = self._create_cache_key(
                            matching_request.text, 
                            matching_request.source_lang, 
                            matching_request.target_lang, 
                            matching_request.context
                        )
                        self.translation_cache[cache_key] = {
                            'translation': translation,
                            'original_text': matching_request.text.strip().lower(),
                            'source_lang': matching_request.source_lang,
                            'target_lang': matching_request.target_lang,
                            'context': matching_request.context,
                            'timestamp': time.time()
                        }
                    
                    # Set result for all requests with this text
                    for request in requests:
                        all_translations[request.request_id] = translation
                        
                        # Resolve the future if it exists
                        if request.request_id in self.pending_results:
                            future = self.pending_results.pop(request.request_id)
                            if not future.done():
                                future.set_result(translation)
                
                # Update statistics
                processing_time = time.time() - start_time
                api_calls_saved = len(batch.requests) - len(texts_to_translate)
                
                self.stats['total_batches'] += 1
                self.stats['batched_requests'] += len(batch.requests)
                self.stats['api_calls_saved'] += api_calls_saved
                self.stats['average_batch_size'] = (
                    self.stats['batched_requests'] / self.stats['total_batches']
                )
                
                # Create batch result
                result = BatchResult(
                    batch_id=batch.batch_id,
                    translations=all_translations,
                    processing_time=processing_time,
                    api_calls_saved=api_calls_saved,
                    cache_hits=len(cached_translations)
                )
                
                self.logger.info(
                    f"Processed batch {batch.batch_id}: {len(batch.requests)} requests, "
                    f"{len(texts_to_translate)} API calls, {api_calls_saved} calls saved, "
                    f"{processing_time:.2f}s"
                )
                
                return result
                
            except Exception as e:
                self.logger.error(f"Batch processing failed: {e}")
                
                # Resolve all pending futures with error or original text
                for request in batch.requests:
                    if request.request_id in self.pending_results:
                        future = self.pending_results.pop(request.request_id)
                        if not future.done():
                            future.set_result(request.text)  # Return original text on error
                
                raise
    
    async def _translate_batch_via_api(self, requests: List[TranslationRequest]) -> Dict[str, str]:
        """Translate a batch of requests via API"""
        if not requests:
            return {}
        
        # Group by API client configuration
        api_groups = defaultdict(list)
        for request in requests:
            # For now, assume all use the same API configuration
            # In the future, this could be more sophisticated
            api_key = "default"  # This should come from configuration
            api_groups[api_key].append(request)
        
        all_translations = {}
        
        for api_key, group_requests in api_groups.items():
            try:
                # Get or create API client
                actual_api_key = os.getenv('DEEPSEEK_API_KEY')
                if not actual_api_key:
                    self.logger.error("No API key available for translation")
                    for request in group_requests:
                        all_translations[request.request_id] = request.text
                    continue
                
                client = await get_or_create_client(
                    api_key=actual_api_key,
                    model="deepseek-chat"
                )
                
                # Extract texts for batch translation
                texts = [request.text for request in group_requests]
                source_lang = group_requests[0].source_lang
                target_lang = group_requests[0].target_lang
                context = group_requests[0].context
                
                # Perform batch translation
                translated_texts = await client.translate_batch(
                    texts=texts,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    context=context
                )
                
                # Map results back to request IDs
                for request, translation in zip(group_requests, translated_texts):
                    all_translations[request.request_id] = translation
                
            except Exception as e:
                self.logger.error(f"API translation failed for group: {e}")
                # Return original texts on error
                for request in group_requests:
                    all_translations[request.request_id] = request.text
        
        return all_translations
    
    async def translate_async(self, text: str, source_lang: str, target_lang: str, 
                            context: Optional[str] = None, priority: int = 0) -> str:
        """
        Translate text asynchronously using smart batching
        
        :param text: Text to translate
        :param source_lang: Source language code
        :param target_lang: Target language code
        :param context: Optional context for better translation
        :param priority: Request priority (higher = more urgent)
        :return: Translated text
        """
        self.stats['total_requests'] += 1
        
        # Check cache first
        cached_translation = self._find_similar_cached_translation(text, source_lang, target_lang, context)
        if cached_translation:
            self.stats['cache_hits'] += 1
            return cached_translation
        
        # Create translation request
        request = TranslationRequest(
            text=text,
            source_lang=source_lang,
            target_lang=target_lang,
            context=context,
            priority=priority
        )
        
        # Create future for result
        future = asyncio.Future()
        self.pending_results[request.request_id] = future
        
        # Add to appropriate queue
        queue_key = self._create_queue_key(source_lang, target_lang, context)
        self.request_queues[queue_key].append(request)
        
        self.logger.debug(f"Added translation request to queue {queue_key}: {text[:50]}...")
        
        # Wait for result
        try:
            result = await future
            return result
        except Exception as e:
            self.logger.error(f"Translation request failed: {e}")
            return text  # Return original text on error
    
    async def translate_multiple(self, texts: List[str], source_lang: str, target_lang: str,
                               context: Optional[str] = None, priority: int = 0) -> List[str]:
        """
        Translate multiple texts concurrently
        
        :param texts: List of texts to translate
        :param source_lang: Source language code
        :param target_lang: Target language code
        :param context: Optional context for better translation
        :param priority: Request priority
        :return: List of translated texts
        """
        tasks = []
        for text in texts:
            task = asyncio.create_task(
                self.translate_async(text, source_lang, target_lang, context, priority)
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions
        translated_texts = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Translation failed for text {i}: {result}")
                translated_texts.append(texts[i])  # Return original text on failure
            else:
                translated_texts.append(result)
        
        return translated_texts
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        return {
            **self.stats,
            'queue_sizes': {k: len(v) for k, v in self.request_queues.items()},
            'cache_size': len(self.translation_cache),
            'active_batches': len(self.active_batches),
            'pending_results': len(self.pending_results),
            'is_processing': self._processing
        }
    
    async def shutdown(self):
        """Shutdown the batch translator and cleanup resources"""
        self.logger.info("Shutting down SmartBatchTranslator...")
        
        # Signal shutdown
        self._shutdown_event.set()
        
        # Cancel batch processor
        if self._batch_processor_task:
            self._batch_processor_task.cancel()
            try:
                await self._batch_processor_task
            except asyncio.CancelledError:
                pass
        
        # Cancel active batches
        for batch_id, task in list(self.active_batches.items()):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # Resolve any pending futures
        for request_id, future in list(self.pending_results.items()):
            if not future.done():
                future.set_result("Translation cancelled")
        
        # Clear data structures
        self.request_queues.clear()
        self.pending_results.clear()
        self.active_batches.clear()
        
        self.logger.info("SmartBatchTranslator shutdown complete")


# Global instance for reuse
_global_batch_translator: Optional[SmartBatchTranslator] = None

async def get_global_batch_translator(**kwargs) -> SmartBatchTranslator:
    """Get or create global batch translator instance"""
    global _global_batch_translator
    
    if _global_batch_translator is None:
        _global_batch_translator = SmartBatchTranslator(**kwargs)
    
    return _global_batch_translator

async def cleanup_global_batch_translator():
    """Cleanup global batch translator instance"""
    global _global_batch_translator
    
    if _global_batch_translator:
        await _global_batch_translator.shutdown()
        _global_batch_translator = None