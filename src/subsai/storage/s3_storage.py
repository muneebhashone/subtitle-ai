"""
S3 Storage service for subtitle files.
"""
import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError, BotoCoreError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

logger = logging.getLogger(__name__)


class S3StorageError(Exception):
    """Custom exception for S3 storage operations."""
    pass


class S3Storage:
    """S3 storage service for subtitle files."""
    
    def __init__(self, bucket_name: str, region: str = "us-east-1", 
                 access_key: Optional[str] = None, secret_key: Optional[str] = None):
        """
        Initialize S3 storage service.
        
        Args:
            bucket_name: S3 bucket name
            region: AWS region
            access_key: AWS access key (optional, can use env vars or IAM)
            secret_key: AWS secret key (optional, can use env vars or IAM)
        """
        if not BOTO3_AVAILABLE:
            raise S3StorageError("boto3 is required for S3 storage. Install with: pip install boto3")
        
        self.bucket_name = bucket_name
        self.region = region
        
        # Initialize S3 client
        try:
            if access_key and secret_key:
                self.s3_client = boto3.client(
                    's3',
                    region_name=region,
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key
                )
            else:
                # Use default credential chain (env vars, IAM role, etc.)
                self.s3_client = boto3.client('s3', region_name=region)
        except Exception as e:
            raise S3StorageError(f"Failed to initialize S3 client: {str(e)}")
    
    def validate_connection(self) -> Dict[str, Any]:
        """
        Validate S3 connection and bucket access.
        
        Returns:
            Dict with validation results
        """
        try:
            # Test bucket access
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            
            # Test write permissions by attempting to list objects
            self.s3_client.list_objects_v2(Bucket=self.bucket_name, MaxKeys=1)
            
            return {
                "success": True,
                "message": f"Successfully connected to S3 bucket: {self.bucket_name}",
                "bucket_region": self._get_bucket_region()
            }
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                return {
                    "success": False,
                    "message": f"Bucket '{self.bucket_name}' not found or no access"
                }
            elif error_code == '403':
                return {
                    "success": False,
                    "message": f"Access denied to bucket '{self.bucket_name}'"
                }
            else:
                return {
                    "success": False,
                    "message": f"S3 error: {e.response['Error']['Message']}"
                }
        except NoCredentialsError:
            return {
                "success": False,
                "message": "AWS credentials not found. Please configure access key and secret key."
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Connection error: {str(e)}"
            }
    
    def upload_subtitle(self, subtitle_content: str, project_name: str, 
                       filename: str, subtitle_format: str = "srt") -> Dict[str, Any]:
        """
        Upload subtitle content to S3.
        
        Args:
            subtitle_content: Subtitle file content as string
            project_name: Project folder name
            filename: Base filename (without extension)
            subtitle_format: Subtitle format (srt, vtt, ass, etc.)
        
        Returns:
            Dict with upload results
        """
        try:
            # Generate S3 key (path)
            s3_key = self._generate_s3_key(project_name, filename, subtitle_format)
            
            # Upload content
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=subtitle_content.encode('utf-8'),
                ContentType=self._get_content_type(subtitle_format),
                Metadata={
                    'original_filename': filename,
                    'subtitle_format': subtitle_format,
                    'project_name': project_name,
                    'upload_timestamp': datetime.utcnow().isoformat()
                }
            )
            
            s3_url = f"s3://{self.bucket_name}/{s3_key}"
            
            logger.info(f"Successfully uploaded subtitle to S3: {s3_url}")
            
            return {
                "success": True,
                "s3_url": s3_url,
                "s3_key": s3_key,
                "bucket": self.bucket_name,
                "message": f"Subtitle uploaded successfully to {s3_url}"
            }
            
        except ClientError as e:
            error_msg = f"Failed to upload to S3: {e.response['Error']['Message']}"
            logger.error(error_msg)
            return {
                "success": False,
                "message": error_msg
            }
        except Exception as e:
            error_msg = f"Upload error: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "message": error_msg
            }
    
    def upload_subtitle_file(self, file_path: str, project_name: str, 
                            custom_filename: Optional[str] = None) -> Dict[str, Any]:
        """
        Upload subtitle file from local path to S3.
        
        Args:
            file_path: Local file path
            project_name: Project folder name
            custom_filename: Custom filename (optional, uses original if not provided)
        
        Returns:
            Dict with upload results
        """
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                return {
                    "success": False,
                    "message": f"File not found: {file_path}"
                }
            
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Use custom filename or original
            filename = custom_filename or file_path.stem
            subtitle_format = file_path.suffix[1:]  # Remove dot
            
            return self.upload_subtitle(content, project_name, filename, subtitle_format)
            
        except Exception as e:
            error_msg = f"Failed to read and upload file: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "message": error_msg
            }
    
    def list_projects(self) -> List[str]:
        """
        List all project folders in the S3 bucket.
        
        Returns:
            List of project folder names
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Delimiter='/'
            )
            
            projects = []
            if 'CommonPrefixes' in response:
                for prefix in response['CommonPrefixes']:
                    # Remove trailing slash
                    project_name = prefix['Prefix'].rstrip('/')
                    projects.append(project_name)
            
            return sorted(projects)
            
        except Exception as e:
            logger.error(f"Failed to list projects: {str(e)}")
            return []
    
    def list_project_files(self, project_name: str) -> List[Dict[str, Any]]:
        """
        List all subtitle files in a project folder.
        
        Args:
            project_name: Project folder name
        
        Returns:
            List of file information dictionaries
        """
        try:
            prefix = f"{project_name}/"
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    # Skip folder markers
                    if obj['Key'].endswith('/'):
                        continue
                        
                    file_info = {
                        'key': obj['Key'],
                        'filename': Path(obj['Key']).name,
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'],
                        's3_url': f"s3://{self.bucket_name}/{obj['Key']}"
                    }
                    files.append(file_info)
            
            return sorted(files, key=lambda x: x['last_modified'], reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to list project files: {str(e)}")
            return []
    
    def _generate_s3_key(self, project_name: str, filename: str, subtitle_format: str) -> str:
        """Generate S3 key (path) for subtitle file."""
        # Sanitize project name and filename
        project_name = self._sanitize_name(project_name)
        filename = self._sanitize_name(filename)
        
        return f"{project_name}/{filename}.{subtitle_format}"
    
    def _sanitize_name(self, name: str) -> str:
        """Sanitize name for S3 key."""
        import re
        # Replace spaces and special characters with hyphens
        sanitized = re.sub(r'[^\w\-_.]', '-', name)
        # Remove multiple consecutive hyphens
        sanitized = re.sub(r'-+', '-', sanitized)
        return sanitized.strip('-')
    
    def _get_content_type(self, subtitle_format: str) -> str:
        """Get MIME type for subtitle format."""
        content_types = {
            'srt': 'text/plain',
            'vtt': 'text/vtt',
            'ass': 'text/plain',
            'ssa': 'text/plain',
            'ttml': 'application/ttml+xml',
            'sbv': 'text/plain'
        }
        return content_types.get(subtitle_format.lower(), 'text/plain')
    
    def _get_bucket_region(self) -> Optional[str]:
        """Get bucket region."""
        try:
            response = self.s3_client.get_bucket_location(Bucket=self.bucket_name)
            return response.get('LocationConstraint') or 'us-east-1'
        except Exception:
            return None


def create_s3_storage(config: Dict[str, Any]) -> Optional[S3Storage]:
    """
    Create S3Storage instance from configuration.
    
    Args:
        config: S3 configuration dictionary
    
    Returns:
        S3Storage instance or None if disabled/invalid
    """
    if not config.get('enabled', False):
        return None
    
    try:
        return S3Storage(
            bucket_name=config['bucket_name'],
            region=config.get('region', 'us-east-1'),
            access_key=config.get('access_key'),
            secret_key=config.get('secret_key')
        )
    except Exception as e:
        logger.error(f"Failed to create S3Storage: {str(e)}")
        return None