"""
Database connection and management for SubsAI authentication system
"""

import sqlite3
import os
import datetime
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from .models import User, Session, UserProject, DatabaseSchema


class Database:
    """Database manager for SQLite operations"""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database connection
        
        Args:
            db_path: Path to SQLite database file. If None, uses default location.
        """
        if db_path is None:
            # Default to a data directory in the project root
            project_root = Path(__file__).parent.parent.parent.parent
            data_dir = project_root / "data"
            data_dir.mkdir(exist_ok=True)
            db_path = str(data_dir / "subsai_auth.db")
        
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self._init_database()
    
    def _init_database(self):
        """Initialize database and create tables if they don't exist"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Create all tables
                for sql in DatabaseSchema.get_create_tables_sql():
                    cursor.execute(sql)
                
                conn.commit()
                self.logger.info(f"Database initialized at {self.db_path}")
                
                # Create default admin user if no users exist
                self._create_default_admin()
                
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            raise
    
    def _create_default_admin(self):
        """Create default admin user if no users exist"""
        try:
            if self.get_user_count() == 0:
                import bcrypt
                
                # Default admin credentials (user should change these)
                default_password = "admin123"
                password_hash = bcrypt.hashpw(default_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                
                admin_user = User(
                    username="admin",
                    email="admin@subsai.local",
                    password_hash=password_hash,
                    role="admin",
                    created_at=datetime.datetime.now()
                )
                
                self.create_user(admin_user)
                self.logger.warning("Created default admin user (username: admin, password: admin123). Please change these credentials!")
                
        except Exception as e:
            self.logger.error(f"Failed to create default admin user: {e}")
    
    @contextmanager
    def get_connection(self):
        """Get database connection with automatic cleanup"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row  # Enable column access by name
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.close()
    
    # User operations
    def create_user(self, user: User) -> Optional[int]:
        """Create a new user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO users (username, email, password_hash, role, created_at, is_active)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (user.username, user.email, user.password_hash, user.role, 
                     user.created_at or datetime.datetime.now(), user.is_active)
                )
                conn.commit()
                return cursor.lastrowid
        except sqlite3.IntegrityError as e:
            if "username" in str(e):
                raise ValueError("Username already exists")
            elif "email" in str(e):
                raise ValueError("Email already exists")
            else:
                raise ValueError(f"User creation failed: {e}")
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE username = ? AND is_active = 1", (username,))
                row = cursor.fetchone()
                
                if row:
                    return User(
                        id=row['id'],
                        username=row['username'],
                        email=row['email'],
                        password_hash=row['password_hash'],
                        role=row['role'],
                        created_at=datetime.datetime.fromisoformat(row['created_at']),
                        is_active=bool(row['is_active'])
                    )
        except Exception as e:
            self.logger.error(f"Error getting user by username: {e}")
        return None
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE id = ? AND is_active = 1", (user_id,))
                row = cursor.fetchone()
                
                if row:
                    return User(
                        id=row['id'],
                        username=row['username'],
                        email=row['email'],
                        password_hash=row['password_hash'],
                        role=row['role'],
                        created_at=datetime.datetime.fromisoformat(row['created_at']),
                        is_active=bool(row['is_active'])
                    )
        except Exception as e:
            self.logger.error(f"Error getting user by ID: {e}")
        return None
    
    def get_all_users(self) -> List[User]:
        """Get all active users"""
        users = []
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE is_active = 1 ORDER BY created_at DESC")
                rows = cursor.fetchall()
                
                for row in rows:
                    user = User(
                        id=row['id'],
                        username=row['username'],
                        email=row['email'],
                        password_hash=row['password_hash'],
                        role=row['role'],
                        created_at=datetime.datetime.fromisoformat(row['created_at']),
                        is_active=bool(row['is_active'])
                    )
                    users.append(user)
        except Exception as e:
            self.logger.error(f"Error getting all users: {e}")
        return users
    
    def get_user_count(self) -> int:
        """Get total number of active users"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
                return cursor.fetchone()[0]
        except Exception as e:
            self.logger.error(f"Error getting user count: {e}")
            return 0
    
    def update_user(self, user: User) -> bool:
        """Update user information"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE users 
                    SET username = ?, email = ?, password_hash = ?, role = ?, is_active = ?
                    WHERE id = ?
                    """,
                    (user.username, user.email, user.password_hash, user.role, user.is_active, user.id)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            self.logger.error(f"Error updating user: {e}")
            return False
    
    def delete_user(self, user_id: int) -> bool:
        """Soft delete user (set is_active to False)"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            self.logger.error(f"Error deleting user: {e}")
            return False
    
    # Session operations
    def create_session(self, session: Session) -> bool:
        """Create a new session"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO sessions (session_id, user_id, expires_at, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (session.session_id, session.user_id, session.expires_at,
                     session.created_at or datetime.datetime.now())
                )
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"Error creating session: {e}")
            return False
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
                row = cursor.fetchone()
                
                if row:
                    return Session(
                        session_id=row['session_id'],
                        user_id=row['user_id'],
                        expires_at=datetime.datetime.fromisoformat(row['expires_at']),
                        created_at=datetime.datetime.fromisoformat(row['created_at'])
                    )
        except Exception as e:
            self.logger.error(f"Error getting session: {e}")
        return None
    
    def delete_session(self, session_id: str) -> bool:
        """Delete session"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            self.logger.error(f"Error deleting session: {e}")
            return False
    
    def clean_expired_sessions(self) -> int:
        """Clean up expired sessions"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM sessions WHERE expires_at < ?", (datetime.datetime.now(),))
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            self.logger.error(f"Error cleaning expired sessions: {e}")
            return 0
    
    # Project operations
    def create_project(self, project: UserProject) -> Optional[int]:
        """Create a new user project"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.datetime.now()
                cursor.execute(
                    """
                    INSERT INTO user_projects (user_id, name, description, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (project.user_id, project.name, project.description, now, now)
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            self.logger.error(f"Error creating project: {e}")
            return None
    
    def get_user_projects(self, user_id: int) -> List[UserProject]:
        """Get all projects for a user"""
        projects = []
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM user_projects WHERE user_id = ? ORDER BY updated_at DESC",
                    (user_id,)
                )
                rows = cursor.fetchall()
                
                for row in rows:
                    project = UserProject(
                        id=row['id'],
                        user_id=row['user_id'],
                        name=row['name'],
                        description=row['description'],
                        created_at=datetime.datetime.fromisoformat(row['created_at']),
                        updated_at=datetime.datetime.fromisoformat(row['updated_at'])
                    )
                    projects.append(project)
        except Exception as e:
            self.logger.error(f"Error getting user projects: {e}")
        return projects
    
    def get_project_by_id(self, project_id: int, user_id: int) -> Optional[UserProject]:
        """Get project by ID (ensuring it belongs to the user)"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM user_projects WHERE id = ? AND user_id = ?",
                    (project_id, user_id)
                )
                row = cursor.fetchone()
                
                if row:
                    return UserProject(
                        id=row['id'],
                        user_id=row['user_id'],
                        name=row['name'],
                        description=row['description'],
                        created_at=datetime.datetime.fromisoformat(row['created_at']),
                        updated_at=datetime.datetime.fromisoformat(row['updated_at'])
                    )
        except Exception as e:
            self.logger.error(f"Error getting project: {e}")
        return None
    
    def update_project(self, project: UserProject) -> bool:
        """Update project"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE user_projects 
                    SET name = ?, description = ?, updated_at = ?
                    WHERE id = ? AND user_id = ?
                    """,
                    (project.name, project.description, datetime.datetime.now(),
                     project.id, project.user_id)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            self.logger.error(f"Error updating project: {e}")
            return False
    
    def delete_project(self, project_id: int, user_id: int) -> bool:
        """Delete project"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM user_projects WHERE id = ? AND user_id = ?",
                    (project_id, user_id)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            self.logger.error(f"Error deleting project: {e}")
            return False