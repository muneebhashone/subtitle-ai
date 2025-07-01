# SubsAI Analytics Implementation

## Overview
A comprehensive analytics system has been implemented for SubsAI to track user activity, file processing, and system performance. The analytics are **admin-only** and include both per-user and system-wide views with privacy controls.

## Architecture

### 1. Database Schema (`src/subsai/auth/models.py`)
Extended the existing SQLite database with three new analytics tables:

- **`analytics_events`**: Tracks all user activities (transcription start/complete, translations, downloads, uploads, errors)
- **`file_analytics`**: Comprehensive file processing metrics (file size, processing time, models used, success/failure)
- **`usage_metrics`**: Daily aggregated metrics per user (transcription count, translation count, processing time, file sizes, errors)

### 2. Analytics Service Layer (`src/subsai/analytics/`)

#### Core Components:
- **`AnalyticsService`**: Main service for collecting and retrieving analytics data
- **`AnalyticsDatabase`**: Database operations for analytics tables
- **`Config`**: Privacy controls and configuration management
- **`Dashboard`**: Admin-only Streamlit dashboard components

#### Key Features:
- Event tracking for all user activities
- Comprehensive file processing analytics
- Privacy controls and data retention policies
- GDPR compliance features
- Admin audit logging

### 3. Integration Points

#### Batch Processing (`src/subsai/batch_processor.py`)
- Tracks transcription start/completion with timing
- Records file processing analytics
- Tracks translation events
- Monitors S3 uploads and downloads
- Error tracking and reporting

#### Web UI (`src/subsai/webui.py`)
- Single file transcription tracking
- Export and download monitoring
- User activity events
- Integration with existing authentication system

#### Admin Panel (`src/subsai/auth/pages.py`)
- New "Analytics" tab in admin interface
- Admin-only access controls
- Privacy management tools

## Analytics Tracked

### 1. File Processing Metrics
- **Files processed**: Count by user and system-wide
- **Processing time**: Individual and aggregated timing data
- **File sizes**: Total data processed per user
- **Success rates**: Percentage of successful vs failed transcriptions
- **Models used**: Most popular transcription models
- **Output formats**: Preferred subtitle formats (SRT, VTT, ASS, OOONA)

### 2. User Activity Events
- **Transcription lifecycle**: Start, completion, errors
- **Translation usage**: Source/target language pairs
- **Download patterns**: File formats and frequency
- **Upload activity**: S3 and OOONA API usage
- **Error tracking**: System errors and user issues

### 3. System Performance
- **Active users**: Daily/weekly active user counts
- **Resource utilization**: Processing time and storage usage
- **Model performance**: Comparative success rates
- **Error rates**: System reliability metrics

## Admin Dashboard Features

### 1. System Overview Tab
- Key performance metrics (files processed, processing time, success rate, active users)
- Most used models and output formats (charts)
- System-wide statistics and trends

### 2. User Analytics Tab
- **All Users View**: Summary table with user statistics
- **Individual User View**: Detailed analytics for specific users
  - Processing statistics and preferences
  - Model and format usage patterns
  - Recent activity and file history

### 3. Performance Metrics Tab
- Average processing times and system reliability
- Model performance comparison
- Resource utilization analysis

### 4. Activity Log Tab
- Recent system events and user activities
- Filterable by event type and time period
- Real-time activity monitoring

### 5. Privacy & Settings Tab
- **Privacy Notice**: Transparent data collection policies
- **GDPR Compliance**: Legal compliance information
- **Data Management**: 
  - Retention policy configuration
  - Old data cleanup tools
  - Analytics enable/disable controls

## Privacy Controls

### 1. Data Retention
- Configurable retention period (7-365 days, default 90 days)
- Automatic cleanup of expired data
- Admin-controlled retention policies

### 2. User Rights
- **Data Export**: JSON/CSV export of user analytics
- **Data Deletion**: Complete removal of user analytics
- **Data Anonymization**: Hash user IDs while preserving analytics value

### 3. Admin Controls
- **Access Control**: Only admin users can view analytics
- **Audit Logging**: All admin actions are tracked
- **Privacy Settings**: System-wide analytics enable/disable

### 4. GDPR Compliance
- **Lawful Basis**: Legitimate interest for service improvement
- **Data Subject Rights**: Access, rectification, erasure, restriction, portability
- **Data Minimization**: Only essential metrics are collected
- **Local Processing**: No external analytics services used

## Security Features

### 1. Access Control
- Admin-only dashboard access via existing authentication system
- Role-based permissions (admin vs regular user)
- Session-based access control

### 2. Data Security
- All data stored in existing secure SQLite database
- No external data transmission
- Local-only analytics processing

### 3. Privacy by Design
- No collection of file content or sensitive data
- Anonymization capabilities built-in
- Configurable data retention and cleanup

## Usage Examples

### 1. Admin Insights
- "How many files are being processed daily?"
- "Which models are most popular among users?"
- "What are the success rates for different file types?"
- "Who are the most active users?"

### 2. Performance Monitoring
- "Is processing time increasing with load?"
- "Which models have the highest success rates?"
- "Are there patterns in user errors?"

### 3. Resource Planning
- "How much storage is being used?"
- "What are peak usage times?"
- "Do we need more processing capacity?"

## Configuration

### Environment Variables
```bash
SUBSAI_ANALYTICS_ENABLED=true          # Enable/disable analytics
SUBSAI_ANALYTICS_RETENTION_DAYS=90     # Data retention period
SUBSAI_ANALYTICS_ANONYMIZE=false       # Auto-anonymize data
```

### Database Tables
Analytics tables are automatically created alongside existing auth tables in the same SQLite database (`./data/subsai_auth.db`).

## Benefits

### 1. For Administrators
- **Usage Insights**: Understand how SubsAI is being used
- **Performance Monitoring**: Track system performance and reliability
- **User Management**: Identify power users and usage patterns
- **Resource Planning**: Make informed decisions about scaling

### 2. For Users
- **Improved Service**: Analytics help identify and fix issues
- **Better Performance**: Optimization based on usage patterns
- **Privacy Protection**: Transparent data practices with user controls

### 3. For System
- **Error Detection**: Proactive identification of issues
- **Performance Optimization**: Data-driven improvements
- **Capacity Planning**: Informed resource allocation
- **Quality Assurance**: Continuous monitoring of success rates

## Implementation Notes

### 1. Non-Breaking Changes
- All analytics functionality is additive
- Existing features continue to work without modification
- Analytics can be disabled without affecting core functionality

### 2. Performance Impact
- Minimal overhead (simple database inserts)
- Asynchronous data collection where possible
- Efficient database queries with proper indexing

### 3. Maintenance
- Automatic data cleanup based on retention policies
- Built-in database maintenance tools
- Self-managing analytics system

## Future Enhancements

### Potential Additions
1. **Real-time Dashboards**: Live metrics and monitoring
2. **Email Reports**: Automated analytics summaries
3. **API Endpoints**: Programmatic access to analytics data
4. **Advanced Visualizations**: Time-series charts and trends
5. **Alerting System**: Notifications for errors or thresholds
6. **Export Formats**: Additional data export options
7. **Comparative Analytics**: Historical trend analysis

### Integration Opportunities
1. **Prometheus/Grafana**: External monitoring integration
2. **Log Aggregation**: Centralized logging systems
3. **Business Intelligence**: BI tool integration
4. **Automated Reporting**: Scheduled analytics reports

This analytics implementation provides a solid foundation for understanding SubsAI usage while maintaining strong privacy protections and admin-only access controls.