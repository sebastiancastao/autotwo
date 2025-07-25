#!/usr/bin/env python3
"""
Test script for Gmail processing workflow functionality
"""

import sys
import os
import time
from datetime import datetime, timedelta

# Add the main script directory to path
sys.path.append('.')

# Import the main class
from python_oauth_automation import GmailOAuthAutomator

def test_time_calculation():
    """Test the time calculation methods"""
    print("🧪 Testing time calculation methods...")
    
    automator = GmailOAuthAutomator()
    
    # Test calculate_next_run_time
    test_end_hour = "14:30"
    next_run = automator.calculate_next_run_time(test_end_hour)
    print(f"📅 Test: End hour {test_end_hour} -> Next run: {next_run}")
    
    # Test with current time
    now = datetime.now()
    current_hour = now.strftime("%H:%M")
    next_run_current = automator.calculate_next_run_time(current_hour)
    print(f"📅 Current time {current_hour} -> Next run: {next_run_current}")
    
    # Test extract_time_range fallback
    start_hour, end_hour = automator.extract_time_range()
    print(f"⏰ Generated time range: {start_hour} - {end_hour}")
    
    print("✅ Time calculation tests completed")

def test_workflow_methods():
    """Test the workflow methods without browser automation"""
    print("🧪 Testing workflow methods...")
    
    automator = GmailOAuthAutomator()
    
    # Test methods that don't require a browser
    print("📅 Testing time range extraction...")
    start_hour, end_hour = automator.extract_time_range()
    print(f"⏰ Time range: {start_hour} - {end_hour}")
    
    print("📅 Testing next run calculation...")
    next_run = automator.calculate_next_run_time(end_hour)
    print(f"⏰ Next run scheduled for: {next_run}")
    
    print("✅ Workflow method tests completed")

def simulate_workflow_cycle():
    """Simulate a single workflow cycle without browser"""
    print("🔄 Simulating workflow cycle...")
    
    # Simulate time range extraction
    now = datetime.now()
    start_time = now - timedelta(minutes=20)
    
    start_hour = start_time.strftime("%H:%M")
    end_hour = now.strftime("%H:%M")
    
    print(f"📅 Simulated time range: {start_hour} - {end_hour}")
    
    # Calculate next run time
    next_run = now + timedelta(minutes=20)
    print(f"⏰ Next cycle would run at: {next_run.strftime('%H:%M')}")
    
    # Simulate short wait (instead of 20 minutes)
    print("⏳ Simulating wait (5 seconds instead of 20 minutes)...")
    for i in range(5):
        time.sleep(1)
        print(f"   {5-i} seconds remaining...")
    
    print("✅ Workflow cycle simulation completed")

if __name__ == "__main__":
    print("🧪 Starting Gmail Processing Workflow Tests")
    print("=" * 50)
    
    try:
        test_time_calculation()
        print()
        
        test_workflow_methods()
        print()
        
        simulate_workflow_cycle()
        print()
        
        print("🎉 All tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 