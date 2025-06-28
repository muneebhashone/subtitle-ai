# 🔄 Batch Processing Documentation

## Overview

The Batch Processing feature allows users to upload multiple media files simultaneously and configure each file independently for transcription and translation. This powerful feature supports large files (up to 10GB) and provides real-time progress tracking with an intuitive web interface.

## ✨ Key Features

### 🚀 **Enhanced Upload Capabilities**
- **Large File Support**: Upload files up to 10GB each
- **Multiple Formats**: Support for MP4, AVI, MKV, MOV, FLV, WebM, WAV, MP3, M4A, FLAC, AAC, OGG
- **No Size Limits**: Removed default Streamlit upload restrictions
- **Bulk Upload**: Select multiple files at once with drag-and-drop interface

### ⚙️ **Flexible Configuration**
- **Per-File Settings**: Configure each file independently
- **Bulk Configuration**: Apply same settings to all files
- **Language Options**: 
  - Source Language: Auto-detect or choose from 20+ languages
  - Target Languages: Multiple target languages per file (transcribe, translate to English, Spanish, French, etc.)
- **Output Formats**: SRT, VTT, ASS, SUB
- **Export Options**: Local save, S3 upload, OOONA conversion

### 📊 **Real-Time Progress Tracking**
- **Live Dashboard**: Real-time updates of batch processing status
- **Individual Job Tracking**: Monitor each file's progress independently
- **Detailed Status**: View current task, progress percentage, and timing information
- **Error Handling**: Clear error messages and recovery options

### 🎛️ **Advanced Controls**
- **Pause/Resume**: Pause processing and resume later
- **Job Cancellation**: Cancel individual pending jobs
- **Progress Visualization**: Interactive progress bars and status indicators
- **Results Management**: Download generated files directly from the interface

## 🏗️ Architecture

### Backend Components

#### **BatchProcessor Class**
```python
class BatchProcessor:
    - add_job(): Add files to processing queue
    - start_processing(): Begin batch processing
    - get_progress(): Get overall progress statistics
    - get_job_details(): Get detailed information about specific jobs
    - cancel_job(): Cancel pending jobs
    - clear_completed(): Remove completed jobs from tracking
```

#### **JobConfig Dataclass**
```python
@dataclass
class JobConfig:
    file_id: str                    # Unique job identifier
    file_path: str                  # Path to media file
    file_name: str                  # Original filename
    file_size: int                  # File size in bytes
    source_language: str            # Source language (auto, en, es, etc.)
    target_languages: List[str]     # Target languages for output
    output_formats: List[str]       # Desired output formats
    status: JobStatus               # Current job status
    progress: float                 # Progress (0.0 to 1.0)
    current_task: str               # Current processing task
    results: List[Dict]             # Generated files information
```

#### **ProgressTracker Class**
```python
class ProgressTracker:
    - add_job(): Track new job
    - update_job_progress(): Update job progress and status
    - get_overall_progress(): Calculate overall batch statistics
    - get_all_jobs(): Get all jobs sorted by creation time
```

### Frontend Components

#### **Batch Processing UI**
- **File Upload Interface**: Multi-file drag-and-drop with format validation
- **Configuration Matrix**: Bulk and per-file configuration options
- **Control Panel**: Start, pause, and cancel operations

#### **Progress Dashboard**
- **Overall Metrics**: Completion percentage, job counts, timing
- **Individual Job Details**: Expandable sections for each file
- **Live Updates**: Auto-refresh during processing
- **Download Interface**: Direct download buttons for generated files

## 🔧 Configuration

### Streamlit Configuration
The system automatically configures Streamlit for large file uploads:

```toml
# .streamlit/config.toml
[server]
maxUploadSize = 10000        # 10GB upload limit
maxMessageSize = 10000       # 10GB message size limit
enableXsrfProtection = false # Disabled for large uploads
```

### Environment Variables
Configure cloud storage and API integrations:

```bash
# S3 Storage (Optional)
AWS_ACCESS_KEY=your_access_key
AWS_SECRET_KEY=your_secret_key
AWS_BUCKET_NAME=your_bucket_name
AWS_REGION=your_region

# OOONA API (Optional)
OOONA_BASE_URL=your_api_url
OOONA_CLIENT_ID=your_client_id
OOONA_CLIENT_SECRET=your_client_secret
OOONA_API_KEY=your_api_key
OOONA_API_NAME=your_api_name
```

## 🎯 Usage Guide

### 1. **Access Batch Processing**
- Start the web interface: `subsai-webui`
- Navigate to the **"Batch Processing"** tab
- The interface will display upload options and any existing jobs

### 2. **Upload Multiple Files**
- Click "Choose media files" or drag files into the upload area
- Select multiple files (up to 10GB each)
- Supported formats: MP4, AVI, MKV, MOV, FLV, WebM, WAV, MP3, M4A, FLAC, AAC, OGG

