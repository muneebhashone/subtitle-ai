"""
Analytics module for SubsAI usage tracking and metrics
"""

from .analytics_service import AnalyticsService
from .analytics_database import AnalyticsDatabase

# Always include basic dashboard
from .basic_dashboard import render_basic_analytics_dashboard

# Advanced dashboard import is optional (requires plotly)
try:
    from .dashboard import render_analytics_dashboard
    __all__ = ['AnalyticsService', 'AnalyticsDatabase', 'render_analytics_dashboard', 'render_basic_analytics_dashboard']
except ImportError:
    __all__ = ['AnalyticsService', 'AnalyticsDatabase', 'render_basic_analytics_dashboard']