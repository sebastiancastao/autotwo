#!/usr/bin/env python3
"""
Web Service for Gmail OAuth Automation
FastAPI-based web service for cloud deployment on Render

DEPLOYMENT BEHAVIOR:
1. Starts as a web service (port 8080) - Render considers deployment "complete"
2. Auto-starts Gmail workflow in background if GMAIL_PASSWORD env var is provided
3. Runs complete workflow: OAuth → Gmail Processing → 20min cycles
4. Provides web dashboard for monitoring and control
5. API endpoints for programmatic access

This solves the Render timeout issue by being a proper web service while
still running the complete Gmail automation workflow in the background.
"""

import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
import base64
import io

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import structlog

# Import our automation classes
from eternal_gmail_automation import EternalGmailAutomator
import redis

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

# Initialize FastAPI app
app = FastAPI(
    title="Gmail OAuth Automation Service",
    description="Cloud-based Gmail OAuth automation for Midas Portal with eternal 20-minute processing cycles",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables
scheduler = AsyncIOScheduler()
automator = None
redis_client = None
automation_status = {
    "running": False,
    "last_cycle": None,
    "next_cycle": None,
    "cycle_count": 0,
    "errors": [],
    "oauth_completed": False,
    "needs_verification": False,
    "verification_message": "",
    "verification_code": None
}

# Pydantic models
class AutomationStatus(BaseModel):
    running: bool
    last_cycle: Optional[datetime]
    next_cycle: Optional[datetime]
    cycle_count: int
    errors: List[str]
    oauth_completed: bool
    needs_verification: bool = False
    verification_message: str = ""
    verification_code: Optional[str] = None

class StartAutomationRequest(BaseModel):
    password: str = Field(..., description="Gmail account password")
    headless: bool = Field(default=False, description="Run browser in headless mode")
    debug: bool = Field(default=False, description="Enable debug mode")

class CycleResult(BaseModel):
    cycle_number: int
    start_time: str
    end_time: str
    success: bool
    error_message: Optional[str] = None

class VerificationCodeRequest(BaseModel):
    verification_code: str = Field(..., description="6-8 digit verification code from 2FA")

# Initialize Redis connection (optional)
def init_redis():
    global redis_client
    
    # Check if Redis is explicitly disabled
    if os.getenv('DISABLE_REDIS', '').lower() in ['true', '1', 'yes']:
        logger.info("Redis disabled via DISABLE_REDIS environment variable")
        redis_client = None
        return
    
    try:
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        redis_client = redis.from_url(redis_url, decode_responses=True)
        redis_client.ping()
        logger.info("Redis connection established", redis_url=redis_url)
    except Exception as e:
        logger.warning("Redis not available - continuing without caching/history features", 
                      error=str(e), 
                      redis_url=os.getenv('REDIS_URL', 'redis://localhost:6379'))
        redis_client = None

# Initialize automation
def init_automator():
    global automator
    
    gmail_email = os.getenv('GMAIL_EMAIL', 'midasportal1234@gmail.com')
    gmail_password = os.getenv('GMAIL_PASSWORD')
    
    if not gmail_password:
        logger.warning("Gmail password not provided via environment variable")
        return None
    
    # Use environment variable to control headless mode (default: false for visible browser)
    headless_mode = os.getenv('BROWSER_HEADLESS', 'false').lower() in ['true', '1', 'yes']
    
    automator = EternalGmailAutomator(
        headless=headless_mode,  # Controlled by BROWSER_HEADLESS environment variable
        port=8080,
        password=gmail_password,
        debug=False,
        base_url=os.getenv('APP_BASE_URL')  # Use environment variable for base URL
    )
    
    # Log browser initialization info
    if hasattr(automator, 'driver') and automator.driver:
        logger.info("Browser driver initialized successfully for screenshots")
    else:
        logger.warning("Browser driver not available - screenshots may not work")
    
    logger.info("Gmail automator initialized", email=gmail_email)
    return automator

# Background automation task
async def run_automation_cycle():
    """Run a single automation cycle with proper timing
    
    This function replicates the complete workflow behavior:
    1. OAuth authentication (if not done)
    2. Gmail processing cycle (confirm connection, set filter, extract time, click process)
    3. Schedule next run 20 minutes after the end of processing time (not from cycle start)
    
    This matches the original --workflow behavior exactly.
    """
    global automation_status, automator
    
    if not automator:
        logger.error("Automator not initialized")
        return
    
    try:
        automation_status["cycle_count"] += 1
        cycle_start = datetime.now()
        
        logger.info("Starting automation cycle", cycle=automation_status["cycle_count"])
        
        # Run OAuth if not completed
        if not automation_status["oauth_completed"]:
            logger.info("Attempting OAuth authentication")
            oauth_success = automator.attempt_oauth_with_retries()
            automation_status["oauth_completed"] = oauth_success
            
            if not oauth_success:
                error_msg = f"OAuth failed in cycle {automation_status['cycle_count']}"
                automation_status["errors"].append(error_msg)
                logger.error(error_msg)
                return
            else:
                logger.info("✅ OAuth completed successfully")
        else:
            logger.info("✅ OAuth already completed, proceeding to Gmail processing")
        
        # Run the complete Gmail processing cycle (same as non-headless workflow)
        cycle_success = automator.gmail_processing_cycle()
        
        if cycle_success:
            # Extract the time range that was processed and calculate next run time
            # This matches the original workflow timing logic
            try:
                start_hour, end_hour = automator.extract_time_range()
                next_run_time = automator.calculate_next_run_time(end_hour)
        
                # Update scheduler for next run based on actual processing time
                if scheduler.running:
                    try:
                        # Remove existing job if it exists, then reschedule
                        try:
                            existing_job = scheduler.get_job('gmail_automation')
                            if existing_job:
                                scheduler.remove_job('gmail_automation')
                                logger.info("📅 Removed existing scheduled job")
                            else:
                                logger.info("📅 No existing job to remove")
                        except Exception:
                            # Job doesn't exist, which is fine
                            logger.info("📅 No existing job found (normal for first run)")
                        
                        # Schedule next run based on processing time
                        scheduler.add_job(
                            run_automation_cycle,
                            trigger='date',  # Single run at specific time
                            run_date=next_run_time,
                            id='gmail_automation',
                            replace_existing=True
                        )
                        automation_status["next_cycle"] = next_run_time
                        logger.info(f"⏰ Next cycle scheduled for: {next_run_time} (20 minutes after processing end time {end_hour})")
                    except Exception as scheduler_error:
                        logger.warning(f"Could not reschedule next run: {scheduler_error}")
                        # Fallback to manual scheduling in 20 minutes
                        automation_status["next_cycle"] = cycle_start + timedelta(minutes=20)
            except Exception as e:
                logger.warning(f"Could not calculate next run time from processing time: {e}")
                # Fallback to simple 20-minute interval
                automation_status["next_cycle"] = cycle_start + timedelta(minutes=20)
        else:
            # If cycle failed, retry in 5 minutes
            automation_status["next_cycle"] = cycle_start + timedelta(minutes=5)
        
        # Update status
        automation_status["last_cycle"] = cycle_start
        
        # Store cycle result in Redis
        if redis_client:
            cycle_result = {
                "cycle_number": automation_status["cycle_count"],
                "success": cycle_success,
                "start_time": cycle_start.isoformat(),
                "end_time": datetime.now().isoformat(),
                "service": "web_service",
                "workflow_completed": cycle_success,
                "next_scheduled": automation_status["next_cycle"].isoformat() if automation_status["next_cycle"] else None
            }
            redis_client.lpush("cycle_history", json.dumps(cycle_result))
            redis_client.ltrim("cycle_history", 0, 99)  # Keep last 100 cycles
        
        logger.info("Automation cycle completed successfully", 
                   cycle=automation_status["cycle_count"],
                   success=cycle_success,
                   next_cycle=automation_status["next_cycle"].isoformat() if automation_status["next_cycle"] else "Not scheduled")
        
    except Exception as e:
        error_msg = f"Error in cycle {automation_status['cycle_count']}: {str(e)}"
        automation_status["errors"].append(error_msg)
        logger.error("Automation cycle failed", cycle=automation_status["cycle_count"], error=str(e))
        
        # Store error in Redis
        if redis_client:
            error_result = {
                "cycle_number": automation_status["cycle_count"],
                "start_time": cycle_start.isoformat(),
                "end_time": datetime.now().isoformat(),
                "success": False,
                "error_message": str(e)
            }
            redis_client.lpush("cycle_history", json.dumps(error_result))

# API Routes
@app.get("/", response_class=HTMLResponse)
async def root():
    """Main dashboard page"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Gmail OAuth Automation Service</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .status { padding: 20px; margin: 20px 0; border-radius: 5px; }
            .running { background: #d4edda; border: 1px solid #c3e6cb; color: #155724; }
            .stopped { background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; }
            .verification { background: #fff3cd; border: 2px solid #ffc107; color: #856404; padding: 25px; margin: 20px 0; border-radius: 10px; box-shadow: 0 4px 8px rgba(255,193,7,0.3); }
            .browser-view { background: #e7f3ff; border: 1px solid #b3d7ff; color: #004085; padding: 20px; margin: 20px 0; border-radius: 5px; }
            .btn { padding: 10px 20px; margin: 10px 5px; border: none; border-radius: 5px; cursor: pointer; }
            .btn-primary { background: #007bff; color: white; }
            .btn-danger { background: #dc3545; color: white; }
            .btn:hover { opacity: 0.8; }
            .logs { background: #f8f9fa; border: 1px solid #dee2e6; padding: 15px; border-radius: 5px; font-family: monospace; max-height: 300px; overflow-y: auto; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 Gmail OAuth Automation Service</h1>
            <p>Cloud-based Gmail processing for <a href="https://midas-portal-f853.vercel.app" target="_blank">Midas Portal</a> with eternal 20-minute cycles</p>
            
            <div id="status" class="status stopped">
                <h3>Status: Loading...</h3>
                <p>Fetching current status...</p>
            </div>
            
            <!-- Enhanced Verification Code Input Section -->
            <div id="verification-section" class="verification" style="display: none;">
                <h3>🔐 Google 2FA Verification Required</h3>
                <div style="background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px; padding: 20px; margin: 15px 0;">
                    <h4 style="margin-top: 0; color: #495057;">📱 Automatic Detection Active</h4>
                    <p style="margin: 10px 0; color: #6c757d;">The system is automatically scanning for verification codes on the page. If a code is detected, it will be used automatically.</p>
                    <p style="margin: 10px 0; color: #6c757d;"><strong>Manual Backup:</strong> If automatic detection fails, enter your code below:</p>
                </div>
                
                <div style="text-align: center; margin: 20px 0;">
                    <label for="verification-code" style="display: block; font-weight: bold; margin-bottom: 8px; color: #495057;">📞 Enter Verification Code from Your Phone:</label>
                    <input type="text" id="verification-code" placeholder="Enter 4-8 digit code" maxlength="8" 
                           style="padding: 15px; font-size: 20px; width: 250px; text-align: center; border: 3px solid #007bff; border-radius: 8px; font-family: monospace; letter-spacing: 2px; box-shadow: 0 2px 4px rgba(0,123,255,0.3);">
                    <br>
                    <button class="btn btn-primary" onclick="submitVerificationCode()" 
                            style="margin-top: 15px; padding: 12px 24px; font-size: 16px; border-radius: 8px;">
                        ✅ Submit Verification Code
                    </button>
                </div>
                
                <div style="text-align: center; margin: 15px 0;">
                    <small style="color: #6c757d;">
                        💡 <strong>Tip:</strong> Check your phone for a text message or push notification with the verification code
                    </small>
                </div>
                
                <div id="verification-message" style="text-align: center; margin: 15px 0; padding: 10px; border-radius: 5px; font-weight: bold;"></div>
                
                <div style="background: #e7f3ff; border: 1px solid #b3d7ff; border-radius: 5px; padding: 15px; margin: 15px 0;">
                    <h5 style="margin-top: 0; color: #004085;">🔍 What the automation is doing:</h5>
                    <ul style="margin: 5px 0; color: #004085; text-align: left;">
                        <li>Scanning the page for displayed verification codes</li>
                        <li>Looking for Google-specific code patterns (G-######)</li>
                        <li>Checking SMS and authenticator app notifications</li>
                        <li>Attempting to automatically enter detected codes</li>
                    </ul>
                    <p style="margin-bottom: 0; color: #004085;"><strong>Note:</strong> If automatic detection works, you won't need to enter anything manually!</p>
                </div>
            </div>
            
            <!-- Live Browser View Section -->
            <div id="browser-view-section" class="browser-view">
                <h3>🖥️ Live Browser View</h3>
                <div style="text-align: center; margin: 15px 0;">
                    <button class="btn btn-primary" onclick="toggleBrowserView()" id="browser-toggle-btn">Show Browser View</button>
                    <button class="btn btn-primary" onclick="refreshScreenshot()" id="refresh-screenshot-btn" style="display: none;">Refresh Screenshot</button>
                    <button class="btn btn-primary" onclick="testScreenshotEndpoint()" id="test-screenshot-btn">Test Browser Connection</button>
                </div>
                <div id="browser-info" style="margin: 10px 0; font-size: 14px; color: #333; background: #f8f9fa; padding: 10px; border-radius: 5px; border: 1px solid #dee2e6; display: none;">
                    <p style="margin: 5px 0;"><strong>🌐 URL:</strong> <span id="current-url">-</span></p>
                    <p style="margin: 5px 0;"><strong>📄 Title:</strong> <span id="page-title">-</span></p>
                    <p style="margin: 5px 0;"><strong>🕐 Last Updated:</strong> <span id="screenshot-timestamp">-</span></p>
                    <p style="margin: 5px 0; font-size: 12px; color: #666;"><em>Auto-refreshes every 5 seconds when visible</em></p>
                </div>
                <div id="screenshot-container" style="text-align: center; border: 2px solid #dee2e6; border-radius: 5px; padding: 10px; background: #f8f9fa; display: none;">
                    <img id="browser-screenshot" style="max-width: 100%; height: auto; border-radius: 5px;" alt="Browser Screenshot">
                    <div id="screenshot-loading" style="padding: 40px; color: #666;">
                        <p>📷 Loading browser view...</p>
                    </div>
                    <div id="screenshot-error" style="padding: 40px; color: #dc3545; background: #f8d7da; border: 1px solid #f5c6cb; border-radius: 5px; margin: 10px 0; display: none;">
                        <p><strong>❌ Unable to capture browser view</strong></p>
                        <p style="font-size: 14px; margin: 10px 0;" id="error-message"></p>
                        <p style="font-size: 12px; color: #666;">
                            <strong>Troubleshooting:</strong><br>
                            • Make sure automation is running<br>
                            • Check if browser is active<br>
                            • Try the "Test Browser Connection" button<br>
                            • Wait for OAuth process to start
                        </p>
                    </div>
                </div>
            </div>
            
            <div>
                <button class="btn btn-primary" onclick="startAutomation()">Start Automation</button>
                <button class="btn btn-danger" onclick="stopAutomation()">Stop Automation</button>
                <button class="btn btn-primary" onclick="refreshStatus()">Refresh Status</button>
            </div>
            
            <h3>Recent Activity</h3>
            <div id="logs" class="logs">Loading logs...</div>
            
            <h3>Configuration</h3>
            <p><strong>Target App:</strong> <a href="https://midas-portal-f853.vercel.app/gmail-processor" target="_blank">Midas Portal Gmail Processor</a></p>
            <p><strong>Workflow:</strong> OAuth → Connect → "Last 20 min" Filter → "Scan & Auto-Process Emails" → Wait 20min → Repeat</p>
            
            <h3>API Endpoints</h3>
            <ul>
                <li><a href="/status">GET /status</a> - Get automation status</li>
                <li><a href="/cycles">GET /cycles</a> - Get cycle history</li>
                <li><a href="/screenshot">GET /screenshot</a> - Get browser screenshot</li>
                <li><a href="/screenshot/test">GET /screenshot/test</a> - Test browser connection</li>
                <li><a href="/health">GET /health</a> - Health check</li>
                <li><a href="/docs">GET /docs</a> - API Documentation</li>
            </ul>
        </div>
        
        <script>
            async function refreshStatus() {
                try {
                    const response = await fetch('/status');
                    const status = await response.json();
                    
                    const statusDiv = document.getElementById('status');
                    statusDiv.className = `status ${status.running ? 'running' : 'stopped'}`;
                    statusDiv.innerHTML = `
                        <h3>Status: ${status.running ? 'Running ✅' : 'Stopped ❌'}</h3>
                        <p><strong>OAuth Completed:</strong> ${status.oauth_completed ? 'Yes ✅' : 'No ❌'}</p>
                        <p><strong>Cycle Count:</strong> ${status.cycle_count}</p>
                        <p><strong>Last Cycle:</strong> ${status.last_cycle || 'Never'}</p>
                        <p><strong>Next Cycle:</strong> ${status.next_cycle || 'Not scheduled'}</p>
                        ${status.errors.length > 0 ? `<p><strong>Recent Errors:</strong> ${status.errors.slice(-3).join(', ')}</p>` : ''}
                    `;
                    
                    // Show/hide verification section based on status
                    const verificationSection = document.getElementById('verification-section');
                    if (status.needs_verification) {
                        verificationSection.style.display = 'block';
                        const messageDiv = document.getElementById('verification-message');
                        messageDiv.innerText = status.verification_message || 'Please check your phone for the verification code.';
                        messageDiv.style.backgroundColor = '#d1ecf1';
                        messageDiv.style.color = '#0c5460';
                        messageDiv.style.border = '1px solid #bee5eb';
                        
                        // Auto-focus the input field
                        setTimeout(() => {
                            const codeInput = document.getElementById('verification-code');
                            if (codeInput) {
                                codeInput.focus();
                            }
                        }, 500);
                    } else {
                        verificationSection.style.display = 'none';
                    }
                } catch (error) {
                    console.error('Failed to fetch status:', error);
                }
            }
            
            async function submitVerificationCode() {
                const codeInput = document.getElementById('verification-code');
                const code = codeInput.value.trim();
                const messageDiv = document.getElementById('verification-message');
                
                if (!code) {
                    messageDiv.innerText = 'Please enter a verification code.';
                    messageDiv.style.color = '#dc3545';
                    return;
                }
                
                try {
                    messageDiv.innerText = 'Submitting verification code...';
                    messageDiv.style.color = '#007bff';
                    
                    const response = await fetch('/submit-verification', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ verification_code: code })
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        messageDiv.innerText = '✅ Verification code submitted successfully!';
                        messageDiv.style.backgroundColor = '#d4edda';
                        messageDiv.style.color = '#155724';
                        messageDiv.style.border = '1px solid #c3e6cb';
                        codeInput.value = '';
                        
                        // Hide verification section after successful submission
                        setTimeout(() => {
                            document.getElementById('verification-section').style.display = 'none';
                        }, 2000);
                        
                        // Refresh status
                        refreshStatus();
                    } else {
                        messageDiv.innerText = '❌ ' + (result.detail || 'Failed to submit verification code.');
                        messageDiv.style.backgroundColor = '#f8d7da';
                        messageDiv.style.color = '#721c24';
                        messageDiv.style.border = '1px solid #f5c6cb';
                    }
                } catch (error) {
                    messageDiv.innerText = 'Error submitting verification code.';
                    messageDiv.style.color = '#dc3545';
                    console.error('Error submitting verification:', error);
                }
            }
            
            async function startAutomation() {
                const password = prompt('Enter Gmail password:');
                if (!password) return;
                
                try {
                    const response = await fetch('/start', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ password: password, headless: false })
                    });
                    
                    if (response.ok) {
                        alert('Automation started successfully!');
                        refreshStatus();
                    } else {
                        const error = await response.json();
                        alert(`Failed to start automation: ${error.detail}`);
                    }
                } catch (error) {
                    alert(`Error: ${error.message}`);
                }
            }
            
            async function stopAutomation() {
                try {
                    const response = await fetch('/stop', { method: 'POST' });
                    if (response.ok) {
                        alert('Automation stopped successfully!');
                        refreshStatus();
                    } else {
                        alert('Failed to stop automation');
                    }
                } catch (error) {
                    alert(`Error: ${error.message}`);
                }
            }
            
            let browserViewVisible = false;
            let screenshotInterval = null;
            
            async function toggleBrowserView() {
                const container = document.getElementById('screenshot-container');
                const info = document.getElementById('browser-info');
                const toggleBtn = document.getElementById('browser-toggle-btn');
                const refreshBtn = document.getElementById('refresh-screenshot-btn');
                
                if (!browserViewVisible) {
                    // Show browser view
                    container.style.display = 'block';
                    info.style.display = 'block';
                    refreshBtn.style.display = 'inline-block';
                    toggleBtn.innerText = 'Hide Browser View';
                    browserViewVisible = true;
                    
                    // Start auto-refresh
                    refreshScreenshot();
                    screenshotInterval = setInterval(refreshScreenshot, 5000); // Refresh every 5 seconds
                } else {
                    // Hide browser view
                    container.style.display = 'none';
                    info.style.display = 'none';
                    refreshBtn.style.display = 'none';
                    toggleBtn.innerText = 'Show Browser View';
                    browserViewVisible = false;
                    
                    // Stop auto-refresh
                    if (screenshotInterval) {
                        clearInterval(screenshotInterval);
                        screenshotInterval = null;
                    }
                }
            }
            
            async function testScreenshotEndpoint() {
                try {
                    const response = await fetch('/screenshot/test');
                    const data = await response.json();
                    
                    if (data.status === 'success') {
                        alert(`✅ Browser Connection Test Successful!\n\nURL: ${data.current_url}\nTitle: ${data.page_title}\nDriver Available: ${data.driver_available}`);
                    } else {
                        alert(`❌ Browser Connection Test Failed!\n\nError: ${data.message}`);
                    }
                } catch (error) {
                    alert(`❌ Test Failed!\n\nError: ${error.message}`);
                }
            }
            
            async function refreshScreenshot() {
                const screenshot = document.getElementById('browser-screenshot');
                const loading = document.getElementById('screenshot-loading');
                const error = document.getElementById('screenshot-error');
                const urlSpan = document.getElementById('current-url');
                const titleSpan = document.getElementById('page-title');
                const timestampSpan = document.getElementById('screenshot-timestamp');
                
                try {
                    // Show loading state
                    screenshot.style.display = 'none';
                    error.style.display = 'none';
                    loading.style.display = 'block';
                    
                    console.log('Fetching screenshot...');
                    const response = await fetch('/screenshot');
                    console.log('Screenshot response:', response.status);
                    
                    if (response.ok) {
                        const data = await response.json();
                        console.log('Screenshot data received, size:', data.screenshot.length);
                        
                        // Update screenshot
                        screenshot.src = data.screenshot;
                        screenshot.style.display = 'block';
                        loading.style.display = 'none';
                        
                        // Update info
                        urlSpan.innerText = data.current_url;
                        titleSpan.innerText = data.page_title;
                        timestampSpan.innerText = new Date(data.timestamp).toLocaleTimeString();
                        
                    } else {
                        const errorData = await response.json();
                        console.error('Screenshot API error:', errorData);
                        throw new Error(errorData.message || errorData.error || 'Failed to capture screenshot');
                    }
                    
                } catch (fetchError) {
                    console.error('Screenshot error:', fetchError);
                    
                    // Show error state
                    screenshot.style.display = 'none';
                    loading.style.display = 'none';
                    error.style.display = 'block';
                    document.getElementById('error-message').innerText = fetchError.message;
                    
                    // Update info with error state
                    urlSpan.innerText = 'Error';
                    titleSpan.innerText = 'Unable to capture';
                    timestampSpan.innerText = new Date().toLocaleTimeString();
                }
            }
            
            async function loadLogs() {
                try {
                    const response = await fetch('/cycles');
                    const cycles = await response.json();
                    
                    const logsDiv = document.getElementById('logs');
                    logsDiv.innerHTML = cycles.slice(0, 10).map(cycle => 
                        `[${cycle.start_time}] Cycle #${cycle.cycle_number}: ${cycle.success ? '✅ Success' : '❌ Failed'} ${cycle.error_message || ''}`
                    ).join('\\n') || 'No cycles yet';
                } catch (error) {
                    document.getElementById('logs').innerHTML = 'Failed to load logs';
                }
            }
            
            // Auto-refresh every 30 seconds
            setInterval(refreshStatus, 30000);
            setInterval(loadLogs, 30000);
            
            // Handle Enter key for verification code input
            document.addEventListener('DOMContentLoaded', function() {
                const codeInput = document.getElementById('verification-code');
                if (codeInput) {
                    codeInput.addEventListener('keypress', function(e) {
                        if (e.key === 'Enter') {
                            submitVerificationCode();
                        }
                    });
                    
                    // Auto-focus the input when it becomes visible
                    const observer = new MutationObserver(function(mutations) {
                        mutations.forEach(function(mutation) {
                            if (mutation.type === 'attributes' && mutation.attributeName === 'style') {
                                const verificationSection = document.getElementById('verification-section');
                                if (verificationSection && verificationSection.style.display !== 'none') {
                                    setTimeout(() => codeInput.focus(), 100);
                                }
                            }
                        });
                    });
                    
                    const verificationSection = document.getElementById('verification-section');
                    if (verificationSection) {
                        observer.observe(verificationSection, {
                            attributes: true,
                            attributeFilter: ['style']
                        });
                    }
                }
            });
            
            // Cleanup on page unload
            window.addEventListener('beforeunload', function() {
                if (screenshotInterval) {
                    clearInterval(screenshotInterval);
                }
            });
            
            // Initial load
            refreshStatus();
            loadLogs();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/health")
async def health_check():
    """Health check endpoint for Render"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "gmail-oauth-automation",
        "version": "1.0.0"
    }

