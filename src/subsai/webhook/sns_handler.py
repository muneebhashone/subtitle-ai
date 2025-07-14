"""
SNS Message Handler for S3 Upload Notifications
Parses and validates SNS messages from S3 bucket events
"""

import json
import logging
from typing import Dict, List, Optional, Any
from urllib.parse import unquote_plus
from dataclasses import dataclass
import hashlib
import hmac
import base64
from urllib.request import urlopen

logger = logging.getLogger(__name__)


@dataclass
class S3EventRecord:
    """Represents an S3 event from SNS notification"""
    bucket_name: str
    object_key: str
    event_name: str
    object_size: int
    timestamp: str
    region: str
    
    @property
    def decoded_key(self) -> str:
        """Get URL-decoded object key"""
        return unquote_plus(self.object_key)
    
    @property
    def filename(self) -> str:
        """Get filename from object key"""
        return self.decoded_key.split('/')[-1]
    
    @property
    def is_upload_folder(self) -> bool:
        """Check if file is in uploads folder"""
        return self.decoded_key.startswith('uploads/')


class SNSHandler:
    """Handles SNS message parsing and validation"""
    
    def __init__(self, verify_signatures: bool = True):
        """
        Initialize SNS handler
        
        :param verify_signatures: Whether to verify SNS message signatures
        """
        self.verify_signatures = verify_signatures
    
    def parse_sns_message(self, raw_message: Dict[str, Any]) -> Optional[List[S3EventRecord]]:
        """
        Parse SNS message and extract S3 events
        
        :param raw_message: Raw SNS message data
        :return: List of S3 event records or None if invalid
        """
        try:
            # Handle subscription confirmation
            if raw_message.get('Type') == 'SubscriptionConfirmation':
                logger.info("Received SNS subscription confirmation")
                if self._confirm_subscription(raw_message):
                    logger.info("SNS subscription confirmed successfully")
                else:
                    logger.error("Failed to confirm SNS subscription")
                return None
            
            # Handle notification message
            if raw_message.get('Type') != 'Notification':
                logger.warning(f"Unexpected SNS message type: {raw_message.get('Type')}")
                return None
            
            # Verify signature if enabled
            if self.verify_signatures and not self._verify_signature(raw_message):
                logger.error("SNS message signature verification failed")
                return None
            
            # Parse the S3 event from the SNS message
            message_body = raw_message.get('Message', '')
            if not message_body:
                logger.error("SNS message has no Message body")
                return None
            
            try:
                s3_event = json.loads(message_body)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse S3 event JSON: {e}")
                return None
            
            # Extract S3 records
            records = s3_event.get('Records', [])
            if not records:
                logger.warning("No S3 records found in SNS message")
                return None
            
            s3_events = []
            for record in records:
                try:
                    s3_record = self._parse_s3_record(record)
                    if s3_record:
                        s3_events.append(s3_record)
                except Exception as e:
                    logger.error(f"Failed to parse S3 record: {e}")
                    continue
            
            logger.info(f"Parsed {len(s3_events)} S3 events from SNS message")
            return s3_events if s3_events else None
            
        except Exception as e:
            logger.error(f"Failed to parse SNS message: {e}")
            return None
    
    def _parse_s3_record(self, record: Dict[str, Any]) -> Optional[S3EventRecord]:
        """
        Parse individual S3 record
        
        :param record: S3 record from SNS message
        :return: S3EventRecord or None if invalid
        """
        try:
            # Extract S3 data
            s3_data = record.get('s3', {})
            bucket_data = s3_data.get('bucket', {})
            object_data = s3_data.get('object', {})
            
            # Required fields
            bucket_name = bucket_data.get('name')
            object_key = object_data.get('key')
            event_name = record.get('eventName')
            
            if not all([bucket_name, object_key, event_name]):
                logger.error(f"Missing required S3 record fields: bucket={bucket_name}, key={object_key}, event={event_name}")
                return None
            
            # Create S3 event record
            s3_event = S3EventRecord(
                bucket_name=bucket_name,
                object_key=object_key,
                event_name=event_name,
                object_size=object_data.get('size', 0),
                timestamp=record.get('eventTime', ''),
                region=record.get('awsRegion', '')
            )
            
            # Validate it's a file upload in the uploads folder
            if not s3_event.is_upload_folder:
                logger.info(f"Ignoring file not in uploads folder: {s3_event.decoded_key}")
                return None
            
            if not event_name.startswith('s3:ObjectCreated'):
                logger.info(f"Ignoring non-creation event: {event_name}")
                return None
            
            logger.info(f"Valid S3 upload event: {s3_event.filename} in {s3_event.bucket_name}")
            return s3_event
            
        except Exception as e:
            logger.error(f"Error parsing S3 record: {e}")
            return None
    
    def _verify_signature(self, message: Dict[str, Any]) -> bool:
        """
        Verify SNS message signature
        
        :param message: SNS message
        :return: True if signature is valid
        """
        try:
            # Get signing cert URL and download cert
            cert_url = message.get('SigningCertURL', '')
            if not cert_url:
                logger.error("No SigningCertURL in SNS message")
                return False
            
            # Validate cert URL is from AWS
            if not cert_url.startswith('https://sns.') or '.amazonaws.com' not in cert_url:
                logger.error(f"Invalid SigningCertURL: {cert_url}")
                return False
            
            # For production, you would download and verify the certificate
            # For now, we'll log the cert URL and return True
            # TODO: Implement full certificate verification
            logger.info(f"SNS message signature validation (cert URL: {cert_url})")
            return True
            
        except Exception as e:
            logger.error(f"Error verifying SNS signature: {e}")
            return False
    
    def _confirm_subscription(self, message: Dict[str, Any]) -> bool:
        """
        Confirm SNS subscription
        
        :param message: SNS subscription confirmation message
        :return: True if confirmation successful
        """
        try:
            subscribe_url = message.get('SubscribeURL')
            if not subscribe_url:
                logger.error("No SubscribeURL in confirmation message")
                return False
            
            # Confirm subscription by visiting the URL
            logger.info(f"Confirming SNS subscription: {subscribe_url}")
            
            with urlopen(subscribe_url) as response:
                if response.status == 200:
                    logger.info("SNS subscription confirmed successfully")
                    return True
                else:
                    logger.error(f"Failed to confirm subscription: HTTP {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error confirming SNS subscription: {e}")
            return False
    
    def filter_media_files(self, events: List[S3EventRecord]) -> List[S3EventRecord]:
        """
        Filter events to only include supported media files
        
        :param events: List of S3 events
        :return: Filtered list of media file events
        """
        supported_extensions = {
            '.mp4', '.avi', '.mkv', '.mov', '.flv', '.webm',  # Video
            '.wav', '.mp3', '.m4a', '.flac', '.aac', '.ogg'   # Audio
        }
        
        media_events = []
        for event in events:
            filename = event.filename.lower()
            if any(filename.endswith(ext) for ext in supported_extensions):
                media_events.append(event)
                logger.info(f"Media file detected: {event.filename}")
            else:
                logger.info(f"Ignoring non-media file: {event.filename}")
        
        return media_events