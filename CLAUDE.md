# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development Commands
- **Install dependencies**: `pip install -r requirements.txt`
- **Install editable package**: `pip install -e .` (for development)
- **Run Web UI**: `subsai-webui` (starts Streamlit web interface on port 8501)
- **Run CLI**: `subsai <media_file> --model <model_name> --format <format>`
- **Build package**: `python -m build` (requires `build` package)
- **Run tests**: `python -m pytest tests/` or `python -m unittest tests.test_main`
- **Run specific test**: `python -m unittest tests.test_main.TestSubsAI.test_transcribe`
- **Test Hebrew models**: `python -m pytest tests/test_hebrew_models.py`

### Docker Commands
- **Build services**: `docker compose build`
- **Run GPU service**: `docker compose up subsai-webui` (requires NVIDIA GPU)
- **Run CPU service**: `docker compose up subsai-webui-cpu`
- **Run with volume**: `docker compose run -p 8501:8501 -v /path/to/media:/media_files subsai-webui`
- **Development with persistence**: `docker compose up -d` (SQLite data persists in `./data/`)

### Documentation
- **Build docs**: `mkdocs build` (requires mkdocs-material, mkdocstrings)
- **Serve docs locally**: `mkdocs serve`
- **Deploy docs**: `mkdocs gh-deploy` (auto-deployed on main branch push)

### Testing
- **Main tests**: `tests/test_main.py` - Core functionality, model creation, transcription pipeline
- **Hebrew models**: `tests/test_hebrew_models.py` - Specialized language model testing
- **Test framework**: Compatible with both unittest and pytest
- **Test coverage**: Model instantiation, transcription validation, configuration schemas

## Architecture

### Core Structure
- **Main API**: `src/subsai/main.py` contains the `SubsAI` class (main entry point) and `Tools` class for subtitle processing
- **Models**: All transcription models inherit from `AbstractModel` in `src/subsai/models/abstract_model.py`
- **Configuration**: `src/subsai/configs.py` defines `AVAILABLE_MODELS` registry and configuration schemas
- **CLI Interface**: `src/subsai/cli.py` provides command-line interface
- **Web Interface**: `src/subsai/webui.py` provides Streamlit-based web UI
- **Batch Processing**: `src/subsai/batch_processor.py` handles multi-file processing with progress tracking
- **Authentication**: `src/subsai/auth/` directory contains user management and session handling
- **Storage Integration**: `src/subsai/storage/` for S3 and OOONA API integrations

### Model System
The project uses a plugin-like architecture for different Whisper implementations:
- Models are registered in `AVAILABLE_MODELS` dict in `configs.py`
- Each model class implements the `AbstractModel.transcribe()` method
- Supported models: OpenAI Whisper, Faster-Whisper, WhisperX, Whisper.cpp, Stable-ts, HuggingFace Transformers, OpenAI API
- Models return `pysubs2.SSAFile` objects containing subtitle data

### Advanced Features Architecture
- **Batch Processing**: Multi-file upload (up to 10GB each), independent configuration per file, real-time progress tracking with pause/resume capabilities
- **Authentication System**: Role-based access (user/admin), bcrypt password hashing, SQLite session management with decorator-based route protection
- **Cloud Storage**: S3 integration via boto3 with project-based organization, OOONA API converter for proprietary format conversion
- **Data Persistence**: SQLite database with Docker volume mounting for production deployment data persistence

#### Hebrew Speech Recognition Models
The project includes specialized Hebrew models for improved accuracy:
- **ivrit-ai/whisper-large-v2-tuned**: Hebrew fine-tuned Whisper Large v2 with crowd-sourced training
- **ivrit-ai/whisper-large-v3**: Latest Hebrew fine-tuned Whisper Large v3 model
- **Shiry/whisper-large-v2-he**: Hebrew Whisper model fine-tuned on Google Fleurs dataset
- **imvladikon/wav2vec2-large-xlsr-53-hebrew**: Alternative Wav2Vec2 architecture for Hebrew
- **sivan22/faster-whisper-ivrit-ai-whisper-large-v2-tuned**: Optimized Faster-Whisper Hebrew model

#### Hebrew Model Usage Examples
```bash
# CLI usage with Hebrew models
subsai hebrew_audio.mp3 --model "ivrit-ai/whisper-large-v2-tuned" --format srt

# For faster inference with Hebrew accuracy
subsai hebrew_audio.mp3 --model "sivan22/faster-whisper-ivrit-ai-whisper-large-v2-tuned" --format srt

# Alternative architecture for Hebrew
subsai hebrew_audio.mp3 --model "imvladikon/wav2vec2-large-xlsr-53-hebrew" --format srt
```

#### Hebrew Model Testing
- Hebrew model tests: `tests/test_hebrew_models.py`
- Run Hebrew model tests: `python -m pytest tests/test_hebrew_models.py`
- Hebrew model benchmarking available for performance comparison

### Tools System
The `Tools` class provides subtitle post-processing:
- **Translation**: Using `dl-translate` with various models (M2M100, mBART, NLLB)
- **Auto-sync**: Using `ffsubsync` to align subtitles with video
- **Video merging**: Using `ffmpeg` to embed subtitles into video files

