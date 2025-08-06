#!/usr/bin/env python3
"""
Async API Client for SubsAI
Handles external API calls with connection pooling, retry logic, and batching
"""

import asyncio
import aiohttp
import logging
import time
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
import json
import backoff
import hashlib

@dataclass
class APIRequest:
    """Represents an API request with metadata"""
    endpoint: str
    method: str = "POST"
    data: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: float = 30.0
    retry_count: int = 3
    created_at: float = field(default_factory=time.time)
    request_id: Optional[str] = None

@dataclass
class APIResponse:
    """Represents an API response with metadata"""
    status_code: int
    data: Any
    headers: Dict[str, str]
    response_time: float
    request_id: Optional[str] = None


class AsyncAPIClient:
    """
    Async API client with connection pooling, retry logic, and batching support
    """
    
    def __init__(self, 
                 base_url: str,
                 api_key: str = None,
                 max_connections: int = 100,
                 max_connections_per_host: int = 10,
                 timeout: float = 30.0,
                 retry_attempts: int = 3,
                 batch_size: int = 10,
                 batch_timeout: float = 1.0):
        """
        Initialize the async API client
        
        :param base_url: Base URL for API endpoints
        :param api_key: API key for authentication
        :param max_connections: Maximum total connections
        :param max_connections_per_host: Maximum connections per host
        :param timeout: Default request timeout
        :param retry_attempts: Number of retry attempts for failed requests
        :param batch_size: Maximum number of requests to batch together
        :param batch_timeout: Time to wait for batch to fill before sending
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        
        # Connection pool configuration
        connector = aiohttp.TCPConnector(
            limit=max_connections,
            limit_per_host=max_connections_per_host,
            ttl_dns_cache=300,  # DNS cache TTL
            use_dns_cache=True,
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )
        
        # Create session with timeout configuration
        timeout_config = aiohttp.ClientTimeout(total=timeout)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout_config,
            headers=self._get_default_headers()
        )
        
        # Batching support
        self.batch_queue = asyncio.Queue()
        self.batch_results = {}
        self.batch_task = None
        
        # Statistics
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'retried_requests': 0,
            'batched_requests': 0,
            'cache_hits': 0,
            'total_response_time': 0.0,
            'average_response_time': 0.0
        }
        
        # Response cache for duplicate requests
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes
        
        # Logger
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"AsyncAPIClient initialized for {base_url}")
        
        # Start batch processing
        self._start_batch_processor()
    
    def _get_default_headers(self) -> Dict[str, str]:
        """Get default headers for requests"""
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'SubsAI-AsyncClient/1.0',
            'Accept': 'application/json'
        }
        
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        
        return headers
    
    def _start_batch_processor(self):
        """Start the batch processing task"""
        self.batch_task = asyncio.create_task(self._batch_processor())
    
    async def _batch_processor(self):
        """Process batched requests"""
        while True:
            try:
                batch = []
                
                # Collect requests for batching
                try:
                    # Wait for first request
                    first_request = await asyncio.wait_for(
                        self.batch_queue.get(), 
                        timeout=self.batch_timeout
                    )
                    batch.append(first_request)
                    
                    # Collect additional requests up to batch_size
                    for _ in range(self.batch_size - 1):
                        try:
                            request = await asyncio.wait_for(
                                self.batch_queue.get(), 
                                timeout=0.1  # Short timeout for additional requests
                            )
                            batch.append(request)
                        except asyncio.TimeoutError:
                            break
                
                except asyncio.TimeoutError:
                    continue  # No requests to process
                
                if batch:
                    await self._process_batch(batch)
                    
            except Exception as e:
                self.logger.error(f"Error in batch processor: {e}")
                await asyncio.sleep(1)  # Brief pause before continuing
    
    async def _process_batch(self, batch: List[APIRequest]):
        """Process a batch of requests"""
        if len(batch) == 1:
            # Single request, process normally
            request = batch[0]
            try:
                response = await self._execute_request(request)
                if request.request_id:
                    self.batch_results[request.request_id] = response
            except Exception as e:
                if request.request_id:
                    self.batch_results[request.request_id] = e
        else:
            # Multiple requests, process concurrently
            tasks = []
            for request in batch:
                task = asyncio.create_task(self._execute_request(request))
                tasks.append((request, task))
            
            # Wait for all requests to complete
            for request, task in tasks:
                try:
                    response = await task
                    if request.request_id:
                        self.batch_results[request.request_id] = response
                    self.stats['batched_requests'] += 1
                except Exception as e:
                    if request.request_id:
                        self.batch_results[request.request_id] = e
    
    def _generate_cache_key(self, request: APIRequest) -> str:
        """Generate cache key for request"""
        cache_data = {
            'endpoint': request.endpoint,
            'method': request.method,
            'data': request.data
        }
        return hashlib.md5(json.dumps(cache_data, sort_keys=True).encode()).hexdigest()
    
    def _is_cache_valid(self, cache_entry: Dict[str, Any]) -> bool:
        """Check if cache entry is still valid"""
        return time.time() - cache_entry['timestamp'] < self.cache_ttl
    
    @backoff.on_exception(
        backoff.expo,
        (aiohttp.ClientError, asyncio.TimeoutError),
        max_tries=3,
        max_time=60
    )
    async def _execute_request(self, request: APIRequest) -> APIResponse:
        """Execute a single API request with retry logic"""
        # Check cache first
        cache_key = self._generate_cache_key(request)
        if cache_key in self.cache and self._is_cache_valid(self.cache[cache_key]):
            self.stats['cache_hits'] += 1
            cached_response = self.cache[cache_key]['response']
            self.logger.debug(f"Cache hit for {request.endpoint}")
            return cached_response
        
        url = f"{self.base_url}{request.endpoint}"
        start_time = time.time()
        
        try:
            # Merge request headers with defaults
            headers = {**self.session.headers, **request.headers}
            
            async with self.session.request(
                method=request.method,
                url=url,
                json=request.data if request.data else None,
                headers=headers
            ) as response:
                response_time = time.time() - start_time
                response_data = await response.json()
                
                api_response = APIResponse(
                    status_code=response.status,
                    data=response_data,
                    headers=dict(response.headers),
                    response_time=response_time,
                    request_id=request.request_id
                )
                
                # Update statistics
                self.stats['total_requests'] += 1
                self.stats['total_response_time'] += response_time
                self.stats['average_response_time'] = (
                    self.stats['total_response_time'] / self.stats['total_requests']
                )
                
                if response.status < 400:
                    self.stats['successful_requests'] += 1
                    
                    # Cache successful responses
                    self.cache[cache_key] = {
                        'response': api_response,
                        'timestamp': time.time()
                    }
                else:
                    self.stats['failed_requests'] += 1
                    self.logger.warning(f"API request failed: {response.status} - {response_data}")
                
                return api_response
                
        except Exception as e:
            self.stats['failed_requests'] += 1
            self.stats['retried_requests'] += 1
            self.logger.error(f"Request to {url} failed: {e}")
            raise
    
    async def request(self, endpoint: str, data: Dict[str, Any] = None, 
                     method: str = "POST", headers: Dict[str, str] = None,
                     timeout: float = None, use_batching: bool = True) -> APIResponse:
        """
        Make an API request
        
        :param endpoint: API endpoint (relative to base_url)
        :param data: Request data
        :param method: HTTP method
        :param headers: Additional headers
        :param timeout: Request timeout (overrides default)
        :param use_batching: Whether to use batching for this request
        :return: APIResponse
        """
        request = APIRequest(
            endpoint=endpoint,
            method=method,
            data=data or {},
            headers=headers or {},
            timeout=timeout or self.timeout
        )
        
        if use_batching:
            # Add to batch queue
            request.request_id = f"{int(time.time() * 1000000)}_{id(request)}"
            await self.batch_queue.put(request)
            
            # Wait for result
            while request.request_id not in self.batch_results:
                await asyncio.sleep(0.01)
            
            result = self.batch_results.pop(request.request_id)
            if isinstance(result, Exception):
                raise result
            return result
        else:
            # Execute immediately
            return await self._execute_request(request)
    
    async def close(self):
        """Close the client and cleanup resources"""
        if self.batch_task:
            self.batch_task.cancel()
            try:
                await self.batch_task
            except asyncio.CancelledError:
                pass
        
        await self.session.close()
        self.logger.info("AsyncAPIClient closed")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics"""
        return {
            **self.stats,
            'cache_size': len(self.cache),
            'queue_size': self.batch_queue.qsize() if self.batch_queue else 0
        }


