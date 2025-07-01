"""
Core authentication logic for SubsAI
"""

import secrets
import datetime
import logging
from typing import Optional, Tuple
import bcrypt

from .database import Database
from .models import User, Session


class AuthManager:
    """Authentication manager for handling user login, registration, and sessions"""
    
    def __init__(self, db: Optional[Database] = None):
        """
        Initialize authentication manager
        
        Args:
            db: Database instance. If None, creates a new one.
        """
        self.db = db or Database()
        self.logger = logging.getLogger(__name__)
        self.session_duration_hours = 24  # Session expires after 24 hours
    
    def register_user(self, username: str, email: str, password: str, role: str = "user") -> Tuple[bool, str]:
        """
        Register a new user (admin only)
        
        Args:
            username: Username for the new user
            email: Email address
            password: Plain text password
            role: User role ('user' or 'admin')
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Validate input
            if not username or len(username) < 3:
                return False, "Username must be at least 3 characters long"
            
            if not email or "@" not in email:
                return False, "Invalid email address"
            
            if not password or len(password) < 6:
                return False, "Password must be at least 6 characters long"
            
            if role not in ["user", "admin"]:
                return False, "Role must be 'user' or 'admin'"
            
            # Hash password
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            # Create user
            user = User(
                username=username.strip().lower(),
                email=email.strip().lower(),
                password_hash=password_hash,
                role=role,
                created_at=datetime.datetime.now()
            )
            
            user_id = self.db.create_user(user)
            if user_id:
                self.logger.info(f"User registered successfully: {username}")
                return True, f"User '{username}' registered successfully"
            else:
                return False, "Failed to create user"
                
        except ValueError as e:
            return False, str(e)
        except Exception as e:
            self.logger.error(f"Registration error: {e}")
            return False, "Registration failed due to an unexpected error"
    
    def login(self, username: str, password: str) -> Tuple[bool, str, Optional[str]]:
        """
        Authenticate user and create session
        
        Args:
            username: Username or email
            password: Plain text password
        
        Returns:
            Tuple of (success: bool, message: str, session_id: Optional[str])
        """
        try:
            # Clean expired sessions first
            self.db.clean_expired_sessions()
            
            # Get user by username
            user = self.db.get_user_by_username(username.strip().lower())
            if not user:
                self.logger.warning(f"Login attempt with invalid username: {username}")
                return False, "Invalid username or password", None
            
            # Verify password
            if not bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
                self.logger.warning(f"Login attempt with invalid password for user: {username}")
                return False, "Invalid username or password", None
            
            # Create session
            session_id = self._generate_session_id()
            expires_at = datetime.datetime.now() + datetime.timedelta(hours=self.session_duration_hours)
            
            session = Session(
                session_id=session_id,
                user_id=user.id,
                expires_at=expires_at,
                created_at=datetime.datetime.now()
            )
            
            if self.db.create_session(session):
                self.logger.info(f"User logged in successfully: {username}")
                return True, "Login successful", session_id
            else:
                return False, "Failed to create session", None
                
        except Exception as e:
            self.logger.error(f"Login error: {e}")
            return False, "Login failed due to an unexpected error", None
    
    def logout(self, session_id: str) -> bool:
        """
        Log out user by deleting session
        
        Args:
            session_id: Session ID to delete
        
        Returns:
            True if successful, False otherwise
        """
        try:
            return self.db.delete_session(session_id)
        except Exception as e:
            self.logger.error(f"Logout error: {e}")
            return False
    
    def validate_session(self, session_id: str) -> Optional[User]:
        """
        Validate session and return user if valid
        
        Args:
            session_id: Session ID to validate
        
        Returns:
            User object if session is valid, None otherwise
        """
        try:
            if not session_id:
                return None
            
            # Get session
            session = self.db.get_session(session_id)
            if not session:
                return None
            
            # Check if session is expired
            if session.is_expired():
                self.db.delete_session(session_id)
                return None
            
            # Get user
            user = self.db.get_user_by_id(session.user_id)
            return user
            
        except Exception as e:
            self.logger.error(f"Session validation error: {e}")
            return None
    
    def is_admin(self, session_id: str) -> bool:
        """
        Check if the current session belongs to an admin user
        
        Args:
            session_id: Session ID to check
        
        Returns:
            True if user is admin, False otherwise
        """
        user = self.validate_session(session_id)
        return user is not None and user.role == "admin"
    
    def get_current_user(self, session_id: str) -> Optional[User]:
        """
        Get current user from session
        
        Args:
            session_id: Session ID
        
        Returns:
            User object if session is valid, None otherwise
        """
        return self.validate_session(session_id)
    
    def change_password(self, user_id: int, old_password: str, new_password: str) -> Tuple[bool, str]:
        """
        Change user password
        
        Args:
            user_id: User ID
            old_password: Current password
            new_password: New password
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Get user
            user = self.db.get_user_by_id(user_id)
            if not user:
                return False, "User not found"
            
            # Verify old password
            if not bcrypt.checkpw(old_password.encode('utf-8'), user.password_hash.encode('utf-8')):
                return False, "Current password is incorrect"
            
            # Validate new password
            if not new_password or len(new_password) < 6:
                return False, "New password must be at least 6 characters long"
            
            # Hash new password
            new_password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            # Update user
            user.password_hash = new_password_hash
            if self.db.update_user(user):
                self.logger.info(f"Password changed for user ID: {user_id}")
                return True, "Password changed successfully"
            else:
                return False, "Failed to update password"
                
        except Exception as e:
            self.logger.error(f"Password change error: {e}")
            return False, "Password change failed due to an unexpected error"
    
    def update_user_info(self, user_id: int, username: str = None, email: str = None) -> Tuple[bool, str]:
        """
        Update user information
        
        Args:
            user_id: User ID
            username: New username (optional)
            email: New email (optional)
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Get user
            user = self.db.get_user_by_id(user_id)
            if not user:
                return False, "User not found"
            
            # Update fields if provided
            if username:
                if len(username) < 3:
                    return False, "Username must be at least 3 characters long"
                user.username = username.strip().lower()
            
            if email:
                if "@" not in email:
                    return False, "Invalid email address"
                user.email = email.strip().lower()
            
            # Update user
            if self.db.update_user(user):
                self.logger.info(f"User info updated for user ID: {user_id}")
                return True, "User information updated successfully"
            else:
                return False, "Failed to update user information"
                
        except ValueError as e:
            return False, str(e)
        except Exception as e:
            self.logger.error(f"User update error: {e}")
            return False, "User update failed due to an unexpected error"
    
    def get_all_users(self) -> list[User]:
        """
        Get all users (admin only)
        
        Returns:
            List of User objects
        """
        return self.db.get_all_users()
    
    def delete_user(self, user_id: int, admin_session_id: str) -> Tuple[bool, str]:
        """
        Delete user (admin only)
        
        Args:
            user_id: ID of user to delete
            admin_session_id: Session ID of admin performing the action
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Verify admin permission
            if not self.is_admin(admin_session_id):
                return False, "Insufficient permissions"
            
            # Don't allow admin to delete themselves
            admin_user = self.get_current_user(admin_session_id)
            if admin_user and admin_user.id == user_id:
                return False, "Cannot delete your own account"
            
            # Delete user
            if self.db.delete_user(user_id):
                self.logger.info(f"User deleted by admin: user_id={user_id}")
                return True, "User deleted successfully"
            else:
                return False, "Failed to delete user"
                
        except Exception as e:
            self.logger.error(f"User deletion error: {e}")
            return False, "User deletion failed due to an unexpected error"
    
    def _generate_session_id(self) -> str:
        """Generate a secure random session ID"""
        return secrets.token_urlsafe(32)
    
    def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions
        
        Returns:
            Number of sessions cleaned up
        """
        return self.db.clean_expired_sessions()