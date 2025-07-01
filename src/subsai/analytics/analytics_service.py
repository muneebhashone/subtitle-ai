"""
Analytics service for tracking and collecting usage metrics
"""

import datetime
import logging
import os
from typing import Optional, List, Dict, Any
from .analytics_database import AnalyticsDatabase
from .config import get_analytics_config, validate_admin_access
from ..auth.models import AnalyticsEvent, FileAnalytics, UsageMetrics


class AnalyticsService:
    """Service for collecting and managing analytics data"""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize analytics service
        
        Args:
            db_path: Path to SQLite database file. If None, uses default location.
        """
        if db_path is None:
            # Use same database as auth system
            from pathlib import Path
            project_root = Path(__file__).parent.parent.parent.parent
            data_dir = project_root / "data"
            data_dir.mkdir(exist_ok=True)
            db_path = str(data_dir / "subsai_auth.db")
        
        self.analytics_db = AnalyticsDatabase(db_path)
        self.logger = logging.getLogger(__name__)
        self.config = get_analytics_config()
        self.enabled = self.config['enabled']
    
    def is_enabled(self) -> bool:
        """Check if analytics is enabled"""
        return self.enabled
    
    def enable_analytics(self, enabled: bool = True):
        """Enable or disable analytics collection"""
        self.enabled = enabled
        self.logger.info(f"Analytics {'enabled' if enabled else 'disabled'}")
    
    # Event tracking methods
    def track_transcription_start(self, user_id: int, filename: str, model: str, 
                                file_size: int, **kwargs) -> Optional[int]:
        """Track when a transcription starts"""
        if not self.enabled:
            return None
        
        event_data = {
            "filename": filename,
            "model": model,
            "file_size": file_size,
            **kwargs
        }
        
        event = AnalyticsEvent(
            user_id=user_id,
            event_type="transcription_start",
            event_data=event_data,
            timestamp=datetime.datetime.now()
        )
        
        return self.analytics_db.create_event(event)
    
    def track_transcription_complete(self, user_id: int, filename: str, model: str,
                                   processing_time: float, success: bool = True,
                                   error_message: Optional[str] = None, **kwargs) -> Optional[int]:
        """Track when a transcription completes"""
        if not self.enabled:
            return None
        
        event_data = {
            "filename": filename,
            "model": model,
            "processing_time": processing_time,
            "success": success,
            "error_message": error_message,
            **kwargs
        }
        
        event = AnalyticsEvent(
            user_id=user_id,
            event_type="transcription_complete",
            event_data=event_data,
            timestamp=datetime.datetime.now()
        )
        
        return self.analytics_db.create_event(event)
    
    def track_translation(self, user_id: int, filename: str, source_lang: str,
                         target_lang: str, **kwargs) -> Optional[int]:
        """Track translation events"""
        if not self.enabled:
            return None
        
        event_data = {
            "filename": filename,
            "source_language": source_lang,
            "target_language": target_lang,
            **kwargs
        }
        
        event = AnalyticsEvent(
            user_id=user_id,
            event_type="translation",
            event_data=event_data,
            timestamp=datetime.datetime.now()
        )
        
        return self.analytics_db.create_event(event)
    
    def track_download(self, user_id: int, filename: str, format: str, **kwargs) -> Optional[int]:
        """Track file downloads"""
        if not self.enabled:
            return None
        
        event_data = {
            "filename": filename,
            "format": format,
            **kwargs
        }
        
        event = AnalyticsEvent(
            user_id=user_id,
            event_type="download",
            event_data=event_data,
            timestamp=datetime.datetime.now()
        )
        
        return self.analytics_db.create_event(event)
    
    def track_upload(self, user_id: int, destination: str, filename: str, **kwargs) -> Optional[int]:
        """Track file uploads to cloud services"""
        if not self.enabled:
            return None
        
        event_data = {
            "destination": destination,  # 's3', 'ooona', etc.
            "filename": filename,
            **kwargs
        }
        
        event = AnalyticsEvent(
            user_id=user_id,
            event_type="upload",
            event_data=event_data,
            timestamp=datetime.datetime.now()
        )
        
        return self.analytics_db.create_event(event)
    
    def track_error(self, user_id: int, error_type: str, error_message: str, **kwargs) -> Optional[int]:
        """Track errors"""
        if not self.enabled:
            return None
        
        event_data = {
            "error_type": error_type,
            "error_message": error_message,
            **kwargs
        }
        
        event = AnalyticsEvent(
            user_id=user_id,
            event_type="error",
            event_data=event_data,
            timestamp=datetime.datetime.now()
        )
        
        return self.analytics_db.create_event(event)
    
    # File analytics
    def record_file_processing(self, user_id: int, filename: str, file_size: int,
                             model_used: str, processing_time: float,
                             success: bool = True, duration: Optional[float] = None,
                             source_language: str = "", target_languages: Optional[List[str]] = None,
                             output_formats: Optional[List[str]] = None,
                             error_message: Optional[str] = None) -> Optional[int]:
        """Record comprehensive file processing analytics"""
        if not self.enabled:
            return None
        
        analytics = FileAnalytics(
            user_id=user_id,
            filename=filename,
            file_size=file_size,
            duration=duration,
            model_used=model_used,
            source_language=source_language,
            target_languages=target_languages or [],
            output_formats=output_formats or [],
            processing_time=processing_time,
            success=success,
            error_message=error_message,
            timestamp=datetime.datetime.now()
        )
        
        # Also update daily usage metrics
        today = datetime.date.today()
        self.analytics_db.update_usage_metrics(
            user_id=user_id,
            date=today,
            transcriptions=1,
            translations=len(target_languages) if target_languages else 0,
            processing_time=processing_time,
            file_size=file_size,
            errors=0 if success else 1,
            models_used=[model_used]
        )
        
        return self.analytics_db.create_file_analytics(analytics)
    
    # Data retrieval methods
    def get_user_analytics(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive analytics for a specific user"""
        if not self.enabled:
            return {}
        
        try:
            # Get usage metrics
            usage_metrics = self.analytics_db.get_usage_metrics_by_user(user_id, days)
            
            # Get recent file analytics
            file_analytics = self.analytics_db.get_file_analytics_by_user(user_id, 50)
            
            # Get recent events
            events = self.analytics_db.get_events_by_user(user_id, 100)
            
            # Calculate summary statistics
            total_transcriptions = sum(m.transcriptions_count for m in usage_metrics)
            total_translations = sum(m.translations_count for m in usage_metrics)
            total_processing_time = sum(m.total_processing_time for m in usage_metrics)
            total_file_size = sum(m.total_file_size for m in usage_metrics)
            total_errors = sum(m.errors_count for m in usage_metrics)
            
            # Most used models
            model_counts = {}
            for fa in file_analytics:
                model_counts[fa.model_used] = model_counts.get(fa.model_used, 0) + 1
            
            top_models = sorted(model_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            
            # Most used formats
            format_counts = {}
            for fa in file_analytics:
                if fa.output_formats:
                    for fmt in fa.output_formats:
                        format_counts[fmt] = format_counts.get(fmt, 0) + 1
            
            top_formats = sorted(format_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            
            return {
                "user_id": user_id,
                "period_days": days,
                "summary": {
                    "total_transcriptions": total_transcriptions,
                    "total_translations": total_translations,
                    "total_processing_time": total_processing_time,
                    "total_file_size": total_file_size,
                    "total_errors": total_errors,
                    "success_rate": ((total_transcriptions - total_errors) / total_transcriptions * 100) if total_transcriptions > 0 else 0
                },
                "top_models": [{"model": k, "count": v} for k, v in top_models],
                "top_formats": [{"format": k, "count": v} for k, v in top_formats],
                "daily_metrics": [m.to_dict() for m in usage_metrics],
                "recent_files": [fa.to_dict() for fa in file_analytics[:10]],
                "recent_events": [e.to_dict() for e in events[:20]]
            }
        except Exception as e:
            self.logger.error(f"Error getting user analytics: {e}")
            return {}
    
    def get_system_analytics(self, days: int = 30) -> Dict[str, Any]:
        """Get system-wide analytics (admin only)"""
        if not self.enabled:
            return {}
        
        try:
            # Get system statistics
            stats = self.analytics_db.get_system_stats(days)
            
            # Get user rankings
            top_users_transcriptions = self.analytics_db.get_user_rankings("transcriptions_count", days)
            top_users_processing_time = self.analytics_db.get_user_rankings("total_processing_time", days)
            
            return {
                "period_days": days,
                "system_stats": stats,
                "top_users_by_transcriptions": top_users_transcriptions,
                "top_users_by_processing_time": top_users_processing_time
            }
        except Exception as e:
            self.logger.error(f"Error getting system analytics: {e}")
            return {}
    
    def get_all_users_analytics(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get analytics for all users (admin only)"""
        if not self.enabled:
            return []
        
        try:
            from ..auth.database import Database
            db = Database()
            users = db.get_all_users()
            
            user_analytics = []
            for user in users:
                analytics = self.get_user_analytics(user.id, days)
                if analytics:
                    analytics["username"] = user.username
                    analytics["email"] = user.email
                    analytics["role"] = user.role
                    user_analytics.append(analytics)
            
            return user_analytics
        except Exception as e:
            self.logger.error(f"Error getting all users analytics: {e}")
            return []
    
    # Privacy and admin control methods
    def validate_admin_access(self, user_role: str) -> bool:
        """Validate that user has admin access for analytics"""
        return validate_admin_access(user_role)
    
    def delete_user_analytics(self, user_id: int, admin_user_id: int) -> bool:
        """Delete all analytics data for a specific user (admin only)"""
        if not self.enabled:
            return False
        
        try:
            with self.analytics_db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Delete from all analytics tables
                cursor.execute("DELETE FROM analytics_events WHERE user_id = ?", (user_id,))
                cursor.execute("DELETE FROM file_analytics WHERE user_id = ?", (user_id,))
                cursor.execute("DELETE FROM usage_metrics WHERE user_id = ?", (user_id,))
                
                conn.commit()
                
                # Log the deletion
                self.track_admin_action(
                    admin_user_id,
                    "delete_user_analytics",
                    {"deleted_user_id": user_id}
                )
                
                self.logger.info(f"Deleted analytics data for user {user_id} by admin {admin_user_id}")
                return True
        except Exception as e:
            self.logger.error(f"Error deleting user analytics: {e}")
            return False
    
    def export_user_analytics(self, user_id: int, format: str = 'json') -> Optional[str]:
        """Export user analytics data in specified format"""
        if not self.enabled:
            return None
        
        try:
            user_data = self.get_user_analytics(user_id, days=365)  # Get all data
            
            if format.lower() == 'json':
                import json
                return json.dumps(user_data, indent=2, default=str)
            elif format.lower() == 'csv':
                # For CSV, we'd need to flatten the data structure
                # This is a simplified implementation
                import csv
                import io
                
                output = io.StringIO()
                if user_data.get('recent_files'):
                    writer = csv.DictWriter(output, fieldnames=user_data['recent_files'][0].keys())
                    writer.writeheader()
                    writer.writerows(user_data['recent_files'])
                
                return output.getvalue()
            else:
                return None
        except Exception as e:
            self.logger.error(f"Error exporting user analytics: {e}")
            return None
    
    def cleanup_old_data(self, retention_days: Optional[int] = None) -> int:
        """Clean up analytics data older than retention period"""
        if not self.enabled:
            return 0
        
        retention_days = retention_days or self.config['retention_days']
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=retention_days)
        
        try:
            with self.analytics_db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Count records to be deleted
                cursor.execute(
                    "SELECT COUNT(*) FROM analytics_events WHERE timestamp < ?", 
                    (cutoff_date,)
                )
                events_count = cursor.fetchone()[0]
                
                cursor.execute(
                    "SELECT COUNT(*) FROM file_analytics WHERE timestamp < ?", 
                    (cutoff_date,)
                )
                files_count = cursor.fetchone()[0]
                
                # Delete old records
                cursor.execute(
                    "DELETE FROM analytics_events WHERE timestamp < ?", 
                    (cutoff_date,)
                )
                cursor.execute(
                    "DELETE FROM file_analytics WHERE timestamp < ?", 
                    (cutoff_date,)
                )
                cursor.execute(
                    "DELETE FROM usage_metrics WHERE date < ?", 
                    (cutoff_date.date(),)
                )
                
                conn.commit()
                
                total_deleted = events_count + files_count
                self.logger.info(f"Cleaned up {total_deleted} old analytics records")
                return total_deleted
        except Exception as e:
            self.logger.error(f"Error cleaning up old data: {e}")
            return 0
    
    def anonymize_user_data(self, user_id: int) -> bool:
        """Anonymize user data while preserving analytics value"""
        if not self.enabled:
            return False
        
        try:
            with self.analytics_db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Replace user_id with a hash to maintain referential integrity
                # while removing direct user identification
                import hashlib
                anonymous_id = int(hashlib.md5(str(user_id).encode()).hexdigest()[:8], 16)
                
                # Update all tables to use anonymous ID
                cursor.execute(
                    "UPDATE analytics_events SET user_id = ? WHERE user_id = ?", 
                    (anonymous_id, user_id)
                )
                cursor.execute(
                    "UPDATE file_analytics SET user_id = ? WHERE user_id = ?", 
                    (anonymous_id, user_id)
                )
                cursor.execute(
                    "UPDATE usage_metrics SET user_id = ? WHERE user_id = ?", 
                    (anonymous_id, user_id)
                )
                
                conn.commit()
                
                self.logger.info(f"Anonymized analytics data for user {user_id}")
                return True
        except Exception as e:
            self.logger.error(f"Error anonymizing user data: {e}")
            return False
    
    def track_admin_action(self, admin_user_id: int, action: str, details: Dict[str, Any]) -> Optional[int]:
        """Track administrative actions for audit purposes"""
        if not self.enabled:
            return None
        
        event_data = {
            "admin_action": action,
            "details": details
        }
        
        event = AnalyticsEvent(
            user_id=admin_user_id,
            event_type="admin_action",
            event_data=event_data,
            timestamp=datetime.datetime.now()
        )
        
        return self.analytics_db.create_event(event)
    
    def get_retention_policy(self) -> Dict[str, Any]:
        """Get current data retention policy"""
        return {
            "retention_days": self.config['retention_days'],
            "anonymize_data": self.config['anonymize_data'],
            "enabled": self.enabled,
            "last_cleanup": None  # Would need to store this in database
        }
    
    def update_retention_policy(self, retention_days: int, admin_user_id: int) -> bool:
        """Update data retention policy (admin only)"""
        try:
            # Update configuration (in a real implementation, this would persist to config file/database)
            self.config['retention_days'] = max(7, min(365, retention_days))
            
            # Log the policy change
            self.track_admin_action(
                admin_user_id,
                "update_retention_policy",
                {"new_retention_days": retention_days}
            )
            
            self.logger.info(f"Updated retention policy to {retention_days} days")
            return True
        except Exception as e:
            self.logger.error(f"Error updating retention policy: {e}")
            return False