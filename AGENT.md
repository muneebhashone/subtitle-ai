# AGENT.md

## Build/Test Commands
```bash
pip install -e .                                                   # Install in dev mode
python -m pytest tests/test_main.py::TestSubsAI::test_transcribe  # Single test  
python -m pytest tests/                                           # All tests
subsai-webui                                                      # Start Streamlit web UI on port 8501
subsai <media_file> --model <model_name> --format <format>       # CLI usage
docker compose up subsai-webui                                    # Run with Docker (GPU)
mkdocs serve                                                      # Serve docs locally
```

## Architecture
- **Main API**: `src/subsai/main.py` - `SubsAI` class (entry point) and `Tools` class for subtitle processing
- **Models**: Inherit from `AbstractModel` in `src/subsai/models/abstract_model.py`, return `pysubs2.SSAFile`
- **Configuration**: `src/subsai/configs.py` - `AVAILABLE_MODELS` registry and config schemas
- **Web UI**: `src/subsai/webui.py` - Streamlit interface with auth/storage/batch processing
- **Authentication**: `src/subsai/auth/` - Role-based access with bcrypt, SQLite sessions
- **Storage**: `src/subsai/storage/` - S3 integration and OOONA API converter
- **Database**: SQLite with Docker volume persistence in `./data/`

## Code Style
- **Imports**: Group stdlib, third-party, local; absolute imports preferred  
- **Types**: Use type hints, models return `pysubs2.SSAFile`
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Error Handling**: Use exceptions, validate inputs, comprehensive logging
- **Structure**: Models inherit from `AbstractModel`, implement `transcribe()` method
