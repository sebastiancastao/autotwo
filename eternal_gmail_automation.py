#!/usr/bin/env python3
"""
ETERNAL Gmail OAuth Automation Script
This version NEVER stops and automatically retries on any error
Runs Gmail processing every 20 minutes forever
"""

import time
import logging
import sys
import json
import argparse
import threading
import http.server
import socketserver
import os
import queue
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta

# Import the original automation class
from python_oauth_automation import GmailOAuthAutomator

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EternalGmailAutomator(GmailOAuthAutomator):
    """Extended version that never stops and retries on all errors"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.retry_delay = 300  # 5 minutes retry delay for errors
        self.max_oauth_retries = 5  # Maximum OAuth retries before longer delay
        self.oauth_retry_count = 0
        
    # Inherits gmail_processing_cycle() method from parent class for single-cycle execution
        
    def eternal_workflow(self):
        """Eternal workflow that never stops"""
        logger.info("🚀 Starting ETERNAL Gmail processing workflow...")
        logger.info("⚠️ This will run FOREVER until manually stopped!")
        logger.info("⚠️ Close the terminal/window to stop the automation")
        
        cycle_count = 0
        oauth_completed = False
        
        while True:  # ETERNAL LOOP - NEVER BREAKS
            try:
                cycle_count += 1
                logger.info(f"🔄 Starting ETERNAL cycle #{cycle_count}")
                
                # Step 1: Ensure OAuth is completed
                if not oauth_completed:
                    logger.info("🔐 OAuth not completed yet, attempting authentication...")
                    oauth_completed = self.attempt_oauth_with_retries()
                    if not oauth_completed:
                        logger.warning(f"⚠️ OAuth failed, retrying in {self.retry_delay} seconds...")
                        time.sleep(self.retry_delay)
                        continue
                
                # Step 2: Confirm Gmail connection (non-blocking)
                if not self.confirm_gmail_connection_eternal():
                    logger.warning("⚠️ Gmail connection not confirmed, but continuing anyway...")
                    # Don't break - just continue with a warning
                
                # Step 3: Set date filter to last 20 minutes (non-blocking)
                if not self.set_date_filter_last_20_minutes_eternal():
                    logger.warning("⚠️ Could not set date filter, using calculated times...")
                    # Don't break - just continue with calculated times
                
                # Step 4: Extract time range (always succeeds with fallback)
                start_hour, end_hour = self.extract_time_range_eternal()
                
                # Step 5: Click Scan & Auto-Process Emails (non-blocking)
                if not self.click_scan_process_button_eternal():
                    logger.warning("⚠️ Could not click Scan & Process button, but continuing cycle...")
                    # Don't break - just continue to next cycle
                
                logger.info(f"✅ ETERNAL cycle #{cycle_count} completed")
                logger.info(f"⏰ Time range processed: {start_hour} - {end_hour}")
                
                # Step 6: Calculate next run time (20 minutes after end_hour)
                next_run_time = self.calculate_next_run_time_eternal(end_hour)
                logger.info(f"⏰ Next ETERNAL cycle scheduled for: {next_run_time}")
                
                # Step 7: Wait until next run time (with interruption handling)
                self.wait_until_next_cycle_eternal(next_run_time)
                
            except KeyboardInterrupt:
                logger.info("🛑 ETERNAL workflow interrupted by user (Ctrl+C)")
                logger.info("💡 To truly stop, close the terminal window")
                logger.info("🔄 Resuming in 10 seconds...")
                time.sleep(10)  # Brief pause then continue
                continue
                
            except Exception as e:
                logger.error(f"❌ Error in ETERNAL cycle #{cycle_count}: {e}")
                logger.info(f"🔄 ETERNAL workflow continuing anyway in {self.retry_delay} seconds...")
                time.sleep(self.retry_delay)
                continue  # Never break - always continue
    
    def attempt_oauth_with_retries(self):
        """Attempt OAuth with retries"""
        logger.info(f"🔐 OAuth attempt {self.oauth_retry_count + 1}")
        
        # Ensure browser driver is set up before OAuth
        if not hasattr(self, 'driver') or not self.driver:
            logger.info("🚀 Setting up browser driver for OAuth...")
            try:
                browser_setup_success = self.setup_driver()
                if not browser_setup_success or not self.driver:
                    logger.error("❌ Failed to set up browser driver for OAuth")
                    self.oauth_retry_count += 1
                    return False
                else:
                    logger.info("✅ Browser driver ready for OAuth")
            except Exception as setup_error:
                logger.error(f"💥 Browser setup error for OAuth: {setup_error}")
                self.oauth_retry_count += 1
                return False
        
        try:
            success = self.monitor_oauth_process(keep_browser_for_workflow=True)
            if success:
                logger.info("✅ OAuth completed successfully!")
                self.oauth_retry_count = 0  # Reset retry count on success
                return True
            else:
                self.oauth_retry_count += 1
                logger.warning(f"⚠️ OAuth attempt {self.oauth_retry_count} failed")
                
                if self.oauth_retry_count >= self.max_oauth_retries:
                    logger.warning(f"⚠️ {self.max_oauth_retries} OAuth attempts failed, longer delay...")
                    time.sleep(self.retry_delay * 2)  # Longer delay after multiple failures
                    self.oauth_retry_count = 0  # Reset counter
                
                return False
                
        except Exception as e:
            logger.error(f"❌ OAuth error: {e}")
            self.oauth_retry_count += 1
            return False
    
    def confirm_gmail_connection_eternal(self):
        """Confirm Gmail connection but never fail"""
        try:
            return self.confirm_gmail_connection()
        except Exception as e:
            logger.warning(f"⚠️ Gmail connection check error: {e}")
            return False  # Return False but don't raise exception
    
    def set_date_filter_last_20_minutes_eternal(self):
        """Set date filter but never fail"""
        try:
            return self.set_date_filter_last_20_minutes()
        except Exception as e:
            logger.warning(f"⚠️ Date filter error: {e}")
            return False  # Return False but don't raise exception
    
    def extract_time_range_eternal(self):
        """Extract time range with guaranteed fallback"""
        try:
            return self.extract_time_range()
        except Exception as e:
            logger.warning(f"⚠️ Time range extraction error: {e}")
            # Always return a fallback time range
            now = datetime.now()
            start_time = now - timedelta(minutes=20)
            start_hour = start_time.strftime("%H:%M")
            end_hour = now.strftime("%H:%M")
            logger.info(f"📅 Using fallback time range: {start_hour} - {end_hour}")
            return start_hour, end_hour
    
    def click_scan_process_button_eternal(self):
        """Click scan process button but never fail"""
        try:
            return self.click_scan_process_button()
        except Exception as e:
            logger.warning(f"⚠️ Scan process button error: {e}")
            return False  # Return False but don't raise exception
    
    def calculate_next_run_time_eternal(self, end_hour):
        """Calculate next run time with guaranteed fallback"""
        try:
            return self.calculate_next_run_time(end_hour)
        except Exception as e:
            logger.warning(f"⚠️ Next run time calculation error: {e}")
            # Fallback: 20 minutes from now
            return datetime.now() + timedelta(minutes=20)
    
    def wait_until_next_cycle_eternal(self, next_run_time):
        """Wait until next cycle with interruption handling"""
        try:
            now = datetime.now()
            wait_seconds = (next_run_time - now).total_seconds()
            
            if wait_seconds <= 0:
                logger.info("⏰ Next cycle time has already passed, starting immediately")
                return
            
            wait_minutes = int(wait_seconds // 60)
            wait_seconds_remaining = int(wait_seconds % 60)
            
            logger.info(f"⏳ ETERNAL wait: {wait_minutes}m {wait_seconds_remaining}s until next cycle...")
            
            # Wait in 1-minute chunks to allow for interruption
            chunk_size = 60  # 1 minute chunks
            total_waited = 0
            
            while total_waited < wait_seconds:
                try:
                    remaining_wait = min(chunk_size, wait_seconds - total_waited)
                    time.sleep(remaining_wait)
                    total_waited += remaining_wait
                    
                    remaining_total = wait_seconds - total_waited
                    if remaining_total > 60:
                        remaining_minutes = int(remaining_total // 60)
                        logger.info(f"⏳ ETERNAL wait continues... {remaining_minutes} minutes remaining")
                        
                except KeyboardInterrupt:
                    logger.info("🛑 Wait interrupted - proceeding to next cycle immediately")
                    return
            
            logger.info("⏰ ETERNAL wait completed, starting next cycle")
            
        except Exception as e:
            logger.warning(f"⚠️ Wait error: {e}")
            logger.info("🔄 Proceeding to next cycle anyway...")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ETERNAL Gmail OAuth Automation - Never Stops!")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    parser.add_argument("--port", type=int, default=8080, help="App port for OAuth redirect")
    parser.add_argument("--password", type=str, help="Password for automatic login")
    parser.add_argument("--debug", action="store_true", help="Debug mode - more detailed logs")
    parser.add_argument("--retry-delay", type=int, default=300, help="Delay in seconds between retries (default: 300)")
    
    args = parser.parse_args()
    
    if not args.password:
        logger.error("❌ Password is required for ETERNAL automation")
        logger.error("💡 Usage: python eternal_gmail_automation.py --password YOUR_PASSWORD")
        sys.exit(1)
    
    logger.info("🚀 Starting ETERNAL Gmail Automation...")
    logger.info("⚠️ This script will run FOREVER!")
    logger.info("⚠️ Close the terminal/window to stop")
    
    automator = EternalGmailAutomator(
        headless=args.headless,
        port=args.port,
        password=args.password,
        debug=args.debug,
        base_url=os.getenv('APP_BASE_URL')  # Use environment variable for base URL
    )
    
    if args.retry_delay:
        automator.retry_delay = args.retry_delay
    
    try:
        automator.eternal_workflow()
    except KeyboardInterrupt:
        logger.info("🛑 ETERNAL automation stopped by user")
    except Exception as e:
        logger.error(f"❌ ETERNAL automation error: {e}")
        logger.info("🔄 Restarting ETERNAL automation...")
        # Even on critical errors, restart
        time.sleep(10)
        automator.eternal_workflow() 