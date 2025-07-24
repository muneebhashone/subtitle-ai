#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
AION SRT - AI-Powered Subtitle Generation Web Interface
Effortless SRT Subtitling for your content
"""

import importlib
import json
import mimetypes
import os
import os.path
import shutil
import sys
import tempfile
import zipfile
from base64 import b64encode
from pathlib import Path

import pandas as pd
import streamlit as st
from pysubs2.time import ms_to_str, make_time
from streamlit import runtime
from streamlit_player import st_player
from st_aggrid import AgGrid, GridUpdateMode, GridOptionsBuilder, DataReturnMode

from subsai import SubsAI, Tools
from subsai.configs import ADVANCED_TOOLS_CONFIGS, DEFAULT_S3_CONFIG, S3_CONFIG_SCHEMA, DEFAULT_WEBHOOK_CONFIG, WEBHOOK_CONFIG_SCHEMA
from subsai.utils import available_subs_formats
from subsai.utils.file_manager import managed_temp_file, BatchFileManager
from subsai.storage.s3_storage import create_s3_storage
from subsai.batch_processor import BatchProcessor, JobStatus, JobConfig
from subsai.auth.decorators import AuthUtils, require_auth, require_admin
from subsai.auth.pages import render_login_page, render_user_dashboard, render_admin_panel
from subsai.analytics import AnalyticsService
from streamlit.web import cli as stcli
from tempfile import NamedTemporaryFile
import time

__author__ = "AION Voice AI"
__contact__ = "hello@aionvoice.ai"
__copyright__ = "Copyright 2025, AION Voice AI"
__deprecated__ = False
__license__ = "GPLv3"
__version__ = importlib.metadata.version('subsai')

subs_ai = SubsAI()
tools = Tools()
analytics = AnalyticsService()


def _init_s3_config():
    """Initialize S3 configuration in session state."""
    if 's3_config' not in st.session_state:
        st.session_state['s3_config'] = DEFAULT_S3_CONFIG.copy()




def _get_s3_config_from_session_state() -> dict:
    """Get S3 configuration from session state and environment variables."""
    
    config = {}
    # Get basic config from session state
    for config_name in S3_CONFIG_SCHEMA:
        key = f"s3_{config_name}"
        if key in st.session_state:
            config[config_name] = st.session_state[key]
        else:
            config[config_name] = S3_CONFIG_SCHEMA[config_name]['default']
    
    # Override 'enabled' with the actual checkbox value
    config['enabled'] = st.session_state.get('s3_enabled', False)
    
    # Add environment variables
    config['bucket_name'] = os.getenv('AWS_BUCKET_NAME', '')
    config['region'] = os.getenv('AWS_REGION', 'us-east-1')
    config['access_key'] = os.getenv('AWS_ACCESS_KEY')
    config['secret_key'] = os.getenv('AWS_SECRET_KEY')
    
    return config


def _init_webhook_config():
    """Initialize webhook configuration in session state."""
    if 'webhook_config' not in st.session_state:
        st.session_state['webhook_config'] = DEFAULT_WEBHOOK_CONFIG.copy()


def _get_webhook_config_from_session_state() -> dict:
    """Get webhook configuration from session state and environment variables."""
    
    config = {}
    # Get basic config from session state
    for config_name in WEBHOOK_CONFIG_SCHEMA:
        key = f"webhook_{config_name}"
        if key in st.session_state:
            config[config_name] = st.session_state[key]
        else:
            config[config_name] = WEBHOOK_CONFIG_SCHEMA[config_name]['default']
    
    # Override 'enabled' with the actual checkbox value
    config['enabled'] = st.session_state.get('webhook_enabled', DEFAULT_WEBHOOK_CONFIG['enabled'])
    
    # Add environment variable overrides
    config['source_language'] = os.getenv('WEBHOOK_SOURCE_LANGUAGE', config['source_language'])
    
    # Handle target languages from environment
    env_target_langs = os.getenv('WEBHOOK_TARGET_LANGUAGES')
    if env_target_langs:
        config['target_languages'] = env_target_langs.split(',')
    
    # Handle output formats from environment
    env_output_formats = os.getenv('WEBHOOK_OUTPUT_FORMATS')
    if env_output_formats:
        config['output_formats'] = env_output_formats.split(',')
    
    return config


def _render_webhook_config_ui():
    """Render webhook configuration UI in admin panel."""
    
    st.subheader("📡 Webhook Configuration")
    st.info("🔗 **Webhook Processing Settings** - Configure default language and output settings for webhook-triggered processing")
    
    # Get database connection
    from subsai.auth.decorators import AuthUtils
    auth = AuthUtils.init_auth()
    db = auth.auth.db
    
    # Load current configuration from database
    current_config = db.get_webhook_config_or_default()
    
    # Check environment variables
    webhook_source_lang = os.getenv('WEBHOOK_SOURCE_LANGUAGE')
    webhook_target_langs = os.getenv('WEBHOOK_TARGET_LANGUAGES')  
    webhook_output_formats = os.getenv('WEBHOOK_OUTPUT_FORMATS')
    
    # Show environment variable status
    if webhook_source_lang or webhook_target_langs or webhook_output_formats:
        st.warning("⚠️ Environment variables are overriding database settings")
        if webhook_source_lang:
            st.write(f"**Source Language (env):** {webhook_source_lang}")
        if webhook_target_langs:
            st.write(f"**Target Languages (env):** {webhook_target_langs}")
        if webhook_output_formats:
            st.write(f"**Output Formats (env):** {webhook_output_formats}")
    else:
        st.success("✅ Using database configuration")
    
    # Configuration form
    with st.form("webhook_config_form"):
        # Enable/disable webhook processing
        webhook_enabled = st.checkbox(
            "Enable webhook processing",
            value=current_config.enabled,
            help="Enable automatic processing of media files uploaded via webhook"
        )
        
        webhook_source_language = None
        webhook_target_languages = None
        webhook_output_formats = None
        
        if webhook_enabled:
            with st.expander("🌐 Language Settings", expanded=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    webhook_source_language = st.selectbox(
                        "Source language",
                        options=WEBHOOK_CONFIG_SCHEMA['source_language']['options'],
                        index=WEBHOOK_CONFIG_SCHEMA['source_language']['options'].index(current_config.source_language),
                        help="Default source language for webhook processing"
                    )
                
                with col2:
                    webhook_target_languages = st.multiselect(
                        "Target languages",
                        options=WEBHOOK_CONFIG_SCHEMA['target_languages']['options'],
                        default=current_config.target_languages,
                        help="Default target languages for webhook processing"
                    )
            
            with st.expander("📄 Output Settings", expanded=True):
                webhook_output_formats = st.multiselect(
                    "Output formats",
                    options=WEBHOOK_CONFIG_SCHEMA['output_formats']['options'],
                    default=current_config.output_formats,
                    help="Default output formats for webhook processing"
                )
            
            # Validation
            if webhook_enabled and not webhook_target_languages:
                st.error("⚠️ Please select at least one target language")
            
            if webhook_enabled and not webhook_output_formats:
                st.error("⚠️ Please select at least one output format")
        
        # Save button
        col1, col2 = st.columns([1, 3])
        with col1:
            save_clicked = st.form_submit_button("💾 Save Configuration", type="primary")
        
        if save_clicked:
            if webhook_enabled and (not webhook_target_languages or not webhook_output_formats):
                st.error("❌ Cannot save: Please select at least one target language and output format")
            else:
                # Create new configuration
                from subsai.auth.models import WebhookConfig
                new_config = WebhookConfig(
                    enabled=webhook_enabled,
                    source_language=webhook_source_language or current_config.source_language,
                    target_languages=webhook_target_languages or current_config.target_languages,
                    output_formats=webhook_output_formats or current_config.output_formats
                )
                
                # Save to database
                if db.save_webhook_config(new_config):
                    st.success("✅ Webhook configuration saved successfully!")
                    st.experimental_rerun()
                else:
                    st.error("❌ Failed to save webhook configuration")
    
    # Show current configuration
    st.subheader("📋 Current Configuration")
    updated_config = db.get_webhook_config_or_default()
    
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Status:** {'🟢 Enabled' if updated_config.enabled else '🔴 Disabled'}")
        st.write(f"**Source Language:** {updated_config.source_language}")
    with col2:
        st.write(f"**Target Languages:** {', '.join(updated_config.target_languages)}")
        st.write(f"**Output Formats:** {', '.join(updated_config.output_formats)}")
    
    if updated_config.updated_at:
        st.write(f"**Last Updated:** {updated_config.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Environment variable export (optional)
    with st.expander("🔧 Environment Variables (Optional)", expanded=False):
        st.info("You can optionally override these settings with environment variables:")
        st.code(f"""