@app.get("/status", response_model=AutomationStatus)
async def get_status():
    """Get current automation status"""
    return AutomationStatus(**automation_status)

@app.post("/start")
async def start_automation(request: StartAutomationRequest, background_tasks: BackgroundTasks):
    """Start the automation with provided credentials"""
    global automator, automation_status
    
    try:
        # Initialize automator with provided password and base URL
        automator = EternalGmailAutomator(
            headless=request.headless,
            port=8080,
            password=request.password,
            debug=request.debug,
            base_url=os.getenv('APP_BASE_URL')  # Use environment variable for base URL
        )
        
        # Verify browser is ready for screenshots
        try:
            if hasattr(automator, 'driver') and automator.driver:
                # Test basic functionality
                test_url = automator.driver.current_url or "about:blank"
                logger.info("Browser ready for screenshots", current_url=test_url)
            else:
                logger.warning("Browser driver not immediately available - will be created during automation")
        except Exception as e:
            logger.warning("Browser test failed", error=str(e))
        
        # Start the scheduler
        if not scheduler.running:
            # Schedule immediate first run (subsequent runs will be scheduled based on processing time)
            scheduler.add_job(
                run_automation_cycle,
                trigger='date',  # Single run, will reschedule itself based on processing time
                run_date=datetime.now() + timedelta(seconds=10),  # Start after 10 seconds
                id='gmail_automation',
                replace_existing=True
            )
            scheduler.start()
        
        automation_status["running"] = True
        automation_status["oauth_completed"] = False
        automation_status["errors"] = []
        
        logger.info("Automation started via API")
        
        return {"message": "Automation started successfully", "status": automation_status}
        
    except Exception as e:
        logger.error("Failed to start automation", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to start automation: {str(e)}")

@app.post("/stop")
async def stop_automation():
    """Stop the automation"""
    global automation_status
    
    try:
        if scheduler.running:
            scheduler.shutdown(wait=False)
        
        automation_status["running"] = False
        automation_status["next_cycle"] = None
        
        logger.info("Automation stopped via API")
        
        return {"message": "Automation stopped successfully", "status": automation_status}
        
    except Exception as e:
        logger.error("Failed to stop automation", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to stop automation: {str(e)}")

@app.post("/submit-verification")
async def submit_verification_code(request: VerificationCodeRequest):
    """Submit verification code for 2FA"""
    global automation_status
    
    try:
        code = request.verification_code.strip()
        
        # Validate code format (4-8 digits)
        if not code.isdigit() or len(code) < 4 or len(code) > 8:
            raise HTTPException(status_code=400, detail="Verification code must be 4-8 digits")
        
        # Store the verification code
        automation_status["verification_code"] = code
        automation_status["needs_verification"] = False
        automation_status["verification_message"] = f"Code {code} received and will be used for authentication"
        
        logger.info(f"Verification code received from UI: {code}")
        
        return {
            "message": "Verification code received successfully",
            "code": code,
            "status": "success"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to process verification code", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to process verification code: {str(e)}")

@app.get("/cycles")
async def get_cycle_history():
    """Get recent automation cycle history"""
    if not redis_client:
        return []
    
    try:
        history = redis_client.lrange("cycle_history", 0, 50)
        return [json.loads(cycle) for cycle in history]
    except Exception as e:
        logger.error("Failed to fetch cycle history", error=str(e))
        return []

@app.get("/logs")
async def get_logs():
    """Get recent application logs"""
    # This would typically read from a log file or logging service
    # For now, return recent errors
    return {"errors": automation_status["errors"][-20:]}

@app.get("/screenshot")
async def get_browser_screenshot():
    """Get current browser screenshot"""
    global automator
    
    try:
        if not automator:
            return JSONResponse(
                status_code=404, 
                content={"error": "Automator not initialized", "message": "No active automation session"}
            )
        
        if not hasattr(automator, 'driver') or not automator.driver:
            return JSONResponse(
                status_code=404, 
                content={"error": "Browser not available", "message": "Browser driver not active"}
            )
        
        # Take screenshot and encode as base64
        try:
            screenshot_png = automator.driver.get_screenshot_as_png()
            screenshot_b64 = base64.b64encode(screenshot_png).decode('utf-8')
            logger.info("Screenshot captured successfully", size=len(screenshot_png))
        except Exception as screenshot_error:
            logger.error("Failed to capture screenshot", error=str(screenshot_error))
            raise
        
        # Get current page info
        try:
            current_url = automator.driver.current_url
            page_title = automator.driver.title
        except:
            current_url = "Unknown"
            page_title = "Unknown"
        
        return {
            "screenshot": f"data:image/png;base64,{screenshot_b64}",
            "timestamp": datetime.now().isoformat(),
            "current_url": current_url,
            "page_title": page_title,
            "automation_running": automation_status["running"]
        }
        
    except Exception as e:
        logger.error("Failed to capture screenshot", error=str(e))
        return JSONResponse(
            status_code=500, 
            content={"error": "Screenshot failed", "message": str(e)}
        )

@app.get("/screenshot/test")
async def test_screenshot_endpoint():
    """Test endpoint to verify screenshot functionality"""
    global automator
    
    try:
        if not automator:
            return {"status": "error", "message": "Automator not initialized"}
        
        if not hasattr(automator, 'driver') or not automator.driver:
            return {"status": "error", "message": "Browser driver not available"}
        
        # Test basic driver functionality
        try:
            url = automator.driver.current_url
            title = automator.driver.title
            return {
                "status": "success", 
                "message": "Browser is accessible",
                "current_url": url,
                "page_title": title,
                "driver_available": True
            }
        except Exception as driver_error:
            return {
                "status": "error", 
                "message": f"Driver error: {str(driver_error)}",
                "driver_available": False
            }
            
    except Exception as e:
        return {"status": "error", "message": f"Test failed: {str(e)}"}

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting Gmail OAuth Automation Service")
    
    # Initialize Redis
    init_redis()
    
    # Auto-start automation if credentials are available
    gmail_password = os.getenv('GMAIL_PASSWORD')
    if gmail_password:
        logger.info("Auto-starting Gmail workflow automation with environment credentials")
        logger.info("This will run the complete workflow: OAuth → Gmail Processing → 20min cycles")
        automator = init_automator()
        
        if automator:
            # Start scheduler immediately (will reschedule itself based on processing time)
            scheduler.add_job(
                run_automation_cycle,
                trigger='date',  # Single run, will reschedule itself based on processing time
                run_date=datetime.now() + timedelta(seconds=30),  # Start after 30 seconds
                id='gmail_automation',
                replace_existing=True
            )
            scheduler.start()
            automation_status["running"] = True
            logger.info("Background Gmail automation started - web service ready for requests")
    else:
        logger.info("No GMAIL_PASSWORD provided - automation will not auto-start")
        logger.info("Use /start endpoint or web dashboard to start manually")
            
    logger.info("Service startup completed")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down Gmail OAuth Automation Service")
    
    if scheduler.running:
        scheduler.shutdown(wait=True)
    
    if redis_client:
        redis_client.close()
    
    logger.info("Service shutdown completed")

# Main entry point
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info("Starting Gmail OAuth Automation Web Service for Midas Portal", 
               host=host, port=port, 
               target_app="https://midas-portal-f853.vercel.app")
    
    uvicorn.run(
        "web_service:app",
        host=host,
        port=port,
        log_level="info",
        access_log=True,
        reload=False  # Set to True for development
    ) 