"""
Authentication UI pages for Streamlit
"""

import streamlit as st
import pandas as pd
from typing import Optional
from .decorators import AuthUtils, require_admin, require_auth
from .models import User, UserProject


def render_login_page():
    """Render the login page"""
    st.set_page_config(
        page_title="SubsAI - Login",
        page_icon="🔐",
        layout="centered"
    )
    
    # Center the login form
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.title("🎞️ SubsAI")
        st.subheader("AI Transcription Tool")
        
        AuthUtils.show_login_form()


@require_auth
def render_user_dashboard():
    """Render user dashboard"""
    auth = AuthUtils.init_auth()
    user = auth.get_current_user()
    
    if not user:
        st.error("Authentication error. Please login again.")
        return
    
    st.title(f"👋 Welcome, {user.username}!")
    
    # User info and logout in sidebar
    AuthUtils.show_user_info(user, "_dashboard")
    
    # Main dashboard content
    tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "📁 My Projects", "⚙️ Settings"])
    
    with tab1:
        render_dashboard_overview(user)
    
    with tab2:
        render_user_projects(user)
    
    with tab3:
        render_user_settings(user)


def render_dashboard_overview(user: User):
    """Render dashboard overview"""
    st.subheader("📊 Dashboard Overview")
    
    # Quick stats
    col1, col2, col3, col4 = st.columns(4)
    
    auth = AuthUtils.init_auth()
    projects = auth.auth.db.get_user_projects(user.id)
    
    with col1:
        st.metric("Total Projects", len(projects))
    
    with col2:
        st.metric("Account Type", user.role.title())
    
    with col3:
        st.metric("Member Since", user.created_at.strftime("%b %Y") if user.created_at else "Unknown")
    
    with col4:
        active_projects = len([p for p in projects if p.updated_at and 
                              (p.updated_at - user.created_at).days < 30]) if user.created_at else 0
        st.metric("Active Projects", active_projects)
    
    # Recent projects
    if projects:
        st.subheader("📁 Recent Projects")
        recent_projects = sorted(projects, key=lambda x: x.updated_at or x.created_at, reverse=True)[:5]
        
        for project in recent_projects:
            with st.expander(f"📄 {project.name}"):
                st.write(f"**Description:** {project.description or 'No description'}")
                st.write(f"**Created:** {project.created_at.strftime('%Y-%m-%d %H:%M') if project.created_at else 'Unknown'}")
                st.write(f"**Updated:** {project.updated_at.strftime('%Y-%m-%d %H:%M') if project.updated_at else 'Unknown'}")
    else:
        st.info("🚀 No projects yet. Start by creating your first subtitle project!")
    
    # Quick actions
    st.subheader("🚀 Quick Actions")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📝 Start Single File Processing", type="primary"):
            st.session_state.current_page = "single_file"
            st.experimental_rerun()
    
    with col2:
        if st.button("🔄 Start Batch Processing"):
            st.session_state.current_page = "batch_processing"
            st.experimental_rerun()


def render_user_projects(user: User):
    """Render user projects management"""
    st.subheader("📁 My Projects")
    
    auth = AuthUtils.init_auth()
    
    # Add new project form
    with st.expander("➕ Create New Project", expanded=False):
        with st.form("new_project_form"):
            project_name = st.text_input("Project Name", max_chars=100)
            project_description = st.text_area("Description", max_chars=500)
            submit = st.form_submit_button("Create Project")
            
            if submit:
                if project_name.strip():
                    project = UserProject(
                        user_id=user.id,
                        name=project_name.strip(),
                        description=project_description.strip()
                    )
                    
                    project_id = auth.auth.db.create_project(project)
                    if project_id:
                        st.success(f"Project '{project_name}' created successfully!")
                        st.experimental_rerun()
                    else:
                        st.error("Failed to create project")
                else:
                    st.error("Please enter a project name")
    
    # List existing projects
    projects = auth.auth.db.get_user_projects(user.id)
    
    if projects:
        st.write(f"**Total Projects:** {len(projects)}")
        
        # Projects table
        projects_data = []
        for project in projects:
            projects_data.append({
                "ID": project.id,
                "Name": project.name,
                "Description": project.description[:50] + "..." if len(project.description or "") > 50 else project.description or "",
                "Created": project.created_at.strftime('%Y-%m-%d') if project.created_at else "Unknown",
                "Updated": project.updated_at.strftime('%Y-%m-%d') if project.updated_at else "Unknown"
            })
        
        df = pd.DataFrame(projects_data)
        
        # Display projects with actions
        for i, project in enumerate(projects):
            with st.expander(f"📄 {project.name}", expanded=False):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.write(f"**Description:** {project.description or 'No description'}")
                    st.write(f"**Created:** {project.created_at.strftime('%Y-%m-%d %H:%M') if project.created_at else 'Unknown'}")
                    st.write(f"**Last Updated:** {project.updated_at.strftime('%Y-%m-%d %H:%M') if project.updated_at else 'Unknown'}")
                
                with col2:
                    if st.button("✏️ Edit", key=f"edit_{project.id}"):
                        st.session_state.editing_project = project.id
                        st.experimental_rerun()
                    
                    if st.button("🗑️ Delete", key=f"delete_{project.id}"):
                        if auth.auth.db.delete_project(project.id, user.id):
                            st.success("Project deleted successfully!")
                            st.experimental_rerun()
                        else:
                            st.error("Failed to delete project")
                
                # Edit form
                if st.session_state.get('editing_project') == project.id:
                    st.write("---")
                    with st.form(f"edit_project_{project.id}"):
                        new_name = st.text_input("Project Name", value=project.name, max_chars=100)
                        new_description = st.text_area("Description", value=project.description or "", max_chars=500)
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            save = st.form_submit_button("💾 Save")
                        with col2:
                            cancel = st.form_submit_button("❌ Cancel")
                        
                        if save:
                            if new_name.strip():
                                project.name = new_name.strip()
                                project.description = new_description.strip()
                                
                                if auth.auth.db.update_project(project):
                                    st.success("Project updated successfully!")
                                    st.session_state.editing_project = None
                                    st.experimental_rerun()
                                else:
                                    st.error("Failed to update project")
                            else:
                                st.error("Please enter a project name")
                        
                        if cancel:
                            st.session_state.editing_project = None
                            st.experimental_rerun()
    else:
        st.info("🚀 No projects yet. Create your first project above!")


