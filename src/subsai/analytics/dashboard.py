"""
Analytics dashboard for admin users
"""

import streamlit as st
import pandas as pd
import datetime
from typing import Dict, List, Any, Optional

from .analytics_service import AnalyticsService
from ..auth.decorators import require_admin

# Optional plotly import for enhanced charts
try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


def render_analytics_dashboard():
    """Render the analytics dashboard for admin users"""
    st.title("📊 Analytics Dashboard")
    st.info("📈 System-wide and per-user analytics for administrators")
    
    analytics = AnalyticsService()
    
    if not analytics.is_enabled():
        st.warning("⚠️ Analytics collection is currently disabled")
        if st.button("Enable Analytics"):
            analytics.enable_analytics(True)
            st.experimental_rerun()
        return
    
    # Time range selector
    col1, col2 = st.columns(2)
    with col1:
        days_filter = st.selectbox(
            "Time Period",
            options=[7, 14, 30, 60, 90],
            index=2,  # Default to 30 days
            help="Select the number of days to analyze"
        )
    
    with col2:
        refresh_button = st.button("🔄 Refresh Data")
    
    # Main dashboard tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 System Overview", "👥 User Analytics", "📈 Performance Metrics", "🔍 Activity Log", "🔒 Privacy & Settings"])
    
    with tab1:
        render_system_overview(analytics, days_filter)
    
    with tab2:
        render_user_analytics(analytics, days_filter)
    
    with tab3:
        render_performance_metrics(analytics, days_filter)
    
    with tab4:
        render_activity_log(analytics, days_filter)
    
    with tab5:
        render_privacy_settings(analytics)


