"""
Analytics configuration and privacy controls
"""

import os
from typing import Dict, Any

# Default analytics configuration
DEFAULT_ANALYTICS_CONFIG = {
    'enabled': True,
    'retention_days': 90,
    'anonymize_data': False,
    'collect_user_events': True,
    'collect_file_analytics': True,
    'collect_performance_metrics': True
}

# Analytics configuration schema
ANALYTICS_CONFIG_SCHEMA = {
    'enabled': {
        'type': 'boolean',
        'default': True,
        'description': 'Enable or disable analytics collection'
    },
    'retention_days': {
        'type': 'integer',
        'default': 90,
        'min': 7,
        'max': 365,
        'description': 'Number of days to retain analytics data'
    },
    'anonymize_data': {
        'type': 'boolean',
        'default': False,
        'description': 'Anonymize user data in analytics'
    },
    'collect_user_events': {
        'type': 'boolean',
        'default': True,
        'description': 'Collect user activity events'
    },
    'collect_file_analytics': {
        'type': 'boolean',
        'default': True,
        'description': 'Collect file processing analytics'
    },
    'collect_performance_metrics': {
        'type': 'boolean',
        'default': True,
        'description': 'Collect system performance metrics'
    }
}


def get_analytics_config() -> Dict[str, Any]:
    """Get analytics configuration from environment and defaults"""
    config = DEFAULT_ANALYTICS_CONFIG.copy()
    
    # Override with environment variables
    if 'SUBSAI_ANALYTICS_ENABLED' in os.environ:
        config['enabled'] = os.getenv('SUBSAI_ANALYTICS_ENABLED', 'true').lower() == 'true'
    
    if 'SUBSAI_ANALYTICS_RETENTION_DAYS' in os.environ:
        try:
            config['retention_days'] = int(os.getenv('SUBSAI_ANALYTICS_RETENTION_DAYS', '90'))
        except ValueError:
            pass
    
    if 'SUBSAI_ANALYTICS_ANONYMIZE' in os.environ:
        config['anonymize_data'] = os.getenv('SUBSAI_ANALYTICS_ANONYMIZE', 'false').lower() == 'true'
    
    return config


def validate_admin_access(user_role: str) -> bool:
    """Validate that user has admin access for analytics"""
    return user_role == 'admin'


def get_privacy_notice() -> str:
    """Get privacy notice for analytics collection"""
    return """
    ## Analytics Privacy Notice
    
    SubsAI collects usage analytics to improve the service and provide insights to administrators.
    
    **What we collect:**
    - File processing statistics (file size, processing time, models used)
    - User activity events (transcriptions, translations, downloads)
    - System performance metrics (success rates, error logs)
    - Export and storage usage patterns
    
    **What we DON'T collect:**
    - File content or actual subtitle text
    - Personal information beyond username/email (already collected for authentication)
    - Sensitive data or proprietary information
    
    **Data Retention:**
    - Analytics data is retained for 90 days by default
    - Data can be anonymized or deleted upon request
    - Only administrators can access analytics data
    
    **Your Rights:**
    - You can request your analytics data to be deleted
    - Analytics collection can be disabled system-wide by administrators
    - Individual users cannot opt-out, but data is aggregated and anonymized
    
    **Security:**
    - All analytics data is stored in the same secure SQLite database as user accounts
    - No external analytics services are used
    - Data never leaves your SubsAI instance
    """


def get_gdpr_compliance_info() -> str:
    """Get GDPR compliance information"""
    return """
    ## GDPR Compliance Information
    
    **Legal Basis for Processing:**
    - Legitimate interest: Improving service performance and reliability
    - Consent: Implicit consent through service usage
    
    **Data Subject Rights:**
    - Right to access: Contact administrators to view your analytics data
    - Right to rectification: Analytics data accuracy is automatically maintained
    - Right to erasure: Contact administrators to delete your analytics data
    - Right to restrict processing: Analytics can be disabled by administrators
    - Right to data portability: Analytics data can be exported in CSV/JSON format
    
    **Data Controller:**
    - Your organization's SubsAI administrator is the data controller
    - SubsAI software itself does not process personal data beyond your local instance
    
    **Data Processor:**
    - SubsAI software acts as a data processor under administrator instructions
    - No third-party processors are involved in analytics
    
    **International Transfers:**
    - No international data transfers occur
    - All data remains within your SubsAI instance
    
    **Retention Period:**
    - Default: 90 days
    - Configurable by administrators (7-365 days)
    - Automatically deleted after retention period
    """