export WEBHOOK_SOURCE_LANGUAGE="{updated_config.source_language}"
export WEBHOOK_TARGET_LANGUAGES="{','.join(updated_config.target_languages)}"
export WEBHOOK_OUTPUT_FORMATS="{','.join(updated_config.output_formats)}"
        """, language="bash")


def _render_s3_config_ui():
    """Render S3 configuration UI in sidebar."""
    
    st.subheader("☁️ S3 Storage")
    
    # Check environment variables
    aws_access_key = os.getenv('AWS_ACCESS_KEY')
    aws_secret_key = os.getenv('AWS_SECRET_KEY')
    aws_bucket_name = os.getenv('AWS_BUCKET_NAME')
    aws_region = os.getenv('AWS_REGION', 'us-east-1')
    
    # Show environment variable status
    if aws_access_key and aws_secret_key and aws_bucket_name:
        st.success("✅ AWS credentials configured via environment variables")
        st.info(f"📍 Bucket: `{aws_bucket_name}` | Region: `{aws_region}`")
        
        # Enable/disable S3
        s3_enabled = st.checkbox(
            "Enable S3 Storage", 
            value=st.session_state.get('s3_enabled', True),
            help="Save subtitles to Amazon S3 bucket",
            key='s3_enabled'
        )
        
        # Test connection button
        if s3_enabled:
            if st.button("🔍 Test S3 Connection"):
                with st.spinner("Testing S3 connection..."):
                    s3_config = {
                        'enabled': True,
                        'bucket_name': aws_bucket_name,
                        'region': aws_region,
                        'access_key': aws_access_key,
                        'secret_key': aws_secret_key
                    }
                    
                    s3_storage = create_s3_storage(s3_config)
                    if s3_storage:
                        result = s3_storage.validate_connection()
                        if result['success']:
                            st.success(f"✅ {result['message']}")
                        else:
                            st.error(f"❌ {result['message']}")
                    else:
                        st.error("❌ Failed to create S3 storage client")
    else:
        st.warning("⚠️ AWS credentials not configured")
        st.info("💡 Configure the following environment variables:")
        st.code("""
