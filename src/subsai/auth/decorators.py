"""
Authentication decorators and middleware for Streamlit
"""

import functools
import streamlit as st
from typing import Optional, Callable, Any
from .auth import AuthManager
from .models import User


class StreamlitAuth:
    """Streamlit authentication helper class"""
    
    def __init__(self, auth_manager: Optional[AuthManager] = None):
        """
        Initialize Streamlit authentication
        
        Args:
            auth_manager: AuthManager instance. If None, creates a new one.
        """
        self.auth = auth_manager or AuthManager()
        
        # Initialize session state for authentication
        if 'session_id' not in st.session_state:
            st.session_state.session_id = None
        if 'user' not in st.session_state:
            st.session_state.user = None
        if 'is_authenticated' not in st.session_state:
            st.session_state.is_authenticated = False
    
    def get_current_user(self) -> Optional[User]:
        """Get current authenticated user"""
        if not st.session_state.session_id:
            return None
        
        user = self.auth.validate_session(st.session_state.session_id)
        if user:
            st.session_state.user = user
            st.session_state.is_authenticated = True
            return user
        else:
            # Session is invalid, clear it
            self.logout()
            return None
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated"""
        return self.get_current_user() is not None
    
    def is_admin(self) -> bool:
        """Check if current user is admin"""
        user = self.get_current_user()
        return user is not None and user.role == "admin"
    
    def login(self, username: str, password: str) -> tuple[bool, str]:
        """
        Login user
        
        Args:
            username: Username
            password: Password
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        success, message, session_id = self.auth.login(username, password)
        
        if success and session_id:
            st.session_state.session_id = session_id
            user = self.get_current_user()
            if user:
                st.session_state.user = user
                st.session_state.is_authenticated = True
                return True, message
        
        return False, message
    
    def logout(self) -> bool:
        """Logout current user"""
        if st.session_state.session_id:
            success = self.auth.logout(st.session_state.session_id)
        else:
            success = True
        
        # Clear session state
        st.session_state.session_id = None
        st.session_state.user = None
        st.session_state.is_authenticated = False
        
        return success
    
    def register_user(self, username: str, email: str, password: str, role: str = "user") -> tuple[bool, str]:
        """
        Register new user (admin only)
        
        Args:
            username: Username
            email: Email
            password: Password
            role: User role
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        if not self.is_admin():
            return False, "Admin privileges required to register users"
        
        return self.auth.register_user(username, email, password, role)


def require_auth(func: Callable) -> Callable:
    """
    Decorator to require authentication for a Streamlit function
    
    Usage:
        @require_auth
        def my_protected_function():
            # This function requires authentication
            pass
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        # Check if we have a global auth instance
        if 'auth_manager' not in st.session_state:
            st.session_state.auth_manager = StreamlitAuth()
        
        auth = st.session_state.auth_manager
        
        if not auth.is_authenticated():
            st.error("🔒 Authentication required. Please log in to access this page.")
            st.stop()
        
        return func(*args, **kwargs)
    
    return wrapper


def require_admin(func: Callable) -> Callable:
    """
    Decorator to require admin privileges for a Streamlit function
    
    Usage:
        @require_admin
        def admin_only_function():
            # This function requires admin privileges
            pass
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        # Check if we have a global auth instance
        if 'auth_manager' not in st.session_state:
            st.session_state.auth_manager = StreamlitAuth()
        
        auth = st.session_state.auth_manager
        
        if not auth.is_authenticated():
            st.error("🔒 Authentication required. Please log in to access this page.")
            st.stop()
        
        if not auth.is_admin():
            st.error("🚫 Admin privileges required to access this page.")
            st.stop()
        
        return func(*args, **kwargs)
    
    return wrapper


def optional_auth(func: Callable) -> Callable:
    """
    Decorator that checks for authentication but doesn't require it
    Makes user information available if authenticated
    
    Usage:
        @optional_auth
        def my_function():
            # Can check st.session_state.is_authenticated
            # and st.session_state.user if needed
            pass
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        # Check if we have a global auth instance
        if 'auth_manager' not in st.session_state:
            st.session_state.auth_manager = StreamlitAuth()
        
        # Check authentication status (but don't require it)
        auth = st.session_state.auth_manager
        auth.get_current_user()  # This updates session state
        
        return func(*args, **kwargs)
    
    return wrapper


class AuthUtils:
    """Utility functions for authentication in Streamlit"""
    
    @staticmethod
    def init_auth() -> StreamlitAuth:
        """Initialize authentication for the current session"""
        if 'auth_manager' not in st.session_state:
            st.session_state.auth_manager = StreamlitAuth()
        return st.session_state.auth_manager
    
    @staticmethod
    def show_user_info(user: User, key_suffix: str = "") -> None:
        """Display user information in sidebar"""
        with st.sidebar:
            st.write("---")
            st.subheader("👤 User Info")
            st.write(f"**Username:** {user.username}")
            st.write(f"**Email:** {user.email}")
            st.write(f"**Role:** {user.role.title()}")
            
            logout_key = f"logout_button{key_suffix}"
            if st.button("🚪 Logout", key=logout_key):
                auth = AuthUtils.init_auth()
                auth.logout()
                st.experimental_rerun()
    
    @staticmethod
    def show_login_form() -> None:
        """Display login form"""
        st.title("🔐 Login")
        
        auth = AuthUtils.init_auth()
        
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
            
            if submit:
                if username and password:
                    success, message = auth.login(username, password)
                    if success:
                        st.success(message)
                        st.experimental_rerun()
                    else:
                        st.error(message)
                else:
                    st.error("Please enter both username and password")
        
        # Show default admin credentials info if no users exist yet
        if auth.auth.db.get_user_count() <= 1:
            st.info("💡 **First time setup:** Use username 'admin' and password 'admin123' to login as administrator. Please change these credentials after login!")
    
    @staticmethod
    def check_auth_and_redirect() -> bool:
        """
        Check authentication and redirect to login if needed
        
        Returns:
            True if authenticated, False if redirected to login
        """
        auth = AuthUtils.init_auth()
        
        if not auth.is_authenticated():
            AuthUtils.show_login_form()
            return False
        
        return True