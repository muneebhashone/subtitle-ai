# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development Commands
- **Install dependencies**: `pip install -r requirements.txt`
- **Run Web UI**: `subsai-webui` (starts Streamlit web interface)
- **Run CLI**: `subsai <media_file> --model <model_name> --format <format>`
- **Run tests**: `python -m pytest tests/` or `python -m unittest tests.test_main`
- **Docker build**: `docker compose build`
- **Docker run**: `docker compose run -p 8501:8501 -v /path/to/media:/media_files subsai-webui`

### Testing
- Test files are located in `tests/` directory
- Main test file: `tests/test_main.py`
- Tests cover model creation, transcription, and tools functionality
- Use `python -m pytest` or `python -m unittest` to run tests

## Architecture

### Core Structure
- **Main API**: `src/subsai/main.py` contains the `SubsAI` class (main entry point) and `Tools` class for subtitle processing
- **Models**: All transcription models inherit from `AbstractModel` in `src/subsai/models/abstract_model.py`
- **Configuration**: `src/subsai/configs.py` defines `AVAILABLE_MODELS` registry and configuration schemas
- **CLI Interface**: `src/subsai/cli.py` provides command-line interface
- **Web Interface**: `src/subsai/webui.py` provides Streamlit-based web UI

### Model System
The project uses a plugin-like architecture for different Whisper implementations:
- Models are registered in `AVAILABLE_MODELS` dict in `configs.py`
- Each model class implements the `AbstractModel.transcribe()` method
- Supported models: OpenAI Whisper, Faster-Whisper, WhisperX, Whisper.cpp, Stable-ts, HuggingFace Transformers, OpenAI API
- Models return `pysubs2.SSAFile` objects containing subtitle data

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
- `pysubs2`: Subtitle file handling and manipulation
- `ffmpeg-python`: Video/audio processing
- `streamlit`: Web UI framework
- Various Whisper implementations as separate models
- `dl_translate`: Translation functionality
- `ffsubsync`: Subtitle synchronization
- `boto3`: AWS S3 integration for cloud storage (v1.38.39+)

### Entry Points
- `subsai` command → `subsai.cli:main`
- `subsai-webui` command → `subsai.webui:run`

### Configuration
- Python 3.9+ required (3.10-3.11 recommended) - Python 3.8 support ended April 2025
- GPU support via CUDA/PyTorch for faster transcription
- Model configurations are JSON-based with validation schemas

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