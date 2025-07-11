#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Configurations file
"""

from ffsubsync.constants import DEFAULT_MAX_SUBTITLE_SECONDS, DEFAULT_START_SECONDS, DEFAULT_MAX_OFFSET_SECONDS, \
    DEFAULT_APPLY_OFFSET_SECONDS, DEFAULT_FRAME_RATE, DEFAULT_VAD

from subsai.models.faster_whisper_model import FasterWhisperModel
from subsai.models.hugging_face_model import HuggingFaceModel
from subsai.models.whisperX_model import WhisperXModel
from subsai.models.whisper_model import WhisperModel
from subsai.models.whisper_timestamped_model import WhisperTimeStamped
from subsai.models.whispercpp_model import WhisperCppModel
from subsai.utils import get_available_devices, available_translation_models
from subsai.models.stable_ts_model import StableTsModel
from subsai.models.whisper_api_model import WhisperAPIModel

AVAILABLE_MODELS = {
    'openai/whisper': {
        'class': WhisperModel,
        'description': 'Whisper is a general-purpose speech recognition model. It is trained on a large dataset of '
                       'diverse audio and is also a multi-task model that can perform multilingual speech recognition '
                       'as well as speech translation and language identification.',
        'url': 'https://github.com/openai/whisper',
        'config_schema': WhisperModel.config_schema,
    },
    'linto-ai/whisper-timestamped': {
        'class': WhisperTimeStamped,
        'description': 'Multilingual Automatic Speech Recognition with word-level timestamps and confidence.',
        'url': 'https://github.com/linto-ai/whisper-timestamped',
        'config_schema': WhisperTimeStamped.config_schema,
    },
    'ggerganov/whisper.cpp': {
        'class': WhisperCppModel,
        'description': 'High-performance inference of OpenAI\'s Whisper automatic speech recognition (ASR) model\n'
                       '* Plain C/C++ implementation without dependencies\n'
                       '* Runs on the CPU\n',
        'url': 'https://github.com/ggerganov/whisper.cpp\nhttps://github.com/abdeladim-s/pywhispercpp',
        'config_schema': WhisperCppModel.config_schema,
    },
    'guillaumekln/faster-whisper': {
        'class': FasterWhisperModel,
        'description': '**faster-whisper** is a reimplementation of OpenAI\'s Whisper model using '
                       '[CTranslate2](https://github.com/OpenNMT/CTranslate2/), which is a fast inference engine for '
                       'Transformer models.\n'
                       'This implementation is up to 4 times faster than [openai/whisper]( '
                       'https://github.com/openai/whisper) for the same accuracy while using less memory. The '
                       'efficiency can be further improved with 8-bit quantization on both CPU and GPU.',
        'url': 'https://github.com/guillaumekln/faster-whisper',
        'config_schema': FasterWhisperModel.config_schema,
    },
    'm-bain/whisperX': {
        'class': WhisperXModel,
        'description': """**whisperX** is a fast automatic speech recognition (70x realtime with large-v2) with word-level timestamps and speaker diarization.""",
        'url': 'https://github.com/m-bain/whisperX',
        'config_schema': WhisperXModel.config_schema,
    },
    'jianfch/stable-ts': {
        'class': StableTsModel,
        'description': '**Stabilizing Timestamps for Whisper** This library modifies [Whisper](https://github.com/openai/whisper) to produce more reliable timestamps and extends its functionality.',
        'url': 'https://github.com/jianfch/stable-ts',
        'config_schema': StableTsModel.config_schema,
    },
    'API/openai/whisper': {
        'class': WhisperAPIModel,
        'description': 'API for the OpenAI large-v2 Whisper model, requires an API key.',
        'url': 'https://platform.openai.com/docs/guides/speech-to-text',
        'config_schema': WhisperAPIModel.config_schema,
    },
    'HuggingFace': {
        'class': HuggingFaceModel,
        'description': 'Hugging Face implementation of Whisper. '
                       'Any speech recognition pretrained model from the Hugging Face hub can be used as well',
        'url': 'https://huggingface.co/tasks/automatic-speech-recognition',
        'config_schema': HuggingFaceModel.config_schema,
    },
    'ivrit-ai/whisper-large-v2-tuned': {
        'class': HuggingFaceModel,
        'description': 'Hebrew fine-tuned Whisper Large v2 model by ivrit-ai. '
                       'Optimized for Hebrew speech recognition with significantly improved accuracy for Hebrew audio. '
                       'Fine-tuned using crowd-sourced Hebrew labeling.',
        'url': 'https://huggingface.co/ivrit-ai/whisper-large-v2-tuned',
        'config_schema': HuggingFaceModel.config_schema,
    },
    'ivrit-ai/whisper-large-v3': {
        'class': HuggingFaceModel,
        'description': 'Hebrew fine-tuned Whisper Large v3 model by ivrit-ai. '
                       'Latest version with improved Hebrew ASR performance. '
                       'Language detection capability degraded - intended for mostly Hebrew audio transcription.',
        'url': 'https://huggingface.co/ivrit-ai/whisper-large-v3',
        'config_schema': HuggingFaceModel.config_schema,
    },
    'Shiry/whisper-large-v2-he': {
        'class': HuggingFaceModel,
        'description': 'Hebrew Whisper Large v2 model fine-tuned on Google Fleurs Hebrew dataset. '
                       'Good performance for Hebrew speech recognition tasks.',
        'url': 'https://huggingface.co/Shiry/whisper-large-v2-he',
        'config_schema': HuggingFaceModel.config_schema,
    },
    'imvladikon/wav2vec2-large-xlsr-53-hebrew': {
        'class': HuggingFaceModel,
        'description': 'Hebrew Wav2Vec2 model based on XLSR-53 architecture. '
                       'Alternative to Whisper for Hebrew speech recognition, fine-tuned on Hebrew YouTube samples. '
                       'Requires 16kHz audio input.',
        'url': 'https://huggingface.co/imvladikon/wav2vec2-large-xlsr-53-hebrew',
        'config_schema': HuggingFaceModel.config_schema,
    },
    'sivan22/faster-whisper-ivrit-ai-whisper-large-v2-tuned': {
        'class': FasterWhisperModel,
        'description': 'Hebrew fine-tuned Faster-Whisper model optimized for speed and Hebrew accuracy. '
                       'Based on ivrit-ai whisper-large-v2 with CTranslate2 optimization for 4x faster inference. '
                       'Ideal for production Hebrew speech recognition with lower memory usage.',
        'url': 'https://huggingface.co/sivan22/faster-whisper-ivrit-ai-whisper-large-v2-tuned',
        'config_schema': FasterWhisperModel.config_schema,
    },
}

BASIC_TOOLS_CONFIGS = {
    'set time': {
        'description': 'Set time to a subtitle',
        'config_schema': {
            'h': {
                'type': float,
                'description': "hours: Integer or float values, may be positive or negative",
                'options': None,
                'default': 0,
            },
            'm': {
                'type': float,
                'description': "minutes: Integer or float values, may be positive or negative",
                'options': None,
                'default': 0,
            },
            's': {
                'type': float,
                'description': "seconds: Integer or float values, may be positive or negative",
                'options': None,
                'default': 0,
            },
            'ms': {
                'type': float,
                'description': "milliseconds: Integer or float values, may be positive or negative",
                'options': None,
                'default': 0,
            }
        }
    },
    'shift': {
        'description': 'Shift all subtitles by constant time amount',
        'config_schema': {
            'h': {
                'type': float,
                'description': "hours: Integer or float values, may be positive or negative",
                'options': None,
                'default': 0,
            },
            'm': {
                'type': float,
                'description': "minutes: Integer or float values, may be positive or negative",
                'options': None,
                'default': 0,
            },
            's': {
                'type': float,
                'description': "seconds: Integer or float values, may be positive or negative",
                'options': None,
                'default': 0,
            },
            'ms': {
                'type': float,
                'description': "milliseconds: Integer or float values, may be positive or negative",
                'options': None,
                'default': 0,
            },
            'frames': {
                'type': int,
                'description': "When specified, must be an integer number of frames",
                'options': None,
                'default': None,
            },
            'fps': {
                'type': float,
                'description': "When specified, must be a positive number.",
                'options': None,
                'default': None,
            }

        }
    },
}

ADVANCED_TOOLS_CONFIGS = {
    'ffsubsync': {
        'description': 'Language-agnostic automatic synchronization of subtitles with video, so that subtitles are '
                       'aligned to the correct starting point within the video.',
        'url': 'https://github.com/smacke/ffsubsync',
        'config_schema': {
            'vad': {
                'type': list,
                'description': "Which voice activity detector to use for speech extraction "
                               "(if using video / audio as a reference",
                'options': [
                    "subs_then_webrtc",
                    "webrtc",
                    "subs_then_auditok",
                    "auditok",
                    "subs_then_silero",
                    "silero",
                ],
                'default': DEFAULT_VAD,
            },
            'max-subtitle-seconds': {
                'type': float,
                'description': 'Maximum duration for a subtitle to appear on-screen',
                'options': None,
                'default': DEFAULT_MAX_SUBTITLE_SECONDS,
            },
            'start-seconds': {
                'type': int,
                'description': 'Start time for processing',
                'options': None,
                'default': DEFAULT_START_SECONDS,
            },
            'max-offset-seconds': {
                'type': float,
                'description': 'The max allowed offset seconds for any subtitle segment',
                'options': None,
                'default': DEFAULT_MAX_OFFSET_SECONDS,
            },
            'apply-offset-seconds': {
                'type': float,
                'description': 'Apply a predefined offset in seconds to all subtitle segments',
                'options': None,
                'default': DEFAULT_APPLY_OFFSET_SECONDS,
            },
            'suppress-output-if-offset-less-than': {
                'type': float,
                'description': 'Apply a predefined offset in seconds to all subtitle segments',
                'options': None,
                'default': None,
            },
            'frame-rate': {
                'type': int,
                'description': 'Frame rate for audio extraction',
                'options': None,
                'default': DEFAULT_FRAME_RATE,
            },
            'output-encoding': {
                'type': str,
                'description': "What encoding to use for writing output subtitles "
                               '(default=utf-8). Can indicate "same" to use same '
                               "encoding as that of the input.",
                'options': None,
                'default': "utf-8",
            },
            'skip-infer-framerate-ratio': {
                'type': bool,
                'description': 'If set, do not try to infer framerate ratio based on duration ratio.',
                'options': None,
                'default': False,
            },
            'no-fix-framerate': {
                'type': bool,
                'description': 'If specified, subsync will not attempt to correct a framerate',
                'options': None,
                'default': False,
            },
            'serialize-speech': {
                'type': bool,
                'description': 'If specified, serialize reference speech to a numpy array.',
                'options': None,
                'default': False,
            },
            'gss': {
                'type': bool,
                'description': "If specified, use golden-section search to try to find"
                               "the optimal framerate ratio between video and subtitles.",
                'options': None,
                'default': False,
            }
        }
    },
    'Translation': {
        'description': 'Translate to different languages using AI',
        'url': 'https://github.com/xhluca/dl-translate',
        'config_schema': {
            'model': {
                'type': list,
                'description': 'The model',
                'options': available_translation_models(),
                'default': available_translation_models()[0]
            },
            'device': {
                'type': list,
                'description': '"cpu", "gpu" or "auto". If it\'s set to "auto", will try to select a GPU when available'
                               ' or else fall back to CPU',
                'options': ['auto', *get_available_devices()],
                'default': 'auto'
            },
            'batch_size': {
                'type': int,
                'description': 'The number of samples to load at once. If set to `None`, it will process everything '
                               'at once\nA smaller value is preferred for `batch_size` if your (video) RAM is limited',
                'options': None,
                'default': 32
            },
            'verbose': {
                'type': bool,
                'description': 'Whether to display the progress bar for every batch processed.',
                'options': None,
                'default': True
            },
        }
    },

}

# S3 Storage Configuration
S3_CONFIG_SCHEMA = {
    'enabled': {
        'type': bool,
        'description': 'Enable S3 storage for subtitles',
        'default': False
    },
    'default_project': {
        'type': str,
        'description': 'Default project folder name',
        'default': 'default'
    }
}

# Default S3 configuration
DEFAULT_S3_CONFIG = {
    'enabled': False,
    'default_project': 'default'
}

# OOONA API Configuration
OOONA_CONFIG_SCHEMA = {
    'enabled': {
        'type': bool,
        'description': 'Enable OOONA API for subtitle format conversion',
        'default': False
    }
}

# Default OOONA configuration
DEFAULT_OOONA_CONFIG = {
    'enabled': False
}
