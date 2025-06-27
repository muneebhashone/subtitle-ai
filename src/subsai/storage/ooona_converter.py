"""
OOONA API integration for subtitle format conversion.
"""
import os
import logging
import json
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, Union
from datetime import datetime, timedelta

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

logger = logging.getLogger(__name__)


class OoonaConverterError(Exception):
    """Custom exception for OOONA converter operations."""
    pass


class OoonaConverter:
    """OOONA API service for subtitle format conversion."""
    
    def __init__(self):
        """
        Initialize OOONA converter service using environment variables.
        
        Environment variables required:
            OOONA_BASE_URL: OOONA API base URL
            OOONA_CLIENT_ID: API client identifier
            OOONA_CLIENT_SECRET: API client secret
        """
        if not REQUESTS_AVAILABLE:
            raise OoonaConverterError("requests is required for OOONA conversion. Install with: pip install requests")
        
        # Get credentials from environment variables
        self.base_url = os.getenv('OOONA_BASE_URL', '').rstrip('/')
        self.client_id = os.getenv('OOONA_CLIENT_ID', '')
        self.client_secret = os.getenv('OOONA_CLIENT_SECRET', '')
        self.api_key = os.getenv('OOONA_API_KEY', '')
        self.api_name = os.getenv('OOONA_API_NAME', '')
        
        # Validate required environment variables
        required_vars = [self.base_url, self.client_id, self.client_secret, self.api_key, self.api_name]
        if not all(required_vars):
            missing = []
            if not self.base_url: missing.append('OOONA_BASE_URL')
            if not self.client_id: missing.append('OOONA_CLIENT_ID')
            if not self.client_secret: missing.append('OOONA_CLIENT_SECRET')
            if not self.api_key: missing.append('OOONA_API_KEY')
            if not self.api_name: missing.append('OOONA_API_NAME')
            raise OoonaConverterError(f"Missing required environment variables: {', '.join(missing)}")
        
        self.access_token = None
        self.token_expires_at = None
    
    def authenticate(self) -> Dict[str, Any]:
        """
        Authenticate with OOONA API and get access token.
        
        Returns:
            Dict containing authentication result
        """
        try:
            # Check if we have a valid token
            if self._is_token_valid():
                return {
                    'success': True,
                    'message': 'Using cached token',
                    'token': self.access_token
                }
            
            # Get new token
            token_url = f"{self.base_url}/token"
            
            # Use JSON payload as per API documentation
            data = {
                'grant_type': 'secret',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'secret': self.api_key,
                'name': self.api_name
            }
            
            response = requests.post(
                token_url,
                data=data,
                timeout=30
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get('access_token')
                expires_in = token_data.get('expires_in', 3600)  # Default 1 hour
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 300)  # 5 min buffer
                
                logger.info("Successfully authenticated with OOONA API")
                return {
                    'success': True,
                    'message': 'Authentication successful',
                    'token': self.access_token,
                    'expires_in': expires_in
                }
            else:
                error_msg = f"Authentication failed: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return {
                    'success': False,
                    'message': error_msg
                }
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error during authentication: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'message': error_msg
            }
        except Exception as e:
            error_msg = f"Unexpected error during authentication: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'message': error_msg
            }
    
    def _is_token_valid(self) -> bool:
        """Check if current token is valid and not expired."""
        return (
            self.access_token is not None and 
            self.token_expires_at is not None and 
            datetime.now() < self.token_expires_at
        )
    
    
    def convert_subtitle(self, subtitle_content: str) -> Dict[str, Any]:
        """
        Convert SRT subtitle content to OOONA format using OOONA API.
        
        Args:
            subtitle_content: The SRT subtitle content to convert
            
        Returns:
            Dict containing conversion result and converted content (JSON response)
        """
        try:
            # Ensure we're authenticated
            auth_result = self.authenticate()
            if not auth_result['success']:
                return auth_result
            
            # Create temporary file for input
            with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as temp_file:
                temp_file.write(subtitle_content)
                temp_file_path = temp_file.name
            
            try:
                # Use fixed conversion endpoint: srt -> ooona
                convert_url = f"{self.base_url}/external/convert/srt/ooona"
                headers = {
                    'Authorization': f'Bearer {self.access_token}'
                }
                
                # Upload file for conversion
                with open(temp_file_path, 'rb') as file:
                    files = {'': file}  # Empty key as per API spec
                    
                    response = requests.post(
                        convert_url,
                        headers=headers,
                        files=files,
                        timeout=60  # Longer timeout for conversion
                    )
                
                if response.status_code == 200:
                    # API returns JSON response, extract content for .ooona file
                    try:
                        json_response = response.json()
                        logger.info("Successfully converted subtitle from SRT to OOONA format")
                        return {
                            'success': True,
                            'message': 'Conversion from SRT to OOONA successful',
                            'content': json.dumps(json_response, indent=2),  # Pretty print JSON for .ooona file
                            'json_data': json_response  # Original JSON data
                        }
                    except json.JSONDecodeError:
                        # Fallback to text response if not JSON
                        converted_content = response.text
                        logger.info("Successfully converted subtitle from SRT to OOONA format (text response)")
                        return {
                            'success': True,
                            'message': 'Conversion from SRT to OOONA successful',
                            'content': converted_content
                        }
                else:
                    error_msg = f"Conversion failed: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    return {
                        'success': False,
                        'message': error_msg
                    }
                    
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
                
        except Exception as e:
            error_msg = f"Error during subtitle conversion: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'message': error_msg
            }
    
    def validate_connection(self) -> Dict[str, Any]:
        """
        Validate connection to OOONA API by testing authentication.
        
        Returns:
            Dict containing validation result
        """
        try:
            auth_result = self.authenticate()
            if auth_result['success']:
                return {
                    'success': True,
                    'message': 'OOONA API connection validated successfully'
                }
            else:
                return auth_result
                
        except Exception as e:
            error_msg = f"Connection validation failed: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'message': error_msg
            }


def create_ooona_converter() -> Optional[OoonaConverter]:
    """
    Factory function to create OOONA converter instance using environment variables.
        
    Returns:
        OoonaConverter instance or None if creation failed
    """
    try:
        return OoonaConverter()
        
    except OoonaConverterError as e:
        logger.error(f"Failed to create OOONA converter: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error creating OOONA converter: {str(e)}")
        return None