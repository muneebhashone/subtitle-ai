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
    
    def __init__(self, base_url: str, client_id: str, client_secret: str):
        """
        Initialize OOONA converter service.
        
        Args:
            base_url: OOONA API base URL
            client_id: API client identifier
            client_secret: API client secret
        """
        if not REQUESTS_AVAILABLE:
            raise OoonaConverterError("requests is required for OOONA conversion. Install with: pip install requests")
        
        self.base_url = base_url.rstrip('/')
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.token_expires_at = None
        
        # Common format template IDs (these would need to be configured or retrieved)
        self.format_templates = {
            'srt': None,  # Will be retrieved from API or configured
            'vtt': None,
            'ooona': None,
            'ass': None,
            'ttml': None
        }
    
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
            
            data = {
                'grant_type': 'client_credentials',
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
            
            response = requests.post(
                token_url,
                data=data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
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
    
    def get_format_templates(self) -> Dict[str, Any]:
        """
        Get available format templates from OOONA API.
        
        Returns:
            Dict containing available formats and their template IDs
        """
        try:
            # Ensure we're authenticated
            auth_result = self.authenticate()
            if not auth_result['success']:
                return auth_result
            
            formats_url = f"{self.base_url}/external/formats"
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(formats_url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                formats_data = response.json()
                
                # Extract format information
                formats_info = {}
                for format_item in formats_data:
                    key = format_item.get('key', '').lower()
                    name = format_item.get('name', '')
                    extensions = format_item.get('extensions', [])
                    
                    formats_info[key] = {
                        'name': name,
                        'extensions': extensions,
                        'key': format_item.get('key')
                    }
                
                logger.info(f"Retrieved {len(formats_info)} format templates")
                return {
                    'success': True,
                    'message': 'Format templates retrieved successfully',
                    'formats': formats_info
                }
            else:
                error_msg = f"Failed to get format templates: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return {
                    'success': False,
                    'message': error_msg
                }
                
        except Exception as e:
            error_msg = f"Error retrieving format templates: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'message': error_msg
            }
    
    def convert_subtitle(self, subtitle_content: str, input_format: str, 
                        output_format: str = 'ooona', 
                        input_config_id: Optional[str] = None,
                        output_config_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Convert subtitle content from one format to another using OOONA API.
        
        Args:
            subtitle_content: The subtitle content to convert
            input_format: Input format (e.g., 'srt', 'vtt')
            output_format: Output format (default: 'ooona')
            input_config_id: Optional input template ID
            output_config_id: Optional output template ID
            
        Returns:
            Dict containing conversion result and converted content
        """
        try:
            # Ensure we're authenticated
            auth_result = self.authenticate()
            if not auth_result['success']:
                return auth_result
            
            # Get format templates if config IDs not provided
            if not input_config_id or not output_config_id:
                templates_result = self.get_format_templates()
                if not templates_result['success']:
                    return templates_result
                
                formats = templates_result['formats']
                
                # Map format names to config IDs
                if not input_config_id:
                    input_format_info = formats.get(input_format.lower())
                    if not input_format_info:
                        return {
                            'success': False,
                            'message': f'Input format "{input_format}" not supported'
                        }
                    input_config_id = input_format_info['key']
                
                if not output_config_id:
                    output_format_info = formats.get(output_format.lower())
                    if not output_format_info:
                        return {
                            'success': False,
                            'message': f'Output format "{output_format}" not supported'
                        }
                    output_config_id = output_format_info['key']
            
            # Create temporary file for input
            with tempfile.NamedTemporaryFile(mode='w', suffix=f'.{input_format}', delete=False) as temp_file:
                temp_file.write(subtitle_content)
                temp_file_path = temp_file.name
            
            try:
                # Prepare conversion request
                convert_url = f"{self.base_url}/external/convert/{input_config_id}/{output_config_id}"
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
                    converted_content = response.text
                    logger.info(f"Successfully converted subtitle from {input_format} to {output_format}")
                    return {
                        'success': True,
                        'message': f'Conversion from {input_format} to {output_format} successful',
                        'content': converted_content,
                        'input_format': input_format,
                        'output_format': output_format
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
        Validate connection to OOONA API.
        
        Returns:
            Dict containing validation result
        """
        try:
            auth_result = self.authenticate()
            if auth_result['success']:
                # Test format retrieval to validate full connection
                formats_result = self.get_format_templates()
                if formats_result['success']:
                    return {
                        'success': True,
                        'message': 'OOONA API connection validated successfully'
                    }
                else:
                    return {
                        'success': False,
                        'message': f'Authentication successful but API access failed: {formats_result["message"]}'
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


def create_ooona_converter(config: Dict[str, Any]) -> Optional[OoonaConverter]:
    """
    Factory function to create OOONA converter instance.
    
    Args:
        config: Configuration dictionary with base_url, client_id, client_secret
        
    Returns:
        OoonaConverter instance or None if creation failed
    """
    try:
        required_fields = ['base_url', 'client_id', 'client_secret']
        for field in required_fields:
            if not config.get(field):
                logger.error(f"Missing required OOONA config field: {field}")
                return None
        
        return OoonaConverter(
            base_url=config['base_url'],
            client_id=config['client_id'],
            client_secret=config['client_secret']
        )
        
    except Exception as e:
        logger.error(f"Failed to create OOONA converter: {str(e)}")
        return None