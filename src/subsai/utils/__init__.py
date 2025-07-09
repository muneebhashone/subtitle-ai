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


def available_translation_models() -> list:
    """
    Returns available translation models
    Features DeepSeek-R1 as the primary translation model with fallback options

    :return: list of available models
    """
    models = [
        "deepseek-r1:1.5b",
    ]
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