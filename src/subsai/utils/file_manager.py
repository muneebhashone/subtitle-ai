"""
File management utilities for automatic cleanup of temporary media files.
"""

import os
import tempfile
import shutil
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Union, List
import atexit

logger = logging.getLogger(__name__)


class ManagedTempFile:
    """Context manager for temporary media files with automatic cleanup."""
    
    def __init__(self, uploaded_file=None, filename: Optional[str] = None, 
                 suffix: Optional[str] = None, prefix: Optional[str] = None):
        """
        Initialize managed temporary file.
        
        Args:
            uploaded_file: Streamlit uploaded file object
            filename: Optional filename to use
            suffix: File suffix (e.g., '.mp4')
            prefix: File prefix
        """
        self.uploaded_file = uploaded_file
        self.filename = filename
        self.suffix = suffix
        self.prefix = prefix
        self.temp_dir = None
        self.file_path = None
        self._cleanup_registered = False
        
    def __enter__(self):
        """Create temporary file and return path."""
        self.temp_dir = tempfile.TemporaryDirectory()
        
        if self.uploaded_file:
            # Use uploaded file name
            filename = self.uploaded_file.name
            self.file_path = os.path.join(self.temp_dir.name, filename)
            
            # Write uploaded file content
            with open(self.file_path, "wb") as f:
                f.write(self.uploaded_file.getbuffer())
                
        elif self.filename:
            # Use provided filename
            self.file_path = os.path.join(self.temp_dir.name, self.filename)
            
        else:
            # Create named temporary file
            fd, self.file_path = tempfile.mkstemp(
                suffix=self.suffix,
                prefix=self.prefix,
                dir=self.temp_dir.name
            )
            os.close(fd)
        
        # Register cleanup on exit
        if not self._cleanup_registered:
            atexit.register(self._cleanup)
            self._cleanup_registered = True
            
        logger.debug(f"Created temporary file: {self.file_path}")
        return self.file_path
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up temporary file and directory."""
        self._cleanup()
        
    def _cleanup(self):
        """Perform cleanup operations."""
        if self.temp_dir:
            try:
                self.temp_dir.cleanup()
                logger.debug(f"Cleaned up temporary directory: {self.temp_dir.name}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp directory: {e}")
            finally:
                self.temp_dir = None
                self.file_path = None


class BatchFileManager:
    """Manager for batch processing temporary files."""
    
    def __init__(self):
        self.temp_files: List[ManagedTempFile] = []
        self.output_dirs: List[str] = []
        
    def add_temp_file(self, uploaded_file) -> str:
        """Add a temporary file and return its path."""
        managed_file = ManagedTempFile(uploaded_file=uploaded_file)
        file_path = managed_file.__enter__()
        self.temp_files.append(managed_file)
        return file_path
        
    def add_output_dir(self, output_dir: str):
        """Track output directory for cleanup."""
        self.output_dirs.append(output_dir)
        
    def cleanup_all(self):
        """Clean up all managed files and directories."""
        # Clean up temp files
        for managed_file in self.temp_files:
            try:
                managed_file.__exit__(None, None, None)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp file: {e}")
        
        # Clean up output directories
        for output_dir in self.output_dirs:
            try:
                if os.path.exists(output_dir):
                    shutil.rmtree(output_dir)
                    logger.debug(f"Cleaned up output directory: {output_dir}")
            except Exception as e:
                logger.warning(f"Failed to cleanup output directory {output_dir}: {e}")
                
        # Clear tracking lists
        self.temp_files.clear()
        self.output_dirs.clear()
        
    def __del__(self):
        """Ensure cleanup on object destruction."""
        self.cleanup_all()


@contextmanager
def managed_temp_file(uploaded_file=None, filename: Optional[str] = None, 
                     suffix: Optional[str] = None, prefix: Optional[str] = None):
    """Context manager for temporary media files with automatic cleanup."""
    with ManagedTempFile(uploaded_file, filename, suffix, prefix) as file_path:
        yield file_path


def cleanup_batch_output_dir(job_id: str):
    """Clean up batch processing output directory."""
    output_dir = os.path.join(tempfile.gettempdir(), "subsai_batch_output", job_id)
    if os.path.exists(output_dir):
        try:
            shutil.rmtree(output_dir)
            logger.debug(f"Cleaned up batch output directory: {output_dir}")
        except Exception as e:
            logger.warning(f"Failed to cleanup batch output directory {output_dir}: {e}")


def cleanup_old_batch_outputs(max_age_hours: int = 24):
    """Clean up old batch processing outputs."""
    import time
    
    batch_root = os.path.join(tempfile.gettempdir(), "subsai_batch_output")
    if not os.path.exists(batch_root):
        return
        
    current_time = time.time()
    cutoff_time = current_time - (max_age_hours * 3600)
    
    try:
        for job_dir in os.listdir(batch_root):
            job_path = os.path.join(batch_root, job_dir)
            if os.path.isdir(job_path):
                # Check directory modification time
                if os.path.getmtime(job_path) < cutoff_time:
                    shutil.rmtree(job_path)
                    logger.debug(f"Cleaned up old batch output: {job_path}")
    except Exception as e:
        logger.warning(f"Failed to cleanup old batch outputs: {e}")