#!/usr/bin/env python3
"""
Background Worker for Gmail OAuth Automation
Handles long-running automation tasks separately from the web service
"""

import os
import asyncio
import logging
import signal
import sys
from datetime import datetime, timedelta
import json
import time

import redis
import structlog
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

# Import our automation classes
from eternal_gmail_automation import EternalGmailAutomator

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

class GmailAutomationWorker:
    """Background worker for Gmail automation tasks"""
    
    def __init__(self):
        self.redis_client = None
        self.automator = None
        self.scheduler = BlockingScheduler()
        self.running = False
        self.cycle_count = 0
        self.oauth_completed = False
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info("Received shutdown signal", signal=signum)
        self.stop()
        sys.exit(0)
    
    def init_redis(self):
        """Initialize Redis connection (optional)"""
        # Check if Redis is explicitly disabled
        if os.getenv('DISABLE_REDIS', '').lower() in ['true', '1', 'yes']:
            logger.info("Worker Redis disabled via DISABLE_REDIS environment variable")
            self.redis_client = None
            return True
            
        try:
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.redis_client.ping()
            logger.info("Worker Redis connection established", redis_url=redis_url)
            return True
        except Exception as e:
            logger.warning("Worker Redis not available - continuing without status tracking", 
                          error=str(e),
                          redis_url=os.getenv('REDIS_URL', 'redis://localhost:6379'))
            self.redis_client = None
            return True  # Changed from False to True to allow worker to continue
    
    def init_automator(self):
        """Initialize the Gmail automator"""
        try:
            gmail_email = os.getenv('GMAIL_EMAIL', 'midasportal1234@gmail.com')
            gmail_password = os.getenv('GMAIL_PASSWORD')
            
            if not gmail_password:
                logger.error("Gmail password not provided via environment variable")
                return False
            
            # Use environment variable to control headless mode (default: false for visible browser)
            headless_mode = os.getenv('BROWSER_HEADLESS', 'false').lower() in ['true', '1', 'yes']
            
            self.automator = EternalGmailAutomator(
                headless=headless_mode,  # Controlled by BROWSER_HEADLESS environment variable
                port=8080,
                password=gmail_password,
                debug=False,
                base_url=os.getenv('APP_BASE_URL')  # Use environment variable for base URL
            )
            
            logger.info("Worker Gmail automator initialized", email=gmail_email)
            return True
            
        except Exception as e:
            logger.error("Failed to initialize automator", error=str(e))
            return False
    
    def update_worker_status(self, status_data):
        """Update worker status in Redis"""
        if self.redis_client:
            try:
                self.redis_client.hset("worker_status", mapping=status_data)
                self.redis_client.expire("worker_status", 300)  # Expire after 5 minutes
            except Exception as e:
                logger.warning("Failed to update worker status", error=str(e))
    
    def run_automation_cycle(self):
        """Execute a single automation cycle"""
        try:
            self.cycle_count += 1
            cycle_start = datetime.now()
            
            logger.info("Worker starting automation cycle", cycle=self.cycle_count)
            
            # Update status
            self.update_worker_status({
                "running": "true",
                "current_cycle": str(self.cycle_count),
                "cycle_start": cycle_start.isoformat(),
                "last_heartbeat": datetime.now().isoformat()
            })
            
            if not self.automator:
                error_msg = "Automator not initialized"
                logger.error(error_msg)
                self._record_cycle_error(cycle_start, error_msg)
                return
            
            # Run OAuth if not completed
            if not self.oauth_completed:
                logger.info("Worker attempting OAuth authentication")
                try:
                    oauth_success = self.automator.attempt_oauth_with_retries()
                    self.oauth_completed = oauth_success
                    
                    if not oauth_success:
                        error_msg = f"OAuth failed in worker cycle {self.cycle_count}"
                        logger.error(error_msg)
                        self._record_cycle_error(cycle_start, error_msg)
                        return
                    else:
                        logger.info("Worker OAuth completed successfully")
                        
                except Exception as e:
                    error_msg = f"OAuth error in worker: {str(e)}"
                    logger.error(error_msg, error=str(e))
                    self._record_cycle_error(cycle_start, error_msg)
                    return
            
            # Run the complete Gmail processing cycle (same as non-headless workflow)
            try:
                cycle_success = self.automator.gmail_processing_cycle()
                logger.info("Worker Gmail processing cycle", success=cycle_success)
                
                results = {
                    "cycle_success": cycle_success,
                    "workflow_completed": True
                }
            except Exception as e:
                logger.error("Worker Gmail processing cycle failed", error=str(e))
                results = {
                    "cycle_success": False,
                    "workflow_completed": False,
                    "error": str(e)
                }
            
            # Record successful cycle
            cycle_end = datetime.now()
            cycle_duration = (cycle_end - cycle_start).total_seconds()
            
            cycle_result = {
                "cycle_number": self.cycle_count,
                "start_time": cycle_start.isoformat(),
                "end_time": cycle_end.isoformat(),
                "duration_seconds": cycle_duration,
                "success": results.get("cycle_success", False),
                "worker_id": "worker-1",
                "workflow_completed": results.get("workflow_completed", False),
                "error": results.get("error", None)
            }
            
            # Store in Redis
            if self.redis_client:
                try:
                    self.redis_client.lpush("worker_cycle_history", json.dumps(cycle_result))
                    self.redis_client.ltrim("worker_cycle_history", 0, 199)  # Keep last 200 cycles
                except Exception as e:
                    logger.warning("Failed to store cycle result", error=str(e))
            
            # Update final status
            next_cycle = cycle_start + timedelta(minutes=20)
            self.update_worker_status({
                "running": "true",
                "current_cycle": str(self.cycle_count),
                "last_cycle_end": cycle_end.isoformat(),
                "next_cycle": next_cycle.isoformat(),
                "last_heartbeat": datetime.now().isoformat(),
                "oauth_completed": str(self.oauth_completed)
            })
            
            logger.info("Worker automation cycle completed successfully", 
                       cycle=self.cycle_count,
                       duration=f"{cycle_duration:.2f}s",
                       time_range=f"{results.get('start_hour', 'N/A')} - {results.get('end_hour', 'N/A')}")
            
        except Exception as e:
            error_msg = f"Critical error in worker cycle {self.cycle_count}: {str(e)}"
            logger.error("Worker cycle failed with critical error", cycle=self.cycle_count, error=str(e))
            self._record_cycle_error(cycle_start, error_msg)
            
            # Update status with error
            self.update_worker_status({
                "running": "true",
                "current_cycle": str(self.cycle_count),
                "last_error": error_msg,
                "last_heartbeat": datetime.now().isoformat()
            })
    
    def _record_cycle_error(self, cycle_start, error_msg):
        """Record a cycle error"""
        cycle_end = datetime.now()
        error_result = {
            "cycle_number": self.cycle_count,
            "start_time": cycle_start.isoformat(),
            "end_time": cycle_end.isoformat(),
            "success": False,
            "error_message": error_msg,
            "worker_id": "worker-1"
        }
        
        if self.redis_client:
            try:
                self.redis_client.lpush("worker_cycle_history", json.dumps(error_result))
                self.redis_client.lpush("worker_errors", json.dumps(error_result))
                self.redis_client.ltrim("worker_errors", 0, 49)  # Keep last 50 errors
            except Exception as e:
                logger.warning("Failed to store error result", error=str(e))
    
    def heartbeat(self):
        """Send periodic heartbeat to indicate worker is alive"""
        try:
            self.update_worker_status({
                "last_heartbeat": datetime.now().isoformat(),
                "running": "true" if self.running else "false"
            })
            logger.debug("Worker heartbeat sent")
        except Exception as e:
            logger.warning("Failed to send worker heartbeat", error=str(e))
    
    def start(self):
        """Start the worker"""
        logger.info("Starting Gmail Automation Worker")
        
        # Initialize Redis (optional)
        if not self.init_redis():
            logger.error("Failed to initialize Redis - this shouldn't happen now")
            return False
        
        # Initialize automator
        if not self.init_automator():
            logger.error("Failed to initialize automator, cannot start worker")
            return False
        
        self.running = True
        
        try:
            # Schedule the automation cycle to run every 20 minutes
            self.scheduler.add_job(
                self.run_automation_cycle,
                trigger=IntervalTrigger(minutes=20),
                id='gmail_automation_cycle',
                replace_existing=True,
                next_run_time=datetime.now() + timedelta(seconds=60)  # Start after 1 minute
            )
            
            # Schedule heartbeat every 60 seconds
            self.scheduler.add_job(
                self.heartbeat,
                trigger=IntervalTrigger(seconds=60),
                id='worker_heartbeat',
                replace_existing=True,
                next_run_time=datetime.now() + timedelta(seconds=10)  # Start after 10 seconds
            )
            
            # Send initial status
            self.update_worker_status({
                "started": datetime.now().isoformat(),
                "running": "true",
                "current_cycle": "0",
                "oauth_completed": "false",
                "worker_id": "worker-1"
            })
            
            logger.info("Worker scheduled jobs created, starting scheduler...")
            
            # Start the scheduler (this blocks)
            self.scheduler.start()
            
        except Exception as e:
            logger.error("Failed to start worker scheduler", error=str(e))
            return False
    
    def stop(self):
        """Stop the worker"""
        logger.info("Stopping Gmail Automation Worker")
        
        self.running = False
        
        try:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=True)
            
            # Update final status
            self.update_worker_status({
                "running": "false",
                "stopped": datetime.now().isoformat(),
                "last_heartbeat": datetime.now().isoformat()
            })
            
            logger.info("Worker stopped successfully")
            
        except Exception as e:
            logger.error("Error stopping worker", error=str(e))

def main():
    """Main entry point for the worker"""
    logger.info("Gmail Automation Worker starting up")
    
    worker = GmailAutomationWorker()
    
    try:
        # Start the worker (this blocks until shutdown)
        success = worker.start()
        if not success:
            logger.error("Failed to start worker")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
        worker.stop()
        
    except Exception as e:
        logger.error("Unexpected error in worker", error=str(e))
        worker.stop()
        sys.exit(1)
    
    logger.info("Worker shutdown complete")

if __name__ == "__main__":
    main() 