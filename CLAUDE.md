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

### Entry Points
- `subsai` command → `subsai.cli:main`
- `subsai-webui` command → `subsai.webui:run`

### Configuration
- Python 3.8+ required (3.10-3.11 recommended)
- GPU support via CUDA/PyTorch for faster transcription
- Model configurations are JSON-based with validation schemas