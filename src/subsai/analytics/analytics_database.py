"""
Database operations for analytics data
"""

import sqlite3
import datetime
import json
import logging
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager
from ..auth.models import AnalyticsEvent, FileAnalytics, UsageMetrics


class AnalyticsDatabase:
    """Database manager for analytics operations"""
    
    def __init__(self, db_path: str):
        """
        Initialize analytics database connection
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
    
    @contextmanager
    def get_connection(self):
        """Get database connection with automatic cleanup"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.close()
    
    # Analytics Events
    def create_event(self, event: AnalyticsEvent) -> Optional[int]:
        """Create a new analytics event"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                event_data_json = json.dumps(event.event_data) if event.event_data else None
                cursor.execute(
                    """
                    INSERT INTO analytics_events (user_id, event_type, event_data, timestamp)
                    VALUES (?, ?, ?, ?)
                    """,
                    (event.user_id, event.event_type, event_data_json, 
                     event.timestamp or datetime.datetime.now())
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            self.logger.error(f"Error creating analytics event: {e}")
            return None
    
    def get_events_by_user(self, user_id: int, limit: int = 100) -> List[AnalyticsEvent]:
        """Get recent events for a user"""
        events = []
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM analytics_events 
                    WHERE user_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                    """, 
                    (user_id, limit)
                )
                rows = cursor.fetchall()
                
                for row in rows:
                    event_data = json.loads(row['event_data']) if row['event_data'] else None
                    event = AnalyticsEvent(
                        id=row['id'],
                        user_id=row['user_id'],
                        event_type=row['event_type'],
                        event_data=event_data,
                        timestamp=datetime.datetime.fromisoformat(row['timestamp'])
                    )
                    events.append(event)
        except Exception as e:
            self.logger.error(f"Error getting events by user: {e}")
        return events
    
    def get_events_by_type(self, event_type: str, start_date: Optional[datetime.datetime] = None, 
                          end_date: Optional[datetime.datetime] = None) -> List[AnalyticsEvent]:
        """Get events by type within date range"""
        events = []
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT * FROM analytics_events WHERE event_type = ?"
                params = [event_type]
                
                if start_date:
                    query += " AND timestamp >= ?"
                    params.append(start_date)
                if end_date:
                    query += " AND timestamp <= ?"
                    params.append(end_date)
                
                query += " ORDER BY timestamp DESC"
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                for row in rows:
                    event_data = json.loads(row['event_data']) if row['event_data'] else None
                    event = AnalyticsEvent(
                        id=row['id'],
                        user_id=row['user_id'],
                        event_type=row['event_type'],
                        event_data=event_data,
                        timestamp=datetime.datetime.fromisoformat(row['timestamp'])
                    )
                    events.append(event)
        except Exception as e:
            self.logger.error(f"Error getting events by type: {e}")
        return events
    
    # File Analytics
    def create_file_analytics(self, analytics: FileAnalytics) -> Optional[int]:
        """Create file analytics record"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                target_langs = json.dumps(analytics.target_languages) if analytics.target_languages else None
                output_formats = json.dumps(analytics.output_formats) if analytics.output_formats else None
                
                cursor.execute(
                    """
                    INSERT INTO file_analytics 
                    (user_id, filename, file_size, duration, model_used, source_language, 
                     target_languages, output_formats, processing_time, success, error_message, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (analytics.user_id, analytics.filename, analytics.file_size, analytics.duration,
                     analytics.model_used, analytics.source_language, target_langs, output_formats,
                     analytics.processing_time, analytics.success, analytics.error_message,
                     analytics.timestamp or datetime.datetime.now())
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            self.logger.error(f"Error creating file analytics: {e}")
            return None
    
    def get_file_analytics_by_user(self, user_id: int, limit: int = 50) -> List[FileAnalytics]:
        """Get file analytics for a user"""
        analytics = []
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM file_analytics 
                    WHERE user_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                    """,
                    (user_id, limit)
                )
                rows = cursor.fetchall()
                
                for row in rows:
                    target_langs = json.loads(row['target_languages']) if row['target_languages'] else None
                    output_formats = json.loads(row['output_formats']) if row['output_formats'] else None
                    
                    file_analytics = FileAnalytics(
                        id=row['id'],
                        user_id=row['user_id'],
                        filename=row['filename'],
                        file_size=row['file_size'],
                        duration=row['duration'],
                        model_used=row['model_used'],
                        source_language=row['source_language'],
                        target_languages=target_langs,
                        output_formats=output_formats,
                        processing_time=row['processing_time'],
                        success=bool(row['success']),
                        error_message=row['error_message'],
                        timestamp=datetime.datetime.fromisoformat(row['timestamp'])
                    )
                    analytics.append(file_analytics)
        except Exception as e:
            self.logger.error(f"Error getting file analytics by user: {e}")
        return analytics
    
    # Usage Metrics
    def update_usage_metrics(self, user_id: int, date: datetime.date, 
                           transcriptions: int = 0, translations: int = 0,
                           processing_time: float = 0.0, file_size: int = 0,
                           errors: int = 0, models_used: List[str] = None) -> bool:
        """Update or create daily usage metrics for a user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                models_json = json.dumps(list(set(models_used))) if models_used else None
                
                cursor.execute(
                    """
                    INSERT INTO usage_metrics 
                    (user_id, date, transcriptions_count, translations_count, 
                     total_processing_time, total_file_size, errors_count, unique_models_used)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, date) DO UPDATE SET
                        transcriptions_count = transcriptions_count + excluded.transcriptions_count,
                        translations_count = translations_count + excluded.translations_count,
                        total_processing_time = total_processing_time + excluded.total_processing_time,
                        total_file_size = total_file_size + excluded.total_file_size,
                        errors_count = errors_count + excluded.errors_count,
                        unique_models_used = CASE 
                            WHEN excluded.unique_models_used IS NOT NULL THEN excluded.unique_models_used
                            ELSE unique_models_used
                        END
                    """,
                    (user_id, date, transcriptions, translations, processing_time, 
                     file_size, errors, models_json)
                )
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"Error updating usage metrics: {e}")
            return False
    
    def get_usage_metrics_by_user(self, user_id: int, days: int = 30) -> List[UsageMetrics]:
        """Get usage metrics for a user over specified days"""
        metrics = []
        try:
            start_date = datetime.date.today() - datetime.timedelta(days=days)
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM usage_metrics 
                    WHERE user_id = ? AND date >= ? 
                    ORDER BY date DESC
                    """,
                    (user_id, start_date)
                )
                rows = cursor.fetchall()
                
                for row in rows:
                    models_used = json.loads(row['unique_models_used']) if row['unique_models_used'] else None
                    metric = UsageMetrics(
                        id=row['id'],
                        user_id=row['user_id'],
                        date=datetime.date.fromisoformat(row['date']),
                        transcriptions_count=row['transcriptions_count'],
                        translations_count=row['translations_count'],
                        total_processing_time=row['total_processing_time'],
                        total_file_size=row['total_file_size'],
                        errors_count=row['errors_count'],
                        unique_models_used=models_used
                    )
                    metrics.append(metric)
        except Exception as e:
            self.logger.error(f"Error getting usage metrics by user: {e}")
        return metrics
    
    # System-wide analytics
    def get_system_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get system-wide statistics"""
        try:
            start_date = datetime.date.today() - datetime.timedelta(days=days)
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Total files processed
                cursor.execute(
                    "SELECT COUNT(*) FROM file_analytics WHERE DATE(timestamp) >= ?",
                    (start_date,)
                )
                total_files = cursor.fetchone()[0]
                
                # Total processing time
                cursor.execute(
                    "SELECT SUM(processing_time) FROM file_analytics WHERE DATE(timestamp) >= ?",
                    (start_date,)
                )
                total_processing_time = cursor.fetchone()[0] or 0
                
                # Success rate
                cursor.execute(
                    "SELECT COUNT(*) FROM file_analytics WHERE success = 1 AND DATE(timestamp) >= ?",
                    (start_date,)
                )
                successful_files = cursor.fetchone()[0]
                
                # Most used models
                cursor.execute(
                    """
                    SELECT model_used, COUNT(*) as count 
                    FROM file_analytics 
                    WHERE DATE(timestamp) >= ? 
                    GROUP BY model_used 
                    ORDER BY count DESC 
                    LIMIT 5
                    """,
                    (start_date,)
                )
                top_models = [{"model": row[0], "count": row[1]} for row in cursor.fetchall()]
                
                # Most used formats
                cursor.execute(
                    "SELECT output_formats FROM file_analytics WHERE DATE(timestamp) >= ?",
                    (start_date,)
                )
                format_counts = {}
                for row in cursor.fetchall():
                    if row[0]:
                        formats = json.loads(row[0])
                        for fmt in formats:
                            format_counts[fmt] = format_counts.get(fmt, 0) + 1
                
                top_formats = [{"format": k, "count": v} for k, v in 
                             sorted(format_counts.items(), key=lambda x: x[1], reverse=True)[:5]]
                
                # Active users
                cursor.execute(
                    "SELECT COUNT(DISTINCT user_id) FROM file_analytics WHERE DATE(timestamp) >= ?",
                    (start_date,)
                )
                active_users = cursor.fetchone()[0]
                
                return {
                    "total_files_processed": total_files,
                    "total_processing_time": total_processing_time,
                    "success_rate": (successful_files / total_files * 100) if total_files > 0 else 0,
                    "top_models": top_models,
                    "top_formats": top_formats,
                    "active_users": active_users,
                    "period_days": days
                }
        except Exception as e:
            self.logger.error(f"Error getting system stats: {e}")
            return {}
    
    def get_user_rankings(self, metric: str = "transcriptions_count", days: int = 30) -> List[Dict[str, Any]]:
        """Get user rankings by specified metric"""
        try:
            start_date = datetime.date.today() - datetime.timedelta(days=days)
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"""
                    SELECT u.username, SUM(um.{metric}) as total
                    FROM usage_metrics um
                    JOIN users u ON u.id = um.user_id
                    WHERE um.date >= ?
                    GROUP BY um.user_id, u.username
                    ORDER BY total DESC
                    LIMIT 10
                    """,
                    (start_date,)
                )
                return [{"username": row[0], "total": row[1]} for row in cursor.fetchall()]
        except Exception as e:
            self.logger.error(f"Error getting user rankings: {e}")
            return []