def render_user_settings(user: User):
    """Render user settings page"""
    st.subheader("⚙️ User Settings")
    
    auth = AuthUtils.init_auth()
    
    # Account information
    with st.expander("👤 Account Information", expanded=True):
        st.write(f"**Username:** {user.username}")
        st.write(f"**Email:** {user.email}")
        st.write(f"**Role:** {user.role.title()}")
        st.write(f"**Account Created:** {user.created_at.strftime('%Y-%m-%d %H:%M') if user.created_at else 'Unknown'}")
    
    # Change password
    with st.expander("🔐 Change Password", expanded=False):
        with st.form("change_password_form"):
            current_password = st.text_input("Current Password", type="password")
            new_password = st.text_input("New Password", type="password")
            confirm_password = st.text_input("Confirm New Password", type="password")
            submit = st.form_submit_button("Change Password")
            
            if submit:
                if not all([current_password, new_password, confirm_password]):
                    st.error("Please fill in all password fields")
                elif new_password != confirm_password:
                    st.error("New passwords do not match")
                elif len(new_password) < 6:
                    st.error("New password must be at least 6 characters long")
                else:
                    success, message = auth.auth.change_password(user.id, current_password, new_password)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
    
    # Update profile information
    with st.expander("📝 Update Profile", expanded=False):
        with st.form("update_profile_form"):
            new_username = st.text_input("Username", value=user.username)
            new_email = st.text_input("Email", value=user.email)
            submit = st.form_submit_button("Update Profile")
            
            if submit:
                if not new_username.strip():
                    st.error("Username cannot be empty")
                elif not new_email.strip() or "@" not in new_email:
                    st.error("Please enter a valid email address")
                else:
                    success, message = auth.auth.update_user_info(
                        user.id, 
                        new_username.strip() if new_username != user.username else None,
                        new_email.strip() if new_email != user.email else None
                    )
                    if success:
                        st.success(message)
                        st.experimental_rerun()
                    else:
                        st.error(message)


@require_admin
def render_admin_panel():
    """Render admin panel"""
    auth = AuthUtils.init_auth()
    user = auth.get_current_user()
    
    if not user:
        st.error("Authentication error. Please login again.")
        return
    
    st.title("🔧 Admin Panel")
    
    # Admin info in sidebar
    AuthUtils.show_user_info(user, "_admin")
    
    # Admin tabs
    tab1, tab2, tab3 = st.tabs(["👥 User Management", "📊 System Stats", "⚙️ System Settings"])
    
    with tab1:
        render_user_management()
    
    with tab2:
        render_system_stats()
    
    with tab3:
        render_system_settings()


