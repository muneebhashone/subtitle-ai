"""
Database models for authentication and user management
"""

import sqlite3
import datetime
import json
from typing import Optional, Dict, Any, List
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


@dataclass
class AnalyticsEvent:
    """Analytics event model for tracking user activities"""
    id: Optional[int] = None
    user_id: int = 0
    event_type: str = ""  # 'transcription_start', 'transcription_complete', 'translation', 'download', 'upload', 'error'
    event_data: Optional[Dict[str, Any]] = None  # JSON data specific to event type
    timestamp: Optional[datetime.datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary"""
        data = asdict(self)
        if self.event_data:
            data['event_data'] = json.dumps(self.event_data)
        return data


@dataclass
class FileAnalytics:
    """File processing analytics model"""
    id: Optional[int] = None
    user_id: int = 0
    filename: str = ""
    file_size: int = 0  # bytes
    duration: Optional[float] = None  # seconds
    model_used: str = ""
    source_language: str = ""
    target_languages: Optional[List[str]] = None  # for translations
    output_formats: Optional[List[str]] = None  # srt, vtt, ass, etc.
    processing_time: Optional[float] = None  # seconds
    success: bool = True
    error_message: Optional[str] = None
    timestamp: Optional[datetime.datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert file analytics to dictionary"""
        data = asdict(self)
        if self.target_languages:
            data['target_languages'] = json.dumps(self.target_languages)
        if self.output_formats:
            data['output_formats'] = json.dumps(self.output_formats)
        return data


@dataclass
class UsageMetrics:
    """Daily usage metrics per user"""
    id: Optional[int] = None
    user_id: int = 0
    date: Optional[datetime.date] = None
    transcriptions_count: int = 0
    translations_count: int = 0
    total_processing_time: float = 0.0  # seconds
    total_file_size: int = 0  # bytes
    errors_count: int = 0
    unique_models_used: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert usage metrics to dictionary"""
        data = asdict(self)
        if self.unique_models_used:
            data['unique_models_used'] = json.dumps(self.unique_models_used)
        return data


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
            """,
            # Analytics tables
            """
            CREATE TABLE IF NOT EXISTS analytics_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                event_data TEXT,  -- JSON data
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS file_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                file_size INTEGER DEFAULT 0,
                duration REAL,
                model_used TEXT NOT NULL,
                source_language TEXT DEFAULT '',
                target_languages TEXT,  -- JSON array
                output_formats TEXT,     -- JSON array
                processing_time REAL,
                success BOOLEAN DEFAULT 1,
                error_message TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS usage_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date DATE NOT NULL,
                transcriptions_count INTEGER DEFAULT 0,
                translations_count INTEGER DEFAULT 0,
                total_processing_time REAL DEFAULT 0.0,
                total_file_size INTEGER DEFAULT 0,
                errors_count INTEGER DEFAULT 0,
                unique_models_used TEXT,  -- JSON array
                UNIQUE(user_id, date),
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
            """,
            # Analytics indexes
            """
            CREATE INDEX IF NOT EXISTS idx_analytics_events_user_id ON analytics_events(user_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_analytics_events_type ON analytics_events(event_type)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_analytics_events_timestamp ON analytics_events(timestamp)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_file_analytics_user_id ON file_analytics(user_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_file_analytics_timestamp ON file_analytics(timestamp)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_usage_metrics_user_id ON usage_metrics(user_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_usage_metrics_date ON usage_metrics(date)
            """
        ]