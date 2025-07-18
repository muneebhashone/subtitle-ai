#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Whisper Model

See [openai/whisper](https://github.com/openai/whisper)
"""

from typing import Tuple
import pysubs2
from subsai.models.abstract_model import AbstractModel
import whisper
from subsai.utils import _load_config, get_available_devices


class WhisperModel(AbstractModel):
    model_name = 'openai/whisper'
    config_schema = {
        'model_type': {
            'type': list,
            'description': 'Whisper model size to use',
            'options': ['tiny', 'tiny.en', 'base', 'base.en', 'small', 'small.en', 'medium', 'medium.en', 'large', 'large-v2', 'large-v3', 'turbo'],
            'default': 'base'
        },
        'source_language': {
            'type': list,
            'description': 'Source language of the audio (auto-detect if not specified)',
            'options': ['auto', 'en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh', 'ar', 'hi', 'tr', 'pl', 'nl', 'sv', 'da', 'no', 'fi'],
            'default': 'auto'
        },
        'target_language': {
            'type': list,
            'description': 'Target language for transcription/translation',
            'options': ['transcribe', 'en'],
            'default': 'transcribe'
        }
    }

    def __init__(self, model_config):
        super(WhisperModel, self).__init__(model_config=model_config,
                                           model_name=self.model_name)
        # Load configuration
        self.model_type = _load_config('model_type', model_config, self.config_schema)
        self.source_language = _load_config('source_language', model_config, self.config_schema)
        self.target_language = _load_config('target_language', model_config, self.config_schema)
        
        # Auto-detect device
        self.device = None
        
        # Load the model with specified model type
        self.model = whisper.load_model(name=self.model_type, device=self.device)

    def transcribe(self, media_file) -> str:
        audio = whisper.load_audio(media_file)
        
        # Set language and task based on simplified config
        language = None if self.source_language == 'auto' else self.source_language
        task = 'translate' if self.target_language == 'en' else 'transcribe'
        
        # Use optimal default settings for transcription
        result = self.model.transcribe(
            audio,
            language=language,
            task=task,
            verbose=False,
            temperature=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
            compression_ratio_threshold=2.4,
            logprob_threshold=-1.0,
            no_speech_threshold=0.6,
            condition_on_previous_text=True
        )
        
        subs = pysubs2.load_from_whisper(result)
        return subs