### Key Dependencies
- **Core AI/ML**: `openai-whisper==20240930`, `torch==2.2.0`, `transformers==4.48.1`, `faster_whisper`, `stable-ts==2.18.2`
- **Web Interface**: `streamlit~=1.20.0`, `streamlit_player~=0.1.5`
- **Subtitle Processing**: `pysubs2~=1.6.0`, `ffsubsync~=0.4.24`
- **Translation**: `dl_translate==0.3.0`, `ollama` (DeepSeek-R1 integration)
- **Cloud Services**: `boto3==1.38.39` (AWS S3), `openai==1.60.1` (OpenAI API)
- **Authentication**: `bcrypt==4.1.2` for password hashing
- **System**: FFmpeg required for audio/video processing

### Entry Points & Package Configuration
- **CLI Command**: `subsai` → `subsai.cli:main`
- **Web UI Command**: `subsai-webui` → `subsai.webui:run`
- **Package Structure**: setuptools with setuptools-scm, dynamic dependencies from requirements.txt
- **Python Support**: 3.8+ (3.10-3.11 recommended for best compatibility)
- **GPU Requirements**: CUDA/PyTorch for acceleration, <8GB GPU memory for large-v2 with beam_size=5

## S3 Storage Integration

### S3 Storage Service
- **Location**: `src/subsai/storage/s3_storage.py`
- **Purpose**: Upload subtitles to Amazon S3 buckets for cloud storage
- **Features**:
  - Connection validation and error handling
  - Project-based folder organization
  - Metadata support for uploaded files
  - Support for all subtitle formats (SRT, VTT, ASS, etc.)

### S3 Configuration
- **Location**: `src/subsai/configs.py` - `S3_CONFIG_SCHEMA` and `DEFAULT_S3_CONFIG`
- **Settings**: Bucket name, AWS region, credentials, default project folder
- **UI Integration**: Sidebar configuration panel in web UI

### S3 Web UI Features
- **Configuration Panel**: 
  - Enable/disable S3 storage toggle
  - Bucket name and region selection
  - AWS credentials input (optional if using IAM roles)
  - Connection test functionality
- **Export Options**:
  - Save locally, to S3, or both
  - Project name input (auto-prefilled with media filename)
  - S3 path preview before upload
  - Upload progress indicators and status messages

### S3 File Structure
```
s3://your-bucket/
├── project-name-1/
│   ├── video1.srt
│   ├── video1.vtt
│   └── video1-translated-es.srt
└── project-name-2/
    └── video2.srt
```

### S3 Requirements
- AWS S3 bucket with appropriate permissions
- AWS credentials (Access Key/Secret Key) or IAM role
- Internet connectivity for uploads
- boto3==1.38.39+ (latest as of June 2025)

## OOONA API Integration

### OOONA Converter Service
- **Location**: `src/subsai/storage/ooona_converter.py`
- **Purpose**: Convert subtitle formats to OOONA proprietary format via API
- **Features**:
  - Bearer token authentication with automatic refresh
  - Format template management and validation
  - SRT to .ooona conversion workflow
  - Comprehensive error handling and logging

### OOONA Configuration
- **Location**: `src/subsai/configs.py` - `OOONA_CONFIG_SCHEMA` and `DEFAULT_OOONA_CONFIG`
- **Settings**: API base URL, client credentials, optional template IDs
- **UI Integration**: Sidebar configuration panel in web UI

### OOONA Web UI Features
- **Configuration Panel**:
  - Enable/disable OOONA format toggle
  - API base URL, client ID, and client secret inputs
  - Advanced template ID settings (optional)
  - Connection test functionality with format validation
- **Export Options**:
  - .ooona format automatically available when enabled
  - Smart validation and error handling
  - Full integration with download, local save, and S3 workflows

### OOONA Conversion Workflow
1. **Setup**: Configure OOONA API credentials in sidebar panel
2. **Test**: Use "Test OOONA Connection" to validate API access
3. **Export**: Select .ooona format for automatic API conversion
4. **Process**: SRT → OOONA API → .ooona file output
5. **Output**: Download, save locally, or upload to S3

### OOONA Requirements
- Valid OOONA API credentials (base URL, client ID, client secret)
- Internet connectivity for API calls
- requests library for HTTP client functionality
- Compatible with all existing export options (download, local, S3)

## Development Workflow

### Docker Development
- **Base Image**: `pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime`
- **GPU Service**: `subsai-webui` with NVIDIA device reservations
- **CPU Service**: `subsai-webui-cpu` for environments without GPU
- **Data Persistence**: SQLite database persists in `./data/` via volume mount
- **Port Configuration**: 8501 (GPU), 8502 (CPU)

### CI/CD Pipeline
- **Documentation**: MkDocs Material theme with auto-deployment to GitHub Pages
- **Docker Images**: Multi-registry push (GitHub Container Registry + Docker Hub)
- **Python Dependencies**: mkdocs-material, mkdocstrings[python], black for code formatting

### Configuration Files
- **Streamlit**: `.streamlit/config.toml` - 10GB upload limits, XSRF protection disabled
- **Environment**: `.env.sample` provides template for OOONA API, AWS S3, deployment settings
- **Build**: `pyproject.toml` with setuptools backend, dynamic dependencies from requirements.txt