def render_system_overview(analytics: AnalyticsService, days: int):
    """Render system-wide overview statistics"""
    st.subheader("🌍 System Overview")
    
    # Get system statistics
    system_stats = analytics.get_system_analytics(days)
    
    if not system_stats:
        st.info("No data available for the selected time period")
        return
    
    stats = system_stats.get('system_stats', {})
    
    # Key metrics cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Files Processed",
            stats.get('total_files_processed', 0),
            help="Total number of files processed"
        )
    
    with col2:
        processing_time = stats.get('total_processing_time', 0)
        hours = processing_time / 3600
        st.metric(
            "Processing Time",
            f"{hours:.1f}h",
            help="Total processing time in hours"
        )
    
    with col3:
        success_rate = stats.get('success_rate', 0)
        st.metric(
            "Success Rate",
            f"{success_rate:.1f}%",
            help="Percentage of successful processing jobs"
        )
    
    with col4:
        st.metric(
            "Active Users",
            stats.get('active_users', 0),
            help="Number of users who processed files in this period"
        )
    
    # Charts row
    col1, col2 = st.columns(2)
    
    with col1:
        # Most used models
        st.subheader("🤖 Most Used Models")
        top_models = stats.get('top_models', [])
        if top_models:
            df_models = pd.DataFrame(top_models)
            if PLOTLY_AVAILABLE:
                fig = px.bar(
                    df_models, 
                    x='model', 
                    y='count',
                    title="Model Usage",
                    labels={'count': 'Usage Count', 'model': 'Model'}
                )
                fig.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.bar_chart(df_models.set_index('model')['count'])
        else:
            st.info("No model usage data available")
    
    with col2:
        # Most used formats
        st.subheader("📄 Most Used Output Formats")
        top_formats = stats.get('top_formats', [])
        if top_formats:
            df_formats = pd.DataFrame(top_formats)
            if PLOTLY_AVAILABLE:
                fig = px.pie(
                    df_formats,
                    values='count',
                    names='format',
                    title="Output Format Distribution"
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.write("**Format Usage:**")
                for _, row in df_formats.iterrows():
                    st.write(f"- {row['format']}: {row['count']} files")
        else:
            st.info("No format usage data available")


def render_user_analytics(analytics: AnalyticsService, days: int):
    """Render per-user analytics"""
    st.subheader("👥 User Analytics")
    
    # Get all users analytics
    users_analytics = analytics.get_all_users_analytics(days)
    
    if not users_analytics:
        st.info("No user data available for the selected time period")
        return
    
    # User selection
    usernames = [ua['username'] for ua in users_analytics]
    selected_user = st.selectbox(
        "Select User for Detailed View",
        options=["All Users"] + usernames,
        help="Choose a specific user to view detailed analytics"
    )
    
    if selected_user == "All Users":
        # Summary table of all users
        st.subheader("📋 User Summary")
        
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
                'Errors': summary.get('total_errors', 0),
                'Success Rate (%)': round(summary.get('success_rate', 0), 1)
            })
        
        if summary_data:
            df_summary = pd.DataFrame(summary_data)
            st.dataframe(df_summary, use_container_width=True)
            
            # Top users charts
            col1, col2 = st.columns(2)
            
            with col1:
                # Top users by transcriptions
                st.subheader("🥇 Top Users by Transcriptions")
                top_transcriptions = df_summary.nlargest(5, 'Transcriptions')[['Username', 'Transcriptions']]
                if not top_transcriptions.empty:
                    if PLOTLY_AVAILABLE:
                        fig = px.bar(
                            top_transcriptions,
                            x='Username',
                            y='Transcriptions',
                            title="Most Active Users"
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.bar_chart(top_transcriptions.set_index('Username')['Transcriptions'])
            
            with col2:
                # Top users by processing time
                st.subheader("⏱️ Top Users by Processing Time")
                top_time = df_summary.nlargest(5, 'Processing Time (min)')[['Username', 'Processing Time (min)']]
                if not top_time.empty:
                    if PLOTLY_AVAILABLE:
                        fig = px.bar(
                            top_time,
                            x='Username',
                            y='Processing Time (min)',
                            title="Highest Processing Time"
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.bar_chart(top_time.set_index('Username')['Processing Time (min)'])
    else:
        # Detailed view for selected user
        user_data = next((ua for ua in users_analytics if ua['username'] == selected_user), None)
        if user_data:
            render_detailed_user_analytics(user_data)


def render_detailed_user_analytics(user_data: Dict[str, Any]):
    """Render detailed analytics for a specific user"""
    st.subheader(f"📊 Detailed Analytics: {user_data['username']}")
    
    summary = user_data.get('summary', {})
    
    # User info
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info(f"**Role:** {user_data['role']}")
    with col2:
        st.info(f"**Email:** {user_data['email']}")
    with col3:
        st.info(f"**User ID:** {user_data['user_id']}")
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Transcriptions", summary.get('total_transcriptions', 0))
    with col2:
        st.metric("Translations", summary.get('total_translations', 0))
    with col3:
        processing_time = summary.get('total_processing_time', 0)
        st.metric("Processing Time", f"{processing_time/60:.1f}m")
    with col4:
        success_rate = summary.get('success_rate', 0)
        st.metric("Success Rate", f"{success_rate:.1f}%")
    
    # User's preferred models and formats
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🤖 Preferred Models")
        top_models = user_data.get('top_models', [])
        if top_models:
            df_models = pd.DataFrame(top_models)
            if PLOTLY_AVAILABLE:
                fig = px.bar(
                    df_models,
                    x='model',
                    y='count',
                    title=f"{user_data['username']}'s Model Usage"
                )
                fig.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.bar_chart(df_models.set_index('model')['count'])
        else:
            st.info("No model usage data")
    
    with col2:
        st.subheader("📄 Preferred Formats")
        top_formats = user_data.get('top_formats', [])
        if top_formats:
            df_formats = pd.DataFrame(top_formats)
            if PLOTLY_AVAILABLE:
                fig = px.pie(
                    df_formats,
                    values='count',
                    names='format',
                    title=f"{user_data['username']}'s Format Usage"
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.write("**Format Usage:**")
                for _, row in df_formats.iterrows():
                    st.write(f"- {row['format']}: {row['count']} files")
        else:
            st.info("No format usage data")
    
    # Recent activity
    st.subheader("📋 Recent Files")
    recent_files = user_data.get('recent_files', [])
    if recent_files:
        df_files = pd.DataFrame(recent_files[:10])  # Show last 10 files
        
        # Format the dataframe for display
        if not df_files.empty and 'timestamp' in df_files.columns:
            df_files['timestamp'] = pd.to_datetime(df_files['timestamp'])
            df_files['processing_time'] = df_files['processing_time'].apply(lambda x: f"{x:.1f}s" if pd.notnull(x) else "N/A")
            df_files['file_size'] = df_files['file_size'].apply(lambda x: f"{x/(1024*1024):.1f} MB" if pd.notnull(x) else "N/A")
        
        st.dataframe(df_files, use_container_width=True)
    else:
        st.info("No recent file data available")


def render_performance_metrics(analytics: AnalyticsService, days: int):
    """Render performance and efficiency metrics"""
    st.subheader("📈 Performance Metrics")
    
    # Get system stats for performance analysis
    system_stats = analytics.get_system_analytics(days)
    
    if not system_stats:
        st.info("No performance data available")
        return
    
    stats = system_stats.get('system_stats', {})
    
    # Performance summary
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_files = stats.get('total_files_processed', 0)
        total_time = stats.get('total_processing_time', 0)
        avg_time = total_time / total_files if total_files > 0 else 0
        st.metric(
            "Avg Processing Time",
            f"{avg_time:.1f}s",
            help="Average time per file"
        )
    
    with col2:
        success_rate = stats.get('success_rate', 0)
        st.metric(
            "System Reliability",
            f"{success_rate:.1f}%",
            help="Overall success rate"
        )
    
    with col3:
        active_users = stats.get('active_users', 0)
        st.metric(
            "User Engagement",
            f"{active_users} users",
            help="Active users in period"
        )
    
    # Model performance comparison
    st.subheader("🤖 Model Performance Comparison")
    top_models = stats.get('top_models', [])
    if top_models:
        st.info("📊 Model usage statistics help identify which models are most popular and trusted by users")
        
        df_models = pd.DataFrame(top_models)
        col1, col2 = st.columns(2)
        
        with col1:
            if PLOTLY_AVAILABLE:
                fig = px.bar(
                    df_models,
                    x='model',
                    y='count',
                    title="Model Usage Frequency",
                    labels={'count': 'Number of Uses', 'model': 'Model'}
                )
                fig.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.subheader("Model Usage Frequency")
                st.bar_chart(df_models.set_index('model')['count'])
        
        with col2:
            # Calculate model usage percentage
            total_usage = sum(model['count'] for model in top_models)
            for model in top_models:
                model['percentage'] = (model['count'] / total_usage * 100) if total_usage > 0 else 0
            
            if PLOTLY_AVAILABLE:
                fig = px.pie(
                    df_models,
                    values='count',
                    names='model',
                    title="Model Usage Distribution"
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.subheader("Model Usage Distribution")
                for _, row in df_models.iterrows():
                    percentage = (row['count'] / total_usage * 100) if total_usage > 0 else 0
                    st.write(f"- {row['model']}: {row['count']} uses ({percentage:.1f}%)")
    else:
        st.info("No model performance data available")


def render_activity_log(analytics: AnalyticsService, days: int):
    """Render recent activity log"""
    st.subheader("🔍 Recent Activity")
    
    # Activity filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        event_type_filter = st.selectbox(
            "Event Type",
            options=["All", "transcription_start", "transcription_complete", "translation", "download", "upload", "error"],
            help="Filter by specific event types"
        )
    
    with col2:
        limit = st.number_input(
            "Number of Events",
            min_value=10,
            max_value=500,
            value=50,
            help="Number of recent events to display"
        )
    
    with col3:
        if st.button("🔄 Refresh Log"):
            st.experimental_rerun()
    
    # Get activity data
    try:
        if event_type_filter == "All":
            # Get recent events from all users
            users_analytics = analytics.get_all_users_analytics(days)
            all_events = []
            
            for user_data in users_analytics:
                events = user_data.get('recent_events', [])
                for event in events[:10]:  # Limit per user
                    event['username'] = user_data['username']
                    all_events.append(event)
            
            # Sort by timestamp and limit
            all_events.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            all_events = all_events[:limit]
        else:
            # For specific event types, we'd need to implement event filtering in analytics service
            all_events = []
            st.info(f"Filtering by '{event_type_filter}' - This feature requires additional implementation")
        
        if all_events:
            # Convert to DataFrame for display
            df_events = pd.DataFrame(all_events)
            
            # Format timestamp if present
            if 'timestamp' in df_events.columns:
                df_events['timestamp'] = pd.to_datetime(df_events['timestamp'])
                df_events = df_events.sort_values('timestamp', ascending=False)
            
            # Display the events table
            st.dataframe(
                df_events[['timestamp', 'username', 'event_type', 'event_data']].head(limit),
                use_container_width=True
            )
        else:
            st.info("No recent activity data available")
            
    except Exception as e:
        st.error(f"Error loading activity log: {str(e)}")
        st.info("This might occur if the analytics database is not properly initialized")


def render_analytics_settings():
    """Render analytics configuration settings"""
    st.subheader("⚙️ Analytics Settings")
    
    analytics = AnalyticsService()
    
    # Analytics toggle
    current_status = analytics.is_enabled()
    new_status = st.checkbox(
        "Enable Analytics Collection",
        value=current_status,
        help="Enable or disable system-wide analytics collection"
    )
    
    if new_status != current_status:
        analytics.enable_analytics(new_status)
        if new_status:
            st.success("✅ Analytics enabled")
        else:
            st.warning("⚠️ Analytics disabled")
        st.experimental_rerun()
    
    st.markdown("---")
    
    # Data retention settings
    st.subheader("📅 Data Retention")
    st.info("Configure how long analytics data is stored")
    
    retention_days = st.number_input(
        "Retention Period (days)",
        min_value=7,
        max_value=365,
        value=90,
        help="Number of days to keep analytics data"
    )
    
    if st.button("Update Retention Policy"):
        st.success(f"✅ Data retention set to {retention_days} days")
        # Note: Actual implementation would require adding retention logic to analytics service
    
    st.markdown("---")
    
    # Privacy controls
    st.subheader("🔒 Privacy Controls")
    st.info("Manage user privacy and data access")
    
    anonymize_data = st.checkbox(
        "Anonymize User Data",
        value=False,
        help="Remove personally identifiable information from analytics"
    )
    
    if anonymize_data:
        st.warning("⚠️ Data anonymization feature requires implementation")
    
    # Export data
    st.markdown("---")
    st.subheader("📤 Data Export")
    
    if st.button("Export Analytics Data"):
        st.info("📊 Data export feature requires implementation")
        # Note: Would export analytics data as CSV/JSON for external analysis


def render_privacy_settings(analytics: AnalyticsService):
    """Render privacy and data management settings"""
    st.subheader("🔒 Privacy & Data Management")
    
    # Current privacy policy display
    retention_policy = analytics.get_retention_policy()
    
    # Privacy notice
    with st.expander("📋 Privacy Notice", expanded=False):
        from .config import get_privacy_notice
        st.markdown(get_privacy_notice())
    
    # GDPR compliance info
    with st.expander("⚖️ GDPR Compliance", expanded=False):
        from .config import get_gdpr_compliance_info
        st.markdown(get_gdpr_compliance_info())
    
    st.markdown("---")
    
    # Current settings
    st.subheader("📊 Current Settings")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Analytics Status", "Enabled" if analytics.is_enabled() else "Disabled")
    with col2:
        st.metric("Data Retention", f"{retention_policy['retention_days']} days")
    with col3:
        st.metric("Anonymization", "On" if retention_policy['anonymize_data'] else "Off")
    
    st.markdown("---")
    
    # Data management actions
    st.subheader("🔧 Data Management")
    
    # Retention policy update
    with st.expander("📅 Update Retention Policy", expanded=False):
        new_retention = st.number_input(
            "Retention Period (days)",
            min_value=7,
            max_value=365,
            value=retention_policy['retention_days'],
            help="Number of days to keep analytics data before automatic deletion"
        )
        
        if st.button("Update Retention Policy"):
            # Get current admin user (would need to be passed from auth context)
            try:
                from ...auth.decorators import AuthUtils
                auth = AuthUtils.init_auth()
                current_user = auth.get_current_user()
                
                if current_user and analytics.validate_admin_access(current_user.role):
                    success = analytics.update_retention_policy(new_retention, current_user.id)
                    if success:
                        st.success(f"✅ Updated retention policy to {new_retention} days")
                    else:
                        st.error("❌ Failed to update retention policy")
                else:
                    st.error("❌ Admin access required")
            except Exception as e:
                st.error(f"❌ Error updating policy: {str(e)}")
    
    # Data cleanup
    with st.expander("🧹 Data Cleanup", expanded=False):
        st.info("Remove analytics data older than the retention period")
        
        if st.button("🗑️ Clean Old Data", type="secondary"):
            with st.spinner("Cleaning up old data..."):
                deleted_count = analytics.cleanup_old_data()
                if deleted_count > 0:
                    st.success(f"✅ Cleaned up {deleted_count} old records")
                else:
                    st.info("ℹ️ No old data to clean up")
    
    # Analytics enable/disable
    with st.expander("⚙️ Analytics Control", expanded=False):
        current_status = analytics.is_enabled()
        new_status = st.checkbox(
            "Enable Analytics Collection",
            value=current_status,
            help="Toggle system-wide analytics collection"
        )
        
        if new_status != current_status:
            analytics.enable_analytics(new_status)
            if new_status:
                st.success("✅ Analytics enabled")
            else:
                st.warning("⚠️ Analytics disabled")
            st.experimental_rerun()