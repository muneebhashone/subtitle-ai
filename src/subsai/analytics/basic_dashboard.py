"""
Basic analytics dashboard fallback for when full dashboard dependencies are not available
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any

from .analytics_service import AnalyticsService


def render_basic_analytics_dashboard():
    """Render a basic analytics dashboard without external dependencies"""
    st.title("📊 Analytics Dashboard (Basic Mode)")
    st.info("📈 Basic analytics view - install 'plotly' for enhanced charts")
    
    analytics = AnalyticsService()
    
    if not analytics.is_enabled():
        st.warning("⚠️ Analytics collection is currently disabled")
        if st.button("Enable Analytics"):
            analytics.enable_analytics(True)
            st.experimental_rerun()
        return
    
    # Time range selector
    days_filter = st.selectbox(
        "Time Period",
        options=[7, 14, 30, 60, 90],
        index=2,  # Default to 30 days
        help="Select the number of days to analyze"
    )
    
    # Basic system overview
    st.subheader("🌍 System Overview")
    
    try:
        system_stats = analytics.get_system_analytics(days_filter)
        stats = system_stats.get('system_stats', {})
        
        if stats:
            # Key metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "Files Processed",
                    stats.get('total_files_processed', 0)
                )
            
            with col2:
                processing_time = stats.get('total_processing_time', 0)
                hours = processing_time / 3600
                st.metric(
                    "Processing Time",
                    f"{hours:.1f}h"
                )
            
            with col3:
                success_rate = stats.get('success_rate', 0)
                st.metric(
                    "Success Rate",
                    f"{success_rate:.1f}%"
                )
            
            with col4:
                st.metric(
                    "Active Users",
                    stats.get('active_users', 0)
                )
            
            # Simple tables instead of charts
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("🤖 Most Used Models")
                top_models = stats.get('top_models', [])
                if top_models:
                    model_df = pd.DataFrame(top_models)
                    st.dataframe(model_df, use_container_width=True)
                else:
                    st.info("No model usage data available")
            
            with col2:
                st.subheader("📄 Output Format Usage")
                top_formats = stats.get('top_formats', [])
                if top_formats:
                    format_df = pd.DataFrame(top_formats)
                    st.dataframe(format_df, use_container_width=True)
                else:
                    st.info("No format usage data available")
        else:
            st.info("No analytics data available for the selected time period")
    
    except Exception as e:
        st.error(f"Error loading system analytics: {str(e)}")
    
    # User overview
    st.subheader("👥 User Overview")
    
    try:
        users_analytics = analytics.get_all_users_analytics(days_filter)
        
        if users_analytics:
            # Create summary table
            summary_data = []
            for ua in users_analytics:
                summary = ua.get('summary', {})
                summary_data.append({
                    'Username': ua['username'],
                    'Role': ua['role'],
                    'Transcriptions': summary.get('total_transcriptions', 0),
                    'Translations': summary.get('total_translations', 0),
                    'Processing Time (min)': round(summary.get('total_processing_time', 0) / 60, 1),
                    'File Size (MB)': round(summary.get('total_file_size', 0) / (1024*1024), 1),
                    'Success Rate (%)': round(summary.get('success_rate', 0), 1)
                })
            
            if summary_data:
                df_summary = pd.DataFrame(summary_data)
                st.dataframe(df_summary, use_container_width=True)
                
                # Top users
                st.subheader("🏆 Top Users")
                top_users = df_summary.nlargest(5, 'Transcriptions')[['Username', 'Transcriptions']]
                if not top_users.empty:
                    st.write("**Most Active Users (by Transcriptions):**")
                    for _, row in top_users.iterrows():
                        st.write(f"- {row['Username']}: {row['Transcriptions']} transcriptions")
            else:
                st.info("No user data available")
        else:
            st.info("No user analytics data available")
    
    except Exception as e:
        st.error(f"Error loading user analytics: {str(e)}")
    
    # Basic controls
    st.subheader("⚙️ Analytics Controls")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔄 Refresh Data"):
            st.experimental_rerun()
    
    with col2:
        current_status = analytics.is_enabled()
        if st.button(f"{'🛑 Disable' if current_status else '🟢 Enable'} Analytics"):
            analytics.enable_analytics(not current_status)
            st.experimental_rerun()
    
    # Show installation instructions for enhanced features
    with st.expander("📦 Enhanced Features Available"):
        st.write("Install additional packages for enhanced analytics:")
        st.code("pip install plotly", language="bash")
        st.write("This will enable:")
        st.write("- Interactive charts and graphs")
        st.write("- Advanced visualizations")
        st.write("- Better data exploration tools")
        st.write("- Enhanced user analytics")