def render_user_management():
    """Render user management section"""
    st.subheader("👥 User Management")
    
    auth = AuthUtils.init_auth()
    
    # Add new user form
    with st.expander("➕ Create New User", expanded=False):
        with st.form("create_user_form"):
            username = st.text_input("Username")
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            role = st.selectbox("Role", ["user", "admin"])
            submit = st.form_submit_button("Create User")
            
            if submit:
                if username and email and password:
                    success, message = auth.register_user(username, email, password, role)
                    if success:
                        st.success(message)
                        st.experimental_rerun()
                    else:
                        st.error(message)
                else:
                    st.error("Please fill in all fields")
    
    # List all users
    users = auth.auth.get_all_users()
    
    if users:
        st.write(f"**Total Users:** {len(users)}")
        
        # Users table
        users_data = []
        for user in users:
            users_data.append({
                "ID": user.id,
                "Username": user.username,
                "Email": user.email,
                "Role": user.role.title(),
                "Created": user.created_at.strftime('%Y-%m-%d') if user.created_at else "Unknown",
                "Status": "Active" if user.is_active else "Inactive"
            })
        
        df = pd.DataFrame(users_data)
        st.dataframe(df, use_container_width=True)
        
        # User actions
        st.write("**User Actions:**")
        for user in users:
            if user.role == "admin" and user.id == auth.get_current_user().id:
                continue  # Don't show actions for current admin
            
            with st.expander(f"👤 {user.username} ({user.role})", expanded=False):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.write(f"**Email:** {user.email}")
                    st.write(f"**Created:** {user.created_at.strftime('%Y-%m-%d') if user.created_at else 'Unknown'}")
                
                with col2:
                    # Get user's projects
                    projects = auth.auth.db.get_user_projects(user.id)
                    st.write(f"**Projects:** {len(projects)}")
                    st.write(f"**Status:** {'Active' if user.is_active else 'Inactive'}")
                
                with col3:
                    if st.button("🗑️ Delete User", key=f"delete_user_{user.id}"):
                        success, message = auth.auth.delete_user(user.id, auth.get_current_user().id)
                        if success:
                            st.success(message)
                            st.experimental_rerun()
                        else:
                            st.error(message)
    else:
        st.info("No users found.")


def render_system_stats():
    """Render system statistics"""
    st.subheader("📊 System Statistics")
    
    auth = AuthUtils.init_auth()
    
    # Basic stats
    total_users = auth.auth.db.get_user_count()
    all_users = auth.auth.get_all_users()
    admin_users = len([u for u in all_users if u.role == "admin"])
    regular_users = total_users - admin_users
    
    # Clean up expired sessions
    expired_sessions = auth.auth.cleanup_expired_sessions()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Users", total_users)
    
    with col2:
        st.metric("Admin Users", admin_users)
    
    with col3:
        st.metric("Regular Users", regular_users)
    
    with col4:
        st.metric("Expired Sessions Cleaned", expired_sessions)
    
    # User registration over time
    if all_users:
        st.subheader("📈 User Registration Over Time")
        
        # Group users by registration date
        registration_data = {}
        for user in all_users:
            if user.created_at:
                date_key = user.created_at.strftime('%Y-%m-%d')
                registration_data[date_key] = registration_data.get(date_key, 0) + 1
        
        if registration_data:
            df = pd.DataFrame(list(registration_data.items()), columns=['Date', 'New Users'])
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.sort_values('Date')
            
            st.line_chart(df.set_index('Date')['New Users'])
    
    # Database information
    st.subheader("💾 Database Information")
    st.write(f"**Database Path:** {auth.auth.db.db_path}")
    
    try:
        import os
        db_size = os.path.getsize(auth.auth.db.db_path) / 1024  # KB
        st.write(f"**Database Size:** {db_size:.2f} KB")
    except Exception:
        st.write("**Database Size:** Unable to determine")


def render_system_settings():
    """Render system settings"""
    st.subheader("⚙️ System Settings")
    
    auth = AuthUtils.init_auth()
    
    # Session management
    with st.expander("🔐 Session Management", expanded=True):
        st.write(f"**Session Duration:** {auth.auth.session_duration_hours} hours")
        
        if st.button("🧹 Clean Expired Sessions"):
            cleaned = auth.auth.cleanup_expired_sessions()
            st.success(f"Cleaned {cleaned} expired sessions")
    
    # Database management
    with st.expander("💾 Database Management", expanded=False):
        st.write(f"**Database Location:** {auth.auth.db.db_path}")
        
        if st.button("🔄 Restart Database Connection"):
            try:
                # Reinitialize database
                auth.auth.db._init_database()
                st.success("Database connection restarted successfully")
            except Exception as e:
                st.error(f"Failed to restart database: {e}")
    
    # System information
    with st.expander("ℹ️ System Information", expanded=False):
        import platform
        import sys
        
        st.write(f"**Python Version:** {sys.version}")
        st.write(f"**Platform:** {platform.system()} {platform.release()}")
        st.write(f"**Streamlit Version:** {st.__version__}")
        
        try:
            import bcrypt
            st.write(f"**bcrypt Version:** {bcrypt.__version__}")
        except Exception:
            st.write("**bcrypt Version:** Unable to determine")