AWS_ACCESS_KEY=your_access_key
AWS_SECRET_KEY=your_secret_key
AWS_BUCKET_NAME=your_bucket_name
AWS_REGION=your_region
        """)
        s3_enabled = False
    
    return s3_enabled


def _init_deepseek_api_config():
    """Initialize DeepSeek API configuration in session state."""
    if 'deepseek_api_config' not in st.session_state:
        st.session_state['deepseek_api_config'] = {
            'enabled': False,
            'api_key': '',
            'base_url': 'https://api.deepseek.com',
            'model': 'api:deepseek-chat'
        }


def _get_deepseek_api_config_from_session_state() -> dict:
    """Get DeepSeek API configuration from session state and environment variables."""
    
    config = {}
    # Get basic config from session state
    config['enabled'] = st.session_state.get('deepseek_api_enabled', False)
    config['api_key'] = st.session_state.get('deepseek_api_key', '') or os.getenv('DEEPSEEK_API_KEY', '')
    config['base_url'] = st.session_state.get('deepseek_api_base_url', 'https://api.deepseek.com')
    config['model'] = st.session_state.get('deepseek_api_model', 'api:deepseek-chat')
    
    return config


def _render_deepseek_api_config_ui():
    """Render DeepSeek API configuration UI in sidebar."""
    
    st.subheader("🧠 DeepSeek API")
    
    # Check environment variable
    env_api_key = os.getenv('DEEPSEEK_API_KEY')
    
    # Show environment variable status
    if env_api_key:
        st.success("✅ DeepSeek API key configured via environment variable")
        api_key = env_api_key
        
        # Enable/disable DeepSeek API
        deepseek_api_enabled = st.checkbox(
            "Enable DeepSeek API Translation", 
            value=st.session_state.get('deepseek_api_enabled', False),
            help="Use DeepSeek API for translation (cloud-based)",
            key='deepseek_api_enabled'
        )
    else:
        st.warning("⚠️ DeepSeek API key not configured")
        
        # API key input
        api_key = st.text_input(
            "DeepSeek API Key",
            value=st.session_state.get('deepseek_api_key', ''),
            type="password",
            help="Enter your DeepSeek API key",
            key='deepseek_api_key'
        )
        
        deepseek_api_enabled = st.checkbox(
            "Enable DeepSeek API Translation", 
            value=st.session_state.get('deepseek_api_enabled', False) and bool(api_key),
            disabled=not bool(api_key),
            help="Use DeepSeek API for translation (cloud-based)",
            key='deepseek_api_enabled'
        )
        
        if not api_key:
            st.info("💡 Get your API key from: https://platform.deepseek.com/api_keys")
    
    if deepseek_api_enabled and api_key:
        # Base URL configuration (advanced)
        with st.expander("Advanced Settings", expanded=False):
            base_url = st.text_input(
                "API Base URL",
                value=st.session_state.get('deepseek_api_base_url', 'https://api.deepseek.com'),
                help="DeepSeek API base URL",
                key='deepseek_api_base_url'
            )
        
        # Model selection
        model = st.selectbox(
            "DeepSeek Model",
            options=['api:deepseek-chat', 'api:deepseek-reasoner'],
            index=0 if st.session_state.get('deepseek_api_model', 'api:deepseek-chat') == 'api:deepseek-chat' else 1,
            help="Choose DeepSeek model: deepseek-chat (faster, cheaper) or deepseek-reasoner (better reasoning)",
            key='deepseek_api_model'
        )
        
        # Test connection button
        if st.button("🔍 Test DeepSeek API Connection"):
            with st.spinner("Testing DeepSeek API connection..."):
                try:
                    from subsai.main import DeepSeekAPITranslationModel
                    test_model = DeepSeekAPITranslationModel(
                        model_name=model,
                        api_key=api_key,
                        base_url=base_url
                    )
                    # Test with a simple translation
                    result = test_model.translate("Hello", "en", "es")
                    if result:
                        st.success(f"✅ DeepSeek API connection successful! Test translation: '{result}'")
                    else:
                        st.error("❌ DeepSeek API connection failed - empty response")
                except Exception as e:
                    st.error(f"❌ DeepSeek API connection failed: {str(e)}")
    
    return deepseek_api_enabled


def _get_key(model_name: str, config_name: str) -> str:
    """
    a simple helper method to generate unique key for configs UI

    :param model_name: name of the model
    :param config_name: configuration key
    :return: str key
    """
    return model_name + '-' + config_name


def _config_ui(config_name: str, key: str, config: dict):
    """
    helper func that returns the config UI based on the type of the config

    :param config_name: the name of the model
    :param key: the key to set for the config ui
    :param config: configuration object

    :return: config UI streamlit objects
    """
    if config['type'] == str:
        return st.text_input(config_name, help=config['description'], key=key, value=config['default'])
    elif config['type'] == list:
        return st.selectbox(config_name, config['options'], index=config['options'].index(config['default']),
                            help=config['description'], key=key)
    elif config['type'] == float or config['type'] == int:
        if config['default'] is None:
            return st.text_input(config_name, help=config['description'], key=key, value=config['default'])
        return st.number_input(label=config_name, help=config['description'], key=key, value=config['default'])
    elif config['type'] == bool:
        return st.checkbox(label=config_name, value=config['default'], help=config['description'], key=key)
    else:
        print(f'Warning: {config_name} does not have a supported UI')
        pass

def _create_batch_download_zip(batch_processor: BatchProcessor) -> bytes:
    """
    Create a ZIP file containing all results from completed batch jobs.
    
    :param batch_processor: The batch processor instance
    :return: ZIP file content as bytes
    """
    import io
    
    # Create ZIP file in memory
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        jobs = batch_processor.get_all_jobs()
        completed_jobs = [job for job in jobs if job.status.value == 'completed' and job.results]
        
        if not completed_jobs:
            # Add empty file to indicate no results
            zip_file.writestr("no_completed_files.txt", "No completed files found.")
            return zip_buffer.getvalue()
        
        for job in completed_jobs:
            # Create a folder for each job
            job_folder = Path(job.file_name).stem  # Use filename without extension as folder name
            
            for result in job.results:
                try:
                    # Read the file content
                    if os.path.exists(result['path']):
                        with open(result['path'], 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # Add to ZIP with job folder structure
                        zip_path = f"{job_folder}/{result['filename']}"
                        zip_file.writestr(zip_path, content)
                except Exception as e:
                    # Add error info if file can't be read
                    error_content = f"Error reading file {result['filename']}: {str(e)}"
                    zip_path = f"{job_folder}/ERROR_{result['filename']}.txt"
                    zip_file.writestr(zip_path, error_content)
    
    return zip_buffer.getvalue()


def _create_single_file_download_zip(results: list, base_filename: str) -> bytes:
    """
    Create a ZIP file containing all results from single file processing.
    
    :param results: List of result dictionaries with 'content', 'filename' keys
    :param base_filename: Base filename to use for the folder name
    :return: ZIP file content as bytes
    """
    import io
    
    # Create ZIP file in memory
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        if not results:
            # Add empty file to indicate no results
            zip_file.writestr("no_files_generated.txt", "No files were generated.")
            return zip_buffer.getvalue()
        
        # Create a folder based on the original filename
        folder_name = Path(base_filename).stem  # Use filename without extension as folder name
        
        for result in results:
            try:
                # Add content directly to ZIP (no file path needed)
                zip_path = f"{folder_name}/{result['filename']}"
                zip_file.writestr(zip_path, result['content'])
            except Exception as e:
                # Add error info if content can't be processed
                error_content = f"Error processing file {result['filename']}: {str(e)}"
                zip_path = f"{folder_name}/ERROR_{result['filename']}.txt"
                zip_file.writestr(zip_path, error_content)
    
    return zip_buffer.getvalue()


@require_auth
def render_batch_processing_with_auth(user):
    """
    Render batch processing with user authentication
    """
    # Initialize batch processor in session state with user context
    if 'batch_processor' not in st.session_state:
        # Get device preference from session state or use auto
        device_preference = st.session_state.get('batch_device_preference', 'auto')
        st.session_state.batch_processor = BatchProcessor(
            user_id=user.id if user else None,
            preferred_device=device_preference
        )
    
    render_batch_processing_ui(st.session_state.batch_processor, subs_ai, user)


def render_batch_processing_ui(batch_processor: BatchProcessor, subs_ai: SubsAI, user=None):
    """
    Render UI for batch processing of multiple files.
    """
    st.title("🔄 AION SRT - Batch Processing")
    st.info("📁 Process multiple media files simultaneously with enterprise-grade efficiency. Upload files up to 10GB each and generate subtitles with high accuracy across 100+ languages.")
    
    # Show user context if provided
    if user:
        st.info(f"👤 Processing files for user: **{user.username}**")

    # Progress display first if processing
    jobs = batch_processor.get_all_jobs()
    if jobs:
        render_batch_progress_dashboard(batch_processor)
    
    # File upload section
    uploaded_files = st.file_uploader(
        "Choose media files", 
        accept_multiple_files=True, 
        type=["mp4", "avi", "mkv", "mov", "flv", "webm", "wav", "mp3", "m4a", "flac", "aac", "ogg"],
        help="Supports large files up to 10GB. Multiple formats supported."
    )

    if uploaded_files:
        st.success(f"📋 Uploaded {len(uploaded_files)} file(s)")
        
        # Bulk configuration options
        st.write("**Bulk Configuration (applies to all files)**")
        
        # Device configuration section
        with st.expander("⚙️ Processing Configuration", expanded=False):
            from subsai.utils import get_available_devices, is_cuda_available
            
            col_device1, col_device2 = st.columns(2)
            
            with col_device1:
                available_devices = get_available_devices()
                device_options = ['auto'] + available_devices
                
                current_device = st.session_state.get('batch_device_preference', 'auto')
                device_preference = st.selectbox(
                    "Processing Device",
                    options=device_options,
                    index=device_options.index(current_device) if current_device in device_options else 0,
                    help="Choose processing device: 'auto' for optimal selection, 'cpu' for CPU-only, or specific CUDA device"
                )
                
                if device_preference != st.session_state.get('batch_device_preference', 'auto'):
                    st.session_state.batch_device_preference = device_preference
                    # Reinitialize batch processor with new device preference
                    if 'batch_processor' in st.session_state:
                        del st.session_state.batch_processor
                    st.experimental_rerun()
            
            with col_device2:
                # Show device status
                cuda_available = is_cuda_available()
                if cuda_available:
                    st.success("✅ CUDA GPU Available")
                    import torch
                    if torch.cuda.is_available():
                        gpu_count = torch.cuda.device_count()
                        st.info(f"🔧 {gpu_count} GPU(s) detected")
                else:
                    st.warning("⚠️ CUDA not available - using CPU")
                    
                # Show current device selection
                if device_preference == 'auto':
                    optimal_device = 'cuda:0' if cuda_available else 'cpu'
                    st.info(f"🎯 Auto-selected: {optimal_device}")
                else:
                    st.info(f"🎯 Selected: {device_preference}")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            bulk_source_language = st.selectbox(
                "Default source language",
                options=['auto', 'en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh', 'ar', 'he', 'hi', 'tr', 'pl', 'nl', 'sv', 'da', 'no', 'fi'],
                index=0
            )
        
        with col2:
            bulk_intermediate_language = st.selectbox(
                "Default bridge language (optional)",
                options=['none', 'en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh', 'ar', 'he', 'hi', 'tr', 'pl', 'nl', 'sv', 'da', 'no', 'fi'],
                index=0,
                help="Optional intermediate language for improved translation quality. Leave as 'none' for direct translation."
            )
        
        with col3:
            bulk_target_languages = st.multiselect(
                "Default target languages",
                options=['transcribe', 'en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh', 'ar', 'he', 'hi', 'tr', 'pl', 'nl', 'sv', 'da', 'no', 'fi'],
                default=['transcribe']
            )
        
        with col4:
            bulk_formats = st.multiselect(
                "Default output formats",
                options=['srt', 'vtt', 'ass', 'sub', 'ooona'],
                default=['srt', 'ooona']
            )
        
        # Model selection for bulk processing
        col1, col2 = st.columns(2)
        
        with col1:
            # Transcription model selection
            available_models = subs_ai.available_models()
            whisper_models = [model for model in available_models if model == 'openai/whisper']
            
            bulk_transcription_model = st.selectbox(
                "Default transcription model",
                options=whisper_models,
                index=0,  # Default to first Whisper model
                help="AI model to use for speech-to-text transcription"
            )
            
            # Model variant selection for bulk processing
            try:
                config_schema = subs_ai.config_schema(bulk_transcription_model)
                if 'model_type' in config_schema:
                    model_type_config = config_schema['model_type']
                    if len(model_type_config['options']) > 1:
                        bulk_model_variant = st.selectbox(
                            "Default model size",
                            options=model_type_config['options'],
                            index=model_type_config['options'].index(model_type_config['default']),
                            help="Model size affects accuracy and processing speed. Larger models are more accurate but slower."
                        )
                    else:
                        bulk_model_variant = model_type_config['default']
                        st.info(f"Model size: {bulk_model_variant}")
            except Exception:
                bulk_model_variant = None
        
        with col2:
            # Translation model selection for bulk processing
            from subsai.utils import available_translation_models
            
            try:
                translation_models = available_translation_models()
            except Exception as e:
                st.error(f"Error loading translation models: {e}")
                translation_models = ["deepseek-r1:1.5b"]
            
            bulk_translation_model = st.selectbox(
                "Default translation model",
                options=translation_models,
                index=0,  # DeepSeek R1 is always first
                help="AI model to use for translation (only used when translating to different languages)"
            )
        
        use_bulk_config = st.checkbox("Use bulk configuration for all files", value=True)
        
        # S3 Upload Option for Batch Processing
        st.write("**Storage Options**")
        col1, col2 = st.columns(2)
        
        with col1:
            batch_s3_upload = st.checkbox(
                "Upload to S3 after processing", 
                value=False,
                help="Automatically upload generated files to S3 bucket (files will also be available for download)"
            )
        
        with col2:
            if batch_s3_upload:
                batch_s3_project = st.text_input(
                    "S3 Project folder",
                    value="batch-processing",
                    help="Folder name in S3 bucket for batch files"
                )
                
                # S3 path preview
                s3_config = _get_s3_config_from_session_state()
                if s3_config.get('bucket_name'):
                    st.info(f"📍 S3 Path: `{s3_config['bucket_name']}/{batch_s3_project}/`")
        
        st.write("**Individual File Configuration**")
        
        # Store temp files and configs
        if 'temp_files' not in st.session_state:
            st.session_state.temp_files = []
        
        # Clear old temp files with proper cleanup
        if hasattr(st.session_state, 'batch_file_manager'):
            st.session_state.batch_file_manager.cleanup_all()
        st.session_state.temp_files = []
        
        # Initialize batch file manager
        if 'batch_file_manager' not in st.session_state:
            st.session_state.batch_file_manager = BatchFileManager()
        
        # Configuration per file
        for i, uploaded_file in enumerate(uploaded_files):
            file_id = f"file-{i}-{uploaded_file.name}"
            
            # Handle file size safely
            file_size_mb = "Unknown"
            if hasattr(uploaded_file, 'size') and uploaded_file.size is not None:
                file_size_mb = f"{uploaded_file.size / (1024*1024):.1f} MB"
            
            with st.expander(f"📄 {uploaded_file.name} ({file_size_mb})", expanded=not use_bulk_config):
                # Save file temporarily with managed cleanup
                temp_file_path = st.session_state.batch_file_manager.add_temp_file(uploaded_file)
                
                # Store temp file info
                st.session_state.temp_files.append({
                    'name': uploaded_file.name,
                    'path': temp_file_path,
                    'size': uploaded_file.size,
                    'managed': True  # Flag to indicate this is managed
                })
                
                if use_bulk_config:
                    source_language = bulk_source_language
                    target_languages = bulk_target_languages
                    formats = bulk_formats
                    intermediate_display = bulk_intermediate_language if bulk_intermediate_language != 'none' else None
                    if intermediate_display:
                        st.info(f"Using bulk configuration: {source_language} → {intermediate_display} → {target_languages} → {formats}")
                    else:
                        st.info(f"Using bulk configuration: {source_language} → {target_languages} → {formats}")
                else:
                    # Individual configuration
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        source_language = st.selectbox(
                            "Source language",
                            options=['auto', 'en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh', 'ar', 'he', 'hi', 'tr', 'pl', 'nl', 'sv', 'da', 'no', 'fi'],
                            index=0, key=f"source-lang-{file_id}"
                        )
                    
                    with col2:
                        intermediate_language = st.selectbox(
                            "Bridge language (optional)",
                            options=['none', 'en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh', 'ar', 'he', 'hi', 'tr', 'pl', 'nl', 'sv', 'da', 'no', 'fi'],
                            index=0, key=f"intermediate-lang-{file_id}"
                        )
                    
                    with col3:
                        target_languages = st.multiselect(
                            "Target languages",
                            options=['transcribe', 'en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh', 'ar', 'he', 'hi', 'tr', 'pl', 'nl', 'sv', 'da', 'no', 'fi'],
                            default=bulk_target_languages, key=f"target-lang-{file_id}"
                        )
                    
                    with col4:
                        formats = st.multiselect(
                            "Output formats",
                            options=['srt', 'vtt', 'ass', 'sub', 'ooona'],
                            default=bulk_formats, key=f"format-{file_id}"
                        )
                    
                    # Model configuration for individual files
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        individual_model = st.selectbox(
                            "Transcription model",
                            options=whisper_models,
                            index=0, key=f"model-{file_id}",
                            help="AI model to use for speech-to-text transcription"
                        )
                        
                    with col2:
                        # Model variant selection for individual files
                        try:
                            config_schema = subs_ai.config_schema(individual_model)
                            if 'model_type' in config_schema:
                                model_type_config = config_schema['model_type']
                                if len(model_type_config['options']) > 1:
                                    individual_model_variant = st.selectbox(
                                        "Model size",
                                        options=model_type_config['options'],
                                        index=model_type_config['options'].index(model_type_config['default']),
                                        key=f"model-variant-{file_id}",
                                        help="Model size affects accuracy and processing speed. Larger models are more accurate but slower."
                                    )
                                else:
                                    individual_model_variant = model_type_config['default']
                                    st.info(f"Model size: {individual_model_variant}")
                        except Exception:
                            individual_model_variant = None
        
        # Action buttons
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("🚀 Start Batch Processing", type="primary", disabled=batch_processor.is_processing()):
                if not any([bulk_target_languages if use_bulk_config else True]):
                    st.error("Please select at least one target language")
                elif not any([bulk_formats if use_bulk_config else True]):
                    st.error("Please select at least one output format")
                else:
                    # Add jobs to processor
                    for i, file_info in enumerate(st.session_state.temp_files):
                        if use_bulk_config:
                            job_target_languages = bulk_target_languages
                            job_formats = bulk_formats
                            job_source_language = bulk_source_language
                            job_intermediate_language = bulk_intermediate_language if bulk_intermediate_language != 'none' else None
                            job_translation_model = bulk_translation_model
                            job_transcription_model = bulk_transcription_model
                            job_model_variant = bulk_model_variant
                        else:
                            file_id = f"file-{i}-{file_info['name']}"
                            job_source_language = st.session_state.get(f"source-lang-{file_id}", 'auto')
                            job_target_languages = st.session_state.get(f"target-lang-{file_id}", ['transcribe'])
                            job_formats = st.session_state.get(f"format-{file_id}", ['srt'])
                            job_intermediate_language_raw = st.session_state.get(f"intermediate-lang-{file_id}", 'none')
                            job_intermediate_language = job_intermediate_language_raw if job_intermediate_language_raw != 'none' else None
                            job_translation_model = bulk_translation_model  # Use bulk model for individual files too for now
                            job_transcription_model = st.session_state.get(f"model-{file_id}", bulk_transcription_model)
                            job_model_variant = st.session_state.get(f"model-variant-{file_id}", bulk_model_variant)
                        
                        # Prepare export options for S3
                        export_options = {}
                        if batch_s3_upload:
                            export_options['s3_upload'] = True
                            export_options['s3_enabled'] = True
                            export_options['s3_project_folder'] = batch_s3_project
                            export_options['s3_config'] = _get_s3_config_from_session_state()
                        
                        batch_processor.add_job(
                            file_path=file_info['path'],
                            file_name=file_info['name'],
                            file_size=file_info['size'],
                            source_language=job_source_language,
                            target_languages=job_target_languages,
                            output_formats=job_formats,
                            intermediate_language=job_intermediate_language,
                            export_options=export_options,
                            translation_model=job_translation_model,
                            transcription_model=job_transcription_model,
                            model_variant=job_model_variant
                        )
                    
                    batch_processor.start_processing()
                    st.success(f"🚀 Started processing {len(st.session_state.temp_files)} files!")
                    st.experimental_rerun()
        
        with col2:
            if st.button("⏸️ Pause Processing", disabled=not batch_processor.is_processing()):
                batch_processor.pause_processing()
                st.info("Processing paused. Current job will complete.")
                time.sleep(1)
                st.experimental_rerun()
        
        with col3:
            # Check if there are completed jobs with results
            jobs = batch_processor.get_all_jobs()
            completed_jobs_with_results = [job for job in jobs if job.status.value == 'completed' and job.results]
            
            if completed_jobs_with_results:
                # Count total files that will be downloaded
                total_files = sum(len(job.results) for job in completed_jobs_with_results)
                
                try:
                    zip_content = _create_batch_download_zip(batch_processor)
                    import datetime
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    zip_filename = f"batch_subtitles_{timestamp}.zip"
                    
                    st.download_button(
                        f"📦 Download All ({total_files} files)",
                        data=zip_content,
                        file_name=zip_filename,
                        mime="application/zip",
                        help=f"Download all {total_files} completed files as a ZIP archive",
                        disabled=batch_processor.is_processing()
                    )
                except Exception as e:
                    st.error(f"Error creating download: {e}")
            else:
                st.button("📦 Download All", disabled=True, help="No completed files to download")
        
        with col4:
            if st.button("🗑️ Clear Completed", disabled=batch_processor.is_processing()):
                batch_processor.clear_completed()
                st.success("Cleared completed jobs")
                st.experimental_rerun()
        
        # Show download summary if there are completed jobs
        if completed_jobs_with_results:
            with st.expander(f"📋 Download Summary ({len(completed_jobs_with_results)} completed jobs)", expanded=False):
                for job in completed_jobs_with_results:
                    st.write(f"**{job.file_name}**: {len(job.results)} files")
                    for result in job.results:
                        file_size_mb = result['size'] / (1024*1024) if result['size'] > 0 else 0
                        st.write(f"  - {result['filename']} ({result['format'].upper()}) - {file_size_mb:.1f} MB")
                st.info("💡 Use the 'Download All' button above to download all files as a ZIP archive before clearing completed jobs.")


def render_batch_progress_dashboard(batch_processor: BatchProcessor):
    """
    Render the batch processing progress dashboard with live updates.
    """
    overall_progress = batch_processor.get_progress()
    jobs = batch_processor.get_all_jobs()
    
    if not jobs:
        return
    
    # Auto-refresh if processing
    if batch_processor.is_processing():
        time.sleep(2)  # Wait 2 seconds before refresh
        st.experimental_rerun()
    
    st.write("---")
    st.subheader("📊 AION SRT - Processing Dashboard")
    
    # Overall progress
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Overall Progress", f"{overall_progress['overall_progress']:.1%}")
        st.progress(overall_progress['overall_progress'])
    
    with col2:
        st.metric("Completed", f"{overall_progress['completed_jobs']}/{overall_progress['total_jobs']}")
    
    with col3:
        st.metric("Processing", overall_progress['processing_jobs'], delta=None)
    
    with col4:
        st.metric("Failed", overall_progress['failed_jobs'], delta=None if overall_progress['failed_jobs'] == 0 else "⚠️")
    
    # Current job info
    current_job_id = batch_processor.get_current_job_id()
    if current_job_id:
        current_job = batch_processor.get_job_details(current_job_id)
        if current_job:
            st.info(f"🔄 Currently processing: **{current_job.file_name}** - {current_job.current_task}")
    
    # Job details
    st.write("**Job Details:**")
    
    for job in jobs:
        # Status icon mapping
        status_icons = {
            JobStatus.PENDING: "⏳",
            JobStatus.PROCESSING: "🔄",
            JobStatus.COMPLETED: "✅",
            JobStatus.FAILED: "❌",
            JobStatus.CANCELLED: "🚫",
            JobStatus.PAUSED: "⏸️"
        }
        
        icon = status_icons.get(job.status, "❓")
        
        with st.expander(f"{icon} {job.file_name} - {job.status.value.title()}", expanded=(job.status == JobStatus.PROCESSING)):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.write(f"**Status:** {job.status.value.title()}")
                st.write(f"**Progress:** {int(job.progress * 100)}%")
                if job.progress > 0:
                    st.progress(job.progress)
                
                if job.current_task:
                    st.write(f"**Current Task:** {job.current_task}")
                
                if job.error_message:
                    st.error(f"**Error:** {job.error_message}")
                
                # Show timing information
                if job.started_at:
                    start_time = time.strftime('%H:%M:%S', time.localtime(job.started_at))
                    st.write(f"**Started:** {start_time}")
                
                if job.completed_at:
                    end_time = time.strftime('%H:%M:%S', time.localtime(job.completed_at))
                    duration = job.completed_at - (job.started_at or job.created_at)
                    st.write(f"**Completed:** {end_time} (Duration: {duration:.1f}s)")
            
            with col2:
                st.write(f"**File Size:** {job.file_size / (1024*1024):.1f} MB")
                if hasattr(job, 'intermediate_language') and job.intermediate_language:
                    st.write(f"**Languages:** {job.source_language} → {job.intermediate_language} → {', '.join(job.target_languages)}")
                else:
                    st.write(f"**Languages:** {job.source_language} → {', '.join(job.target_languages)}")
                st.write(f"**Formats:** {', '.join(job.output_formats)}")
                
                # Cancel button for pending jobs
                if job.status == JobStatus.PENDING:
                    if st.button(f"Cancel", key=f"cancel-{job.file_id}"):
                        if batch_processor.cancel_job(job.file_id):
                            st.success("Job cancelled")
                            st.experimental_rerun()
            
            # Results section
            if job.results:
                st.write("**📁 Generated Files:**")
                for result in job.results:
                    file_size_mb = result['size'] / (1024*1024) if result['size'] > 0 else 0
                    st.success(f"📄 {result['filename']} ({result['format'].upper()}) - {file_size_mb:.1f} MB")
                    
                    # Download button for each result
                    try:
                        if os.path.exists(result['path']):
                            with open(result['path'], 'r', encoding='utf-8') as f:
                                content = f.read()
                            st.download_button(
                                f"📥 Download {result['filename']}",
                                data=content,
                                file_name=result['filename'],
                                mime='text/plain',
                                key=f"download-{job.file_id}-{result['filename']}"
                            )
                    except Exception as e:
                        st.error(f"Error reading file: {e}")


def _generate_config_ui(model_name, config_schema):
    """
    Loops through configuration dict object and generates the configuration UIs
    :param model_name:
    :param config_schema:
    :return: Config UIs
    """
    for config_name in config_schema:
        config = config_schema[config_name]
        key = _get_key(model_name, config_name)
        _config_ui(config_name, key, config)


def _get_config_from_session_state(model_name: str, config_schema: dict, notification_placeholder) -> dict:
    """
    Helper function to get configuration dict from the generated config UIs

    :param model_name: name of the model
    :param config_schema: configuration schema
    :param notification_placeholder: notification placeholder streamlit object in case of errors

    :return: dict of configs
    """
    model_config = {}
    for config_name in config_schema:
        key = _get_key(model_name, config_name)
        try:
            value = st.session_state[key]
            if config_schema[config_name]['type'] == str:
                if value == 'None' or value == '':
                    value = None
            elif config_schema[config_name]['type'] == float:
                if value == 'None' or value == '':
                    value = None
                else:
                    value = float(value)
            elif config_schema[config_name]['type'] == int:
                if value == 'None' or value == '':
                    value = None
                else:
                    value = int(value)

            model_config[config_name] = value
        except KeyError as e:
            pass
        except Exception as e:
            notification_placeholder.error(f'Problem parsing configs!! \n {e}')
            return
    return model_config


def _vtt_base64(subs_str: str, mime='application/octet-stream'):
    """
    Helper func to return vtt subs as base64 to load them into the video

    :param subs_str: str of the subtitles
    :param mime: mime type

    :return: base64 data
    """
    data = b64encode(subs_str.encode()).decode()
    return f"data:{mime};base64,{data}"


def _media_file_base64(file_path, mime='video/mp4', start_time=0):
    """
    Helper func that returns base64 of the media file

    :param file_path: path of the file
    :param mime: mime type
    :param start_time: start time

    :return: base64 of the media file
    """
    if file_path == '':
        data = ''
        return [{"type": mime, "src": f"data:{mime};base64,{data}#t={start_time}"}]
    with open(file_path, "rb") as media_file:
        data = b64encode(media_file.read()).decode()
        try:
            mime = mimetypes.guess_type(file_path)[0]
        except Exception as e:
            print(f'Unrecognized video type!')

    return [{"type": mime, "src": f"data:{mime};base64,{data}#t={start_time}"}]

def _create_translation_model(model_name: str):
    """
    Returns a translation model (no caching to avoid CUDA memory issues)

    :param model_name: name of the model

    :return: translation model
    """
    translation_model = tools.create_translation_model(model_name)
    return translation_model


@st.cache_data
def _transcribe(file_path, model_name, model_config):
    """
    Returns and caches the generated subtitles

    :param file_path: path of the media file
    :param model_name: name of the model
    :param model_config: configs dict

    :return: `SSAFile` subs
    """
    model = subs_ai.create_model(model_name, model_config=model_config)
    subs = subs_ai.transcribe(media_file=file_path, model=model)
    return subs


def _process_single_file_with_batch_flow(file_path, filename, file_size, source_language, target_languages, output_formats, 
                                        device_preference, translation_model, transcription_model, model_config, enable_download, save_local, save_s3, s3_project, 
                                        progress_placeholder, results_placeholder, user, intermediate_language=None):
    """
    Process single file using batch processing workflow
    
    :param file_path: path to media file
    :param filename: name of the file
    :param file_size: size of the file in bytes
    :param source_language: source language code
    :param target_languages: list of target languages
    :param output_formats: list of output formats
    :param device_preference: preferred device for processing
    :param translation_model: translation model to use for translation
    :param transcription_model: transcription model to use for speech-to-text
    :param model_config: configuration for the transcription model
    :param enable_download: whether to enable download buttons
    :param save_local: whether to save files locally
    :param save_s3: whether to save to S3
    :param s3_project: S3 project folder name
    :param progress_placeholder: Streamlit placeholder for progress
    :param results_placeholder: Streamlit placeholder for results
    :param user: current user object
    :return: dict with results
    """
    from subsai.utils import get_optimal_device, is_cuda_available
    from pathlib import Path
    import tempfile
    
    start_time = time.time()
    results = []
    
    try:
        # Track transcription start
        if analytics.is_enabled():
            analytics.track_transcription_start(
                user_id=user.id,
                filename=filename,
                model=transcription_model,
                file_size=file_size,
                source_language=source_language,
                target_languages=target_languages,
                output_formats=output_formats
            )
        
        # Step 1: Initialize device configuration
        progress_placeholder.info("🔧 Initializing processing device...")
        
        def get_model_device_config(model_type, preferred_device):
            """Get device configuration based on preferences"""
            if preferred_device == 'auto':
                device = get_optimal_device()
            elif preferred_device == 'cpu':
                device = 'cpu'
            elif preferred_device.startswith('cuda'):
                if is_cuda_available():
                    device = preferred_device
                else:
                    device = 'cpu'
            else:
                device = get_optimal_device()
            
            device_config = {}
            if model_type == 'openai/whisper':
                device_config['device'] = device
            
            return device_config, device
        
        # Step 2: Create model with device handling
        model_type = transcription_model
        # Use the provided model_config and add language settings
        final_model_config = model_config.copy()
        final_model_config.update({
            'source_language': source_language,
            'target_language': 'transcribe'
        })
        
        device_config, selected_device = get_model_device_config(model_type, device_preference)
        final_model_config.update(device_config)
        
        progress_placeholder.info(f"🤖 Creating model with device: {selected_device}")
        
        try:
            model = subs_ai.create_model(model_type, final_model_config)
        except Exception as model_error:
            # Handle GPU-specific errors and fallback to CPU
            error_msg = str(model_error).lower()
            if any(gpu_error in error_msg for gpu_error in ['cuda', 'gpu', 'device']):
                progress_placeholder.warning(f"⚠️ GPU model creation failed, falling back to CPU...")
                
                # Recreate model with CPU configuration
                cpu_config = final_model_config.copy()
                cpu_config['device'] = 'cpu'
                if 'device_index' in cpu_config:
                    del cpu_config['device_index']
                
                model = subs_ai.create_model(model_type, cpu_config)
                selected_device = 'cpu'
            else:
                raise model_error
        
        # Step 3: Transcribe the audio
        device_info = f"using {selected_device} device"
        progress_placeholder.info(f"🎙️ Transcribing audio ({source_language}) {device_info}...")
        
        try:
            base_subs = subs_ai.transcribe(file_path, model)
        except Exception as transcribe_error:
            # Handle transcription errors, particularly GPU-related ones
            error_msg = str(transcribe_error).lower()
            if any(gpu_error in error_msg for gpu_error in ['cuda', 'gpu', 'device', 'memory']):
                progress_placeholder.warning(f"⚠️ GPU transcription failed, retrying with CPU...")
                
                # Recreate model with CPU-only configuration
                cpu_config = final_model_config.copy()
                cpu_config['device'] = 'cpu'
                if 'device_index' in cpu_config:
                    del cpu_config['device_index']
                
                model = subs_ai.create_model(model_type, cpu_config)
                base_subs = subs_ai.transcribe(file_path, model)
                selected_device = 'cpu'
            else:
                raise transcribe_error
        
        # Step 4: Process each target language
        total_tasks = len(target_languages) * len(output_formats)
        completed_tasks = 0
        
        for target_language in target_languages:
            # Handle transcription vs translation
            if target_language == 'transcribe':
                current_subs = base_subs
                lang_suffix = source_language if source_language != 'auto' else 'original'
            else:
                # Translate to target language
                progress_placeholder.info(f"🌐 Translating to {target_language}...")
                
                try:
                    current_subs = tools.translate(
                        subs=base_subs,
                        source_language=source_language if source_language != 'auto' else 'auto',
                        target_language=target_language,
                        model=translation_model,
                        intermediate_language=intermediate_language
                    )
                except Exception as translation_error:
                    # Handle CUDA errors specifically
                    error_msg = str(translation_error).lower()
                    if any(cuda_error in error_msg for cuda_error in ['cuda', 'device-side assert', 'gpu']):
                        progress_placeholder.warning(f"⚠️ CUDA translation error, clearing memory and retrying...")
                        
                        # Force clear CUDA memory
                        try:
                            import torch
                            import gc
                            if torch.cuda.is_available():
                                torch.cuda.empty_cache()
                                torch.cuda.synchronize()
                                gc.collect()
                        except ImportError:
                            pass
                        
                        # Retry translation
                        current_subs = tools.translate(
                            subs=base_subs,
                            source_language=source_language if source_language != 'auto' else 'auto',
                            target_language=target_language,
                            model=translation_model,
                            intermediate_language=intermediate_language
                        )
                    else:
                        raise translation_error
                
                # Clear CUDA memory after translation to prevent device-side assert errors
                try:
                    import torch
                    import gc
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                        torch.cuda.synchronize()
                        gc.collect()
                except ImportError:
                    pass  # torch not available, skip CUDA cleanup
                
                lang_suffix = target_language
            
            # Generate files in each requested format
            for output_format in output_formats:
                progress_placeholder.info(f"📄 Generating {output_format.upper()} for {target_language}...")
                
                # Generate filename
                base_name = Path(filename).stem
                if len(target_languages) > 1 or target_languages[0] != 'transcribe':
                    generated_filename = f"{base_name}-{lang_suffix}.{output_format}"
                else:
                    generated_filename = f"{base_name}.{output_format}"
                
                # Generate subtitle content
                if output_format == 'ooona':
                    # Handle OOONA format conversion
                    try:
                        from subsai.storage.ooona_converter import create_ooona_converter
                        ooona_converter = create_ooona_converter()
                        if ooona_converter:
                            input_content = current_subs.to_string(format_='srt')
                            conversion_result = ooona_converter.convert_subtitle(input_content)
                            if conversion_result['success']:
                                subtitle_content = conversion_result['content']
                            else:
                                raise Exception(f"OOONA conversion failed: {conversion_result['message']}")
                        else:
                            raise Exception("OOONA converter not available")
                    except ImportError:
                        raise Exception("OOONA converter not available")
                else:
                    # Standard format
                    subtitle_content = current_subs.to_string(format_=output_format)
                
                # Store result
                result_info = {
                    'filename': generated_filename,
                    'format': output_format,
                    'language': target_language,
                    'content': subtitle_content,
                    'size': len(subtitle_content.encode('utf-8'))
                }
                
                # Handle local save
                if save_local:
                    try:
                        local_path = Path(filename).parent / generated_filename
                        with open(local_path, 'w', encoding='utf-8') as f:
                            f.write(subtitle_content)
                        result_info['local_path'] = str(local_path)
                    except Exception as e:
                        result_info['local_error'] = str(e)
                
                # Handle S3 upload
                if save_s3:
                    try:
                        from subsai.storage.s3_storage import create_s3_storage
                        s3_config = _get_s3_config_from_session_state()
                        s3_config['enabled'] = True
                        s3_storage = create_s3_storage(s3_config)
                        if s3_storage:
                            temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=f'.{output_format}')
                            temp_file.write(subtitle_content)
                            temp_file.close()
                            
                            s3_result = s3_storage.upload_subtitle_file(
                                file_path=temp_file.name,
                                project_name=s3_project,
                                custom_filename=generated_filename
                            )
                            if s3_result['success']:
                                result_info['s3_url'] = s3_result['s3_url']
                                result_info['s3_upload'] = True
                            else:
                                result_info['s3_error'] = s3_result['message']
                            
                            # Clean up temp file
                            Path(temp_file.name).unlink()
                        else:
                            result_info['s3_error'] = "S3 storage not configured"
                    except Exception as e:
                        result_info['s3_error'] = str(e)
                
                results.append(result_info)
                completed_tasks += 1
                
                # Update progress
                progress_percent = (completed_tasks / total_tasks) * 100
                progress_placeholder.progress(progress_percent / 100)
        
        # Step 5: Calculate processing time and track completion
        processing_time = time.time() - start_time
        
        # Track successful completion
        if analytics.is_enabled():
            analytics.track_transcription_complete(
                user_id=user.id,
                filename=filename,
                model=transcription_model,
                processing_time=processing_time,
                success=True
            )
            
            # Record comprehensive file analytics
            analytics.record_file_processing(
                user_id=user.id,
                filename=filename,
                file_size=file_size,
                model_used=transcription_model,
                processing_time=processing_time,
                success=True,
                source_language=source_language,
                target_languages=[lang for lang in target_languages if lang != 'transcribe'],
                output_formats=output_formats
            )
            
            # Track translations
            for target_lang in target_languages:
                if target_lang != 'transcribe':
                    analytics.track_translation(
                        user_id=user.id,
                        filename=filename,
                        source_lang=source_language,
                        target_lang=target_lang
                    )
        
        progress_placeholder.success(f"✅ Processing completed successfully! Generated {len(results)} files in {processing_time:.2f} seconds")
        
        return {
            'success': True,
            'results': results,
            'processing_time': processing_time,
            'device_used': selected_device,
            'base_subs': base_subs  # Include the base SSAFile object for legacy compatibility
        }
        
    except Exception as e:
        processing_time = time.time() - start_time
        
        # Track error
        if analytics.is_enabled():
            analytics.track_transcription_complete(
                user_id=user.id,
                filename=filename,
                model=transcription_model,
                processing_time=processing_time,
                success=False,
                error_message=str(e)
            )
            
            analytics.track_error(
                user_id=user.id,
                error_type='single_file_processing_error',
                error_message=str(e),
                filename=filename
            )
        
        progress_placeholder.error(f"❌ Processing failed: {str(e)}")
        
        return {
            'success': False,
            'error': str(e),
            'processing_time': processing_time
        }


def _subs_df(subs):
    """
    helper function that returns a :class:`pandas.DataFrame` from subs object

    :param subs: subtitles

    :return::class:`pandas.DataFrame`
    """
    sub_table = []
    if subs is not None:
        for sub in subs:
            row = [ms_to_str(sub.start, fractions=True), ms_to_str(sub.end, fractions=True), sub.text]
            sub_table.append(row)

    df = pd.DataFrame(sub_table, columns=['Start time', 'End time', 'Text'])
    return df

def webui() -> None:
    """
    main web UI with authentication
    :return: None
    """
    # Initialize authentication
    auth = AuthUtils.init_auth()
    
    # Check authentication status
    if not auth.is_authenticated():
        render_login_page()
        return
    
    # Get current user
    user = auth.get_current_user()
    if not user:
        st.error("Authentication error. Please refresh the page.")
        return
    
    # Set page config
    st.set_page_config(
        page_title=f'AION SRT - {user.username}',
        page_icon="🎞️",
        menu_items={
            'About': f"### AION SRT - AI-Powered Subtitle Generation \nv{__version__} "
                     f"\n \nEffortless SRT Subtitling for your content"
                     f"\n \n🌐 Visit: https://aionvoice.ai"
                     f"\n📧 Contact: hello@aionvoice.ai"
                     f"\n \nLicense: GPLv3"
        },
        layout="wide",
        initial_sidebar_state='auto'
    )
    
    # Navigation
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "dashboard"
    
    # Sidebar navigation
    with st.sidebar:
        # Display AION logo
        try:
            logo_path = "https://img1.wsimg.com/isteam/ip/9c622456-5f71-4284-96ff-893018ba6b31/blob-79abe2c.png"
            st.image(logo_path, width=150)
        except Exception:
            st.title("🎞️ AION SRT")
        
        # User info
        AuthUtils.show_user_info(user, "_nav")
        
        # Navigation menu
        st.subheader("📍 Navigation")
        
        pages = {
            "dashboard": "👋 Dashboard",
            "single_file": "📝 Single File SRT",
            "batch_processing": "🔄 Batch SRT Processing"
        }
        
        # Add admin page for admin users
        if user.role == "admin":
            pages["admin"] = "🔧 Admin Panel"
        
        for page_key, page_label in pages.items():
            if st.button(page_label, key=f"nav_{page_key}", use_container_width=True):
                st.session_state.current_page = page_key
                st.experimental_rerun()
    
    # Render appropriate page
    if st.session_state.current_page == "dashboard":
        render_user_dashboard()
    elif st.session_state.current_page == "admin" and user.role == "admin":
        render_admin_panel()
    elif st.session_state.current_page == "single_file":
        render_single_file_processing(user)
    elif st.session_state.current_page == "batch_processing":
        render_batch_processing_with_auth(user)
    else:
        st.session_state.current_page = "dashboard"
        st.experimental_rerun()


@require_auth
def render_single_file_processing(user):
    """
    Render single file processing page with user authentication
    """
    st.title("📝 AION SRT - Single File Processing")
    st.info("🎯 Upload your media file and generate professional subtitles in seconds with ultra-fast AI transcription. Perfect for content creators and professionals.")
    
    if 'transcribed_subs' in st.session_state:
        subs = st.session_state['transcribed_subs']
    else:
        subs = None

    notification_placeholder = st.empty()
    
    # User-specific project selection
    auth = AuthUtils.init_auth()
    user_projects = auth.auth.db.get_user_projects(user.id)
    
    if user_projects:
        st.subheader("📋 Select Project")
        project_options = {"None": None}
        for project in user_projects:
            project_options[project.name] = project.id
        
        selected_project_name = st.selectbox(
            "Choose a project for this transcription",
            options=list(project_options.keys()),
            help="Associate this transcription with one of your projects"
        )
        selected_project_id = project_options[selected_project_name]
        st.session_state['selected_project_id'] = selected_project_id
        
        if selected_project_id:
            project = auth.auth.db.get_project_by_id(selected_project_id, user.id)
            if project:
                st.info(f"📋 Working on project: **{project.name}**")
    
    with st.sidebar:
        st.title("AION SRT Settings")
    
    with st.expander('📁 Media File', expanded=True):
        file_mode = st.selectbox("Select file mode", ['Local path', 'Upload'], index=0,
                                 help='Use `Local Path` if you are on a local machine, or use `Upload` to '
                                      'upload your files if you are using a remote server')
        if file_mode == 'Local path':
            file_path = st.text_input('Media file path', help='Absolute path of the media file')
        else:
            uploaded_file = st.file_uploader("Choose a media file")
            if uploaded_file is not None:
                # Store uploaded file info for managed cleanup
                st.session_state['uploaded_file'] = uploaded_file
                file_path = "uploaded_file"  # Placeholder - will be handled by managed context
            else:
                file_path = ""

        st.session_state['file_path'] = file_path

    # Processing Configuration
    with st.expander("⚙️ Processing Configuration", expanded=False):
        from subsai.utils import get_available_devices, is_cuda_available
        
        col_device1, col_device2 = st.columns(2)
        
        with col_device1:
            available_devices = get_available_devices()
            device_options = ['auto'] + available_devices
            
            current_device = st.session_state.get('single_device_preference', 'auto')
            device_preference = st.selectbox(
                "Processing Device",
                options=device_options,
                index=device_options.index(current_device) if current_device in device_options else 0,
                help="Choose processing device: 'auto' for optimal selection, 'cpu' for CPU-only, or specific CUDA device",
                key="single_device_select"
            )
            
            st.session_state['single_device_preference'] = device_preference
        
        with col_device2:
            # Show device status
            cuda_available = is_cuda_available()
            if cuda_available:
                st.success("✅ CUDA GPU Available")
                import torch
                if torch.cuda.is_available():
                    gpu_count = torch.cuda.device_count()
                    st.info(f"🔧 {gpu_count} GPU(s) detected")
            else:
                st.warning("⚠️ CUDA not available - using CPU")
                
            # Show current device selection
            if device_preference == 'auto':
                optimal_device = 'cuda:0' if cuda_available else 'cpu'
                st.info(f"🎯 Auto-selected: {optimal_device}")
            else:
                st.info(f"🎯 Selected: {device_preference}")

    # Language Configuration
    with st.expander("🌐 Language Configuration", expanded=True):
        # First row: Source and Bridge language
        col1, col2 = st.columns(2)
        
        with col1:
            source_language = st.selectbox(
                "Source language",
                options=['auto', 'en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh', 'ar', 'he', 'hi', 'tr', 'pl', 'nl', 'sv', 'da', 'no', 'fi'],
                index=0,
                help="Language of the input audio/video file"
            )
        
        with col2:
            intermediate_language = st.selectbox(
                "Bridge language (optional)",
                options=['none', 'en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh', 'ar', 'he', 'hi', 'tr', 'pl', 'nl', 'sv', 'da', 'no', 'fi'],
                index=0,
                help="Optional intermediate language for improved translation quality. Leave as 'none' for direct translation."
            )
        
        # Second row: Target languages
        target_languages = st.multiselect(
            "Target languages",
            options=['transcribe', 'en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh', 'ar', 'he', 'hi', 'tr', 'pl', 'nl', 'sv', 'da', 'no', 'fi'],
            default=['transcribe'],
            help="Languages to transcribe/translate to ('transcribe' = same as source)"
        )

    # Transcription Model Configuration
    with st.expander("🎙️ Transcription Model Configuration", expanded=True):
        available_models = subs_ai.available_models()
        whisper_models = [model for model in available_models if model == 'openai/whisper']
        
        transcription_model = st.selectbox(
            "Transcription model",
            options=whisper_models,
            index=0,  # Default to first Whisper model
            help="AI model to use for speech-to-text transcription. Large models provide better accuracy but require more memory."
        )
        
        # Show model information
        try:
            model_info = subs_ai.model_info(transcription_model)
            st.info(f"📋 {model_info['description'][:100]}...")
        except Exception:
            pass
        
        # Show model-specific configuration if available
        try:
            config_schema = subs_ai.config_schema(transcription_model)
            if 'model_type' in config_schema:
                model_type_config = config_schema['model_type']
                if len(model_type_config['options']) > 1:
                    selected_model_size = st.selectbox(
                        "Model size",
                        options=model_type_config['options'],
                        index=model_type_config['options'].index(model_type_config['default']),
                        help="Model size affects accuracy and processing speed. Larger models are more accurate but slower."
                    )
                else:
                    selected_model_size = model_type_config['default']
                    st.info(f"Model size: {selected_model_size}")
        except Exception:
            selected_model_size = None

    # Translation Model Configuration
    with st.expander("🔄 Translation Configuration", expanded=False):
        from subsai.utils import available_translation_models
        
        try:
            translation_models = available_translation_models()
        except Exception as e:
            st.error(f"Error loading translation models: {e}")
            translation_models = ["deepseek-r1:1.5b"]
        
        translation_model = st.selectbox(
            "Translation model",
            options=translation_models,
            index=0,  # DeepSeek R1 is always first
            help="AI model to use for translation (only used when translating to different languages)"
        )
        
        if translation_model != "deepseek-r1:1.5b":
            st.info(f"Using {translation_model} for translation")

    # Output Configuration
    with st.expander("📄 Output Configuration", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            output_formats = st.multiselect(
                "Output formats",
                options=['srt', 'vtt', 'ass', 'sub', 'ooona'],
                default=['srt', 'ooona'],
                help="Subtitle formats to generate"
            )
        
        with col2:
            # Storage options
            st.write("**Storage Options**")
            enable_download = st.checkbox("Enable download", value=True, help="Provide download buttons for generated files")
            save_local = st.checkbox("Save locally", value=False, help="Save files to local directory")
            save_s3 = st.checkbox("Save to S3", value=False, help="Upload files to S3 bucket (requires S3 configuration)")
            
            if save_s3:
                s3_project = st.text_input(
                    "S3 Project folder",
                    value="single-file-processing",
                    help="Folder name in S3 bucket"
                )

    # S3 Configuration Panel
    with st.sidebar.expander('S3 Storage', expanded=False):
            _init_s3_config()
            s3_enabled = _render_s3_config_ui()

    # OOONA Configuration Panel
    with st.sidebar.expander('OOONA API', expanded=False):
            ooona_enabled = st.checkbox(
                "Enable OOONA Format", 
                value=st.session_state.get('ooona_enabled', True),
                help="Enable OOONA API for .ooona format conversion (requires environment variables)",
                key='ooona_enabled'
            )
            if ooona_enabled:
                st.info("💡 OOONA API credentials should be set as environment variables:\n"
                       "- OOONA_BASE_URL\n"
                       "- OOONA_CLIENT_ID\n"
                       "- OOONA_CLIENT_SECRET\n"
                       "- OOONA_API_KEY\n"
                       "- OOONA_API_NAME")

    # DeepSeek API Configuration Panel
    with st.sidebar.expander('DeepSeek API Translation', expanded=False):
            _init_deepseek_api_config()
            deepseek_api_enabled = _render_deepseek_api_config_ui()

    # Validation before processing
    if not target_languages:
        st.error("Please select at least one target language")
        return
    
    if not output_formats:
        st.error("Please select at least one output format")
        return
    
    if not any([enable_download, save_local, save_s3]):
        st.error("Please select at least one storage option")
        return

    process_button = st.button('🚀 Process File', type='primary')
    progress_placeholder = st.empty()
    results_placeholder = st.empty()

    # Show persistent Download All button if results exist
    if 'single_file_results' in st.session_state and st.session_state['single_file_results']:
        st.subheader("📦 Previous Results")
        col_download_all, col_clear = st.columns([2, 1])
        
        with col_download_all:
            try:
                results = st.session_state['single_file_results']
                base_filename = st.session_state.get('single_file_base_filename', 'subtitles')
                zip_content = _create_single_file_download_zip(results, base_filename)
                import datetime
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                zip_filename = f"{Path(base_filename).stem}_subtitles_{timestamp}.zip"
                
                st.download_button(
                    f"📦 Download All Previous Results ({len(results)} files)",
                    data=zip_content,
                    file_name=zip_filename,
                    mime="application/zip",
                    help=f"Download all {len(results)} previously generated files as a ZIP archive"
                )
            except Exception as e:
                st.error(f"Error creating download: {e}")
        
        with col_clear:
            if st.button("🗑️ Clear Results"):
                del st.session_state['single_file_results']
                if 'single_file_base_filename' in st.session_state:
                    del st.session_state['single_file_base_filename']
                st.experimental_rerun()
        
        st.write("---")

    if process_button:
        # Clear previous results when starting new processing
        if 'single_file_results' in st.session_state:
            del st.session_state['single_file_results']
        if 'single_file_base_filename' in st.session_state:
            del st.session_state['single_file_base_filename']
        
        # Validate file input
        if not file_path:
            st.error("Please select a media file")
            return
        
        # Handle different file modes
        if file_mode == 'Local path':
            # Use local file path directly
            actual_file_path = file_path
            file_size = os.path.getsize(actual_file_path) if os.path.exists(actual_file_path) else 0
            filename = os.path.basename(actual_file_path)
        else:
            # Use uploaded file with managed cleanup
            if 'uploaded_file' in st.session_state:
                uploaded_file = st.session_state['uploaded_file']
                filename = uploaded_file.name
                file_size = len(uploaded_file.getbuffer())
            else:
                st.error("No file uploaded")
                return
        
        # Prepare transcription model configuration
        model_config = {}
        if 'selected_model_size' in locals() and selected_model_size:
            model_config['model_type'] = selected_model_size
        
        # Process the file with the new batch processing workflow
        if file_mode == 'Local path':
            result = _process_single_file_with_batch_flow(
                file_path=actual_file_path,
                filename=filename,
                file_size=file_size,
                source_language=source_language,
                target_languages=target_languages,
                output_formats=output_formats,
                device_preference=device_preference,
                translation_model=translation_model,
                transcription_model=transcription_model,
                model_config=model_config,
                enable_download=enable_download,
                save_local=save_local,
                save_s3=save_s3,
                s3_project=s3_project if save_s3 else None,
                progress_placeholder=progress_placeholder,
                results_placeholder=results_placeholder,
                user=user,
                intermediate_language=intermediate_language if intermediate_language != 'none' else None
            )
        else:
            # Use managed temp file with automatic cleanup
            with managed_temp_file(uploaded_file=uploaded_file) as temp_file_path:
                result = _process_single_file_with_batch_flow(
                    file_path=temp_file_path,
                    filename=filename,
                    file_size=file_size,
                    source_language=source_language,
                    target_languages=target_languages,
                    output_formats=output_formats,
                    device_preference=device_preference,
                    translation_model=translation_model,
                    transcription_model=transcription_model,
                    model_config=model_config,
                    enable_download=enable_download,
                    save_local=save_local,
                    save_s3=save_s3,
                    s3_project=s3_project if save_s3 else None,
                    progress_placeholder=progress_placeholder,
                    results_placeholder=results_placeholder,
                    user=user,
                    intermediate_language=intermediate_language if intermediate_language != 'none' else None
                )
        
        # Display results
        if result['success']:
            # Store results in session state for Download All functionality
            st.session_state['single_file_results'] = result['results']
            st.session_state['single_file_base_filename'] = filename
            
            with results_placeholder.container():
                st.success(f"🎉 Processing completed successfully!")
                st.info(f"⏱️ Processing time: {result['processing_time']:.2f} seconds")
                st.info(f"🔧 Device used: {result['device_used']}")
                
                # Display generated files
                st.subheader("📄 Generated Files")
                
                # Add Download All button first
                if len(result['results']) > 1:
                    col_download_all, col_spacer = st.columns([1, 3])
                    with col_download_all:
                        try:
                            zip_content = _create_single_file_download_zip(result['results'], filename)
                            import datetime
                            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                            zip_filename = f"{Path(filename).stem}_subtitles_{timestamp}.zip"
                            
                            st.download_button(
                                f"📦 Download All ({len(result['results'])} files)",
                                data=zip_content,
                                file_name=zip_filename,
                                mime="application/zip",
                                help=f"Download all {len(result['results'])} generated files as a ZIP archive"
                            )
                        except Exception as e:
                            st.error(f"Error creating download: {e}")
                    
                    st.write("---")
                
                for file_result in result['results']:
                    col1, col2, col3 = st.columns([2, 1, 1])
                    
                    with col1:
                        st.write(f"**{file_result['filename']}**")
                        st.write(f"📊 {file_result['format'].upper()} • {file_result['language']} • {file_result['size']:,} bytes")
                        
                        # Show storage status
                        if file_result.get('local_path'):
                            st.success(f"💾 Saved locally: {file_result['local_path']}")
                        elif file_result.get('local_error'):
                            st.error(f"❌ Local save failed: {file_result['local_error']}")
                        
                        if file_result.get('s3_upload'):
                            st.success(f"☁️ Uploaded to S3: {file_result['s3_url']}")
                        elif file_result.get('s3_error'):
                            st.error(f"❌ S3 upload failed: {file_result['s3_error']}")
                    
                    with col2:
                        if enable_download:
                            st.download_button(
                                "📥 Download",
                                data=file_result['content'],
                                file_name=file_result['filename'],
                                mime='text/plain',
                                key=f"download_{file_result['filename']}"
                            )
                    
                    with col3:
                        # Download analytics tracking
                        if analytics.is_enabled():
                            analytics.track_download(
                                user_id=user.id,
                                filename=file_result['filename'],
                                format=file_result['format'],
                                file_size=file_result['size']
                            )
                
                # Store results for legacy compatibility
                if result['results'] and 'base_subs' in result:
                    # Store the base SSAFile object for legacy compatibility
                    st.session_state['transcribed_subs'] = result['base_subs']
        else:
            # Clear results on failure
            if 'single_file_results' in st.session_state:
                del st.session_state['single_file_results']
            if 'single_file_base_filename' in st.session_state:
                del st.session_state['single_file_base_filename']
            
            with results_placeholder.container():
                st.error(f"❌ Processing failed: {result['error']}")
                st.info(f"⏱️ Processing time: {result['processing_time']:.2f} seconds")

def run():
    if runtime.exists():
        webui()
    else:
        # Configure Streamlit for large file uploads and batch processing
        sys.argv = [
            "streamlit", "run", __file__, 
            "--theme.base", "dark",
            "--server.address", "0.0.0.0",  # Bind to all interfaces for Docker
            "--server.maxUploadSize", "10000",  # 10GB upload limit
            "--server.maxMessageSize", "10000",  # 10GB message size limit
            "--browser.gatherUsageStats", "false"
        ] + sys.argv
        sys.exit(stcli.main())


if __name__ == '__main__':
    run()
