"""
S3 File Downloader for Webhook Processing
Downloads media files from S3 for automatic processing
"""

import os
import tempfile
import logging
from pathlib import Path
from typing import Optional, Tuple
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)


class S3Downloader:
    """Downloads files from S3 for webhook processing"""
    
    def __init__(self, aws_access_key_id: Optional[str] = None, 
                 aws_secret_access_key: Optional[str] = None,
                 region_name: str = 'eu-west-2'):
        """
        Initialize S3 downloader
        
        :param aws_access_key_id: AWS access key (optional, uses env vars)
        :param aws_secret_access_key: AWS secret key (optional, uses env vars)
        :param region_name: AWS region
        """
        self.region_name = region_name
        
        # Initialize S3 client
        try:
            if aws_access_key_id and aws_secret_access_key:
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=aws_access_key_id,
                    aws_secret_access_key=aws_secret_access_key,
                    region_name=region_name
                )
            else:
                # Use environment variables or IAM role
                self.s3_client = boto3.client('s3', region_name=region_name)
                
            logger.info(f"S3 client initialized for region: {region_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            raise
    
    def download_file(self, bucket_name: str, s3_key: str, 
                     local_dir: Optional[str] = None) -> Tuple[str, int]:
        """
        Download file from S3 to local filesystem
        
        :param bucket_name: S3 bucket name
        :param s3_key: S3 object key
        :param local_dir: Local directory (uses temp dir if None)
        :return: Tuple of (local_file_path, file_size)
        :raises: ClientError, FileNotFoundError
        """
        try:
            # Get file info first
            head_response = self.s3_client.head_object(Bucket=bucket_name, Key=s3_key)
            file_size = head_response['ContentLength']
            
            # Create local directory if specified
            if local_dir:
                os.makedirs(local_dir, exist_ok=True)
                local_file_path = os.path.join(local_dir, os.path.basename(s3_key))
            else:
                # Use temporary directory
                temp_dir = tempfile.mkdtemp(prefix='webhook_download_')
                local_file_path = os.path.join(temp_dir, os.path.basename(s3_key))
            
            # Download the file
            logger.info(f"Downloading {s3_key} from bucket {bucket_name} to {local_file_path}")
            
            self.s3_client.download_file(bucket_name, s3_key, local_file_path)
            
            # Verify file was downloaded
            if not os.path.exists(local_file_path):
                raise FileNotFoundError(f"Downloaded file not found: {local_file_path}")
            
            actual_size = os.path.getsize(local_file_path)
            if actual_size != file_size:
                logger.warning(f"File size mismatch: expected {file_size}, got {actual_size}")
            
            logger.info(f"Successfully downloaded {s3_key} ({file_size} bytes)")
            return local_file_path, file_size
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                raise FileNotFoundError(f"S3 object not found: {s3_key}")
            elif error_code == 'NoSuchBucket':
                raise FileNotFoundError(f"S3 bucket not found: {bucket_name}")
            else:
                logger.error(f"S3 client error downloading {s3_key}: {e}")
                raise
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            raise
        except Exception as e:
            logger.error(f"Unexpected error downloading {s3_key}: {e}")
            raise
    
    def validate_media_file(self, file_path: str) -> bool:
        """
        Validate that the downloaded file is a supported media format
        
        :param file_path: Path to the downloaded file
        :return: True if valid media file
        """
        supported_extensions = {
            '.mp4', '.avi', '.mkv', '.mov', '.flv', '.webm',  # Video
            '.wav', '.mp3', '.m4a', '.flac', '.aac', '.ogg'   # Audio
        }
        
        file_extension = Path(file_path).suffix.lower()
        is_valid = file_extension in supported_extensions
        
        if not is_valid:
            logger.warning(f"Unsupported file format: {file_extension}")
        
        return is_valid
    
    def cleanup_file(self, file_path: str) -> bool:
        """
        Clean up downloaded file
        
        :param file_path: Path to file to delete
        :return: True if successful
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Cleaned up file: {file_path}")
                
                # Also remove parent directory if it's a temp directory
                parent_dir = os.path.dirname(file_path)
                if 'webhook_download_' in parent_dir and os.path.exists(parent_dir):
                    try:
                        os.rmdir(parent_dir)
                        logger.info(f"Cleaned up temp directory: {parent_dir}")
                    except OSError:
                        # Directory not empty, that's okay
                        pass
                        
                return True
        except Exception as e:
            logger.error(f"Failed to cleanup file {file_path}: {e}")
            
        return False
    
    def test_connection(self, bucket_name: str) -> bool:
        """
        Test S3 connection and bucket access
        
        :param bucket_name: Bucket to test access to
        :return: True if connection successful
        """
        try:
            self.s3_client.head_bucket(Bucket=bucket_name)
            logger.info(f"S3 connection test successful for bucket: {bucket_name}")
            return True
        except Exception as e:
            logger.error(f"S3 connection test failed: {e}")
            return False