"""
FastAPI Webhook Server for SubsAI
Handles S3 SNS notifications and triggers automatic Hebrew audio processing
"""

import os
import asyncio
import logging
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

from subsai.webhook import SNSHandler, S3Downloader
from subsai.auth.user_management import UserManager, User
from subsai.analytics import AnalyticsService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="SubsAI Webhook Server",
    description="Webhook endpoint for automatic Hebrew audio processing from S3 uploads",
    version="1.0.0"
)

# Global components
sns_handler = SNSHandler(verify_signatures=True)
s3_downloader = S3Downloader()
user_manager = UserManager()
analytics = AnalyticsService()
thread_pool = ThreadPoolExecutor(max_workers=3)  # Limit concurrent processing


class WebhookPayload(BaseModel):
    """SNS webhook payload model"""
    Type: str
    MessageId: Optional[str] = None
    Message: Optional[str] = None
    Timestamp: Optional[str] = None
    SignatureVersion: Optional[str] = None
    Signature: Optional[str] = None
    SigningCertURL: Optional[str] = None
    SubscribeURL: Optional[str] = None
    TopicArn: Optional[str] = None
    Subject: Optional[str] = None


@app.on_event("startup")
async def startup_event():
    """Initialize webhook server components"""
    logger.info("Starting SubsAI Webhook Server...")
    
    # Initialize system user for webhook processing
    await create_system_user()
    
    # Test S3 connection
    bucket_name = os.getenv('WEBHOOK_S3_BUCKET', 'aidevlondon')
    if s3_downloader.test_connection(bucket_name):
        logger.info(f"S3 connection verified for bucket: {bucket_name}")
    else:
        logger.warning(f"S3 connection failed for bucket: {bucket_name}")
    
    logger.info("Webhook server startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on server shutdown"""
    logger.info("Shutting down webhook server...")
    thread_pool.shutdown(wait=True)
    logger.info("Webhook server shutdown complete")


async def create_system_user():
    """Create system user for webhook processing"""
    try:
        system_username = "webhook-system"
        system_password = "webhook-auto-process-2024"
        
        # Check if system user already exists
        if user_manager.get_user_by_username(system_username):
            logger.info("System user already exists")
            return
        
        # Create system user with admin role
        user_manager.create_user(
            username=system_username,
            password=system_password,
            role="admin"
        )
        logger.info("Created system user for webhook processing")
        
    except Exception as e:
        logger.error(f"Failed to create system user: {e}")


def get_system_user() -> Optional[User]:
    """Get system user for processing"""
    try:
        return user_manager.get_user_by_username("webhook-system")
    except Exception as e:
        logger.error(f"Failed to get system user: {e}")
        return None


@app.post("/webhook/upload")
async def handle_s3_upload_webhook(
    payload: WebhookPayload,
    background_tasks: BackgroundTasks,
    request: Request
):
    """
    Handle S3 upload notifications from SNS
    
    Processes Hebrew audio files with predefined settings:
    - Source Language: Hebrew (he)
    - Target Languages: Hebrew, English, French
    - Output Formats: SRT, OOONA
    """
    try:
        # Log incoming request
        client_ip = request.client.host
        logger.info(f"Received webhook request from {client_ip}: {payload.Type}")
        
        # Convert Pydantic model to dict for processing
        raw_message = payload.dict(exclude_none=True)
        
        # Parse SNS message
        s3_events = sns_handler.parse_sns_message(raw_message)
        
        if not s3_events:
            # This might be a subscription confirmation or invalid message
            return JSONResponse(
                status_code=200,
                content={"status": "acknowledged", "message": "No processing required"}
            )
        
        # Filter for media files only
        media_events = sns_handler.filter_media_files(s3_events)
        
        if not media_events:
            logger.info("No media files found in S3 events")
            return JSONResponse(
                status_code=200,
                content={"status": "acknowledged", "message": "No media files to process"}
            )
        
        # Process each media file
        job_ids = []
        for event in media_events:
            job_id = str(uuid.uuid4())
            job_ids.append(job_id)
            
            # Queue processing in background
            background_tasks.add_task(
                process_s3_media_file,
                job_id=job_id,
                bucket_name=event.bucket_name,
                s3_key=event.decoded_key,
                filename=event.filename,
                file_size=event.object_size
            )
            
            logger.info(f"Queued processing job {job_id} for {event.filename}")
        
        return JSONResponse(
            status_code=202,
            content={
                "status": "processing",
                "job_ids": job_ids,
                "files_queued": len(job_ids),
                "message": "Files queued for Hebrew processing"
            }
        )
        
    except Exception as e:
        logger.error(f"Error handling webhook: {e}")
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")


async def process_s3_media_file(job_id: str, bucket_name: str, s3_key: str, 
                               filename: str, file_size: int):
    """
    Process media file from S3 with Hebrew audio processing
    
    :param job_id: Unique job identifier
    :param bucket_name: S3 bucket name
    :param s3_key: S3 object key
    :param filename: Original filename
    :param file_size: File size in bytes
    """
    logger.info(f"Starting processing job {job_id} for {filename}")
    start_time = datetime.now()
    
    try:
        # Get system user
        system_user = get_system_user()
        if not system_user:
            raise Exception("System user not found for webhook processing")
        
        # Download file from S3
        logger.info(f"Downloading {filename} from S3...")
        local_file_path, actual_size = s3_downloader.download_file(bucket_name, s3_key)
        
        if not s3_downloader.validate_media_file(local_file_path):
            raise Exception(f"Invalid media file format: {filename}")
        
        # Import processing function
        try:
            from subsai.webui import _process_single_file_with_batch_flow
        except ImportError:
            raise Exception("Failed to import processing function")
        
        # Configure Hebrew processing parameters
        processing_config = {
            'file_path': local_file_path,
            'filename': filename,
            'file_size': actual_size,
            'source_language': 'he',  # Hebrew source language
            'target_languages': ['transcribe', 'en', 'fr'],  # Hebrew + English + French
            'output_formats': ['srt', 'ooona'],  # Both required formats
            'device_preference': 'auto',  # Optimal device selection
            'enable_download': False,  # No UI download needed
            'save_local': False,  # Don't save locally
            'save_s3': True,  # Upload results to S3
            's3_project': f'webhook-{datetime.now().strftime("%Y%m%d")}',  # Daily folders
            'progress_placeholder': None,  # No UI progress updates
            'results_placeholder': None,  # No UI result display
            'user': system_user
        }
        
        # Track processing start
        if analytics.is_enabled():
            analytics.track_transcription_start(
                user_id=system_user.id,
                filename=filename,
                model='openai/whisper',
                file_size=actual_size,
                source_language='he',
                target_languages=['transcribe', 'en', 'fr'],
                output_formats=['srt', 'ooona']
            )
        
        # Process the file (this runs in thread pool)
        logger.info(f"Processing {filename} with Hebrew audio settings...")
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            thread_pool,
            _process_single_file_with_batch_flow,
            **processing_config
        )
        
        # Track processing completion
        processing_time = (datetime.now() - start_time).total_seconds()
        
        if analytics.is_enabled():
            analytics.track_transcription_completion(
                user_id=system_user.id,
                filename=filename,
                processing_time=processing_time,
                success=result.get('success', False),
                output_formats=['srt', 'ooona']
            )
        
        # Log successful completion
        if result.get('success'):
            logger.info(f"Successfully processed {filename} in {processing_time:.1f}s")
            logger.info(f"Results uploaded to S3: {result.get('s3_files', [])}")
        else:
            error_msg = result.get('error', 'Unknown error')
            logger.error(f"Processing failed for {filename}: {error_msg}")
        
    except Exception as e:
        error_msg = f"Job {job_id} failed for {filename}: {str(e)}"
        logger.error(error_msg)
        
        # Track processing failure
        if analytics.is_enabled() and 'system_user' in locals():
            processing_time = (datetime.now() - start_time).total_seconds()
            analytics.track_transcription_completion(
                user_id=system_user.id,
                filename=filename,
                processing_time=processing_time,
                success=False,
                error_message=error_msg
            )
    
    finally:
        # Clean up downloaded file
        if 'local_file_path' in locals():
            s3_downloader.cleanup_file(local_file_path)
            logger.info(f"Cleaned up temporary file for {filename}")


@app.get("/webhook/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "SubsAI Webhook Server"
    }


@app.get("/webhook/status")
async def webhook_status():
    """Get webhook server status"""
    bucket_name = os.getenv('WEBHOOK_S3_BUCKET', 'aidevlondon')
    s3_healthy = s3_downloader.test_connection(bucket_name)
    system_user = get_system_user()
    
    return {
        "status": "operational",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "s3_connection": "healthy" if s3_healthy else "unhealthy",
            "system_user": "configured" if system_user else "missing",
            "analytics": "enabled" if analytics.is_enabled() else "disabled"
        },
        "configuration": {
            "s3_bucket": bucket_name,
            "source_language": "he",
            "target_languages": ["transcribe", "en", "fr"],
            "output_formats": ["srt", "ooona"]
        }
    }


def run_webhook_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the webhook server"""
    logger.info(f"Starting webhook server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_webhook_server()