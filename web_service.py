#!/usr/bin/env python3
"""
Web Service for Gmail OAuth Automation
FastAPI-based web service for cloud deployment on Render
"""

import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
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
    "oauth_completed": False
}

# Pydantic models
class AutomationStatus(BaseModel):
    running: bool
    last_cycle: Optional[datetime]
    next_cycle: Optional[datetime]
    cycle_count: int
    errors: List[str]
    oauth_completed: bool

class StartAutomationRequest(BaseModel):
    password: str = Field(..., description="Gmail account password")
    headless: bool = Field(default=True, description="Run browser in headless mode")
    debug: bool = Field(default=False, description="Enable debug mode")

class CycleResult(BaseModel):
    cycle_number: int
    start_time: str
    end_time: str
    success: bool
    error_message: Optional[str] = None

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
    
    automator = EternalGmailAutomator(
        headless=True,  # Always headless in cloud
        port=8080,
        password=gmail_password,
        debug=False,
        base_url=os.getenv('APP_BASE_URL')  # Use environment variable for base URL
    )
    
    logger.info("Gmail automator initialized", email=gmail_email)
    return automator

# Background automation task
async def run_automation_cycle():
    """Run a single automation cycle"""
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
        
        # Run the complete Gmail processing cycle (same as non-headless workflow)
        cycle_success = automator.gmail_processing_cycle()
        
        # Update status
        automation_status["last_cycle"] = cycle_start
        automation_status["next_cycle"] = cycle_start + timedelta(minutes=20)
        
        # Store cycle result in Redis
        if redis_client:
            cycle_result = {
                "cycle_number": automation_status["cycle_count"],
                "success": cycle_success,
                "start_time": cycle_start.isoformat(),
                "end_time": datetime.now().isoformat(),
                "service": "web_service",
                "workflow_completed": cycle_success
            }
            redis_client.lpush("cycle_history", json.dumps(cycle_result))
            redis_client.ltrim("cycle_history", 0, 99)  # Keep last 100 cycles
        
        logger.info("Automation cycle completed successfully", 
                   cycle=automation_status["cycle_count"],
                   success=cycle_success)
        
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
            
            <div>
                <button class="btn btn-primary" onclick="startAutomation()">Start Automation</button>
                <button class="btn btn-danger" onclick="stopAutomation()">Stop Automation</button>
                <button class="btn btn-primary" onclick="refreshStatus()">Refresh Status</button>
            </div>
            
            <h3>Recent Activity</h3>
            <div id="logs" class="logs">Loading logs...</div>
            
            <h3>Configuration</h3>
            <p><strong>Target App:</strong> <a href="https://midas-portal-f853.vercel.app/gmail-processor" target="_blank">Midas Portal Gmail Processor</a></p>
            <p><strong>Workflow:</strong> OAuth → Connect → Filter → Process → Wait 20min → Repeat</p>
            
            <h3>API Endpoints</h3>
            <ul>
                <li><a href="/status">GET /status</a> - Get automation status</li>
                <li><a href="/cycles">GET /cycles</a> - Get cycle history</li>
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
                } catch (error) {
                    console.error('Failed to fetch status:', error);
                }
            }
            
            async function startAutomation() {
                const password = prompt('Enter Gmail password:');
                if (!password) return;
                
                try {
                    const response = await fetch('/start', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ password: password, headless: true })
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
        
        # Start the scheduler
        if not scheduler.running:
            # Schedule immediate first run, then every 20 minutes
            scheduler.add_job(
                run_automation_cycle,
                trigger=IntervalTrigger(minutes=20),
                id='gmail_automation',
                replace_existing=True,
                next_run_time=datetime.now()
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
        logger.info("Auto-starting automation with environment credentials")
        automator = init_automator()
        
        if automator:
            # Start scheduler immediately
            scheduler.add_job(
                run_automation_cycle,
                trigger=IntervalTrigger(minutes=20),
                id='gmail_automation',
                replace_existing=True,
                next_run_time=datetime.now() + timedelta(seconds=30)  # Start after 30 seconds
            )
            scheduler.start()
            automation_status["running"] = True
            
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