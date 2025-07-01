#!/usr/bin/env python3
"""
Quick test script to verify analytics functionality
"""

import sys
import os
from pathlib import Path

# Add the src directory to the path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

def test_analytics_import():
    """Test that analytics can be imported"""
    try:
        from subsai.analytics import AnalyticsService
        print("✅ AnalyticsService imported successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to import AnalyticsService: {e}")
        return False

def test_analytics_initialization():
    """Test analytics service initialization"""
    try:
        from subsai.analytics import AnalyticsService
        analytics = AnalyticsService()
        print(f"✅ AnalyticsService initialized, enabled: {analytics.is_enabled()}")
        return True
    except Exception as e:
        print(f"❌ Failed to initialize AnalyticsService: {e}")
        return False

def test_basic_dashboard_import():
    """Test basic dashboard import"""
    try:
        from subsai.analytics.basic_dashboard import render_basic_analytics_dashboard
        print("✅ Basic dashboard imported successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to import basic dashboard: {e}")
        return False

def test_advanced_dashboard_import():
    """Test advanced dashboard import (optional)"""
    try:
        from subsai.analytics.dashboard import render_analytics_dashboard
        print("✅ Advanced dashboard imported successfully")
        return True
    except Exception as e:
        print(f"⚠️ Advanced dashboard not available (this is OK): {e}")
        return False

def main():
    """Run all tests"""
    print("🔍 Testing SubsAI Analytics System")
    print("=" * 40)
    
    tests = [
        ("Analytics Import", test_analytics_import),
        ("Analytics Initialization", test_analytics_initialization),
        ("Basic Dashboard Import", test_basic_dashboard_import),
        ("Advanced Dashboard Import", test_advanced_dashboard_import),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}:")
        result = test_func()
        results.append(result)
    
    print("\n" + "=" * 40)
    print("📊 Test Results:")
    passed = sum(results[:3])  # First 3 tests are required
    required = 3
    print(f"✅ Required tests passed: {passed}/{required}")
    
    if results[3]:
        print("🎨 Advanced features: Available")
    else:
        print("📊 Advanced features: Basic mode (install plotly for enhanced charts)")
    
    if passed == required:
        print("\n🎉 Analytics system is ready!")
        return True
    else:
        print(f"\n❌ {required - passed} required tests failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)