### 3. **Configure Processing Options**

#### **Bulk Configuration** (Recommended for similar files)
- Set default source language (auto-detect recommended)
- Choose target languages (multiple selections allowed)
- Select output formats (SRT, VTT, ASS, SUB)
- Enable "Use bulk configuration for all files"

#### **Individual Configuration** (For diverse files)
- Disable bulk configuration
- Configure each file independently in expandable sections
- Set specific languages and formats per file

### 4. **Start Processing**
- Click "🚀 Start Batch Processing"
- Monitor progress in the live dashboard
- View detailed status for each file
- Use controls to pause or cancel as needed

### 5. **Download Results**
- Generated files appear in the dashboard as jobs complete
- Click download buttons for individual files
- Files are organized by original filename and target language

## 📈 Progress Monitoring

### Overall Dashboard
- **Progress Bar**: Visual representation of batch completion
- **Job Counters**: Completed, processing, pending, and failed counts
- **Current Activity**: Information about the currently processing file

### Individual Job Status
- **Status Icons**: Visual indicators for each job state
  - ⏳ Pending
  - 🔄 Processing  
  - ✅ Completed
  - ❌ Failed
  - 🚫 Cancelled

- **Detailed Information**:
  - Progress percentage with visual bar
  - Current processing task
  - File size and configuration
  - Start time and duration
  - Error messages (if applicable)

### Job States
1. **Pending**: Job queued, waiting to start
2. **Processing**: Currently being transcribed/translated
3. **Completed**: Successfully finished with downloadable results
4. **Failed**: Error occurred, with detailed error message
5. **Cancelled**: User cancelled before processing started

## 🔧 Advanced Features

### **Multi-Language Output**
- Process one source file into multiple target languages
- Automatic filename generation with language suffixes
- Example: `video.mp4` → `video-en.srt`, `video-es.srt`, `video-fr.srt`

### **Format Flexibility**
- Generate multiple output formats per file
- Support for standard subtitle formats and OOONA proprietary format
- Smart filename handling for different format combinations

### **Cloud Integration**
- **S3 Storage**: Automatically upload results to Amazon S3
- **OOONA API**: Convert to proprietary format via API
- **Local Storage**: Save files to local directories

### **Resource Management**
- **Queue-based Processing**: Files processed sequentially to manage resources
- **Progress Persistence**: Job status maintained during browser refresh
- **Error Recovery**: Failed jobs can be manually retried

## 🎛️ Control Features

### **Processing Controls**
- **Start**: Begin processing queued jobs
- **Pause**: Stop after current job completes
- **Cancel Individual Jobs**: Remove specific pending jobs
- **Clear Completed**: Remove finished jobs from view

### **Real-Time Updates**
- **Auto-refresh**: Dashboard updates every 2 seconds during processing
- **Live Progress**: Real-time progress bars and status updates
- **Instant Feedback**: Immediate response to user actions

## 🐛 Troubleshooting

### **Common Issues**

#### **Upload Failures**
- **Solution**: Check file size (max 10GB) and format support
- **Files not appearing**: Refresh browser and try again
- **Large file timeout**: Upload may take time, be patient

#### **Processing Errors**
- **Model initialization failed**: Check system resources and dependencies
- **Translation errors**: Verify network connection for DeepSeek v3 API
- **File format issues**: Ensure audio/video files are not corrupted

#### **Performance Issues**
- **Slow processing**: Large files take longer, consider smaller batches
- **Memory usage**: Close other applications during processing
- **Network timeouts**: For cloud uploads, check internet connection

### **Error Recovery**
1. **Review error messages** in job details
2. **Cancel failed jobs** and retry with different settings
3. **Check logs** in terminal for detailed error information
4. **Restart application** if persistent issues occur

## 📋 Best Practices

### **File Organization**
- **Consistent naming**: Use clear, descriptive filenames
- **Group similar files**: Process files with similar characteristics together
- **Check file integrity**: Ensure media files are not corrupted before upload

### **Configuration Tips**
- **Use auto-detect** for source language when uncertain
- **Start with smaller batches** to test configuration
- **Monitor progress** during first few jobs to catch issues early
- **Save successful configurations** for future use

### **Performance Optimization**
- **Process in smaller batches** (5-10 files) for better monitoring
- **Use SRT format** for fastest processing
- **Close unnecessary applications** to free up system resources
- **Ensure stable internet** for cloud features

## 🔮 Future Enhancements

- **Resume interrupted batches** after application restart
- **Parallel processing** for independent tasks
- **Batch configuration templates** for common use cases
- **Email notifications** for batch completion
- **Advanced scheduling** with time-based processing
- **Cloud-native processing** with distributed computing

---

This batch processing system transforms SubsAI into a powerful production tool capable of handling enterprise-scale subtitle generation workflows while maintaining an intuitive user experience.
