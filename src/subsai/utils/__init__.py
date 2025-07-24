#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Utility functions
"""

import torch
from pysubs2.formats import FILE_EXTENSION_TO_FORMAT_IDENTIFIER


def _load_config(config_name, model_config, config_schema):
    """
    Helper function to load default values if `config_name` is not specified

    :param config_name: the name of the config
    :param model_config: configuration provided to the model
    :param config_schema: the schema of the configuration

    :return: config value
    """
    if config_name in model_config:
        return model_config[config_name]
    return config_schema[config_name]['default']


def get_available_devices() -> list:
    """
    Get available devices (cpu and gpus)
    Only returns CUDA devices that are actually available

    :return: list of available devices
    """
    devices = ['cpu']
    if torch.cuda.is_available():
        devices.extend([f'cuda:{i}' for i in range(torch.cuda.device_count())])
    return devices


def get_optimal_device() -> str:
    """
    Get the optimal device for processing
    Returns 'cuda:0' if CUDA is available, otherwise 'cpu'

    :return: optimal device string
    """
    if torch.cuda.is_available() and torch.cuda.device_count() > 0:
        return 'cuda:0'
    return 'cpu'


def is_cuda_available() -> bool:
    """
    Check if CUDA is available and accessible

    :return: True if CUDA is available, False otherwise
    """
    return torch.cuda.is_available() and torch.cuda.device_count() > 0


def get_ollama_models() -> list:
    """
    Fetches available models from Ollama service
    
    :return: list of available Ollama model names
    """
    try:
        import ollama
        import os
        
        # Configure Ollama client for Docker environment
        if os.getenv('DOCKER_ENV', 'false').lower() == 'true':
            ollama_host = "http://host.docker.internal:11434"
            client = ollama.Client(host=ollama_host)
        else:
            ollama_host = "http://localhost:11434"
            client = ollama.Client()
        
        # Get list of models
        models_response = client.list()
        model_names = [model['name'] for model in models_response.get('models', [])]
        print(f"Successfully fetched {len(model_names)} models from Ollama at {ollama_host}")
        return model_names
        
    except ImportError as e:
        print(f"Warning: Ollama package not installed: {e}")
        print("Install with: pip install ollama")
        return []
    except ConnectionError as e:
        print(f"Warning: Could not connect to Ollama service: {e}")
        print("Make sure Ollama is running: ollama serve")
        return []
    except Exception as e:
        # If Ollama is not available, return empty list
        print(f"Warning: Could not fetch Ollama models: {e}")
        print("Troubleshooting:")
        print("1. Make sure Ollama is installed: pip install ollama")
        print("2. Make sure Ollama service is running: ollama serve")
        print("3. Test connection: ollama list")
        return []


def available_translation_models() -> list:
    """
    Returns available translation models
    Features DeepSeek-R1 as the primary translation model with dynamically fetched Ollama models
    and API-based DeepSeek models

    :return: list of available models
    """
    # Start with API-based DeepSeek models (always available if API key is provided)
    models = ["api:deepseek-chat", "api:deepseek-reasoner"]
    
    # Add default local Ollama translation models
    models.extend(["deepseek-r1:1.5b", "mistral-nemo:latest", "qwen2.5:7b"])
    
    # Add other available Ollama models
    ollama_models = get_ollama_models()
    for model in ollama_models:
        if model not in models:  # Avoid duplicates
            models.append(model)
    
    return models


def available_subs_formats(include_extensions=True):
    """
    Returns available subtitles formats

    :param include_extensions: whether to include extensions with formats
    :return: list of available formats
    """
    formats = []
    for format_name in FILE_EXTENSION_TO_FORMAT_IDENTIFIER.values():
        if include_extensions:
            extensions = []
            for ext, fmt in FILE_EXTENSION_TO_FORMAT_IDENTIFIER.items():
                if fmt == format_name:
                    extensions.append(ext)
            formats.append((format_name, extensions))
        else:
            formats.append(format_name)
    return formats


# Model Display Name Mapping System
# ================================

# Transcription model display name mappings
TRANSCRIPTION_MODEL_DISPLAY_NAMES = {
    'openai/whisper': 'OAIW - C3PO'
}

# Translation model display name mappings
TRANSLATION_MODEL_DISPLAY_NAMES = {
    'api:deepseek-chat': 'API DSC C3PO',
    'api:deepseek-reasoner': 'API DSR C3PO',
    'deepseek-r1:1.5b': 'LOCAL DSR1 C3PO',
    'mistral-nemo:latest': 'LOCAL MNL C3PO',
    'qwen2.5:7b': 'LOCAL Q27 C3PO'
}

# Reverse mappings for faster lookup
TRANSCRIPTION_DISPLAY_TO_INTERNAL = {v: k for k, v in TRANSCRIPTION_MODEL_DISPLAY_NAMES.items()}
TRANSLATION_DISPLAY_TO_INTERNAL = {v: k for k, v in TRANSLATION_MODEL_DISPLAY_NAMES.items()}


def get_model_display_name(internal_name: str, model_type: str = 'translation') -> str:
    """
    Convert internal model name to user-friendly display name.
    
    :param internal_name: Internal model name (e.g., 'api:deepseek-chat')
    :param model_type: Type of model ('transcription' or 'translation')
    :return: Display name (e.g., 'API DSC C3PO') or original name if no mapping
    """
    if model_type == 'transcription':
        return TRANSCRIPTION_MODEL_DISPLAY_NAMES.get(internal_name, internal_name)
    elif model_type == 'translation':
        return TRANSLATION_MODEL_DISPLAY_NAMES.get(internal_name, internal_name)
    else:
        return internal_name


def get_model_internal_name(display_name: str, model_type: str = 'translation') -> str:
    """
    Convert display name to internal model name.
    
    :param display_name: User-friendly display name (e.g., 'API DSC C3PO')
    :param model_type: Type of model ('transcription' or 'translation')
    :return: Internal name (e.g., 'api:deepseek-chat') or original name if no mapping
    """
    if model_type == 'transcription':
        return TRANSCRIPTION_DISPLAY_TO_INTERNAL.get(display_name, display_name)
    elif model_type == 'translation':
        return TRANSLATION_DISPLAY_TO_INTERNAL.get(display_name, display_name)
    else:
        return display_name


def get_model_options_for_display(internal_models: list, model_type: str = 'translation') -> tuple:
    """
    Convert list of internal model names to display names for UI selectboxes.
    
    :param internal_models: List of internal model names
    :param model_type: Type of model ('transcription' or 'translation')
    :return: Tuple of (display_options, internal_options) for selectbox handling
    """
    display_options = []
    internal_options = []
    
    for internal_name in internal_models:
        display_name = get_model_display_name(internal_name, model_type)
        display_options.append(display_name)
        internal_options.append(internal_name)
    
    return display_options, internal_options


def get_model_display_index(selected_internal: str, internal_models: list, model_type: str = 'translation') -> int:
    """
    Get the index of a model in the display list based on its internal name.
    
    :param selected_internal: Internal name of the selected model
    :param internal_models: List of internal model names
    :param model_type: Type of model ('transcription' or 'translation')
    :return: Index in the list, or 0 if not found
    """
    try:
        return internal_models.index(selected_internal)
    except ValueError:
        return 0