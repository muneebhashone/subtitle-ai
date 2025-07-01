#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
AI Transcription Tool Web User Interface (webui)
"""

import importlib
import json
import mimetypes
import os
import os.path
import shutil
import sys
import tempfile
from base64 import b64encode
from pathlib import Path

import pandas as pd
import streamlit as st
from pysubs2.time import ms_to_str, make_time
from streamlit import runtime
from streamlit_player import st_player
from st_aggrid import AgGrid, GridUpdateMode, GridOptionsBuilder, DataReturnMode

from subsai import SubsAI, Tools
from subsai.configs import ADVANCED_TOOLS_CONFIGS, DEFAULT_S3_CONFIG, S3_CONFIG_SCHEMA
from subsai.utils import available_subs_formats
from subsai.storage.s3_storage import create_s3_storage
from subsai.batch_processor import BatchProcessor, JobStatus, JobConfig
from subsai.auth.decorators import AuthUtils, require_auth, require_admin
from subsai.auth.pages import render_login_page, render_user_dashboard, render_admin_panel
from streamlit.web import cli as stcli
from tempfile import NamedTemporaryFile
import time

__author__ = "hashone"
__contact__ = ""
__copyright__ = "Copyright 2025,"
__deprecated__ = False
__license__ = "GPLv3"
__version__ = importlib.metadata.version('subsai')

subs_ai = SubsAI()
tools = Tools()


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
    
    # Add environment variables
    config['bucket_name'] = os.getenv('AWS_BUCKET_NAME', '')
    config['region'] = os.getenv('AWS_REGION', 'us-east-1')
    config['access_key'] = os.getenv('AWS_ACCESS_KEY')
    config['secret_key'] = os.getenv('AWS_SECRET_KEY')
    
    return config




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

@require_auth
def render_batch_processing_with_auth(user):
    """
    Render batch processing with user authentication
    """
    # Initialize batch processor in session state
    if 'batch_processor' not in st.session_state:
        st.session_state.batch_processor = BatchProcessor()
    
    render_batch_processing_ui(st.session_state.batch_processor, subs_ai, user)


def render_batch_processing_ui(batch_processor: BatchProcessor, subs_ai: SubsAI, user=None):
    """
    Render UI for batch processing of multiple files.
    """
    st.title("🔄 Batch Processing")
    st.info("📁 Upload multiple media files and configure each one independently. Files larger than 10GB are supported!")
    
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
        col1, col2, col3 = st.columns(3)
        
        with col1:
            bulk_source_language = st.selectbox(
                "Default source language",
                options=['auto', 'en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh', 'ar', 'he', 'hi', 'tr', 'pl', 'nl', 'sv', 'da', 'no', 'fi'],
                index=0
            )
        
        with col2:
            bulk_target_languages = st.multiselect(
                "Default target languages",
                options=['transcribe', 'en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh', 'ar', 'he', 'hi', 'tr', 'pl', 'nl', 'sv', 'da', 'no', 'fi'],
                default=['transcribe']
            )
        
        with col3:
            bulk_formats = st.multiselect(
                "Default output formats",
                options=['srt', 'vtt', 'ass', 'sub', 'ooona'],
                default=['srt', 'ooona']
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
                s3_config = get_s3_config()
                if s3_config.get('bucket_name'):
                    st.info(f"📍 S3 Path: `{s3_config['bucket_name']}/{batch_s3_project}/`")
        
        st.write("**Individual File Configuration**")
        
        # Store temp files and configs
        if 'temp_files' not in st.session_state:
            st.session_state.temp_files = []
        
        # Clear old temp files
        st.session_state.temp_files = []
        
        # Configuration per file
        for i, uploaded_file in enumerate(uploaded_files):
            file_id = f"file-{i}-{uploaded_file.name}"
            
            # Handle file size safely
            file_size_mb = "Unknown"
            if hasattr(uploaded_file, 'size') and uploaded_file.size is not None:
                file_size_mb = f"{uploaded_file.size / (1024*1024):.1f} MB"
            
            with st.expander(f"📄 {uploaded_file.name} ({file_size_mb})", expanded=not use_bulk_config):
                # Save file temporarily
                temp_dir = tempfile.TemporaryDirectory()
                temp_file_path = os.path.join(temp_dir.name, uploaded_file.name)
                with open(temp_file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # Store temp file info
                st.session_state.temp_files.append({
                    'name': uploaded_file.name,
                    'path': temp_file_path,
                    'size': uploaded_file.size,
                    'temp_dir': temp_dir
                })
                
                if use_bulk_config:
                    source_language = bulk_source_language
                    target_languages = bulk_target_languages
                    formats = bulk_formats
                    st.info(f"Using bulk configuration: {source_language} → {target_languages} → {formats}")
                else:
                    # Individual configuration
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        source_language = st.selectbox(
                            "Source language",
                            options=['auto', 'en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh', 'ar', 'he', 'hi', 'tr', 'pl', 'nl', 'sv', 'da', 'no', 'fi'],
                            index=0, key=f"source-lang-{file_id}"
                        )
                    
                    with col2:
                        target_languages = st.multiselect(
                            "Target languages",
                            options=['transcribe', 'en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh', 'ar', 'he', 'hi', 'tr', 'pl', 'nl', 'sv', 'da', 'no', 'fi'],
                            default=bulk_target_languages, key=f"target-lang-{file_id}"
                        )
                    
                    with col3:
                        formats = st.multiselect(
                            "Output formats",
                            options=['srt', 'vtt', 'ass', 'sub', 'ooona'],
                            default=bulk_formats, key=f"format-{file_id}"
                        )
        
        # Action buttons
        col1, col2, col3 = st.columns(3)
        
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
                        else:
                            file_id = f"file-{i}-{file_info['name']}"
                            job_source_language = st.session_state.get(f"source-lang-{file_id}", 'auto')
                            job_target_languages = st.session_state.get(f"target-lang-{file_id}", ['transcribe'])
                            job_formats = st.session_state.get(f"format-{file_id}", ['srt'])
                        
                        # Prepare export options for S3
                        export_options = {}
                        if batch_s3_upload:
                            export_options['s3_upload'] = True
                            export_options['s3_project_folder'] = batch_s3_project
                        
                        batch_processor.add_job(
                            file_path=file_info['path'],
                            file_name=file_info['name'],
                            file_size=file_info['size'],
                            source_language=job_source_language,
                            target_languages=job_target_languages,
                            output_formats=job_formats,
                            export_options=export_options
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
            if st.button("🗑️ Clear Completed", disabled=batch_processor.is_processing()):
                batch_processor.clear_completed()
                st.success("Cleared completed jobs")
                st.experimental_rerun()


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
    st.subheader("📊 Batch Processing Dashboard")
    
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

@st.cache_resource
def _create_translation_model(model_name: str):
    """
    Returns a translation model and caches it

    :param model_name: name of the model
    :param model_config: configs

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


