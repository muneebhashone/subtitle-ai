#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Hugging Face Model

See [automatic-speech-recognition](https://huggingface.co/tasks/automatic-speech-recognition)
"""

import os
import tempfile
import ffmpeg
import pysubs2
from pysubs2 import SSAFile, SSAEvent
from subsai.models.abstract_model import AbstractModel
from subsai.utils import _load_config, get_available_devices

from transformers import pipeline

TMPDIR = tempfile.gettempdir()

def convert_video_to_audio_ffmpeg(video_file, output_ext="wav"):
    """Convert video file to audio for HuggingFace models"""
    path, filename = os.path.split(video_file)
    filename_no_ext = os.path.splitext(filename)[0]
    output_file = os.path.join(TMPDIR, f"{filename_no_ext}.{output_ext}")
    
    # Skip conversion if audio file already exists
    if os.path.exists(output_file):
        return output_file
    
    print(f'Converting {video_file} to audio: {output_file}')
    try:
        (
            ffmpeg
            .input(video_file)
            .output(output_file, acodec='pcm_s16le', ac=1, ar='16000')  # 16kHz mono for ASR
            .overwrite_output()
            .run(quiet=True, capture_stdout=True)
        )
        return output_file
    except ffmpeg.Error as e:
        print(f"FFmpeg error: {e}")
        # If conversion fails, try with original file (might be audio already)
        return video_file

def is_video_file(file_path):
    """Check if file is a video file based on extension"""
    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v'}
    return os.path.splitext(file_path.lower())[1] in video_extensions


devices = get_available_devices()

class HuggingFaceModel(AbstractModel):
    model_name = 'HuggingFaceModel'
    config_schema = {
        # load model config
        'model_id': {
            'type': str,
            'description': 'The model id from the Hugging Face Hub.',
            'options': None,
            'default': 'openai/whisper-tiny'
        },
        'device': {
            'type': list,
            'description': 'Pytorch device',
            'options': devices,
            'default': devices[0]
        },
        'segment_type': {
            'type': list,
            'description': "Sentence-level or word-level timestamps",
            'options': ['sentence', 'word'],
            'default': 'sentence'
        },
        'chunk_length_s': {
            'type': float,
            'description': '(`float`, *optional*, defaults to 0):'
                           'The input length for in each chunk. If `chunk_length_s = 0` then chunking is disabled (default).',
            'options': None,
            'default': 30
        },
        'language': {
            'type': str,
            'description': 'Language to force for transcription (e.g., "hebrew", "he"). '
                           'Leave empty for automatic detection. Required for Hebrew-specific models.',
            'options': None,
            'default': None
        },
        'task': {
            'type': list,
            'description': 'Task to perform: transcribe or translate',
            'options': ['transcribe', 'translate'],
            'default': 'transcribe'
        }
    }

    def __init__(self, model_config):
        super(HuggingFaceModel, self).__init__(model_config=model_config,
                                               model_name=self.model_name)
        # config
        self._model_id = _load_config('model_id', model_config, self.config_schema)
        self._device = _load_config('device', model_config, self.config_schema)
        self.segment_type = _load_config('segment_type', model_config, self.config_schema)
        self._chunk_length_s = _load_config('chunk_length_s', model_config, self.config_schema)
        self._language = _load_config('language', model_config, self.config_schema)
        self._task = _load_config('task', model_config, self.config_schema)

        # Auto-detect Hebrew models and set default language
        if 'hebrew' in self._model_id.lower() or 'ivrit' in self._model_id.lower() or 'he' in self._model_id.lower():
            if self._language is None:
                self._language = 'hebrew'

        self.model = pipeline(
            "automatic-speech-recognition",
            model=self._model_id,
            device=self._device,
        )

    def transcribe(self, media_file):
        # Convert video to audio if needed
        if is_video_file(media_file):
            audio_file = convert_video_to_audio_ffmpeg(media_file)
        else:
            audio_file = media_file
        
        # Prepare generation kwargs for language and task settings
        generate_kwargs = {}
        if self._language:
            generate_kwargs['language'] = self._language
        if self._task:
            generate_kwargs['task'] = self._task

        results = self.model(
            audio_file,
            chunk_length_s=self._chunk_length_s,
            return_timestamps=True if self.segment_type == 'sentence' else 'word',
            generate_kwargs=generate_kwargs if generate_kwargs else None,
        )
        subs = SSAFile()
        for chunk in results['chunks']:
            event = SSAEvent(start=pysubs2.make_time(s=chunk['timestamp'][0]),
                             end=pysubs2.make_time(s=chunk['timestamp'][1]))
            event.plaintext = chunk['text']
            subs.append(event)
        return subs
