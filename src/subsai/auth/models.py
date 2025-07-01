"""
Database models for authentication and user management
"""

import sqlite3
import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict


@dataclass
class User:
    """User model for authentication"""
    id: Optional[int] = None
    username: str = ""
    email: str = ""
    password_hash: str = ""
    role: str = "user"  # 'user' or 'admin'
    created_at: Optional[datetime.datetime] = None
    is_active: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary, excluding password hash"""
        data = asdict(self)
        if 'password_hash' in data:
            del data['password_hash']
        return data


@dataclass
class Session:
    """Session model for user authentication"""
    session_id: str = ""
    user_id: int = 0
    expires_at: Optional[datetime.datetime] = None
    created_at: Optional[datetime.datetime] = None
    
    def is_expired(self) -> bool:
        """Check if session is expired"""
        if not self.expires_at:
            return True
        return datetime.datetime.now() > self.expires_at


@dataclass
class UserProject:
    """User project model for organizing user's subtitle projects"""
    id: Optional[int] = None
    user_id: int = 0
    name: str = ""
    description: str = ""
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert project to dictionary"""
        return asdict(self)


class DatabaseSchema:
    """Database schema definitions"""
    
    @staticmethod
    def get_create_tables_sql() -> list[str]:
        """Get SQL statements to create all required tables"""
        return [
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user' CHECK (role IN ('user', 'admin')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS user_projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_user_projects_user_id ON user_projects(user_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)
            """
        ]