footer = """
<style>
    #page-container {
      position: relative;
    }

    footer{
        visibility:hidden;
    }

    .footer {
    position: relative;
    left: 0;
    top:230px;
    bottom: 0;
    width: 100%;
    background-color: transparent;
    color: #808080; /* theme's text color hex code at 50 percent brightness*/
    text-align: left; /* you can replace 'left' with 'center' or 'right' if you want*/
    }
</style>

<div id="page-container">
    <div class="footer">
        <p style='font-size: 0.875em;'>
        Made with ❤</p>
    </div>
</div>
"""


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
        page_title=f'SubsAI - {user.username}',
        page_icon="🎞️",
        menu_items={
            'About': f"### AI Transcription Tool \nv{__version__} "
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
        st.title("🎞️ SubsAI")
        
        # User info
        AuthUtils.show_user_info(user, "_nav")
        
        # Navigation menu
        st.subheader("📍 Navigation")
        
        pages = {
            "dashboard": "👋 Dashboard",
            "single_file": "📝 Single File",
            "batch_processing": "🔄 Batch Processing"
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
    st.title("📝 Single File Processing")
    st.info("🎯 Upload or select a single media file for transcription and subtitle generation.")
    
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
        st.title("Settings")
    
    with st.expander('Media file', expanded=True):
        file_mode = st.selectbox("Select file mode", ['Local path', 'Upload'], index=0,
                                 help='Use `Local Path` if you are on a local machine, or use `Upload` to '
                                      'upload your files if you are using a remote server')
        if file_mode == 'Local path':
            file_path = st.text_input('Media file path', help='Absolute path of the media file')
        else:
            uploaded_file = st.file_uploader("Choose a media file")
            if uploaded_file is not None:
                temp_dir = tempfile.TemporaryDirectory()
                tmp_dir_path = temp_dir.name
                file_path = os.path.join(tmp_dir_path, uploaded_file.name)
                file = open(file_path, "wb")
                file.write(uploaded_file.getbuffer())
            else:
                file_path = ""

        st.session_state['file_path'] = file_path

    stt_model_name = st.selectbox("Select Model", subs_ai.available_models(), index=0,
                                  help='Select an AI model to use for '
                                       'transcription')

    with st.sidebar.expander('Model Description', expanded=True):
            info = subs_ai.model_info(stt_model_name)
            st.info(info['description'] + '\n' + info['url'])
            st.info('💡 **Simplified UX**: This tool now focuses on the essential options for a clean user experience. Source and target language settings are the only required configurations.')

    configs_mode = st.selectbox("Select Configs Mode", ['Manual', 'Load from local file'], index=0,
                                help='Play manually with the model configs or load them from an exported json file.')

    with st.sidebar.expander('Model Configs', expanded=False):
            config_schema = SubsAI.config_schema(stt_model_name)

            if configs_mode == 'Manual':
                _generate_config_ui(stt_model_name, config_schema)
            else:
                configs_path = st.text_input('Configs path', help='Absolute path of the configs file')

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

    transcribe_button = st.button('Transcribe', type='primary')
    transcribe_loading_placeholder = st.empty()

    if transcribe_button:
        config_schema = SubsAI.config_schema(stt_model_name)
        if configs_mode == 'Manual':
            model_config = _get_config_from_session_state(stt_model_name, config_schema, notification_placeholder)
        else:
            with open(configs_path, 'r', encoding='utf-8') as f:
                model_config = json.load(f)
        subs = _transcribe(file_path, stt_model_name, model_config)
        st.session_state['transcribed_subs'] = subs
        transcribe_loading_placeholder.success('Done!', icon="✅")

    with st.expander('Post Processing Tools', expanded=False):
        basic_tool = st.selectbox('Basic tools', options=['', 'Set time', 'Shift'],
                                  help="Basic tools to modify subtitles")
        if basic_tool == 'Set time':
            st.info('Set subtitle time')
            sub_index = st.selectbox('Subtitle index', options=range(len(subs)))
            time_to_change = st.radio('Select what you want to modify', options=['Start time', 'End time'])
            h_col, m_col, s_col, ms_col = st.columns([1, 1, 1, 1])
            with h_col:
                h = st.number_input('h')
            with m_col:
                m = st.number_input('m')
            with s_col:
                s = st.number_input('s')
            with ms_col:
                ms = st.number_input('ms')
            submit = st.button('Modify')
            if submit:
                if time_to_change == 'Start time':
                    subs[sub_index].start = make_time(h, m, s, ms)
                elif time_to_change == 'End time':
                    subs[sub_index].end = make_time(h, m, s, ms)
                st.session_state['transcribed_subs'] = subs

        elif basic_tool == 'Shift':
            st.info('Shift all subtitles by constant time amount')
            h_col, m_col, s_col, ms_col, frames_col, fps_col = st.columns([1, 1, 1, 1, 1, 1])
            with h_col:
                h = st.number_input('h', key='h')
            with m_col:
                m = st.number_input('m', key='m')
            with s_col:
                s = st.number_input('s', key='s')
            with ms_col:
                ms = st.number_input('ms', key='ms')
            with frames_col:
                frames = st.number_input('frames')
            with fps_col:
                fps = st.number_input('fps')
            submit = st.button('Shift')
            if submit:
                subs.shift(h, m, s, ms, frames=None if frames == 0 else frames, fps=None if fps == 0 else fps)
                st.session_state['transcribed_subs'] = subs
        advanced_tool = st.selectbox('Advanced tools', options=['', *list(ADVANCED_TOOLS_CONFIGS.keys())],
                                     help='some post processing tools')
        if advanced_tool == 'Translation':
            st.info('Translate subtitles using DeepSeek-R1 1.5B AI translation model')
            
            # Simple language selection
            available_languages = [
                'Auto-detect', 'English', 'Spanish', 'French', 'German', 'Italian', 'Portuguese', 
                'Russian', 'Japanese', 'Korean', 'Chinese', 'Arabic', 'Hebrew', 'Hindi', 'Turkish', 
                'Polish', 'Dutch', 'Swedish', 'Danish', 'Norwegian', 'Finnish'
            ]
            
            source_language = st.selectbox('Source language', options=available_languages, index=0)
            target_language = st.selectbox('Target language', options=available_languages[1:], index=0)  # Exclude auto-detect for target
            
            # Auto initialize the model using DeepSeek-R1
            if 'translation_model' not in st.session_state:
                if st.button('Initialize Translation Model'):
                    with st.spinner("Initializing DeepSeek-R1 1.5B translation model..."):
                        try:
                            translation_model = _create_translation_model('deepseek-r1:1.5b')
                            st.session_state['translation_model'] = translation_model
                            st.success('✅ DeepSeek-R1 1.5B model initialized successfully!')
                        except Exception as e:
                            st.error(f'Failed to initialize translation model: {e}')
            
            if 'translation_model' in st.session_state:
                b1, b2 = st.columns([1, 1])
                with b1:
                    submitted = st.button("Translate")
                    if submitted:
                        if 'transcribed_subs' not in st.session_state:
                            st.error('No subtitles to translate')
                        else:
                            with st.spinner("Translating with DeepSeek-R1..."):
                                try:
                                    translated_subs = tools.translate(subs=subs,
                                                                      source_language=source_language,
                                                                      target_language=target_language,
                                                                      model=st.session_state['translation_model'])
                                    st.session_state['original_subs'] = st.session_state['transcribed_subs']
                                    st.session_state['transcribed_subs'] = translated_subs
                                    notification_placeholder.success('Translation completed successfully!', icon="✅")
                                except Exception as e:
                                    st.error(f'Translation failed: {e}')
                with b2:
                    reload_transcribed_subs = st.button('Reload Original subtitles')
                    if reload_transcribed_subs:
                        if 'original_subs' in st.session_state:
                            st.session_state['transcribed_subs'] = st.session_state['original_subs']
                        else:
                            st.error('Original subs are already loaded')

        if advanced_tool == 'ffsubsync':
            configs = ADVANCED_TOOLS_CONFIGS[advanced_tool]
            description = configs['description'] + '\n\nURL: ' + configs['url']
            config_schema = configs['config_schema']
            st.info(description)
            _generate_config_ui(advanced_tool, config_schema)
            ffsubsync_config = _get_config_from_session_state(advanced_tool, config_schema, notification_placeholder)
            submitted = st.button("ffsubsync")
            if submitted:
                with st.spinner("Processing (This may take a while) ..."):
                    synced_subs = tools.auto_sync(subs, file_path, **ffsubsync_config)
                    st.session_state['original_subs'] = st.session_state['transcribed_subs']
                    st.session_state['transcribed_subs'] = synced_subs
                notification_placeholder.success('Success!', icon="✅")

    subs_column, video_column = st.columns([4, 3])

    with subs_column:
        if 'transcribed_subs' in st.session_state:
            df = _subs_df(st.session_state['transcribed_subs'])
        else:
            df = pd.DataFrame()
        gb = GridOptionsBuilder()
        # customize gridOptions
        gb.configure_default_column(groupable=False, value=True, enableRowGroup=True, editable=True)

        gb.configure_column("Start time", type=["customDateTimeFormat"],
                            custom_format_string='HH:mm:ss', pivot=False, editable=False)
        gb.configure_column("End time", type=["customDateTimeFormat"],
                            custom_format_string='HH:mm:ss', pivot=False, editable=False)
        gb.configure_column("Text", type=["textColumn"], editable=True)

        gb.configure_grid_options(domLayout='normal', allowContextMenuWithControlKey=False, undoRedoCellEditing=True, )
        gb.configure_selection(use_checkbox=False)

        gridOptions = gb.build()

        returned_grid = AgGrid(df,
                               height=500,
                               width='100%',
                               fit_columns_on_grid_load=True,
                               theme="alpine",
                               update_on=['rowValueChanged'],
                               update_mode=GridUpdateMode.VALUE_CHANGED,
                               data_return_mode=DataReturnMode.AS_INPUT,
                               try_to_convert_back_to_original_types=False,
                               gridOptions=gridOptions)

        # change subs
        if len(returned_grid['selected_rows']) != 0:
            st.session_state['selected_row_idx'] = returned_grid.selected_rows[0]['_selectedRowNodeInfo'][
                'nodeRowIndex']
            try:
                selected_row = returned_grid['selected_rows'][0]
                changed_sub_index = selected_row['_selectedRowNodeInfo']['nodeRowIndex']
                changed_sub_text = selected_row['Text']
                subs = st.session_state['transcribed_subs']
                subs[changed_sub_index].text = changed_sub_text
                st.session_state['transcribed_subs'] = subs
            except Exception as e:
                print(e)
                notification_placeholder.error('Error parsing subs!', icon="🚨")

    with video_column:
        if subs is not None:
            subs = st.session_state['transcribed_subs']
            vtt_subs = _vtt_base64(subs.to_string(format_='vtt'))
        else:
            vtt_subs = ""

        options = {
            "playback_rate": 1,
            'config': {
                'file': {
                    'attributes': {
                        'crossOrigin': 'true'
                    },
                    'tracks': [
                        {'kind': 'subtitles',
                         'src': vtt_subs,
                         'srcLang': 'default', 'default': 'true'},
                    ]
                }}
        }

        if 'file_path' in st.session_state and st.session_state['file_path'] != '':
            if os.path.getsize(file_path) > st.web.server.server.get_max_message_size_bytes():
                print(f"Media file cannot be previewed: size exceeds the message size limit of {st.web.server.server.get_max_message_size_bytes() / int(1e6):.2f} MB.")
                st.info(f'Media file cannot be previewed: size exceeds the size limit of {st.web.server.server.get_max_message_size_bytes() / int(1e6):.2f} MB.'
                        f' But you can try to run the transcription as usual.', icon="🚨")
                st.info(f' You can increase the limit by running: subsai-webui --server.maxMessageSize Your_desired_size_limit_in_MB')
                st.info(f"If it didn't work, please use the command line interface instead.")
            else:
                event = st_player(_media_file_base64(st.session_state['file_path']), **options, height=500, key="player")

    with st.expander('Export subtitles file'):
        media_file = Path(file_path)
        
        # Build format list (include .ooona if OOONA is enabled)
        format_options = available_subs_formats()
        ooona_enabled = st.session_state.get('ooona_enabled', False)
        if ooona_enabled:
            format_options = format_options + ['.ooona']
        
        export_format = st.radio(
            "Format",
            format_options)
        export_filename = st.text_input('Filename', value=media_file.stem)
        
        # Export Options
        st.write("**Export Options**")
        col1, col2, col3 = st.columns(3)
        with col1:
            enable_download = st.checkbox('Enable download', value=True, help='Download file directly to your browser')
        with col2:
            save_local = st.checkbox('Save locally', value=False, help='Save file to local directory')
        with col3:
            s3_enabled = st.session_state.get('s3_enabled', False)
            aws_bucket_name = os.getenv('AWS_BUCKET_NAME')
            if s3_enabled and aws_bucket_name:
                save_s3 = st.checkbox('Save to S3', value=False, help='Upload file to S3 bucket')
            else:
                save_s3 = False
        
        # S3 Configuration (only show if S3 is enabled and selected)
        if save_s3:
            # Project name input with smart default
            project_name = st.text_input(
                'S3 Project folder', 
                value=media_file.stem,
                help='Folder name in S3 bucket (will be prefilled with media filename)'
            )
            
            # S3 path preview
            bucket_name = os.getenv('AWS_BUCKET_NAME', '')
            s3_preview_path = f"s3://{bucket_name}/{project_name}/{export_filename}{export_format}"
            st.info(f"📍 S3 Path: `{s3_preview_path}`")
        else:
            project_name = ""
        
        if export_format == '.sub':
            fps = st.number_input('Framerate', help='Framerate must be specified when writing MicroDVD')
        else:
            fps = None
            
        submitted = st.button("Export")
        if submitted:
            try:
                subs = st.session_state['transcribed_subs']
                export_results = []
                
                # Handle OOONA format conversion
                if export_format == '.ooona':
                    if not ooona_enabled:
                        st.error("OOONA API is not enabled. Please enable it in the sidebar.")
                        return
                    
                    # Import here to avoid errors when OOONA is not used
                    try:
                        from subsai.storage.ooona_converter import create_ooona_converter
                    except ImportError:
                        st.error("OOONA converter not available. Please ensure all dependencies are installed.")
                        return
                    
                    # Create OOONA converter (uses environment variables)
                    ooona_converter = create_ooona_converter()
                    if not ooona_converter:
                        st.error("Failed to create OOONA converter. Please check environment variables:\n"
                                "- OOONA_BASE_URL\n"
                                "- OOONA_CLIENT_ID\n"
                                "- OOONA_CLIENT_SECRET\n"
                                "- OOONA_API_KEY\n"
                                "- OOONA_API_NAME")
                        return
                    
                    # Convert to OOONA format using API
                    with st.spinner("Converting to OOONA format using API..."):
                        # Generate SRT content as input
                        input_content = subs.to_string(format_='srt')
                        
                        # Convert using simplified OOONA API
                        conversion_result = ooona_converter.convert_subtitle(input_content)
                        
                        if conversion_result['success']:
                            subtitle_content = conversion_result['content']
                            st.success("✅ Successfully converted to OOONA format")
                        else:
                            st.error(f"OOONA conversion failed: {conversion_result['message']}")
                            return
                else:
                    # Generate subtitle content in memory for standard formats
                    subtitle_content = subs.to_string(format_=export_format[1:])  # Remove dot from format
                
                # Local save
                if save_local:
                    exported_file = media_file.parent / (export_filename + export_format)
                    if export_format == '.ooona':
                        # Write OOONA content directly to file
                        with open(exported_file, 'w', encoding='utf-8') as f:
                            f.write(subtitle_content)
                    else:
                        # Use standard pysubs2 save for other formats
                        subs.save(exported_file, fps=fps)
                    export_results.append(f"💾 Local: {exported_file}")
                
                # S3 save
                if save_s3 and s3_enabled:
                    with st.spinner("Uploading to S3..."):
                        s3_config = _get_s3_config_from_session_state()
                        s3_storage = create_s3_storage(s3_config)
                        
                        if s3_storage:
                            result = s3_storage.upload_subtitle(
                                subtitle_content=subtitle_content,
                                project_name=project_name,
                                filename=export_filename,
                                subtitle_format=export_format[1:]  # Remove dot
                            )
                            
                            if result['success']:
                                export_results.append(f"☁️ S3: {result['s3_url']}")
                            else:
                                st.error(f"S3 upload failed: {result['message']}")
                        else:
                            st.error("Failed to create S3 storage client")
                
                # Show results
                if export_results or enable_download:
                    if export_results:
                        st.success('✅ Export completed successfully!', icon="✅")
                        for result in export_results:
                            st.success(result)
                    
                    # Download button (always available when enabled)
                    if enable_download:
                        st.download_button(
                            '📥 Download File', 
                            data=subtitle_content,
                            file_name=export_filename + export_format,
                            mime='text/plain'
                        )
                else:
                    st.warning("Please select at least one export option (Download, Save locally, or Save to S3)")
                
            except Exception as e:
                st.error("Maybe you forgot to run the transcription! Please transcribe a media file first to export its transcription!")
                st.error("See the terminal for more info!")
                print(e)

    with st.expander('Merge subtitles with video'):
        media_file = Path(file_path)
        subs_lang = st.text_input('Subtitles language', value='English', key='merged_video_subs_lang')
        exported_video_filename = st.text_input('Filename', value=f"{media_file.stem}-subs-merged", key='merged_video_out_file')
        submitted = st.button("Merge", key='merged_video_export_btn')
        if submitted:
            try:
                subs = st.session_state['transcribed_subs']
                exported_file_path = tools.merge_subs_with_video({subs_lang: subs}, str(media_file.resolve()), exported_video_filename)
                st.success(f'Exported file to {exported_file_path}', icon="✅")
                with open(exported_file_path, 'rb') as f:
                    st.download_button('Download', f, file_name=f"{exported_video_filename}{media_file.suffix}")
            except Exception as e:
                st.error("Something went wrong!")
                st.error("See the terminal for more info!")
                print(e)

    with st.expander('Export configs file'):
        export_filename = st.text_input('Filename', value=f"{stt_model_name}_configs.json".replace('/', '-'))
        configs_dict = _get_config_from_session_state(stt_model_name, config_schema, notification_placeholder)
        st.download_button('Download', data=json.dumps(configs_dict), file_name=export_filename, mime='json')


    st.markdown(footer, unsafe_allow_html=True)


def run():
    if runtime.exists():
        webui()
    else:
        # Configure Streamlit for large file uploads and batch processing
        sys.argv = [
            "streamlit", "run", __file__, 
            "--theme.base", "dark",
            "--server.maxUploadSize", "10000",  # 10GB upload limit
            "--server.maxMessageSize", "10000",  # 10GB message size limit
            "--browser.gatherUsageStats", "false"
        ] + sys.argv
        sys.exit(stcli.main())


if __name__ == '__main__':
    run()