class DeepSeekAPIClient(AsyncAPIClient):
    """
    Specialized async client for DeepSeek API with optimized translation batching
    """
    
    def __init__(self, api_key: str, model: str = "deepseek-chat", 
                 base_url: str = "https://api.deepseek.com", **kwargs):
        """
        Initialize DeepSeek API client
        
        :param api_key: DeepSeek API key
        :param model: Model to use (deepseek-chat or deepseek-reasoner)
        :param base_url: API base URL
        """
        super().__init__(base_url=base_url, api_key=api_key, **kwargs)
        self.model = model
        self.translation_cache = {}  # Specialized cache for translations
        
    async def translate_text(self, text: str, source_lang: str, target_lang: str,
                           context: str = None) -> str:
        """
        Translate text using DeepSeek API
        
        :param text: Text to translate
        :param source_lang: Source language code
        :param target_lang: Target language code
        :param context: Optional context for better translation
        :return: Translated text
        """
        # Create translation cache key
        cache_key = hashlib.md5(
            f"{text}|{source_lang}|{target_lang}|{context or ''}".encode()
        ).hexdigest()
        
        # Check translation cache
        if cache_key in self.translation_cache:
            cache_entry = self.translation_cache[cache_key]
            if self._is_cache_valid(cache_entry):
                self.stats['cache_hits'] += 1
                return cache_entry['translation']
        
        # Prepare translation prompt
        if context:
            prompt = f"Translate the following {source_lang} text to {target_lang}. Context: {context}\n\nText: {text}\n\nTranslation:"
        else:
            prompt = f"Translate the following {source_lang} text to {target_lang}:\n\n{text}"
        
        request_data = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,  # Low temperature for consistent translations
            "max_tokens": len(text) * 2,  # Rough estimate for translation length
            "stream": False
        }
        
        try:
            response = await self.request("/v1/chat/completions", data=request_data)
            
            if response.status_code == 200:
                translated_text = response.data["choices"][0]["message"]["content"].strip()
                
                # Cache the translation
                self.translation_cache[cache_key] = {
                    'translation': translated_text,
                    'timestamp': time.time()
                }
                
                return translated_text
            else:
                raise Exception(f"DeepSeek API error: {response.status_code} - {response.data}")
                
        except Exception as e:
            self.logger.error(f"Translation failed: {e}")
            raise
    
    async def translate_batch(self, texts: List[str], source_lang: str, target_lang: str,
                            context: str = None) -> List[str]:
        """
        Translate multiple texts concurrently
        
        :param texts: List of texts to translate
        :param source_lang: Source language code
        :param target_lang: Target language code
        :param context: Optional context for better translation
        :return: List of translated texts
        """
        tasks = []
        for text in texts:
            task = asyncio.create_task(
                self.translate_text(text, source_lang, target_lang, context)
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


@asynccontextmanager
async def create_deepseek_client(api_key: str, model: str = "deepseek-chat", **kwargs):
    """Context manager for creating and managing DeepSeek API client"""
    client = DeepSeekAPIClient(api_key=api_key, model=model, **kwargs)
    try:
        yield client
    finally:
        await client.close()


# Global client instance for reuse
_global_clients = {}

async def get_or_create_client(api_key: str, model: str = "deepseek-chat", **kwargs) -> DeepSeekAPIClient:
    """Get or create a global client instance for reuse"""
    client_key = f"{api_key[:10]}_{model}"
    
    if client_key not in _global_clients:
        _global_clients[client_key] = DeepSeekAPIClient(
            api_key=api_key, 
            model=model, 
            **kwargs
        )
    
    return _global_clients[client_key]

async def cleanup_global_clients():
    """Cleanup all global client instances"""
    for client in _global_clients.values():
        await client.close()
    _global_clients.clear()