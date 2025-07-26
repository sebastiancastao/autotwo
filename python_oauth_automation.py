#!/usr/bin/env python3
"""
Gmail OAuth Automation Script
Automatically handles Google OAuth authentication for midasportal1234@gmail.com
Bypasses CSP restrictions by using browser automation instead of DOM manipulation
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

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Try to load from env.local first, then .env as fallback
    if os.path.exists('env.local'):
        load_dotenv('env.local')
        logger = logging.getLogger(__name__)
        logger.info("✅ Environment variables loaded from env.local file")
    elif os.path.exists('.env'):
        load_dotenv('.env')
        logger = logging.getLogger(__name__)
        logger.info("✅ Environment variables loaded from .env file")
    else:
        logger = logging.getLogger(__name__)
        logger.warning("⚠️ No .env or env.local file found, using system environment variables")
except ImportError:
    print("💡 python-dotenv not installed. Install with: pip install python-dotenv")
    print("💡 Trying to load environment variables from system...")
except Exception as e:
    print(f"⚠️ Error loading environment file: {e}")
    print("💡 Using system environment variables...")

# Check for required dependencies
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    import requests
    from datetime import datetime, timedelta
    import os
except ImportError as e:
    print("❌ Missing required dependency. Please install with:")
    print("   pip install selenium requests")
    print("\nIf you want automatic ChromeDriver management, also run:")
    print("   pip install webdriver-manager")
    sys.exit(1)

# Optional Supabase import for token saving
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
    print("✅ Supabase available for token saving")
except ImportError:
    print("⚠️ Supabase not available - token saving will be disabled")
    print("💡 To enable token saving, install: pip install supabase")
    SUPABASE_AVAILABLE = False

# Configuration
TARGET_EMAIL = "midasportal1234@gmail.com"
TARGET_PASSWORD = None  # Will be set via command line argument
OAUTH_TIMEOUT = 60  # seconds
POLLING_INTERVAL = 2  # seconds

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')
GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', 'https://midas-portal-f853.vercel.app/oauth-callback.html')
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URL = 'https://www.googleapis.com/oauth2/v2/userinfo'

# Supabase Configuration
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://bjsgbihymgzahrubrgjl.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_ANON_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJqc2diaWh5bWd6YWhydWJyZ2psIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTEwNTAzOTIsImV4cCI6MjA2NjYyNjM5Mn0.7aO5K6t7drP3D6_-7wIBP27LbZfGSlXMU1LBSjWjSe8')

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GmailOAuthAutomator:
    def __init__(self, headless=False, port=8080, password=None, debug=False, keep_open=0, skip_webdriver_manager=False, base_url=None):
        """Initialize the OAuth automator"""
        self.target_email = TARGET_EMAIL
        self.password = password or TARGET_PASSWORD
        self.headless = headless
        self.port = port
        self.debug = debug
        self.keep_open = keep_open
        self.skip_webdriver_manager = skip_webdriver_manager
        # Use provided base_url or environment variable, fallback to Midas Portal
        self.base_url = base_url or os.getenv('APP_BASE_URL', 'https://midas-portal-f853.vercel.app')
        if self.base_url.endswith('/'):
            self.base_url = self.base_url.rstrip('/')  # Remove trailing slash
        
        # Log the base URL being used for debugging
        logger.info(f"🌐 Base URL configured: {self.base_url}")
        self.driver = None
        self.oauth_triggered = False
        self.trigger_server = None
        self.auth_code = None
        self.access_token = None
        self.refresh_token = None
        self.token_data = {}
        
        # Initialize Supabase client
        self.supabase = None
        if SUPABASE_AVAILABLE:
            try:
                if SUPABASE_URL and SUPABASE_KEY:
                    self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
                    logger.info("✅ Supabase client initialized successfully")
                else:
                    logger.warning("⚠️ Supabase URL or KEY not configured")
                    logger.info(f"SUPABASE_URL: {'Set' if SUPABASE_URL else 'Not set'}")
                    logger.info(f"SUPABASE_KEY: {'Set' if SUPABASE_KEY else 'Not set'}")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Supabase client: {e}")
                self.supabase = None
        elif not SUPABASE_AVAILABLE:
            logger.info("💡 Supabase not available - OAuth will work but tokens won't be saved")
            self.supabase = None
        else:
            logger.warning("⚠️ Supabase credentials not provided - tokens won't be saved")
            self.supabase = None
        
    def setup_driver(self):
        """Setup Chrome WebDriver with appropriate options"""
        logger.info("🚀 Setting up Chrome WebDriver...")
        
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument("--headless")
        
        # Important: Allow popups and disable web security for OAuth
        chrome_options.add_argument("--disable-popup-blocking")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--allow-running-insecure-content")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        # User agent to avoid detection
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Window size and positioning
        chrome_options.add_argument("--window-size=1200,800")
        chrome_options.add_argument("--window-position=100,100")
        
        # Improve stability
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--disable-images")  # Faster loading
        
        # Try the fastest method first - system ChromeDriver
        logger.info("🔧 Quick Method: Trying system ChromeDriver first...")
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.set_page_load_timeout(30)
            self.driver.implicitly_wait(10)
            logger.info("✅ Chrome WebDriver initialized with system ChromeDriver (fastest method)")
            return True
        except Exception as e:
            logger.warning(f"⚠️ System ChromeDriver failed: {e}")
            if self.skip_webdriver_manager:
                logger.info("🔧 Skipping webdriver-manager as requested...")
            else:
                logger.info("🔧 Falling back to webdriver-manager...")
        
        # Method 1: Try with webdriver-manager (with timeout) - unless skipped
        if not self.skip_webdriver_manager:
            try:
                logger.info("🔧 Method 1: Trying webdriver-manager with timeout...")
                import threading
                import queue
                
                def webdriver_manager_task(result_queue):
                    try:
                        from webdriver_manager.chrome import ChromeDriverManager
                        logger.info("📥 Downloading/locating ChromeDriver...")
                        
                        chrome_driver_manager = ChromeDriverManager()
                        driver_path = chrome_driver_manager.install()
                        logger.info(f"✅ ChromeDriver located at: {driver_path}")
                        
                        service = Service(driver_path)
                        driver = webdriver.Chrome(service=service, options=chrome_options)
                        
                        result_queue.put(('success', driver))
                    except Exception as e:
                        result_queue.put(('error', e))
                
                # Run webdriver-manager in a separate thread with timeout
                result_queue = queue.Queue()
                thread = threading.Thread(target=webdriver_manager_task, args=(result_queue,))
                thread.daemon = True
                thread.start()
                thread.join(timeout=30)  # 30 second timeout
                
                if thread.is_alive():
                    logger.warning("⏰ WebDriver manager timed out after 30 seconds")
                    raise TimeoutError("WebDriver manager timeout")
                
                try:
                    result_type, result = result_queue.get_nowait()
                    if result_type == 'success':
                        self.driver = result
                        self.driver.set_page_load_timeout(30)
                        self.driver.implicitly_wait(10)
                        logger.info("✅ Chrome WebDriver initialized with webdriver-manager")
                        return True
                    else:
                        raise result
                except queue.Empty:
                    raise Exception("WebDriver manager task completed but no result")
                    
            except Exception as e:
                logger.warning(f"⚠️ webdriver-manager failed: {e}")
        
        # Method 2: Try Chrome from common installation paths
        logger.info("🔧 Method 2: Trying Chrome from common paths...")
        common_chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Users\{}\AppData\Local\Google\Chrome\Application\chrome.exe".format(os.getenv('USERNAME', '')),
            "/usr/bin/google-chrome",
            "/usr/bin/chromium-browser",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        ]
        
        for chrome_path in common_chrome_paths:
            if os.path.exists(chrome_path):
                try:
                    logger.info(f"🔧 Trying Chrome at: {chrome_path}")
                    chrome_options.binary_location = chrome_path
                    self.driver = webdriver.Chrome(options=chrome_options)
                    self.driver.set_page_load_timeout(30)
                    self.driver.implicitly_wait(10)
                    logger.info(f"✅ Chrome WebDriver initialized with Chrome at: {chrome_path}")
                    return True
                except Exception as e2:
                    logger.warning(f"⚠️ Chrome at {chrome_path} failed: {e2}")
                    continue
        
        # Method 3: Download ChromeDriver manually and try
        try:
            logger.info("🔧 Method 3: Attempting manual ChromeDriver download...")
            import requests
            import zipfile
            import platform
            
            # Determine ChromeDriver URL based on system
            system = platform.system().lower()
            if 'windows' in system:
                driver_url = "https://chromedriver.storage.googleapis.com/114.0.5735.90/chromedriver_win32.zip"
                driver_filename = "chromedriver.exe"
            elif 'darwin' in system:
                driver_url = "https://chromedriver.storage.googleapis.com/114.0.5735.90/chromedriver_mac64.zip"
                driver_filename = "chromedriver"
            else:
                driver_url = "https://chromedriver.storage.googleapis.com/114.0.5735.90/chromedriver_linux64.zip"
                driver_filename = "chromedriver"
            
            driver_dir = os.path.join(os.getcwd(), "chromedriver_temp")
            os.makedirs(driver_dir, exist_ok=True)
            driver_path = os.path.join(driver_dir, driver_filename)
            
            if not os.path.exists(driver_path):
                logger.info(f"📥 Downloading ChromeDriver from: {driver_url}")
                response = requests.get(driver_url, timeout=30)
                response.raise_for_status()
                
                zip_path = os.path.join(driver_dir, "chromedriver.zip")
                with open(zip_path, 'wb') as f:
                    f.write(response.content)
                
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(driver_dir)
                
                os.remove(zip_path)
                
                # Make executable on Unix systems
                if not 'windows' in system:
                    os.chmod(driver_path, 0o755)
                
                logger.info(f"✅ ChromeDriver downloaded to: {driver_path}")
            
            service = Service(driver_path)
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.set_page_load_timeout(30)
            self.driver.implicitly_wait(10)
            logger.info("✅ Chrome WebDriver initialized with manually downloaded ChromeDriver")
            return True
            
        except Exception as e3:
            logger.warning(f"⚠️ Manual ChromeDriver download failed: {e3}")
        
        # Method 4: Last resort - try Edge WebDriver
        try:
            logger.info("🔧 Method 4: Last resort - trying Microsoft Edge...")
            from selenium.webdriver.edge.options import Options as EdgeOptions
            from selenium.webdriver.edge.service import Service as EdgeService
            
            edge_options = EdgeOptions()
            if self.headless:
                edge_options.add_argument("--headless")
            
            # Copy Chrome options to Edge
            for arg in chrome_options.arguments:
                if "--user-agent=" not in arg:  # Skip Chrome user agent
                    edge_options.add_argument(arg)
            
            try:
                from webdriver_manager.microsoft import EdgeChromiumDriverManager
                edge_service = EdgeService(EdgeChromiumDriverManager().install())
                self.driver = webdriver.Edge(service=edge_service, options=edge_options)
            except:
                self.driver = webdriver.Edge(options=edge_options)
            
            self.driver.set_page_load_timeout(30)
            self.driver.implicitly_wait(10)
            logger.info("✅ Edge WebDriver initialized as fallback")
            return True
            
        except Exception as e4:
            logger.warning(f"⚠️ Edge fallback also failed: {e4}")
        
        logger.error("❌ All WebDriver setup methods failed")
        logger.error("💡 Please ensure Chrome or Edge is installed and try one of these solutions:")
        logger.error("   1. Install Chrome: https://www.google.com/chrome/")
        logger.error("   2. Update Chrome to latest version")
        logger.error("   3. Run: pip install --upgrade webdriver-manager")
        logger.error("   4. Check your internet connection for ChromeDriver download")
        logger.error("   5. Disable antivirus/firewall temporarily")
        return False
    
    def wait_for_oauth_page(self, oauth_url=None):
        """Monitor browser for Google OAuth pages or navigate to provided URL"""
        logger.info("🔍 Monitoring for Google OAuth pages...")
        
        # If OAuth URL is provided, navigate to it first
        if oauth_url:
            logger.info(f"🌐 Navigating to OAuth URL: {oauth_url}")
            try:
                self.driver.get(oauth_url)
                time.sleep(3)  # Wait for page to load
            except Exception as e:
                logger.error(f"❌ Failed to navigate to OAuth URL: {e}")
                return False
        else:
            # If no URL provided, try to trigger OAuth from the main app
            logger.info("🔍 No OAuth URL provided, checking for web app...")
            try:
                # Try multiple potential app URLs
                potential_urls = [
                    f"{self.base_url}/gmail-processor",  # Primary Gmail processing route
                    self.base_url,
                    f"{self.base_url}/index.html"
                ]
                
                success = False
                for app_url in potential_urls:
                    try:
                        logger.info(f"🌐 Trying app URL: {app_url}")
                        self.driver.get(app_url)
                        time.sleep(3)
                        
                        # Check if page loaded successfully
                        page_source = self.driver.page_source.lower()
                        current_url = self.driver.current_url
                        page_title = self.driver.title
                        
                        logger.info(f"📍 Current URL: {current_url}")
                        logger.info(f"📄 Page title: {page_title}")
                        
                        # Check for error indicators (precise detection to avoid false positives)
                        page_title_lower = page_title.lower()
                        
                        # Check for specific error patterns in title (most reliable)
                        title_error_patterns = [
                            "404:",  # "404: This page could not be found"
                            "not found",
                            "page not found", 
                            "404 - ",  # "404 - Page Not Found"
                            "error 404"
                        ]
                        has_title_error = any(pattern in page_title_lower for pattern in title_error_patterns)
                        
                        # Only check page source for severe errors if title looks OK
                        page_error_patterns = [
                            "404 not found", 
                            "this page could not be found",
                            "site can't be reached",
                            "connection refused",
                            "server error"
                        ]
                        has_page_error = any(pattern in page_source for pattern in page_error_patterns) if not has_title_error else False
                        
                        has_error = has_title_error or has_page_error
                        
                        # Log detailed error detection for debugging
                        if has_error:
                            logger.warning(f"⚠️ Error detected - Title: '{page_title}', Title Error: {has_title_error}, Page Error: {has_page_error}")
                        else:
                            logger.info(f"✅ Page appears healthy - Title: '{page_title}'")
                        
                        if not has_error:
                            logger.info(f"✅ Successfully loaded: {app_url}")
                            
                            # Look for and click the Gmail connect button
                            if self.trigger_oauth_from_app():
                                logger.info("✅ OAuth flow triggered from web app")
                                return True
                            # Don't break here - continue trying other URLs if this one doesn't have the button
                            success = True  # Mark that we found a working page
                        else:
                            logger.warning(f"⚠️ URL {app_url} returned 404 or error (page content indicates error)")
                    except Exception as url_error:
                        logger.warning(f"⚠️ Failed to load {app_url}: {url_error}")
                        continue
                
                if not success:
                    logger.warning("⚠️ Could not trigger OAuth from any web app URL")
                    return False
                
            except Exception as e:
                logger.error(f"❌ Failed to access web app: {e}")
                return False
        
        start_time = time.time()
        
        while time.time() - start_time < OAUTH_TIMEOUT:
            try:
                current_url = self.driver.current_url
                
                # Check if we're on a Google OAuth page
                if self.is_google_oauth_page(current_url):
                    logger.info(f"🎯 Google OAuth page detected: {current_url}")
                    return self.handle_oauth_flow()
                
                time.sleep(POLLING_INTERVAL)
                
            except Exception as e:
                logger.warning(f"⚠️ Error checking URL: {e}")
                time.sleep(POLLING_INTERVAL)
        
        logger.warning("⏰ Timeout waiting for OAuth page")
        return False
    
    def trigger_oauth_from_app(self):
        """Try to trigger OAuth flow from the web application"""
        logger.info("🔍 Looking for Gmail connect buttons in web app...")
        
        try:
            # Wait for page to load completely and for JavaScript to execute
            logger.info("⏳ Waiting for page to load...")
            time.sleep(5)
            
            # Wait for DOM to be ready
            WebDriverWait(self.driver, 15).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            
            # Wait a bit more for any dynamic content to load
            time.sleep(3)
            
            # Debug: Log current page info
            logger.info(f"📄 Current page URL: {self.driver.current_url}")
            logger.info(f"📄 Page title: {self.driver.title}")
            
            # Check if this looks like a JavaScript application
            page_source = self.driver.page_source
            is_spa = any(framework in page_source.lower() for framework in ['react', 'vue', 'angular', 'next.js'])
            if is_spa:
                logger.info("🔧 Detected JavaScript framework - waiting longer for dynamic content")
                time.sleep(5)
            
            # Find all buttons and log them for debugging
            all_buttons = self.driver.find_elements(By.TAG_NAME, "button")
            all_links = self.driver.find_elements(By.TAG_NAME, "a")
            all_divs_with_role = self.driver.find_elements(By.XPATH, "//div[@role='button']")
            
            total_interactive = len(all_buttons) + len(all_links) + len(all_divs_with_role)
            logger.info(f"🔍 Found {len(all_buttons)} buttons, {len(all_links)} links, {len(all_divs_with_role)} div buttons = {total_interactive} total interactive elements")
            
            # Log details of first 10 buttons and look specifically for Gmail+Drive button
            gmail_drive_button_found = False
            for i, button in enumerate(all_buttons[:15]):  # Check more buttons
                try:
                    text = button.text.strip()
                    classes = button.get_attribute("class") or ""
                    onclick = button.get_attribute("onclick") or ""
                    id_attr = button.get_attribute("id") or ""
                    
                    # Check if this looks like the Gmail+Drive button
                    text_lower = text.lower()
                    is_gmail_drive = any(phrase in text_lower for phrase in [
                        'connect to gmail + drive',  # Exact expected text
                        'connect gmail',  # Simplified (since disconnect is "Disconnect Gmail")
                        'connect to gmail',  # Common variation
                        'connect to gmail and drive',
                        'connect gmail + drive',
                        'connect gmail drive',
                        'gmail + drive',
                        'gmail and drive'
                    ])
                    
                    if is_gmail_drive:
                        logger.info(f"🎯 FOUND Gmail+Drive button {i+1}: text='{text}', classes='{classes}', id='{id_attr}'")
                        gmail_drive_button_found = True
                    else:
                        logger.info(f"  Button {i+1}: text='{text}', classes='{classes}', id='{id_attr}', onclick='{onclick[:50]}'")
                except Exception as e:
                    logger.info(f"  Button {i+1}: Error reading attributes - {e}")
            
            if not gmail_drive_button_found:
                logger.warning("⚠️ 'Connect to Gmail + Drive' button not found in visible buttons")
            
            # Also log some links that might be styled as buttons
            for i, link in enumerate(all_links[:5]):
                try:
                    text = link.text.strip()
                    href = link.get_attribute("href") or ""
                    classes = link.get_attribute("class") or ""
                    if text and ('btn' in classes.lower() or 'button' in classes.lower() or any(keyword in text.lower() for keyword in ['connect', 'auth', 'login', 'sign'])):
                        logger.info(f"  Link {i+1}: text='{text}', classes='{classes}', href='{href[:50]}'")
                except Exception as e:
                    logger.info(f"  Link {i+1}: Error reading attributes - {e}")
            
            # Look for various types of connect buttons with improved selectors
            connect_selectors = [
                # Exact text patterns (most reliable)
                "//button[contains(text(), 'Connect to Gmail + Drive')]",  # Exact expected text
                "//button[text()='Connect to Gmail + Drive']",  # Exact match
                "//button[contains(text(), 'Connect Gmail')]",  # Simplified version
                "//button[contains(text(), 'Connect to Gmail')]",  # Common variation
                "//a[contains(text(), 'Connect to Gmail + Drive')]",  # In case it's a link
                "//a[contains(text(), 'Connect Gmail')]",
                
                # Case-insensitive versions
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'connect to gmail + drive')]",
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'connect to gmail') and contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'drive')]",
                "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'connect to gmail + drive')]",
                "//div[@role='button'][contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'connect to gmail + drive')]",
                # Gmail specific buttons
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'connect') and contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'gmail')]",
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'gmail')]",
                # Generic connect buttons
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'connect')]",
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'authorize')]",
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'authenticate')]",
                # Buttons with specific attributes
                "//button[@onclick*='connect']",
                "//button[@onclick*='auth']",
                "//button[@onclick*='gmail']",
                "//button[@onclick*='oauth']",
                # CSS class based selectors
                "//button[contains(@class, 'connect')]",
                "//button[contains(@class, 'gmail')]",
                "//button[contains(@class, 'auth')]",
                # ID based selectors
                "//button[@id*='connect']",
                "//button[@id*='gmail']",
                "//button[@id*='auth']",
                # Div buttons
                "//div[@role='button'][contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'connect')]",
                "//div[contains(@class, 'btn') and contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'connect')]",
                # Links
                "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'connect')]",
                "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'gmail')]"
            ]
            
            for selector in connect_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    logger.info(f"🔍 Selector '{selector[:50]}...' found {len(elements)} elements")
                    
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            text = element.text.lower().strip()
                            if text:  # Only click buttons with text
                                logger.info(f"🖱️ Found clickable button: '{element.text}' (tag: {element.tag_name})")
                                self.click_element_safely(element)
                                time.sleep(7)  # Wait longer for OAuth to start
                                
                                # Check if OAuth started
                                current_url = self.driver.current_url
                                if 'accounts.google.com' in current_url or 'oauth' in current_url:
                                    logger.info("✅ OAuth flow detected after button click")
                                    logger.info("🔄 Now proceeding with systematic OAuth automation...")
                                    return self.handle_oauth_flow()
                                
                                # Check for any popup windows
                                if len(self.driver.window_handles) > 1:
                                    logger.info("✅ Popup window detected - switching to OAuth popup")
                                    # Switch to the popup window
                                    self.driver.switch_to.window(self.driver.window_handles[-1])
                                    time.sleep(2)  # Wait for popup to load
                                    
                                    # Continue OAuth flow in the popup
                                    logger.info("🔄 Continuing OAuth flow in popup window...")
                                    oauth_success = self.handle_oauth_flow()
                                    
                                    # Switch back to main window
                                    try:
                                        self.driver.switch_to.window(self.driver.window_handles[0])
                                        logger.info("🔄 Switched back to main window")
                                    except:
                                        pass
                                    
                                    return oauth_success
                                
                except Exception as e:
                    logger.warning(f"⚠️ Error with selector: {e}")
                    continue
            
            # If no specific connect button found, try more generic approaches
            logger.info("🔍 Looking for generic authentication buttons...")
            
            # Try clicking any visible, enabled button that might trigger auth
            generic_selectors = [
                "//button[not(contains(@class, 'danger')) and not(contains(@class, 'secondary')) and not(contains(@class, 'cancel'))]",
                "//button[@type='submit']",
                "//input[@type='submit']",
                "//button[contains(@class, 'primary')]",
                "//button[contains(@class, 'btn-primary')]"
            ]
            
            for selector in generic_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    logger.info(f"🔍 Generic selector found {len(elements)} elements")
                    
                    for element in elements[:5]:  # Only check first 5 generic buttons
                        if element.is_displayed() and element.is_enabled():
                            text = element.text.lower().strip()
                            # Look for authentication-related text
                            if any(keyword in text for keyword in ['auth', 'login', 'sign', 'connect', 'start', 'begin']):
                                logger.info(f"🖱️ Trying generic auth button: '{element.text}'")
                                self.click_element_safely(element)
                                time.sleep(5)
                                
                                # Check if OAuth started
                                current_url = self.driver.current_url
                                if 'accounts.google.com' in current_url or 'oauth' in current_url:
                                    logger.info("✅ OAuth flow detected after generic button click")
                                    logger.info("🔄 Now proceeding with systematic OAuth automation...")
                                    return self.handle_oauth_flow()
                                    
                                # Check for popup windows
                                if len(self.driver.window_handles) > 1:
                                    logger.info("✅ Popup detected after generic button click - switching to OAuth popup")
                                    self.driver.switch_to.window(self.driver.window_handles[-1])
                                    time.sleep(2)  # Wait for popup to load
                                    
                                    # Continue OAuth flow in the popup
                                    logger.info("🔄 Continuing OAuth flow in popup window...")
                                    oauth_success = self.handle_oauth_flow()
                                    
                                    # Switch back to main window
                                    try:
                                        self.driver.switch_to.window(self.driver.window_handles[0])
                                        logger.info("🔄 Switched back to main window")
                                    except:
                                        pass
                                    
                                    return oauth_success
                                    
                except Exception as e:
                    logger.warning(f"⚠️ Error with generic selector: {e}")
                    continue
            
            # Final attempt: Try any button that looks clickable
            logger.info("🔍 Final attempt: trying any clickable buttons...")
            all_clickable = self.driver.find_elements(By.XPATH, "//button | //div[@role='button'] | //a[@href] | //input[@type='submit']")
            
            for element in all_clickable[:10]:  # Try first 10 clickable elements
                try:
                    if element.is_displayed() and element.is_enabled():
                        text = element.text.lower().strip()
                        if text and len(text) < 50:  # Reasonable button text length
                            logger.info(f"🖱️ Trying clickable element: '{element.text}' (tag: {element.tag_name})")
                            
                            # Store original URL to detect navigation
                            original_url = self.driver.current_url
                            
                            self.click_element_safely(element)
                            time.sleep(3)
                            
                            # Check if URL changed or popup appeared
                            new_url = self.driver.current_url
                            if (new_url != original_url or 
                                len(self.driver.window_handles) > 1 or
                                'accounts.google.com' in new_url or 
                                'oauth' in new_url):
                                
                                logger.info("✅ Navigation detected - OAuth may have started")
                                if len(self.driver.window_handles) > 1:
                                    logger.info("✅ Popup detected during final attempt - switching to OAuth popup")
                                    self.driver.switch_to.window(self.driver.window_handles[-1])
                                    time.sleep(2)  # Wait for popup to load
                                    
                                    # Continue OAuth flow in the popup
                                    logger.info("🔄 Continuing OAuth flow in popup window...")
                                    oauth_success = self.handle_oauth_flow()
                                    
                                    # Switch back to main window
                                    try:
                                        self.driver.switch_to.window(self.driver.window_handles[0])
                                        logger.info("🔄 Switched back to main window")
                                    except:
                                        pass
                                    
                                    return oauth_success
                                else:
                                    # URL changed but no popup - direct navigation
                                    logger.info("🔄 Direct OAuth navigation detected")
                                    return self.handle_oauth_flow()
                                
                except Exception as e:
                    logger.warning(f"⚠️ Error clicking element: {e}")
                    continue
            
            logger.warning("⚠️ No connect buttons found in web app")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error triggering OAuth from app: {e}")
            return False
    
    def is_google_oauth_page(self, url):
        """Check if current page is a Google OAuth page"""
        oauth_indicators = [
            "accounts.google.com",
            "oauth2/auth",
            "signin/oauth",
            "accounts/signin/oauth",
            "myaccount.google.com"
        ]
        
        return any(indicator in url.lower() for indicator in oauth_indicators)
    
    def handle_oauth_flow(self):
        """Handle the complete OAuth authentication flow"""
        logger.info("🤖 Starting OAuth automation...")
        
        try:
            # Log current page state before starting
            try:
                current_url = self.driver.current_url
                page_title = self.driver.title
                logger.info(f"📍 Starting OAuth flow at: {current_url}")
                logger.info(f"📄 Page title: {page_title}")
            except Exception as e:
                logger.warning(f"⚠️ Could not get initial page state: {e}")
            
            # Step 1: Handle account selection
            logger.info("🔄 Step 1: Account selection...")
            try:
                account_result = self.handle_account_selection()
                if account_result:
                    logger.info("✅ Account selection successful")
                else:
                    logger.warning("⚠️ Account selection failed, continuing...")
                
                # Log page state after account selection
                try:
                    post_account_url = self.driver.current_url
                    post_account_title = self.driver.title
                    logger.info(f"📍 After account selection: {post_account_url}")
                    logger.info(f"📄 Title: {post_account_title}")
                except:
                    pass
                    
            except Exception as e:
                logger.warning(f"⚠️ Account selection error (continuing): {e}")
                # Don't return False here - continue with flow
            
            # Wait for page to load after account selection
            logger.info("⏳ Waiting after account selection...")
            time.sleep(3)
            
            # Step 2: Handle password if needed
            logger.info("🔄 Step 2: Password input...")
            try:
                password_result = self.handle_password_input()
                if password_result:
                    logger.info("✅ Password handling completed")
                else:
                    logger.warning("⚠️ Password handling failed, continuing...")
                
                # Log page state after password
                try:
                    post_password_url = self.driver.current_url
                    post_password_title = self.driver.title
                    logger.info(f"📍 After password: {post_password_url}")
                    logger.info(f"📄 Title: {post_password_title}")
                except:
                    pass
                    
            except Exception as e:
                logger.warning(f"⚠️ Password handling error (continuing): {e}")
                # Don't return False here - continue with flow
            
            # Wait for authentication to process
            logger.info("⏳ Waiting after password...")
            time.sleep(4)
            
            # Step 2.5: Check for 2FA verification codes
            logger.info("🔄 Step 2.5: Checking for 2FA verification...")
            try:
                twofa_result = self.handle_2fa_verification()
                if twofa_result:
                    logger.info("✅ 2FA verification handled")
                else:
                    logger.info("ℹ️ No 2FA verification required")
                
                # Log page state after 2FA
                try:
                    post_2fa_url = self.driver.current_url
                    post_2fa_title = self.driver.title
                    logger.info(f"📍 After 2FA check: {post_2fa_url}")
                    logger.info(f"📄 Title: {post_2fa_title}")
                except:
                    pass
                    
            except Exception as e:
                logger.warning(f"⚠️ 2FA handling error (continuing): {e}")
                # Don't return False here - continue with flow
            
            # Wait for 2FA to process
            logger.info("⏳ Waiting after 2FA check...")
            time.sleep(3)
            
            # Step 3: Handle consent/permissions
            logger.info("🔄 Step 3: Consent screen...")
            try:
                consent_result = self.handle_consent_screen()
                if consent_result:
                    logger.info("✅ Consent screen handled")
                else:
                    logger.warning("⚠️ Consent screen handling failed, continuing...")
                
                # Log page state after consent
                try:
                    post_consent_url = self.driver.current_url
                    post_consent_title = self.driver.title
                    logger.info(f"📍 After consent: {post_consent_url}")
                    logger.info(f"📄 Title: {post_consent_title}")
                except:
                    pass
                    
            except Exception as e:
                logger.warning(f"⚠️ Consent screen error (continuing): {e}")
                # Don't return False here - continue with flow
            
            # Wait for consent to process
            logger.info("⏳ Waiting after consent...")
            time.sleep(3)
            
            # Step 4: Wait for redirect back to app
            logger.info("🔄 Step 4: Waiting for OAuth completion...")
            try:
                completion_result = self.wait_for_oauth_completion()
                logger.info(f"🔄 OAuth completion result: {completion_result}")
                return completion_result
            except Exception as e:
                logger.error(f"❌ OAuth completion error: {e}")
                logger.info("🔍 OAuth completion failed, but keeping browser open for debugging...")
                
                # Keep browser open longer for debugging
                if not self.headless:
                    logger.info("🔍 Browser will stay open for 60 seconds for manual completion...")
                    time.sleep(60)
                
                return False
            
        except Exception as e:
            logger.error(f"❌ Critical OAuth automation error: {e}")
            logger.info("🔍 Critical error occurred, keeping browser open for debugging...")
            
            # Keep browser open for debugging on critical errors
            if not self.headless:
                logger.info("🔍 Browser will stay open for 60 seconds due to critical error...")
                time.sleep(60)
            
            return False
    
    def handle_account_selection(self):
        """Handle Google account selection screen"""
        logger.info("🔍 Looking for account selection...")
        
        # First check current page state
        try:
            current_url = self.driver.current_url
            page_title = self.driver.title
            logger.info(f"📍 Current URL: {current_url}")
            logger.info(f"📄 Page title: {page_title}")
        except Exception as e:
            logger.warning(f"⚠️ Could not get page state: {e}")
            current_url = ""
            page_title = ""
        
        # Take a screenshot for debugging
        try:
            screenshot_path = "oauth_page_debug.png"
            self.driver.save_screenshot(screenshot_path)
            logger.info(f"📸 Screenshot saved: {screenshot_path}")
        except Exception as e:
            logger.warning(f"⚠️ Could not save screenshot: {e}")
        
        # Log page source length for debugging
        try:
            page_source_length = len(self.driver.page_source)
            logger.info(f"📄 Page source length: {page_source_length} characters")
        except Exception as e:
            logger.warning(f"⚠️ Could not get page source length: {e}")
        
        # Check for direct email input FIRST (most common case)
        logger.info("🔍 Checking for direct email input...")
        email_selectors = [
            "//input[@id='identifierId']",  # Most common Google selector
            "//input[@name='identifier']",  # EXACT MATCH for the element
            "//input[@type='email']",  # EXACT MATCH for type
            "//input[contains(@class, 'whsOnd')]",  # EXACT CLASS from the element
            "//input[contains(@class, 'zHQkBf')]",  # EXACT CLASS from the element 
            "//input[@jsname='YPqjbf']",  # EXACT JSNAME from the element
            "//input[contains(@autocomplete, 'username')]",  # Partial match for autocomplete
            "//input[contains(@aria-label, 'Correo electrónico')]",  # Spanish: "Email"
            "//input[contains(@aria-label, 'teléfono')]",  # Spanish: "phone"
            "//input[contains(@aria-label, 'email')]",  # English
            "//input[contains(@aria-label, 'Email')]",  # English
            "//input[@name='email']",
            "//input[@autocomplete='email']",
            "//input[contains(@placeholder, 'email')]",
            "//input[contains(@placeholder, 'Email')]",
            "//input[contains(@placeholder, 'correo')]",  # Spanish
            "//input[contains(@class, 'email')]",
            "//input[contains(@class, 'identifier')]"
        ]
        
        for selector in email_selectors:
            try:
                logger.info(f"🔍 Trying email selector: {selector}")
                elements = self.driver.find_elements(By.XPATH, selector)
                logger.info(f"   Found {len(elements)} elements")
                
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        logger.info("✅ Found email input field - proceeding with email entry")
                        return self.enter_email_manually()
            except Exception as e:
                logger.info(f"   Selector failed: {e}")
                continue
        
        # If we're already past account selection AND no email input found, skip this step
        if 'password' in current_url.lower() or 'consent' in current_url.lower():
            logger.info("✅ Already past account selection - skipping")
            return True
        
        # If no direct email input, look for account selection
        try:
            logger.info("⏳ Looking for account selection elements...")
            
            # Wait for page to fully load
            WebDriverWait(self.driver, 10).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            time.sleep(2)  # Additional wait for dynamic content
            
            # Log all visible text on the page for debugging
            try:
                page_text = self.driver.find_element(By.TAG_NAME, "body").text
                logger.info(f"📄 Page content preview: {page_text[:500]}...")
            except:
                pass
            
            # Strategy 1: Look for exact email match
            target_selectors = [
                f"//div[@data-email='{self.target_email}']",
                f"//div[contains(text(), '{self.target_email}')]",
                f"//span[contains(text(), '{self.target_email}')]",
                f"//div[@data-identifier='{self.target_email}']",
                f"//li[contains(text(), '{self.target_email}')]"
            ]
            
            for selector in target_selectors:
                try:
                    logger.info(f"🔍 Trying account selector: {selector}")
                    element = self.driver.find_element(By.XPATH, selector)
                    if element.is_displayed():
                        logger.info(f"✅ Found target account element: {selector}")
                        self.click_element_safely(element)
                        time.sleep(2)  # Wait for navigation
                        return True
                except NoSuchElementException:
                    continue
            
            # Strategy 2: Look for clickable elements containing target email
            clickable_selectors = [
                "//div[@role='button']",
                "//div[contains(@class, 'account')]",
                "//li[@role='presentation']",
                "//div[@jsaction]"
            ]
            
            for selector in clickable_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for element in elements:
                        if self.target_email in element.text:
                            logger.info(f"✅ Found target account in clickable element")
                            self.click_element_safely(element)
                            return True
                except Exception as e:
                    continue
            
            # Strategy 3: Look for "Use another account" if target not visible
            logger.info("🔄 Target account not visible, looking for 'Use another account'...")
            another_account_selectors = [
                "//div[contains(text(), 'Use another account')]",
                "//div[contains(text(), 'Add account')]",
                "//div[contains(text(), 'Switch account')]",
                "//span[contains(text(), 'Use another account')]"
            ]
            
            for selector in another_account_selectors:
                try:
                    element = self.driver.find_element(By.XPATH, selector)
                    logger.info("🔄 Clicking 'Use another account'...")
                    self.click_element_safely(element)
                    time.sleep(2)
                    
                    # Now try to enter email manually
                    return self.enter_email_manually()
                except NoSuchElementException:
                    continue
            
            logger.warning("⚠️ Could not find account selection elements")
            return False
            
        except TimeoutException:
            logger.warning("⚠️ Account selection elements not found within timeout")
            return False
    
    def find_input_field_systematically(self):
        """Systematically go through all elements to find input fields"""
        logger.info("🔍 Starting systematic element-by-element search for input fields...")
        
        # Strategy 1: Find all input elements and examine each one
        try:
            all_inputs = self.driver.find_elements(By.TAG_NAME, "input")
            logger.info(f"📊 Found {len(all_inputs)} total input elements on page")
            
            for i, input_elem in enumerate(all_inputs):
                try:
                    logger.info(f"🔍 Examining input element {i+1}/{len(all_inputs)}...")
                    
                    # Get all attributes for this input
                    input_type = input_elem.get_attribute("type") or ""
                    input_name = input_elem.get_attribute("name") or ""
                    input_id = input_elem.get_attribute("id") or ""
                    input_placeholder = input_elem.get_attribute("placeholder") or ""
                    input_class = input_elem.get_attribute("class") or ""
                    input_autocomplete = input_elem.get_attribute("autocomplete") or ""
                    input_aria_label = input_elem.get_attribute("aria-label") or ""
                    input_jsname = input_elem.get_attribute("jsname") or ""
                    is_displayed = input_elem.is_displayed()
                    is_enabled = input_elem.is_enabled()
                    
                    logger.info(f"  📋 Input {i+1} attributes:")
                    logger.info(f"    type='{input_type}', name='{input_name}', id='{input_id}'")
                    logger.info(f"    placeholder='{input_placeholder}', class='{input_class[:50]}...'")
                    logger.info(f"    autocomplete='{input_autocomplete}', aria-label='{input_aria_label}'")
                    logger.info(f"    jsname='{input_jsname}', visible={is_displayed}, enabled={is_enabled}")
                    
                    # Check if this is a suitable email input field
                    if is_displayed and is_enabled:
                        # Check for email-related indicators
                        email_indicators = [
                            input_type.lower() == "email",
                            input_name.lower() in ["identifier", "email", "username", "user", "login"],
                            input_id.lower() in ["identifierid", "email", "username", "user", "login"],
                            "email" in input_placeholder.lower(),
                            "correo" in input_placeholder.lower(),  # Spanish
                            "identifier" in input_class.lower(),
                            "email" in input_class.lower(),
                            "username" in input_autocomplete.lower(),
                            "email" in input_autocomplete.lower(),
                            "email" in input_aria_label.lower(),
                            "correo" in input_aria_label.lower(),  # Spanish
                            "teléfono" in input_aria_label.lower(),  # Spanish phone/email
                            input_jsname == "YPqjbf",  # Google specific
                            input_class and ("whsOnd" in input_class or "zHQkBf" in input_class),  # Google classes
                            # Generic text inputs that could be email fields
                            (input_type.lower() in ["text", ""] and not any(skip in input_name.lower() for skip in ["password", "captcha", "otp", "code"]))
                        ]
                        
                        if any(email_indicators):
                            logger.info(f"✅ Input {i+1} identified as potential email field")
                            logger.info(f"  🎯 Matched indicators: {[ind for ind, match in zip(['type=email', 'name match', 'id match', 'placeholder email', 'placeholder correo', 'class identifier', 'class email', 'autocomplete username', 'autocomplete email', 'aria-label email', 'aria-label correo', 'aria-label teléfono', 'jsname Google', 'class Google', 'generic text'], email_indicators) if match]}")
                            
                            # Try to interact with this element to confirm it's usable
                            try:
                                # Scroll into view
                                self.driver.execute_script("arguments[0].scrollIntoView(true);", input_elem)
                                time.sleep(0.5)
                                
                                # Try to click and focus
                                input_elem.click()
                                time.sleep(0.3)
                                
                                # Test if we can enter text (try a short test)
                                original_value = input_elem.get_attribute("value") or ""
                                input_elem.send_keys("test")
                                time.sleep(0.2)
                                
                                # Clear the test input
                                input_elem.clear()
                                time.sleep(0.2)
                                
                                logger.info(f"✅ Input {i+1} successfully tested - selecting as email field")
                                return input_elem
                                
                            except Exception as e:
                                logger.info(f"  ⚠️ Input {i+1} failed interaction test: {e}")
                                continue
                        else:
                            logger.info(f"  ⚪ Input {i+1} does not match email field criteria")
                    else:
                        logger.info(f"  ❌ Input {i+1} not visible or not enabled")
                        
                except Exception as e:
                    logger.info(f"  ⚠️ Error examining input {i+1}: {e}")
                    continue
            
        except Exception as e:
            logger.warning(f"⚠️ Error during input element search: {e}")
        
        # Strategy 2: Look for other interactive elements that might be input fields
        logger.info("🔍 Strategy 2: Examining other potentially interactive elements...")
        
        # Look for elements with contenteditable, role=textbox, etc.
        other_selectors = [
            "//div[@contenteditable='true']",
            "//div[@role='textbox']",
            "//span[@role='textbox']",
            "//textarea",
            "//*[@contenteditable='true']",
            "//*[@role='textbox']"
        ]
        
        for selector in other_selectors:
            try:
                logger.info(f"🔍 Checking selector: {selector}")
                elements = self.driver.find_elements(By.XPATH, selector)
                logger.info(f"  📊 Found {len(elements)} elements")
                
                for j, element in enumerate(elements):
                    try:
                        if element.is_displayed() and element.is_enabled():
                            element_text = element.text or ""
                            element_class = element.get_attribute("class") or ""
                            element_id = element.get_attribute("id") or ""
                            
                            logger.info(f"  🔍 Element {j+1}: text='{element_text[:30]}...', class='{element_class[:30]}...', id='{element_id}'")
                            
                            # Check if this looks like an email input
                            if (len(element_text) < 50 and  # Not too much existing text
                                not any(skip in element_class.lower() for skip in ["button", "menu", "dropdown"]) and
                                not any(skip in element_text.lower() for skip in ["password", "search", "menu"])):
                                
                                logger.info(f"  ✅ Alternative element {j+1} looks like a text input")
                                
                                # Test interaction
                                try:
                                    self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                                    time.sleep(0.5)
                                    element.click()
                                    time.sleep(0.3)
                                    
                                    # Try to enter text
                                    element.send_keys("test")
                                    time.sleep(0.2)
                                    
                                    # Clear test text
                                    element.clear()
                                    time.sleep(0.2)
                                    
                                    logger.info(f"✅ Alternative element {j+1} successfully tested")
                                    return element
                                    
                                except Exception as e:
                                    logger.info(f"  ⚠️ Alternative element {j+1} failed test: {e}")
                                    continue
                    except Exception as e:
                        logger.info(f"  ⚠️ Error testing alternative element {j+1}: {e}")
                        continue
                        
            except Exception as e:
                logger.info(f"  ⚠️ Selector '{selector}' failed: {e}")
                continue
        
        # Strategy 3: Last resort - try any focusable elements that might accept text
        logger.info("🔍 Strategy 3: Examining any focusable elements as last resort...")
        
        try:
            focusable_elements = self.driver.find_elements(By.XPATH, "//*[@tabindex or @contenteditable or contains(@class, 'input') or contains(@class, 'field')]")
            logger.info(f"📊 Found {len(focusable_elements)} potentially focusable elements")
            
            for k, element in enumerate(focusable_elements[:20]):  # Limit to first 20
                try:
                    if element.is_displayed() and element.is_enabled():
                        tag_name = element.tag_name.lower()
                        element_class = element.get_attribute("class") or ""
                        
                        # Skip obvious non-input elements
                        if tag_name in ["button", "a", "img", "video", "audio"]:
                            continue
                            
                        if any(skip in element_class.lower() for skip in ["button", "btn", "link", "menu", "dropdown", "nav"]):
                            continue
                        
                        logger.info(f"  🔍 Focusable element {k+1}: tag='{tag_name}', class='{element_class[:30]}...'")
                        
                        # Test if we can input text
                        try:
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                            time.sleep(0.3)
                            element.click()
                            time.sleep(0.3)
                            
                            # Try to type
                            element.send_keys("test")
                            time.sleep(0.2)
                            
                            # If we got here, it accepted text input
                            element.clear()
                            time.sleep(0.2)
                            
                            logger.info(f"✅ Focusable element {k+1} accepts text input!")
                            return element
                            
                        except Exception as e:
                            logger.info(f"  ⚠️ Focusable element {k+1} failed text input test: {e}")
                            continue
                            
                except Exception as e:
                    logger.info(f"  ⚠️ Error testing focusable element {k+1}: {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"⚠️ Error during focusable element search: {e}")
        
        logger.warning("❌ Systematic search completed - no suitable input field found")
        return None
    
    def enter_email_manually(self):
        """Manually enter email address in input field"""
        logger.info("📧 Entering email manually...")
        
        # Wait for page to be ready
        try:
            WebDriverWait(self.driver, 10).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
        except:
            pass
        
        # Additional wait for dynamic content
        time.sleep(3)
        
        # Log current page state for debugging
        current_url = self.driver.current_url
        page_title = self.driver.title
        logger.info(f"📍 Email entry URL: {current_url}")
        logger.info(f"📄 Email entry title: {page_title}")
        
        # Systematically find all input fields by going element by element
        logger.info("🔍 Systematically searching for input fields element by element...")
        email_input = self.find_input_field_systematically()
        
        if not email_input:
            logger.error("❌ Could not find any usable email input field after systematic search")
            logger.info("🔍 Taking screenshot for debugging...")
            try:
                self.driver.save_screenshot("email_input_not_found.png")
                logger.info("📸 Screenshot saved: email_input_not_found.png")
            except:
                pass
            return False
        
        # Now try to enter the email using the systematically found input field
        try:
            logger.info(f"📧 Entering email using systematically found input field...")
            
            # Scroll element into view
            self.driver.execute_script("arguments[0].scrollIntoView(true);", email_input)
            time.sleep(0.5)
            
            # Click to focus the input field
            try:
                email_input.click()
                logger.info("✅ Input field focused via click")
            except Exception as e:
                logger.info(f"⚠️ Click failed, trying JavaScript focus: {e}")
                self.driver.execute_script("arguments[0].focus();", email_input)
            
            time.sleep(0.5)
            
            # Clear any existing content
            try:
                email_input.clear()
                logger.info("✅ Input field cleared")
            except Exception as e:
                logger.info(f"⚠️ Clear failed, trying JavaScript clear: {e}")
                self.driver.execute_script("arguments[0].value = '';", email_input)
            
            time.sleep(0.5)
            
            # Enter email using multiple methods for reliability
            email_entered = False
            
            # Method 1: Standard send_keys
            try:
                email_input.send_keys(self.target_email)
                time.sleep(0.5)
                
                # Verify the email was entered
                entered_value = email_input.get_attribute("value") or ""
                if self.target_email in entered_value:
                    logger.info(f"✅ Email entered successfully via send_keys: {self.target_email}")
                    email_entered = True
                else:
                    logger.info(f"⚠️ send_keys partial success. Expected: '{self.target_email}', Got: '{entered_value}'")
            except Exception as e:
                logger.info(f"⚠️ send_keys method failed: {e}")
            
            # Method 2: JavaScript input if send_keys failed or was incomplete
            if not email_entered:
                try:
                    logger.info("🔄 Trying JavaScript input method...")
                    self.driver.execute_script(f"arguments[0].value = '{self.target_email}';", email_input)
                    self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", email_input)
                    self.driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", email_input)
                    time.sleep(0.5)
                    
                    # Verify JavaScript entry
                    entered_value = email_input.get_attribute("value") or ""
                    if self.target_email in entered_value:
                        logger.info(f"✅ Email entered successfully via JavaScript: {self.target_email}")
                        email_entered = True
                    else:
                        logger.warning(f"⚠️ JavaScript method partial success. Expected: '{self.target_email}', Got: '{entered_value}'")
                except Exception as e:
                    logger.warning(f"⚠️ JavaScript input method failed: {e}")
            
            # Method 3: Character-by-character input as last resort
            if not email_entered:
                try:
                    logger.info("🔄 Trying character-by-character input method...")
                    email_input.clear()
                    time.sleep(0.3)
                    
                    for char in self.target_email:
                        email_input.send_keys(char)
                        time.sleep(0.05)  # Small delay between characters
                    
                    time.sleep(0.5)
                    entered_value = email_input.get_attribute("value") or ""
                    if self.target_email in entered_value:
                        logger.info(f"✅ Email entered successfully character-by-character: {self.target_email}")
                        email_entered = True
                    else:
                        logger.warning(f"⚠️ Character-by-character partial success. Expected: '{self.target_email}', Got: '{entered_value}'")
                except Exception as e:
                    logger.warning(f"⚠️ Character-by-character method failed: {e}")
            
            if not email_entered:
                logger.error(f"❌ Failed to enter email using all methods")
                return False
            
            # Wait for field to process the input
            time.sleep(2)
            
                        # Look for Next/Continue button after email
            logger.info("🔍 Looking for Next/Continue button after email...")
            next_selectors = [
                "//button[@id='identifierNext']",  # Google's standard ID
                "//button[contains(text(), 'Next')]",
                "//button[contains(text(), 'Siguiente')]",  # Spanish
                "//button[contains(text(), 'Continue')]",
                "//button[contains(text(), 'Continuar')]",  # Spanish
                "//input[@value='Next']",
                "//input[@value='Siguiente']",  # Spanish
                "//input[@value='Continue']",
                "//input[@value='Continuar']",  # Spanish
                "//div[@role='button'][contains(text(), 'Next')]",
                "//div[@role='button'][contains(text(), 'Siguiente')]",  # Spanish
                "//div[@role='button'][contains(text(), 'Continue')]",
                "//div[@role='button'][contains(text(), 'Continuar')]",  # Spanish
                "//span[contains(text(), 'Next')]/ancestor::button",
                "//span[contains(text(), 'Siguiente')]/ancestor::button",  # Spanish
                "//span[contains(text(), 'Continue')]/ancestor::button",
                "//span[contains(text(), 'Continuar')]/ancestor::button",  # Spanish
                "//button[@type='submit']",
                "//*[@data-action='next']",
                "//*[@data-action='continue']",
                "//*[contains(@class, 'next')]//button",
                "//*[contains(@class, 'continue')]//button"
            ]
            
            next_clicked = False
            for next_selector in next_selectors:
                try:
                    logger.info(f"🔍 Looking for Next button: {next_selector}")
                    next_elements = self.driver.find_elements(By.XPATH, next_selector)
                    logger.info(f"   Found {len(next_elements)} Next button candidates")
                    
                    for k, next_button in enumerate(next_elements):
                        try:
                            if next_button.is_displayed() and next_button.is_enabled():
                                button_text = next_button.text or next_button.get_attribute("value") or "No text"
                                
                                # Skip obviously wrong buttons
                                if any(skip_word in button_text.lower() for skip_word in ['cancel', 'back', 'previous']):
                                    logger.info(f"   Skipping button: '{button_text}' (negative action)")
                                    continue
                                
                                logger.info(f"✅ Found clickable Next button {k+1}: '{button_text}'")
                                
                                # Scroll into view and click
                                self.driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
                                time.sleep(0.5)
                                self.click_element_safely(next_button)
                                logger.info("✅ Clicked Next button")
                                time.sleep(2)  # Wait for navigation
                                next_clicked = True
                                break
                        except Exception as e:
                            logger.info(f"   Button interaction failed: {e}")
                            continue
                
                    if next_clicked:
                        break
                
                except Exception as e:
                    logger.info(f"   Next button selector failed: {e}")
                    continue
            
            if not next_clicked:
                logger.warning("⚠️ Could not find Next button, trying alternative methods...")
                
                # Try pressing Enter key
                try:
                    logger.info("🔄 Trying Enter key...")
                    email_input.send_keys("\n")
                    logger.info("✅ Pressed Enter key")
                    next_clicked = True
                except Exception as e:
                    logger.warning(f"⚠️ Enter key failed: {e}")
                
                # Try Tab + Enter
                if not next_clicked:
                    try:
                        logger.info("🔄 Trying Tab + Enter...")
                        email_input.send_keys("\t\n")
                        logger.info("✅ Pressed Tab + Enter")
                        next_clicked = True
                    except Exception as e:
                        logger.warning(f"⚠️ Tab + Enter failed: {e}")
            
            # Wait for page transition
            logger.info("⏳ Waiting for page transition...")
            time.sleep(5)
            
            # Check if page changed
            new_url = self.driver.current_url
            new_title = self.driver.title
            logger.info(f"📍 After email entry URL: {new_url}")
            logger.info(f"📄 After email entry title: {new_title}")
            
            if new_url != current_url or 'password' in new_url.lower():
                logger.info("✅ Page transition detected - email entry successful")
                return True
            else:
                logger.warning("⚠️ No page transition detected")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error entering email: {e}")
            return False
    
    def find_password_field_systematically(self):
        """Systematically find password input fields element by element"""
        logger.info("🔍 Starting systematic search for password input fields...")
        
        # Strategy 1: Look for input elements and examine each one for password indicators
        try:
            all_inputs = self.driver.find_elements(By.TAG_NAME, "input")
            logger.info(f"📊 Found {len(all_inputs)} total input elements on page")
            
            for i, input_elem in enumerate(all_inputs):
                try:
                    logger.info(f"🔍 Examining input element {i+1}/{len(all_inputs)} for password field...")
                    
                    # Get all attributes for this input
                    input_type = input_elem.get_attribute("type") or ""
                    input_name = input_elem.get_attribute("name") or ""
                    input_id = input_elem.get_attribute("id") or ""
                    input_placeholder = input_elem.get_attribute("placeholder") or ""
                    input_class = input_elem.get_attribute("class") or ""
                    input_autocomplete = input_elem.get_attribute("autocomplete") or ""
                    input_aria_label = input_elem.get_attribute("aria-label") or ""
                    is_displayed = input_elem.is_displayed()
                    is_enabled = input_elem.is_enabled()
                    
                    logger.info(f"  📋 Input {i+1} attributes:")
                    logger.info(f"    type='{input_type}', name='{input_name}', id='{input_id}'")
                    logger.info(f"    placeholder='{input_placeholder}', class='{input_class[:50]}...'")
                    logger.info(f"    autocomplete='{input_autocomplete}', aria-label='{input_aria_label}'")
                    logger.info(f"    visible={is_displayed}, enabled={is_enabled}")
                    
                    # Check if this is a password input field
                    if is_displayed and is_enabled:
                        # Check for password-related indicators
                        password_indicators = [
                            input_type.lower() == "password",
                            input_name.lower() in ["password", "passwd", "pwd", "pass"],
                            input_id.lower() in ["password", "passwd", "pwd", "pass"],
                            "password" in input_placeholder.lower(),
                            "contraseña" in input_placeholder.lower(),  # Spanish
                            "password" in input_class.lower(),
                            "current-password" in input_autocomplete.lower(),
                            "new-password" in input_autocomplete.lower(),
                            "password" in input_aria_label.lower(),
                            "contraseña" in input_aria_label.lower(),  # Spanish
                        ]
                        
                        if any(password_indicators):
                            logger.info(f"✅ Input {i+1} identified as potential password field")
                            logger.info(f"  🎯 Matched indicators: {[ind for ind, match in zip(['type=password', 'name match', 'id match', 'placeholder password', 'placeholder contraseña', 'class password', 'autocomplete current-password', 'autocomplete new-password', 'aria-label password', 'aria-label contraseña'], password_indicators) if match]}")
                            
                            # Try to interact with this element to confirm it's usable
                            try:
                                # Scroll into view
                                self.driver.execute_script("arguments[0].scrollIntoView(true);", input_elem)
                                time.sleep(0.5)
                                
                                # Try to click and focus
                                input_elem.click()
                                time.sleep(0.3)
                                
                                # Test if we can enter text (try a short test)
                                input_elem.send_keys("test")
                                time.sleep(0.2)
                                
                                # Clear the test input
                                input_elem.clear()
                                time.sleep(0.2)
                                
                                logger.info(f"✅ Password input {i+1} successfully tested - selecting as password field")
                                return input_elem
                                
                            except Exception as e:
                                logger.info(f"  ⚠️ Password input {i+1} failed interaction test: {e}")
                                continue
                        else:
                            logger.info(f"  ⚪ Input {i+1} does not match password field criteria")
                    else:
                        logger.info(f"  ❌ Input {i+1} not visible or not enabled")
                        
                except Exception as e:
                    logger.info(f"  ⚠️ Error examining input {i+1}: {e}")
                    continue
            
        except Exception as e:
            logger.warning(f"⚠️ Error during password input element search: {e}")
        
        logger.warning("❌ Systematic password field search completed - no suitable password field found")
        return None
    
    def handle_password_input(self):
        """Handle password input if required"""
        logger.info("🔍 Checking for password input...")
        
        try:
            # First try systematic search for password fields
            logger.info("🔍 Using systematic search for password fields...")
            password_input = self.find_password_field_systematically()
            
            # If systematic search fails, fall back to simple wait
            if not password_input:
                logger.info("🔄 Systematic search failed, trying simple wait for password field...")
                try:
                    password_input = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, "//input[@type='password']"))
                    )
                    logger.info("✅ Password field found via simple wait")
                except TimeoutException:
                    logger.info("⚪ No password field found via simple wait either")
                    return True  # No password screen - likely already authenticated
            
            if password_input:
                logger.info("🔐 Password screen detected")
                logger.info(f"🔍 Password available: {bool(self.password)}")
            
            if self.password and password_input:
                logger.info("🔑 Entering password automatically...")
                try:
                    # Wait for password field to become interactable
                    WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable(password_input)
                    )
                    
                    # Scroll password field into view
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", password_input)
                    time.sleep(1)
                    
                    # Click to focus - try multiple times if needed
                    for attempt in range(3):
                        try:
                            password_input.click()
                            logger.info(f"✅ Password field clicked (attempt {attempt + 1})")
                            break
                        except Exception as e:
                            logger.info(f"   Click attempt {attempt + 1} failed: {e}")
                            time.sleep(1)
                    
                    time.sleep(1)
                    
                    # Enter password using multiple methods for reliability
                    password_entered = False
                    
                    # Method 1: Standard send_keys
                    try:
                        password_input.clear()
                        time.sleep(0.5)
                        password_input.send_keys(self.password)
                        time.sleep(0.5)
                        
                        # Verify password was entered (can't check value for security, but check if field has content)
                        try:
                            # Check if field appears to have content (some password fields show dots/asterisks)
                            field_value = password_input.get_attribute("value") or ""
                            if len(field_value) > 0:
                                logger.info("✅ Password entered successfully via send_keys")
                                password_entered = True
                            else:
                                logger.info("⚠️ send_keys appears to have failed - field still empty")
                        except:
                            # If we can't check, assume it worked if no exception was thrown
                            logger.info("✅ Password entered via send_keys (cannot verify due to security)")
                            password_entered = True
                            
                    except Exception as e:
                        logger.info(f"⚠️ send_keys method failed: {e}")
                    
                    # Method 2: JavaScript input if send_keys failed
                    if not password_entered:
                        try:
                            logger.info("🔄 Trying JavaScript password input method...")
                            self.driver.execute_script(f"arguments[0].value = '{self.password}';", password_input)
                            self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", password_input)
                            self.driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", password_input)
                            time.sleep(0.5)
                            
                            # Check if JavaScript method worked
                            try:
                                field_value = password_input.get_attribute("value") or ""
                                if len(field_value) > 0:
                                    logger.info("✅ Password entered successfully via JavaScript")
                                    password_entered = True
                                else:
                                    logger.info("⚠️ JavaScript method appears to have failed - field still empty")
                            except:
                                logger.info("✅ Password entered via JavaScript (cannot verify due to security)")
                                password_entered = True
                                
                        except Exception as e:
                            logger.warning(f"⚠️ JavaScript password input method failed: {e}")
                    
                    # Method 3: Character-by-character input as last resort
                    if not password_entered:
                        try:
                            logger.info("🔄 Trying character-by-character password input method...")
                            password_input.clear()
                            time.sleep(0.3)
                            
                            for char in self.password:
                                password_input.send_keys(char)
                                time.sleep(0.05)  # Small delay between characters
                            
                            time.sleep(0.5)
                            try:
                                field_value = password_input.get_attribute("value") or ""
                                if len(field_value) > 0:
                                    logger.info("✅ Password entered successfully character-by-character")
                                    password_entered = True
                                else:
                                    logger.info("⚠️ Character-by-character method appears to have failed")
                            except:
                                logger.info("✅ Password entered character-by-character (cannot verify due to security)")
                                password_entered = True
                                
                        except Exception as e:
                            logger.warning(f"⚠️ Character-by-character password method failed: {e}")
                    
                    if not password_entered:
                        logger.error("❌ Failed to enter password using all methods")
                        # Continue anyway as the field might have accepted the input despite verification issues
                        logger.info("⚠️ Continuing despite password entry uncertainty...")
                    
                    time.sleep(1)  # Wait for password field to process
                    
                    # Look for and click the Next/Continue button
                    next_selectors = [
                        "//button[@id='passwordNext']",
                        "//button[contains(text(), 'Next')]",
                        "//button[contains(text(), 'Siguiente')]",  # Spanish
                        "//button[contains(text(), 'Continue')]",
                        "//button[contains(text(), 'Continuar')]",  # Spanish
                        "//input[@value='Next']",
                        "//input[@value='Siguiente']",  # Spanish
                        "//div[@role='button'][contains(text(), 'Next')]",
                        "//div[@role='button'][contains(text(), 'Siguiente')]",  # Spanish
                        "//button[@type='submit']"
                    ]
                    
                    next_clicked = False
                    for selector in next_selectors:
                        try:
                            logger.info(f"🔍 Looking for Next button: {selector}")
                            next_button = WebDriverWait(self.driver, 3).until(
                                EC.element_to_be_clickable((By.XPATH, selector))
                            )
                            logger.info(f"🖱️ Clicking Next button: {selector}")
                            self.click_element_safely(next_button)
                            next_clicked = True
                            break
                        except TimeoutException:
                            logger.info(f"   Next button not found: {selector}")
                            continue
                    
                    if not next_clicked:
                        logger.warning("⚠️ Could not find Next button, trying Enter key...")
                        try:
                            password_input.send_keys("\n")
                            logger.info("✅ Pressed Enter key on password field")
                        except Exception as e:
                            logger.warning(f"⚠️ Enter key failed: {e}")
                    
                    # Wait for password screen to disappear or continue button to appear
                    try:
                        # First, wait a moment for any UI changes
                        time.sleep(3)
                        
                        # Check if password screen disappeared (success)
                        try:
                            WebDriverWait(self.driver, 10).until_not(
                                EC.presence_of_element_located((By.XPATH, "//input[@type='password']"))
                            )
                            logger.info("✅ Password screen disappeared - authentication completed")
                            return True
                        except TimeoutException:
                            logger.info("🔍 Password screen still present, checking for additional steps...")
                            
                            # Look for any additional Continue/Next buttons after password
                            additional_continue_selectors = [
                                "//button[contains(text(), 'Continue')]",
                                "//button[contains(text(), 'Continuar')]",  # Spanish
                                "//button[contains(text(), 'Next')]",
                                "//button[contains(text(), 'Siguiente')]",  # Spanish
                                "//div[@role='button'][contains(text(), 'Continue')]",
                                "//div[@role='button'][contains(text(), 'Continuar')]",
                                "//span[contains(text(), 'Continue')]/ancestor::button",
                                "//span[contains(text(), 'Continuar')]/ancestor::button",
                                "//button[@type='submit']",
                                "//*[@data-action='continue']",
                                "//*[contains(@class, 'continue')]//button"
                            ]
                            
                            continue_found = False
                            for selector in additional_continue_selectors:
                                try:
                                    logger.info(f"🔍 Looking for additional Continue button: {selector}")
                                    elements = self.driver.find_elements(By.XPATH, selector)
                                    for element in elements:
                                        if element.is_displayed() and element.is_enabled():
                                            button_text = element.text or element.get_attribute("value") or "No text"
                                            logger.info(f"✅ Found additional Continue button: '{button_text}'")
                                            self.click_element_safely(element)
                                            logger.info("✅ Clicked additional Continue button")
                                            time.sleep(3)  # Wait for navigation
                                            continue_found = True
                                            break
                                    if continue_found:
                                        break
                                except Exception as e:
                                    logger.info(f"   Additional Continue selector failed: {e}")
                                    continue
                            
                            if continue_found:
                                # Wait again for password screen to disappear
                                try:
                                    WebDriverWait(self.driver, 10).until_not(
                                        EC.presence_of_element_located((By.XPATH, "//input[@type='password']"))
                                    )
                                    logger.info("✅ Password authentication completed after additional Continue")
                                    return True
                                except TimeoutException:
                                    logger.warning("⚠️ Password screen still present after additional Continue")
                            
                    except Exception as e:
                        logger.warning(f"⚠️ Error in password completion check: {e}")
                    
                    # Look for additional Continue buttons on subsequent pages
                    logger.info("🔍 Checking for additional Continue buttons on next pages...")
                    for additional_attempt in range(3):  # Try up to 3 additional Continue clicks
                        try:
                            logger.info(f"🔄 Additional Continue attempt {additional_attempt + 1}/3")
                            time.sleep(2)  # Wait for page to load
                            
                            # First, look for and select any checkboxes on this page
                            logger.info(f"🔍 Checking for checkboxes on additional page {additional_attempt + 1}...")
                            page_checkbox_selectors = [
                                "//input[@type='checkbox']",
                                "//input[@type='checkbox' and not(@checked)]",
                                "//div[@role='checkbox']",
                                "//div[@role='checkbox'][@aria-checked='false']"
                            ]
                            
                            page_checkboxes_selected = 0
                            for cb_selector in page_checkbox_selectors:
                                try:
                                    page_checkboxes = self.driver.find_elements(By.XPATH, cb_selector)
                                    for cb in page_checkboxes:
                                        if cb.is_displayed() and cb.is_enabled():
                                            is_checked = cb.is_selected() or cb.get_attribute("checked") or cb.get_attribute("aria-checked") == "true"
                                            if not is_checked:
                                                logger.info(f"✅ Selecting checkbox on additional page {additional_attempt + 1}")
                                                self.driver.execute_script("arguments[0].scrollIntoView(true);", cb)
                                                time.sleep(0.3)
                                                self.click_element_safely(cb)
                                                page_checkboxes_selected += 1
                                                time.sleep(0.3)
                                except Exception as e:
                                    continue
                            
                            if page_checkboxes_selected > 0:
                                logger.info(f"✅ Selected {page_checkboxes_selected} checkboxes on additional page {additional_attempt + 1}")
                                time.sleep(1)
                            
                            # Look for Continue buttons on the current page
                            subsequent_continue_selectors = [
                                "//button[contains(text(), 'Continue')]",
                                "//button[contains(text(), 'Continuar')]",  # Spanish
                                "//button[contains(text(), 'Next')]",
                                "//button[contains(text(), 'Siguiente')]",  # Spanish
                                "//button[contains(text(), 'Allow')]",
                                "//button[contains(text(), 'Permitir')]",  # Spanish
                                "//div[@role='button'][contains(text(), 'Continue')]",
                                "//div[@role='button'][contains(text(), 'Continuar')]",
                                "//div[@role='button'][contains(text(), 'Allow')]",
                                "//div[@role='button'][contains(text(), 'Permitir')]",
                                "//input[@value='Continue']",
                                "//input[@value='Continuar']",
                                "//input[@value='Allow']",
                                "//input[@value='Permitir']",
                                "//span[contains(text(), 'Continue')]/ancestor::button",
                                "//span[contains(text(), 'Continuar')]/ancestor::button",
                                "//button[@type='submit']"
                            ]
                            
                            subsequent_continue_found = False
                            for selector in subsequent_continue_selectors:
                                try:
                                    elements = self.driver.find_elements(By.XPATH, selector)
                                    for element in elements:
                                        if element.is_displayed() and element.is_enabled():
                                            button_text = element.text or element.get_attribute("value") or "No text"
                                            
                                            # Skip negative buttons
                                            if any(skip_word in button_text.lower() for skip_word in ['cancel', 'deny', 'decline', 'back', 'previous']):
                                                continue
                                                
                                            logger.info(f"✅ Found subsequent Continue button: '{button_text}'")
                                            self.click_element_safely(element)
                                            logger.info(f"✅ Clicked subsequent Continue button (attempt {additional_attempt + 1})")
                                            subsequent_continue_found = True
                                            break
                                    if subsequent_continue_found:
                                        break
                                except Exception as e:
                                    continue
                            
                            if not subsequent_continue_found:
                                logger.info(f"🔍 No more Continue buttons found on attempt {additional_attempt + 1}")
                                break
                            else:
                                # Wait for page transition after clicking
                                time.sleep(3)
                                
                        except Exception as e:
                            logger.warning(f"⚠️ Error in additional Continue attempt {additional_attempt + 1}: {e}")
                            continue
                    
                    logger.info("✅ Password authentication and subsequent steps completed")
                    return True
                    
                except Exception as e:
                    logger.error(f"❌ Error entering password: {e}")
                    logger.info("💡 Please enter password manually and the script will continue...")
                    
                    # Fallback to manual entry
                    WebDriverWait(self.driver, 60).until_not(
                        EC.presence_of_element_located((By.XPATH, "//input[@type='password']"))
                    )
                    return True
            else:
                # No password provided - require manual intervention
                logger.warning("⚠️ Password required but not provided")
                logger.info("💡 Please enter password manually and the script will continue...")
                logger.info("💡 To automate this, run with: --password YOUR_PASSWORD")
                
                # Wait for password screen to be completed manually
                WebDriverWait(self.driver, 60).until_not(
                    EC.presence_of_element_located((By.XPATH, "//input[@type='password']"))
                )
                
                logger.info("✅ Password screen completed")
                return True
            
        except TimeoutException:
            # No password screen - likely already authenticated
            logger.info("✅ No password required (likely already authenticated)")
            return True
    
    def handle_2fa_verification(self):
        """Handle 2FA verification codes and print them for the user"""
        logger.info("🔍 Checking for 2FA verification codes...")
        
        try:
            # Wait a moment for any 2FA pages to load
            time.sleep(3)
            
            # Get current page info
            current_url = self.driver.current_url
            page_title = self.driver.title
            page_source = self.driver.page_source.lower()
            
            logger.info(f"📍 Current URL: {current_url}")
            logger.info(f"📄 Page title: {page_title}")
            
            # Check for 2FA-related keywords in page content
            twofa_keywords = [
                "verify", "verification", "code", "phone", "mobile", "sms", "text", 
                "authenticator", "security", "factor", "confirm", "confirmation",
                "enter the code", "verification code", "phone number", "mobile number",
                "we sent", "sent to", "check your phone", "text message", "sms code"
            ]
            
            has_2fa_content = any(keyword in page_source for keyword in twofa_keywords)
            
            if has_2fa_content:
                logger.info("🔒 2FA verification page detected!")
                
                # Look for verification codes displayed on the page
                verification_code_patterns = [
                    # Common patterns for displayed verification codes
                    r'\b\d{6}\b',  # 6-digit codes
                    r'\b\d{8}\b',  # 8-digit codes  
                    r'\b\d{4}\b',  # 4-digit codes
                    r'\b\d{5}\b',  # 5-digit codes
                    r'\b\d{7}\b'   # 7-digit codes
                ]
                
                # Search for codes in page text
                import re
                page_text = self.driver.find_element(By.TAG_NAME, "body").text
                
                found_codes = []
                for pattern in verification_code_patterns:
                    matches = re.findall(pattern, page_text)
                    for match in matches:
                        # Filter out common non-code numbers (like years, phone numbers, etc.)
                        if (len(match) >= 4 and len(match) <= 8 and 
                            match not in ['2024', '2023', '2025', '1234', '0000']):
                            found_codes.append(match)
                
                # Remove duplicates while preserving order
                unique_codes = list(dict.fromkeys(found_codes))
                
                if unique_codes:
                    logger.info("📱 VERIFICATION CODES FOUND ON PAGE:")
                    for code in unique_codes:
                        print(f"\n🔢 VERIFICATION CODE: {code}")
                        print(f"📱 Please enter this code on your phone: {code}")
                        logger.info(f"📱 VERIFICATION CODE DETECTED: {code}")
                
                # Look for specific 2FA elements and messages
                verification_selectors = [
                    "//div[contains(text(), 'verify')]",
                    "//div[contains(text(), 'code')]", 
                    "//span[contains(text(), 'verify')]",
                    "//span[contains(text(), 'code')]",
                    "//p[contains(text(), 'verify')]",
                    "//p[contains(text(), 'code')]",
                    "//div[contains(text(), 'phone')]",
                    "//div[contains(text(), 'mobile')]",
                    "//div[contains(text(), 'Check your')]",
                    "//div[contains(text(), 'We sent')]"
                ]
                
                verification_messages = []
                for selector in verification_selectors:
                    try:
                        elements = self.driver.find_elements(By.XPATH, selector)
                        for element in elements[:3]:  # Limit to first 3 matches per selector
                            if element.is_displayed():
                                text = element.text.strip()
                                if text and len(text) < 200:  # Reasonable length limit
                                    verification_messages.append(text)
                    except:
                        continue
                
                # Remove duplicates and show verification messages
                unique_messages = list(dict.fromkeys(verification_messages))
                if unique_messages:
                    logger.info("📲 2FA Messages found on page:")
                    for message in unique_messages[:5]:  # Show max 5 messages
                        logger.info(f"   📱 {message}")
                        print(f"📱 2FA MESSAGE: {message}")
                
                # Look for verification code input fields
                verification_input_selectors = [
                    "//input[@type='tel']",
                    "//input[@type='number']",
                    "//input[@type='text'][contains(@placeholder, 'code')]",
                    "//input[@type='text'][contains(@placeholder, 'verify')]",
                    "//input[contains(@id, 'code')]",
                    "//input[contains(@id, 'verify')]",
                    "//input[contains(@name, 'code')]",
                    "//input[contains(@name, 'verify')]",
                    "//input[contains(@class, 'code')]",
                    "//input[contains(@class, 'verify')]"
                ]
                
                verification_input_found = False
                for selector in verification_input_selectors:
                    try:
                        elements = self.driver.find_elements(By.XPATH, selector)
                        if elements:
                            for element in elements:
                                if element.is_displayed():
                                    placeholder = element.get_attribute('placeholder') or 'No placeholder'
                                    input_type = element.get_attribute('type') or 'text'
                                    logger.info(f"🔍 Found verification input field: type='{input_type}', placeholder='{placeholder}'")
                                    verification_input_found = True
                                    break
                        if verification_input_found:
                            break
                    except:
                        continue
                
                if verification_input_found:
                    print(f"\n🔑 VERIFICATION INPUT FIELD DETECTED")
                    print(f"📱 Please check your phone for the verification code and enter it manually")
                    logger.info("🔑 Verification input field detected - user needs to enter code manually")
                
                # Wait longer for user to complete 2FA
                logger.info("⏳ Waiting 30 seconds for 2FA completion...")
                print(f"\n⏳ Waiting 30 seconds for you to complete 2FA verification...")
                time.sleep(30)
                
                return True  # 2FA page was detected and handled
            
            else:
                logger.info("ℹ️ No 2FA verification required - continuing...")
                return False  # No 2FA needed
                
        except Exception as e:
            logger.warning(f"⚠️ Error in 2FA verification handling: {e}")
            return False
    
    def handle_consent_screen(self):
        """Handle OAuth consent/permissions screen"""
        logger.info("🔍 Looking for consent screen...")
        
        # Log current page state
        current_url = self.driver.current_url
        page_title = self.driver.title
        logger.info(f"📍 Consent check URL: {current_url}")
        logger.info(f"📄 Consent check title: {page_title}")
        
        try:
            # Wait briefly for consent screen elements
            logger.info("⏳ Waiting for consent screen elements...")
            
            # First, wait for the page to load completely
            time.sleep(2)
            
            # Look for and select checkboxes before clicking Continue
            logger.info("🔍 Looking for permission checkboxes to select...")
            checkbox_selectors = [
                "//input[@type='checkbox']",
                "//input[@type='checkbox' and not(@checked)]",  # Unchecked checkboxes
                "//div[@role='checkbox']",
                "//div[@role='checkbox'][@aria-checked='false']",  # Unchecked role checkboxes
                "//span[contains(@class, 'checkbox')]",
                "//label[contains(@class, 'checkbox')]//input",
                "//*[contains(@class, 'consent')]//input[@type='checkbox']",
                "//*[contains(@class, 'permission')]//input[@type='checkbox']",
                "//*[contains(@class, 'scope')]//input[@type='checkbox']"
            ]
            
            checkboxes_selected = 0
            for selector in checkbox_selectors:
                try:
                    logger.info(f"🔍 Looking for checkboxes: {selector}")
                    checkboxes = self.driver.find_elements(By.XPATH, selector)
                    logger.info(f"   Found {len(checkboxes)} checkboxes")
                    
                    for i, checkbox in enumerate(checkboxes):
                        try:
                            if checkbox.is_displayed() and checkbox.is_enabled():
                                # Check if it's already selected
                                is_checked = checkbox.is_selected() or checkbox.get_attribute("checked") or checkbox.get_attribute("aria-checked") == "true"
                                
                                if not is_checked:
                                    logger.info(f"✅ Selecting checkbox {i+1}")
                                    # Scroll into view and click
                                    self.driver.execute_script("arguments[0].scrollIntoView(true);", checkbox)
                                    time.sleep(0.5)
                                    self.click_element_safely(checkbox)
                                    checkboxes_selected += 1
                                    time.sleep(0.5)  # Small delay between selections
                                else:
                                    logger.info(f"✅ Checkbox {i+1} already selected")
                                    checkboxes_selected += 1
                        except Exception as e:
                            logger.info(f"   Error selecting checkbox {i+1}: {e}")
                            continue
                except Exception as e:
                    logger.info(f"   Checkbox selector failed: {e}")
                    continue
            
            if checkboxes_selected > 0:
                logger.info(f"✅ Selected {checkboxes_selected} permission checkboxes")
                time.sleep(2)  # Wait after selecting checkboxes
            else:
                logger.info("🔍 No checkboxes found or all already selected")
            
            # Check for consent/permission screens with comprehensive detection
            all_possible_consent_selectors = [
                # Standard consent buttons
                "//button[contains(text(), 'Allow')]",
                "//button[contains(text(), 'Permitir')]",  # Spanish
                "//button[contains(text(), 'Continue')]", 
                "//button[contains(text(), 'Continuar')]",  # Spanish
                "//button[contains(text(), 'Accept')]",
                "//button[contains(text(), 'Aceptar')]",  # Spanish
                "//button[contains(text(), 'Authorize')]",
                "//button[contains(text(), 'Autorizar')]",  # Spanish
                # Button with specific attributes
                "//button[@data-value='allow']",
                "//button[@data-action='allow']",
                "//button[@data-action='continue']",
                # Div role buttons
                "//div[@role='button'][contains(text(), 'Allow')]",
                "//div[@role='button'][contains(text(), 'Permitir')]",  # Spanish
                "//div[@role='button'][contains(text(), 'Continue')]",
                "//div[@role='button'][contains(text(), 'Continuar')]",  # Spanish
                # Input buttons
                "//input[@value='Allow']",
                "//input[@value='Permitir']",  # Spanish
                "//input[@value='Continue']",
                "//input[@value='Continuar']",  # Spanish
                # Span buttons (nested)
                "//span[contains(text(), 'Allow')]/ancestor::button",
                "//span[contains(text(), 'Continue')]/ancestor::button",
                "//span[contains(text(), 'Continuar')]/ancestor::button",
                # Generic submit buttons
                "//button[@type='submit']",
                # Class-based detection
                "//*[contains(@class, 'allow')]//button",
                "//*[contains(@class, 'continue')]//button",
                "//*[contains(@class, 'consent')]//button"
            ]
            
            consent_found = False
            for selector in all_possible_consent_selectors:
                try:
                    logger.info(f"🔍 Checking consent selector: {selector}")
                    elements = self.driver.find_elements(By.XPATH, selector)
                    logger.info(f"   Found {len(elements)} elements")
                    
                    for element in elements:
                        try:
                            if element.is_displayed() and element.is_enabled():
                                button_text = element.text or element.get_attribute("value") or "No text"
                                # Skip obviously wrong buttons
                                if any(skip_word in button_text.lower() for skip_word in ['cancel', 'deny', 'decline', 'back']):
                                    logger.info(f"   Skipping button: '{button_text}' (negative action)")
                                    continue
                                    
                                logger.info(f"✅ Found consent button: '{button_text}'")
                                
                                # Scroll into view and click
                                self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                                time.sleep(0.5)
                                self.click_element_safely(element)
                                logger.info("✅ Clicked consent button")
                                
                                # Wait for page to respond
                                time.sleep(3)
                                consent_found = True
                                break
                        except Exception as e:
                            logger.info(f"   Element interaction failed: {e}")
                            continue
                            
                    if consent_found:
                        break
                except Exception as e:
                    logger.info(f"   Selector failed: {e}")
                    continue
            
            if consent_found:
                logger.info("✅ Consent screen handled successfully")
                # Wait for consent action to process
                time.sleep(3)
                
                # Look for additional Continue buttons after consent
                logger.info("🔍 Checking for additional Continue buttons after consent...")
                for post_consent_attempt in range(2):  # Try up to 2 more Continue clicks
                    try:
                        logger.info(f"🔄 Post-consent Continue attempt {post_consent_attempt + 1}/2")
                        time.sleep(2)
                        
                        post_consent_continue_found = False
                        for selector in all_possible_consent_selectors:
                            try:
                                elements = self.driver.find_elements(By.XPATH, selector)
                                for element in elements:
                                    if element.is_displayed() and element.is_enabled():
                                        button_text = element.text or element.get_attribute("value") or "No text"
                                        if any(skip_word in button_text.lower() for skip_word in ['cancel', 'deny', 'decline', 'back']):
                                            continue
                                            
                                        logger.info(f"✅ Found post-consent Continue button: '{button_text}'")
                                        self.click_element_safely(element)
                                        logger.info(f"✅ Clicked post-consent Continue button (attempt {post_consent_attempt + 1})")
                                        post_consent_continue_found = True
                                        break
                                if post_consent_continue_found:
                                    break
                            except Exception as e:
                                continue
                        
                        if not post_consent_continue_found:
                            logger.info(f"🔍 No more post-consent Continue buttons found on attempt {post_consent_attempt + 1}")
                            break
                        else:
                            time.sleep(3)  # Wait for page transition
                            
                    except Exception as e:
                        logger.warning(f"⚠️ Error in post-consent Continue attempt {post_consent_attempt + 1}: {e}")
                        continue
                
                return True
            else:
                logger.info("✅ No consent screen found (likely already authorized)")
                return True
                
        except Exception as e:
            logger.warning(f"⚠️ Consent screen error: {e}")
            logger.info("✅ Continuing anyway (consent may not be required)")
            return True
    
    def exchange_code_for_tokens(self, auth_code):
        """Exchange authorization code for access and refresh tokens"""
        logger.info("🔄 Exchanging authorization code for tokens...")
        
        if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
            logger.error("❌ Google OAuth credentials not configured")
            return False
        
        token_data = {
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'code': auth_code,
            'grant_type': 'authorization_code',
            'redirect_uri': GOOGLE_REDIRECT_URI
        }
        
        try:
            logger.info(f"🔧 Using redirect_uri: {GOOGLE_REDIRECT_URI}")
            logger.info(f"🔧 Using client_id: {GOOGLE_CLIENT_ID}")
            logger.info(f"🔧 Auth code length: {len(auth_code)}")
            
            response = requests.post(GOOGLE_TOKEN_URL, data=token_data)
            
            # Log response details for debugging
            logger.info(f"🔧 Token exchange response status: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"❌ Token exchange failed with status {response.status_code}")
                logger.error(f"❌ Response text: {response.text}")
                return False
            
            token_response = response.json()
            
            self.access_token = token_response.get('access_token')
            self.refresh_token = token_response.get('refresh_token')
            self.token_data = token_response
            
            logger.info("✅ Successfully exchanged code for tokens")
            logger.info(f"🔑 Access token: {self.access_token[:20]}...")
            logger.info(f"🔑 Refresh token: {'Yes' if self.refresh_token else 'No'}")
            
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to exchange code for tokens: {e}")
            try:
                logger.error(f"❌ Response content: {e.response.text if hasattr(e, 'response') and e.response else 'No response'}")
            except:
                pass
            return False
    
    def get_user_profile(self):
        """Get user profile information from Google"""
        logger.info("👤 Getting user profile information...")
        
        if not self.access_token:
            logger.error("❌ No access token available for profile request")
            return None
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Accept': 'application/json'
        }
        
        try:
            response = requests.get(GOOGLE_USERINFO_URL, headers=headers)
            response.raise_for_status()
            
            profile_data = response.json()
            
            logger.info("✅ Successfully retrieved user profile")
            logger.info(f"👤 User: {profile_data.get('name', 'Unknown')} ({profile_data.get('email', 'Unknown')})")
            
            return profile_data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to get user profile: {e}")
            return None
    
    def save_tokens_to_supabase(self, profile_data=None):
        """Save OAuth tokens to Supabase oauth_tokens table"""
        logger.info("💾 Saving tokens to Supabase...")
        logger.info(f"🔧 SUPABASE_AVAILABLE: {SUPABASE_AVAILABLE}")
        logger.info(f"🔧 Supabase client: {'Initialized' if self.supabase else 'Not initialized'}")
        logger.info(f"🔧 Access token: {'Available' if self.access_token else 'Not available'}")
        
        if not SUPABASE_AVAILABLE:
            logger.info("💡 Supabase not available - skipping token save")
            logger.info("💡 To enable token saving, install: pip install supabase")
            return False
        
        if not self.supabase:
            logger.warning("⚠️ Supabase not initialized - skipping token save")
            logger.warning(f"⚠️ SUPABASE_URL: {'Set' if SUPABASE_URL else 'Not set'}")
            logger.warning(f"⚠️ SUPABASE_KEY: {'Set' if SUPABASE_KEY else 'Not set'}")
            return False
        
        if not self.access_token:
            logger.error("❌ No access token to save")
            logger.error(f"❌ Token data: {self.token_data}")
            return False
        
        # Calculate expiration time
        expires_in = self.token_data.get('expires_in', 3600)  # Default 1 hour
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        
        # Prepare token record
        token_record = {
            'user_id': self.target_email,  # Using email as user_id
            'service_type': 'gmail',
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
            'token_type': self.token_data.get('token_type', 'Bearer'),
            'expires_at': expires_at.isoformat(),
            'scope': self.token_data.get('scope', ''),
            'user_email': profile_data.get('email', self.target_email) if profile_data else self.target_email,
            'user_name': profile_data.get('name', '') if profile_data else '',
            'user_profile': profile_data if profile_data else {},
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'last_used_at': datetime.utcnow().isoformat(),
            'is_active': True,
            'notes': f'OAuth automation - {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")}'
        }
        
        try:
            # Check if token already exists for this user and service
            existing_query = self.supabase.table('oauth_tokens').select('*').eq('user_id', self.target_email).eq('service_type', 'gmail')
            existing_result = existing_query.execute()
            
            if existing_result.data:
                # Update existing record
                logger.info("🔄 Updating existing token record...")
                token_record['updated_at'] = datetime.utcnow().isoformat()
                # Remove created_at for update
                del token_record['created_at']
                
                result = self.supabase.table('oauth_tokens').update(token_record).eq('user_id', self.target_email).eq('service_type', 'gmail').execute()
                logger.info("✅ Token record updated in Supabase")
            else:
                # Insert new record
                logger.info("➕ Creating new token record...")
                result = self.supabase.table('oauth_tokens').insert(token_record).execute()
                logger.info("✅ Token record created in Supabase")
            
            logger.info(f"💾 Saved tokens for user: {token_record['user_email']}")
            logger.info(f"🔑 Token expires at: {expires_at.strftime('%Y-%m-%d %H:%M:%S')} UTC")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to save tokens to Supabase: {e}")
            return False

    def wait_for_oauth_completion(self):
        """Wait for OAuth flow to complete and return to app"""
        logger.info("⏳ Waiting for OAuth completion...")
        
        start_time = time.time()
        
        # Get initial window count safely
        try:
            initial_window_count = len(self.driver.window_handles)
            logger.info(f"🪟 Initial window count: {initial_window_count}")
        except Exception as e:
            logger.warning(f"⚠️ Could not get initial window count: {e}")
            initial_window_count = 1
        
        while time.time() - start_time < 45:  # Increased timeout to 45 seconds
            try:
                # Check if browser/window is still available
                try:
                    current_window_count = len(self.driver.window_handles)
                    
                    # Switch to the first available window if current one is closed
                    if current_window_count > 0:
                        self.driver.switch_to.window(self.driver.window_handles[0])
                    else:
                        logger.warning("⚠️ No windows available - browser may have closed")
                        break
                        
                except Exception as window_error:
                    logger.warning(f"⚠️ Window access error: {window_error}")
                    # If we can't access windows, OAuth might have completed with window closure
                    logger.info("🎯 Window closure detected - this may indicate OAuth completion")
                    logger.info("✅ Treating window closure as potential OAuth success")
                    return True
                
                # Get current page info safely
                try:
                    current_url = self.driver.current_url
                    page_title = self.driver.title
                    
                    logger.info(f"🔍 Current URL: {current_url[:100]}...")
                    logger.info(f"🔍 Current title: {page_title}")
                    logger.info(f"🪟 Window count: {current_window_count}")
                    
                except Exception as page_error:
                    logger.warning(f"⚠️ Could not get page info: {page_error}")
                    if "no such window" in str(page_error).lower() or "target window already closed" in str(page_error).lower():
                        logger.info("🎯 Target window closed - OAuth likely completed")
                        logger.info("✅ Treating window closure as OAuth success")
                        return True
                    else:
                        # Other error, continue trying
                        time.sleep(2)
                        continue
                
                # Check for various OAuth completion indicators
                oauth_complete_indicators = [
                    f"localhost:{self.port}" in current_url,
                    "127.0.0.1" in current_url,
                    self.base_url in current_url,  # Check for base URL
                    "code=" in current_url,
                    "access_token=" in current_url,
                    "token=" in current_url,
                    "oauth/callback" in current_url,
                    "storagerelay" in current_url,  # Google's storage relay
                    current_url.startswith("http://localhost"),
                    current_url.startswith("http://127.0.0.1"),
                    current_url.startswith(self.base_url)  # Check for base URL prefix
                ]
                
                if any(oauth_complete_indicators):
                    logger.info("🎉 OAuth completion indicator detected!")
                    logger.info(f"📍 Completion URL: {current_url}")
                    
                    # Extract auth code or token if present
                    if "code=" in current_url:
                        try:
                            parsed_url = urlparse(current_url)
                            params = parse_qs(parsed_url.query)
                            if 'code' in params:
                                self.auth_code = params['code'][0]
                                logger.info("✅ Authorization code captured")
                                logger.info(f"🔑 Auth code: {self.auth_code[:20]}...")
                                
                                # Exchange code for tokens
                                if self.exchange_code_for_tokens(self.auth_code):
                                    # Get user profile
                                    profile_data = self.get_user_profile()
                                    
                                    # Save tokens to Supabase
                                    if self.save_tokens_to_supabase(profile_data):
                                        logger.info("🎉 OAuth tokens successfully saved to Supabase!")
                                    else:
                                        logger.warning("⚠️ OAuth completed but token save failed")
                                else:
                                    logger.warning("⚠️ OAuth completed but token exchange failed")
                        except Exception as e:
                            logger.warning(f"⚠️ Error processing OAuth completion: {e}")
                    
                    if "access_token=" in current_url:
                        logger.info("✅ Access token detected in URL")
                        # Note: Direct access token in URL is less secure, prefer auth code flow
                    
                    return True
                
                # Check if popup window closed (indicates OAuth completion)
                if initial_window_count > 1 and current_window_count == 1:
                    logger.info("🎉 OAuth popup closed - checking main window")
                    try:
                        # Switch to main window safely
                        try:
                            if len(self.driver.window_handles) > 0:
                                self.driver.switch_to.window(self.driver.window_handles[0])
                                time.sleep(3)  # Wait for main window to update
                            else:
                                logger.warning("⚠️ No windows available after popup closed")
                                return True  # Assume OAuth completed
                        except Exception as window_switch_error:
                            if "no such window" in str(window_switch_error).lower():
                                logger.info("🎯 Main window also closed - OAuth likely completed")
                                return True
                            else:
                                raise window_switch_error
                        
                        # Check if main window now has OAuth completion
                        try:
                            main_url = self.driver.current_url
                            main_title = self.driver.title
                            logger.info(f"🔍 Main window URL: {main_url}")
                            logger.info(f"🔍 Main window title: {main_title}")
                            
                            if (f"localhost:{self.port}" in main_url or 
                                "127.0.0.1" in main_url or 
                                self.base_url in main_url or
                                "code=" in main_url or 
                                "token=" in main_url):
                                logger.info("✅ OAuth completed in main window")
                                
                                # Process tokens if code is present
                                if "code=" in main_url:
                                    try:
                                        parsed_url = urlparse(main_url)
                                        params = parse_qs(parsed_url.query)
                                        if 'code' in params:
                                            self.auth_code = params['code'][0]
                                            logger.info("✅ Authorization code captured from main window")
                                            logger.info(f"🔑 Auth code: {self.auth_code[:20]}...")
                                            
                                            # Exchange code for tokens
                                            if self.exchange_code_for_tokens(self.auth_code):
                                                # Get user profile
                                                profile_data = self.get_user_profile()
                                                
                                                # Save tokens to Supabase
                                                if self.save_tokens_to_supabase(profile_data):
                                                    logger.info("🎉 OAuth tokens successfully saved to Supabase!")
                                                else:
                                                    logger.warning("⚠️ OAuth completed but token save failed")
                                            else:
                                                logger.warning("⚠️ OAuth completed but token exchange failed")
                                    except Exception as e:
                                        logger.warning(f"⚠️ Error processing main window OAuth: {e}")
                                
                                return True
                        except Exception as main_window_error:
                            if "no such window" in str(main_window_error).lower():
                                logger.info("🎯 Main window closed during check - OAuth likely completed")
                                return True
                            else:
                                logger.warning(f"⚠️ Error checking main window: {main_window_error}")
                                
                    except Exception as switch_error:
                        if "no such window" in str(switch_error).lower() or "target window already closed" in str(switch_error).lower():
                            logger.info("🎯 Window closure during popup check - OAuth likely completed")
                            return True
                        else:
                            logger.warning(f"⚠️ Error switching to main window: {switch_error}")
                
                # Check for Google OAuth success/error pages
                if "oauth" in current_url and "success" in current_url.lower():
                    logger.info("✅ Google OAuth success page detected")
                    return True
                
                if "consent" in current_url and "completed" in page_title.lower():
                    logger.info("✅ OAuth consent completed")
                    time.sleep(2)  # Wait for redirect
                    continue
                
                # Log periodic status
                elapsed = time.time() - start_time
                if int(elapsed) % 10 == 0:  # Every 10 seconds
                    logger.info(f"⏳ Still waiting... ({int(elapsed)}s elapsed)")
                
                time.sleep(2)  # Increased polling interval
                
            except Exception as e:
                # Handle specific window closure errors
                if ("no such window" in str(e).lower() or 
                    "target window already closed" in str(e).lower() or
                    "web view not found" in str(e).lower()):
                    logger.info("🎯 Window closure detected in main loop - OAuth likely completed")
                    logger.info("✅ Treating window closure as OAuth success")
                    return True
                else:
                    logger.warning(f"⚠️ Error checking completion: {e}")
                    time.sleep(2)
        
        logger.warning("⏰ Timeout waiting for OAuth completion")
        logger.info("💡 OAuth may have completed but wasn't detected")
        
        # Final check - try to switch back to main window anyway
        try:
            window_handles = self.driver.window_handles
            if len(window_handles) > 0:
                self.driver.switch_to.window(window_handles[0])
                final_url = self.driver.current_url
                logger.info(f"🔍 Final main window URL: {final_url}")
                
                if (f"localhost:{self.port}" in final_url or 
                    "127.0.0.1" in final_url or
                    self.base_url in final_url):
                    logger.info("✅ OAuth may have completed despite timeout")
                    return True
            else:
                logger.info("🎯 No windows available in final check - OAuth may have completed with full browser closure")
                return True
        except Exception as e:
            if "no such window" in str(e).lower() or "target window already closed" in str(e).lower():
                logger.info("🎯 Window closure in final check - OAuth likely completed")
                return True
            else:
                logger.warning(f"⚠️ Error in final check: {e}")
        
        return False
    
    def click_element_safely(self, element):
        """Safely click an element with retry logic"""
        try:
            # Scroll element into view
            self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
            time.sleep(0.5)
            
            # Try regular click first
            element.click()
            logger.info("✅ Element clicked successfully")
            
        except Exception as e:
            try:
                # Fallback: JavaScript click
                self.driver.execute_script("arguments[0].click();", element)
                logger.info("✅ Element clicked via JavaScript")
            except Exception as e2:
                logger.error(f"❌ Failed to click element: {e2}")
                raise
    
    def monitor_oauth_process(self, initial_url=None, keep_browser_for_workflow=False):
        """Main method to monitor and handle OAuth process"""
        logger.info("🚀 Starting Gmail OAuth automation...")
        
        if not self.setup_driver():
            return False
        
        success = False
        try:
            # If initial URL provided, navigate to it
            if initial_url:
                logger.info(f"🌐 Navigating to: {initial_url}")
                self.driver.get(initial_url)
            
            # Monitor for OAuth flow
            success = self.wait_for_oauth_page(initial_url)
            
            if success:
                logger.info("🎉 OAuth automation completed successfully!")
            else:
                logger.error("❌ OAuth automation failed")
            
        except Exception as e:
            logger.error(f"❌ Error during OAuth monitoring: {e}")
            logger.info("🔍 Current page state:")
            try:
                logger.info(f"   URL: {self.driver.current_url}")
                logger.info(f"   Title: {self.driver.title}")
            except:
                logger.info("   Could not get page state")
        
        finally:
            # Don't close browser if keeping it for workflow
            if keep_browser_for_workflow and success:
                logger.info("🔄 Keeping browser open for Gmail processing workflow...")
                # Don't close the browser, just return success
                return success
            
            # Keep browser open longer for debugging if there was an error or debug mode
            if not self.headless:
                if self.keep_open > 0:
                    logger.info(f"🔍 Keeping browser open for {self.keep_open} seconds as requested...")
                    logger.info("💡 You can manually complete OAuth in the browser if needed")
                    time.sleep(self.keep_open)
                elif self.debug:
                    logger.info("🔍 Debug mode: Keeping browser open for 60 seconds...")
                    logger.info("💡 You can manually complete OAuth in the browser if needed")
                    time.sleep(60)
                elif not success:
                    logger.info("🔍 OAuth failed - keeping browser open for 30 seconds for debugging...")
                    logger.info("💡 Check the browser for error messages or incomplete steps")
                    logger.info("💡 You can manually complete OAuth in the browser")
                    time.sleep(30)
                else:
                    logger.info("✅ OAuth completed successfully - closing browser in 5 seconds...")
                    time.sleep(5)
            else:
                # Even in headless mode, wait a bit for completion
                if not success:
                    logger.info("🔍 Headless mode: Waiting 10 seconds for potential completion...")
                    time.sleep(10)
            
            # Final status check before closing
            if self.driver:
                try:
                    final_url = self.driver.current_url
                    logger.info(f"📍 Final URL before closing: {final_url}")
                    
                    # Check if OAuth actually completed despite errors
                    if ("localhost" in final_url or "127.0.0.1" in final_url or 
                        "code=" in final_url or "access_token=" in final_url):
                        logger.info("🎉 OAuth may have completed despite reported failure!")
                        success = True
                        
                except Exception as e:
                    logger.warning(f"⚠️ Could not get final URL: {e}")
                
                try:
                    self.driver.quit()
                    logger.info("🔚 WebDriver closed")
                except Exception as e:
                    logger.warning(f"⚠️ Error closing WebDriver: {e}")
        
        return success
    
    def confirm_gmail_connection(self, max_retries=3):
        """Confirm that Gmail connection is successful by checking for 'Disconnect Gmail' button"""
        logger.info("🔍 Confirming Gmail connection status...")

        # Disconnect button selectors (prioritize exact text)
        disconnect_selectors = [
            "//button[contains(text(), 'Disconnect Gmail')]",  # Exact text from Midas Portal
            "//button[text()='Disconnect Gmail']",  # Exact match
            "//a[contains(text(), 'Disconnect Gmail')]",  # In case it's a link
            "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'disconnect gmail')]",
            "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'disconnect')]",
            "//button[contains(text(), 'Disconnect')]",
            "//input[@value='Disconnect Gmail']",
            "//input[@value='Disconnect']"
        ]

        for attempt in range(max_retries):
            try:
                logger.info(f"🔄 Connection confirmation attempt {attempt + 1}/{max_retries}")
                
                # Wait for page to load
                time.sleep(5)
                
                # Get current page info
                current_url = self.driver.current_url
                page_title = self.driver.title
                logger.info(f"📍 Current URL: {current_url}")
                logger.info(f"📄 Page title: {page_title}")
                
                # Refresh page to ensure UI updates after OAuth (important!)
                logger.info("🔄 Refreshing page to ensure UI updates after OAuth...")
                self.driver.refresh()
                time.sleep(5)  # Wait for refresh to complete
                
                # Log page after refresh
                refreshed_url = self.driver.current_url
                refreshed_title = self.driver.title
                logger.info(f"📍 After refresh - URL: {refreshed_url}")
                logger.info(f"📄 After refresh - Title: {refreshed_title}")
                
                # Search for disconnect button
                logger.info("🔍 Searching for 'Disconnect Gmail' button...")
                
                for i, selector in enumerate(disconnect_selectors):
                    try:
                        logger.info(f"   Trying selector {i+1}/{len(disconnect_selectors)}: {selector[:50]}...")
                        elements = self.driver.find_elements(By.XPATH, selector)
                        
                        if elements:
                            disconnect_button = elements[0]
                            button_text = disconnect_button.text.strip()
                            button_class = disconnect_button.get_attribute('class') or 'none'
                            
                            logger.info(f"✅ FOUND 'Disconnect Gmail' button!")
                            logger.info(f"   Text: '{button_text}'")
                            logger.info(f"   Class: {button_class}")
                            logger.info("🎉 Gmail connection confirmed - proceeding with workflow!")
                            return True
                            
                    except Exception as e:
                        logger.debug(f"   Selector {i+1} failed: {e}")
                        continue
                
                # If we reach here, disconnect button was not found
                logger.warning(f"⚠️ 'Disconnect Gmail' button not found on attempt {attempt + 1}")
                
                # If this is not the last attempt, try to trigger OAuth again
                if attempt < max_retries - 1:
                    logger.info("🔄 Disconnect button not found - will retry OAuth process...")
                    
                    # Navigate back to Gmail processor page and look for Connect button
                    logger.info("🌐 Navigating to Gmail processor page...")
                    gmail_processor_url = f"{self.base_url}/gmail-processor"
                    self.driver.get(gmail_processor_url)
                    time.sleep(5)
                    
                    # Try to find and click Connect button to retry OAuth
                    logger.info("🔍 Looking for 'Connect to Gmail + Drive' button to retry OAuth...")
                    connect_success = self.trigger_oauth_from_app()
                    
                    if not connect_success:
                        logger.warning("⚠️ Could not find Connect button to retry OAuth")
                        continue  # Try next attempt anyway
                    
                    # Wait for OAuth to complete
                    logger.info("⏳ Waiting for OAuth to complete...")
                    time.sleep(10)
                    
                    # Continue to next attempt to check for disconnect button
                    continue
                
            except Exception as e:
                logger.error(f"❌ Error in connection confirmation attempt {attempt + 1}: {e}")
                continue
        
        # If we exhausted all retries
        logger.error("❌ Failed to confirm Gmail connection after all retries")
        logger.error("❌ 'Disconnect Gmail' button not found - Gmail may not be connected")
        logger.info("💡 This means OAuth may have failed or the UI hasn't updated yet")
        return False
    
    def set_date_filter_last_20_minutes(self):
        """Set the date filter to last 20 minutes"""
        logger.info("📅 Setting date filter to last 20 minutes...")
        
        try:
            # Wait for page to fully load
            time.sleep(3)
            
            # Debug: Log current page info
            current_url = self.driver.current_url
            page_title = self.driver.title
            logger.info(f"📍 Current URL: {current_url}")
            logger.info(f"📄 Page title: {page_title}")
            
            # Debug: Scan for all potential date filter elements on page
            logger.info("🔍 Scanning page for all potential date filter elements...")
            self._debug_scan_date_filter_elements()
            
            # First, try to find the specific 20-minute button directly
            logger.info("🔍 Looking for 20-minute filter button directly...")
            
            # Look for "Last 20 min" option - exact text from Midas Portal
            last_20_min_selectors = [
                # Exact text patterns (most reliable)
                "//button[contains(text(), 'Last 20 min')]",  # Exact text from Midas Portal
                "//button[text()='Last 20 min']",  # Exact match
                "//option[contains(text(), 'Last 20 min')]",  # In case it's a dropdown option
                "//option[text()='Last 20 min']",  # Exact option match
                "//div[contains(text(), 'Last 20 min')]",  # In case it's a div element
                "//li[contains(text(), 'Last 20 min')]",  # In case it's a list item
                "//a[contains(text(), 'Last 20 min')]",  # In case it's a link
                
                # Case-insensitive versions
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'last 20 min')]",
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '20 min')]",
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'last 20')]",
                
                # Fallback patterns
                "//button[contains(@title, 'Last 20 min')]",
                "//button[contains(@title, '20 min')]",
                "//option[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '20 min')]",
                "//div[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '20 min')]",
                "//li[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '20 min')]"
            ]
            
            for i, selector in enumerate(last_20_min_selectors):
                try:
                    logger.info(f"🔍 Trying selector {i+1}/{len(last_20_min_selectors)}: {selector[:50]}...")
                    elements = self.driver.find_elements(By.XPATH, selector)
                    logger.info(f"   Found {len(elements)} elements")
                    
                    if elements:
                        option = elements[0]
                        option_text = option.text.strip()
                        option_tag = option.tag_name
                        option_class = option.get_attribute('class') or 'none'
                        option_title = option.get_attribute('title') or 'none'
                        
                        logger.info(f"✅ Found 20-minute option:")
                        logger.info(f"   Text: '{option_text}'")
                        logger.info(f"   Tag: {option_tag}")
                        logger.info(f"   Class: {option_class}")
                        logger.info(f"   Title: {option_title}")
                        
                        self.click_element_safely(option)
                        logger.info("✅ Set date filter to last 20 minutes")
                        time.sleep(2)
                        return True
                except Exception as e:
                    logger.debug(f"   Selector {i+1} failed: {e}")
                    continue
            
            logger.warning("⚠️ Could not find 'last 20 minutes' option in date filter")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error setting date filter: {e}")
            return False
    
    def _debug_scan_date_filter_elements(self):
        """Debug method to scan page for potential date filter elements"""
        try:
            # Scan for elements containing time-related keywords
            time_keywords = ['min', 'hour', 'day', 'week', 'month', 'time', 'last', 'recent', '20', 'filter', 'date']
            
            logger.info("🔍 Scanning for buttons with time-related text...")
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            logger.info(f"   Found {len(buttons)} total buttons on page")
            
            relevant_buttons = []
            for i, button in enumerate(buttons[:20]):  # Limit to first 20 buttons
                try:
                    button_text = button.text.strip()
                    button_class = button.get_attribute('class') or 'none'
                    if any(keyword in button_text.lower() for keyword in time_keywords):
                        relevant_buttons.append(f"Button {i+1}: '{button_text}' (class: {button_class})")
                except:
                    continue
            
            if relevant_buttons:
                logger.info("📋 Found buttons with time-related text:")
                for btn_info in relevant_buttons:
                    logger.info(f"   {btn_info}")
            else:
                logger.info("   No buttons with time-related keywords found")
            
            # Check dropdown options
            logger.info("🔍 Scanning for dropdown options...")
            options = self.driver.find_elements(By.TAG_NAME, "option")
            logger.info(f"   Found {len(options)} total options on page")
            
            relevant_options = []
            for i, option in enumerate(options[:20]):  # Limit to first 20 options
                try:
                    option_text = option.text.strip()
                    if any(keyword in option_text.lower() for keyword in time_keywords):
                        relevant_options.append(f"Option {i+1}: '{option_text}'")
                except:
                    continue
            
            if relevant_options:
                logger.info("📋 Found options with time-related text:")
                for opt_info in relevant_options:
                    logger.info(f"   {opt_info}")
            else:
                logger.info("   No options with time-related keywords found")
            
            # Check divs and spans
            logger.info("🔍 Scanning for divs/spans with time-related text...")
            divs_spans = self.driver.find_elements(By.XPATH, "//div | //span")
            logger.info(f"   Found {len(divs_spans)} total divs/spans on page")
            
            relevant_divs = []
            for i, element in enumerate(divs_spans[:50]):  # Limit to first 50 elements
                try:
                    element_text = element.text.strip()
                    element_tag = element.tag_name
                    element_class = element.get_attribute('class') or 'none'
                    if any(keyword in element_text.lower() for keyword in time_keywords) and len(element_text) < 100:
                        relevant_divs.append(f"{element_tag.upper()} {i+1}: '{element_text}' (class: {element_class})")
                except:
                    continue
            
            if relevant_divs:
                logger.info("📋 Found divs/spans with time-related text:")
                for div_info in relevant_divs[:10]:  # Show only first 10
                    logger.info(f"   {div_info}")
            else:
                logger.info("   No divs/spans with time-related keywords found")
                
        except Exception as e:
            logger.warning(f"Debug scan failed: {e}")
    
    def extract_time_range(self):
        """Extract the start and end time from the current filter selection"""
        logger.info("⏰ Extracting time range from current filter...")
        
        try:
            # Look for time display elements
            time_display_selectors = [
                "//div[contains(@class, 'time-range')]",
                "//div[contains(@class, 'date-range')]",
                "//span[contains(@class, 'time')]",
                "//span[contains(@class, 'date')]",
                "//div[contains(@class, 'filter-display')]",
                "//div[contains(@class, 'selected-range')]",
                "//*[contains(text(), ':') and contains(text(), '-')]",
                "//*[contains(text(), 'from') and contains(text(), 'to')]",
                "//*[contains(text(), 'desde') and contains(text(), 'hasta')]"
            ]
            
            time_info = None
            for selector in time_display_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for element in elements:
                        text = element.text.strip()
                        if ':' in text and (('-' in text) or ('to' in text.lower()) or ('hasta' in text.lower())):
                            time_info = text
                            logger.info(f"✅ Found time range display: '{time_info}'")
                            break
                    if time_info:
                        break
                except Exception as e:
                    continue
            
            # If no explicit time display found, generate time range for last 20 minutes
            if not time_info:
                from datetime import datetime, timedelta
                now = datetime.now()
                start_time = now - timedelta(minutes=20)
                
                start_hour = start_time.strftime("%H:%M")
                end_hour = now.strftime("%H:%M")
                
                logger.info(f"📅 Generated time range: {start_hour} - {end_hour}")
                return start_hour, end_hour
            
            # Parse the found time info
            import re
            time_pattern = r'(\d{1,2}:\d{2})'
            times = re.findall(time_pattern, time_info)
            
            if len(times) >= 2:
                start_hour = times[0]
                end_hour = times[1]
                logger.info(f"📅 Extracted time range: {start_hour} - {end_hour}")
                return start_hour, end_hour
            elif len(times) == 1:
                # Only one time found, assume it's the end time and calculate start
                end_hour = times[0]
                from datetime import datetime, timedelta
                end_dt = datetime.strptime(end_hour, "%H:%M")
                start_dt = end_dt - timedelta(minutes=20)
                start_hour = start_dt.strftime("%H:%M")
                logger.info(f"📅 Calculated time range: {start_hour} - {end_hour}")
                return start_hour, end_hour
            else:
                # Fallback to current time - 20 minutes
                from datetime import datetime, timedelta
                now = datetime.now()
                start_time = now - timedelta(minutes=20)
                
                start_hour = start_time.strftime("%H:%M")
                end_hour = now.strftime("%H:%M")
                
                logger.info(f"📅 Fallback time range: {start_hour} - {end_hour}")
                return start_hour, end_hour
            
        except Exception as e:
            logger.error(f"❌ Error extracting time range: {e}")
            # Fallback to current time - 20 minutes
            from datetime import datetime, timedelta
            now = datetime.now()
            start_time = now - timedelta(minutes=20)
            
            start_hour = start_time.strftime("%H:%M")
            end_hour = now.strftime("%H:%M")
            
            logger.info(f"📅 Error fallback time range: {start_hour} - {end_hour}")
            return start_hour, end_hour
    
    def click_scan_process_button(self):
        """Click the Scan & Auto-Process Emails button"""
        logger.info("🔄 Looking for Scan & Auto-Process Emails button...")
        
        try:
            # Wait for page to fully load
            time.sleep(3)
            
            # Debug: Log current page info
            current_url = self.driver.current_url
            page_title = self.driver.title
            logger.info(f"📍 Current URL: {current_url}")
            logger.info(f"📄 Page title: {page_title}")
            
            # Debug: Scan for all potential scan/process elements on page
            logger.info("🔍 Scanning page for all potential scan/process elements...")
            self._debug_scan_process_elements()
            
            scan_process_selectors = [
                # Exact text patterns (most reliable)
                "//button[contains(text(), 'Scan & Auto-Process Emails')]",  # Exact text from Midas Portal
                "//button[text()='Scan & Auto-Process Emails']",  # Exact match
                "//button[contains(text(), 'Auto-Process Emails')]",  # Shortened version
                "//a[contains(text(), 'Scan & Auto-Process Emails')]",  # In case it's a link
                "//input[@value='Scan & Auto-Process Emails']",  # In case it's an input
                
                # Case-insensitive versions
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'scan & auto-process emails')]",
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'auto-process emails')]",
                
                # Fallback patterns (original selectors)
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'scan') and contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'auto') and contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'process')]",
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'scan') and contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'process')]",
                "//button[contains(text(), 'Scan & Auto Process')]",
                "//button[contains(text(), 'Scan and Auto Process')]",
                "//button[contains(text(), 'Auto Process')]",
                "//input[@value='Scan & Auto Process']",
                "//input[@value='Auto Process']"
            ]
            
            for selector in scan_process_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    if elements:
                        button = elements[0]
                        button_text = button.text.strip()
                        logger.info(f"✅ Found scan & process button: '{button_text}'")
                        self.click_element_safely(button)
                        logger.info("✅ Clicked Scan & Auto-Process Emails button")
                        return True
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue
            
            logger.warning("⚠️ Could not find Scan & Auto-Process Emails button")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error clicking Scan & Auto-Process Emails button: {e}")
            return False
    
    def _debug_scan_process_elements(self):
        """Debug method to scan page for potential scan/process elements"""
        try:
            # Scan for elements containing scan/process-related keywords
            process_keywords = ['scan', 'process', 'auto', 'email', 'start', 'run', 'execute', 'submit', 'go']
            
            logger.info("🔍 Scanning for buttons with scan/process-related text...")
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            logger.info(f"   Found {len(buttons)} total buttons on page")
            
            relevant_buttons = []
            for i, button in enumerate(buttons[:20]):  # Limit to first 20 buttons
                try:
                    button_text = button.text.strip()
                    button_class = button.get_attribute('class') or 'none'
                    button_type = button.get_attribute('type') or 'none'
                    if any(keyword in button_text.lower() for keyword in process_keywords):
                        relevant_buttons.append(f"Button {i+1}: '{button_text}' (class: {button_class}, type: {button_type})")
                except:
                    continue
            
            if relevant_buttons:
                logger.info("📋 Found buttons with scan/process-related text:")
                for btn_info in relevant_buttons:
                    logger.info(f"   {btn_info}")
            else:
                logger.info("   No buttons with scan/process keywords found")
            
            # Check input elements
            logger.info("🔍 Scanning for input elements...")
            inputs = self.driver.find_elements(By.TAG_NAME, "input")
            logger.info(f"   Found {len(inputs)} total inputs on page")
            
            relevant_inputs = []
            for i, input_elem in enumerate(inputs[:20]):  # Limit to first 20 inputs
                try:
                    input_value = input_elem.get_attribute('value') or ''
                    input_type = input_elem.get_attribute('type') or 'none'
                    input_class = input_elem.get_attribute('class') or 'none'
                    if any(keyword in input_value.lower() for keyword in process_keywords):
                        relevant_inputs.append(f"Input {i+1}: value='{input_value}' (type: {input_type}, class: {input_class})")
                except:
                    continue
            
            if relevant_inputs:
                logger.info("📋 Found inputs with scan/process-related values:")
                for inp_info in relevant_inputs:
                    logger.info(f"   {inp_info}")
            else:
                logger.info("   No inputs with scan/process keywords found")
            
            # Check links
            logger.info("🔍 Scanning for links with scan/process-related text...")
            links = self.driver.find_elements(By.TAG_NAME, "a")
            logger.info(f"   Found {len(links)} total links on page")
            
            relevant_links = []
            for i, link in enumerate(links[:20]):  # Limit to first 20 links
                try:
                    link_text = link.text.strip()
                    link_class = link.get_attribute('class') or 'none'
                    if any(keyword in link_text.lower() for keyword in process_keywords) and len(link_text) < 100:
                        relevant_links.append(f"Link {i+1}: '{link_text}' (class: {link_class})")
                except:
                    continue
            
            if relevant_links:
                logger.info("📋 Found links with scan/process-related text:")
                for link_info in relevant_links[:10]:  # Show only first 10
                    logger.info(f"   {link_info}")
            else:
                logger.info("   No links with scan/process keywords found")
                
        except Exception as e:
            logger.warning(f"Debug scan failed: {e}")
    
    def gmail_processing_cycle(self):
        """Execute a single Gmail processing cycle (for headless/service use)"""
        logger.info("🔄 Executing Gmail processing cycle...")
        
        try:
            # Step 1: Confirm Gmail connection (includes page refresh and OAuth retry if needed)
            if not self.confirm_gmail_connection():
                logger.error("❌ Gmail connection not confirmed - 'Disconnect Gmail' button not found")
                logger.error("❌ This means OAuth failed or the page hasn't updated properly")
                logger.info("💡 The automation will retry the entire cycle in a few minutes")
                return False
            
            # Step 2: Set date filter to last 20 minutes
            if not self.set_date_filter_last_20_minutes():
                logger.warning("⚠️ Could not set date filter, continuing anyway...")
            
            # Step 3: Extract time range
            start_hour, end_hour = self.extract_time_range()
            
                            # Step 4: Click Scan & Auto-Process Emails
            if not self.click_scan_process_button():
                logger.error("❌ Could not click Scan & Process button")
                return False
            
            logger.info("✅ Gmail processing cycle completed successfully")
            logger.info(f"⏰ Time range processed: {start_hour} - {end_hour}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error in Gmail processing cycle: {e}")
            return False

    def gmail_processing_workflow(self):
        """Main workflow for Gmail processing after OAuth completion"""
        logger.info("🔄 Starting Gmail processing workflow...")
        
        cycle_count = 0
        
        while True:
            cycle_count += 1
            logger.info(f"🔄 Starting processing cycle #{cycle_count}")
            
            try:
                # Execute single cycle
                if not self.gmail_processing_cycle():
                    logger.error("❌ Processing cycle failed. Stopping workflow.")
                    break
                
                logger.info(f"✅ Cycle #{cycle_count} completed successfully")
                
                # Step 5: Calculate next run time (20 minutes from now)
                next_run_time = self.calculate_next_run_time_from_now()
                logger.info(f"⏰ Next cycle scheduled for: {next_run_time}")
                
                # Step 6: Wait until next run time
                if not self.wait_until_next_cycle(next_run_time):
                    logger.info("🛑 Workflow stopped by user or error")
                    break
                
            except KeyboardInterrupt:
                logger.info("🛑 Workflow stopped by user (Ctrl+C)")
                break
            except Exception as e:
                logger.error(f"❌ Error in processing cycle #{cycle_count}: {e}")
                logger.info("⏳ Waiting 5 minutes before retrying...")
                time.sleep(300)  # Wait 5 minutes before retrying
                continue
    
    def calculate_next_run_time_from_now(self):
        """Calculate the next run time (20 minutes from now)"""
        from datetime import datetime, timedelta
        return datetime.now() + timedelta(minutes=20)

    def calculate_next_run_time(self, end_hour):
        """Calculate the next run time (20 minutes after end_hour)"""
        from datetime import datetime, timedelta
        
        try:
            # Parse end_hour (format: HH:MM)
            today = datetime.now().date()
            end_time = datetime.strptime(f"{today} {end_hour}", "%Y-%m-%d %H:%M")
            
            # If end_time is in the past (earlier today), assume it's for tomorrow
            now = datetime.now()
            if end_time < now:
                end_time += timedelta(days=1)
            
            # Add 20 minutes
            next_run = end_time + timedelta(minutes=20)
            
            return next_run
            
        except Exception as e:
            logger.error(f"❌ Error calculating next run time: {e}")
            # Fallback: 20 minutes from now
            return datetime.now() + timedelta(minutes=20)
    
    def wait_until_next_cycle(self, next_run_time):
        """Wait until the next cycle time"""
        from datetime import datetime
        
        try:
            now = datetime.now()
            wait_seconds = (next_run_time - now).total_seconds()
            
            if wait_seconds <= 0:
                logger.info("⏰ Next cycle time has already passed, starting immediately")
                return True
            
            wait_minutes = int(wait_seconds // 60)
            wait_seconds_remaining = int(wait_seconds % 60)
            
            logger.info(f"⏳ Waiting {wait_minutes} minutes and {wait_seconds_remaining} seconds until next cycle...")
            
            # Wait in chunks to allow for interruption
            chunk_size = 60  # 1 minute chunks
            total_waited = 0
            
            while total_waited < wait_seconds:
                remaining_wait = min(chunk_size, wait_seconds - total_waited)
                time.sleep(remaining_wait)
                total_waited += remaining_wait
                
                remaining_total = wait_seconds - total_waited
                if remaining_total > 60:
                    remaining_minutes = int(remaining_total // 60)
                    logger.info(f"⏳ Still waiting... {remaining_minutes} minutes remaining")
            
            logger.info("⏰ Wait time completed, starting next cycle")
            return True
            
        except KeyboardInterrupt:
            logger.info("🛑 Wait interrupted by user")
            return False
        except Exception as e:
            logger.error(f"❌ Error during wait: {e}")
            return False

def create_trigger_server(automator, port=9999):
    """Create a simple HTTP server to trigger OAuth automation"""
    
    class TriggerHandler(http.server.SimpleHTTPRequestHandler):
        def do_OPTIONS(self):
            """Handle CORS preflight requests"""
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.end_headers()
        
        def do_POST(self):
            """Handle POST requests with OAuth URLs"""
            if self.path == '/trigger-oauth':
                try:
                    # Read POST data
                    content_length = int(self.headers['Content-Length'])
                    post_data = self.rfile.read(content_length)
                    data = json.loads(post_data.decode('utf-8'))
                    
                    oauth_url = data.get('oauth_url')
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    
                    # Start OAuth automation in background thread with URL
                    def run_automation_with_url():
                        try:
                            logger.info(f"🚀 Starting OAuth automation with URL: {oauth_url}")
                            result = automator.monitor_oauth_process(oauth_url)
                            logger.info(f"OAuth automation result: {result}")
                        except Exception as e:
                            logger.error(f"Automation error: {e}")
                    
                    threading.Thread(target=run_automation_with_url, daemon=True).start()
                    
                    response = {
                        "status": "OAuth automation triggered with URL", 
                        "target_email": TARGET_EMAIL,
                        "oauth_url": oauth_url
                    }
                    self.wfile.write(json.dumps(response).encode())
                    
                except Exception as e:
                    logger.error(f"❌ Error handling POST request: {e}")
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    
                    response = {"error": str(e)}
                    self.wfile.write(json.dumps(response).encode())
            else:
                self.send_response(404)
                self.end_headers()
        
        def do_GET(self):
            if self.path == '/trigger-oauth':
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                
                # Start OAuth automation in background thread
                def run_automation():
                    try:
                        result = automator.monitor_oauth_process()
                        logger.info(f"OAuth automation result: {result}")
                    except Exception as e:
                        logger.error(f"Automation error: {e}")
                
                threading.Thread(target=run_automation, daemon=True).start()
                
                response = {"status": "OAuth automation triggered", "target_email": TARGET_EMAIL}
                self.wfile.write(json.dumps(response).encode())
                
            elif self.path == '/status':
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                
                response = {"status": "OAuth automator ready", "target_email": TARGET_EMAIL}
                self.wfile.write(json.dumps(response).encode())
            else:
                self.send_response(404)
                self.end_headers()
    
    try:
        with socketserver.TCPServer(("", port), TriggerHandler) as httpd:
            logger.info(f"🌐 OAuth trigger server running on http://localhost:{port}")
            logger.info(f"💡 Trigger OAuth: http://localhost:{port}/trigger-oauth")
            logger.info(f"📊 Check status: http://localhost:{port}/status")
            httpd.serve_forever()
    except Exception as e:
        logger.error(f"❌ Failed to start trigger server: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gmail OAuth Automation")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    parser.add_argument("--port", type=int, default=8080, help="App port for OAuth redirect")
    parser.add_argument("--trigger-port", type=int, default=9999, help="Port for trigger server")
    parser.add_argument("--url", type=str, help="Initial URL to navigate to")
    parser.add_argument("--server", action="store_true", help="Run as trigger server")
    parser.add_argument("--password", type=str, help="Password for automatic login (use with caution)")
    parser.add_argument("--debug", action="store_true", help="Debug mode - keeps browser open longer and shows detailed logs")
    parser.add_argument("--base-url", type=str, help="Base URL for the app (e.g., https://your-app.vercel.app)")
    parser.add_argument("--keep-open", type=int, default=0, help="Keep browser open for specified seconds after completion (useful for debugging)")
    parser.add_argument("--skip-webdriver-manager", action="store_true", help="Skip webdriver-manager and use faster startup methods")
    parser.add_argument("--workflow", action="store_true", help="Enable Gmail processing workflow after OAuth (continuous processing every 20 minutes)")
    
    args = parser.parse_args()
    
    # Set global password if provided
    if args.password:
        TARGET_PASSWORD = args.password
    
    automator = GmailOAuthAutomator(
        headless=args.headless, 
        port=args.port, 
        password=args.password,
        debug=args.debug,
        keep_open=args.keep_open,
        skip_webdriver_manager=args.skip_webdriver_manager,
        base_url=getattr(args, 'base_url', None)  # Use getattr to handle hyphenated argument
    )
    
    if args.server:
        # Run as trigger server
        create_trigger_server(automator, args.trigger_port)
    else:
        # Run OAuth automation directly
        success = automator.monitor_oauth_process(args.url, keep_browser_for_workflow=args.workflow)
        
        # If OAuth was successful and workflow mode is enabled, start the Gmail processing workflow
        if success and args.workflow:
            logger.info("🔄 Starting Gmail processing workflow...")
            try:
                automator.gmail_processing_workflow()
            except KeyboardInterrupt:
                logger.info("🛑 Gmail processing workflow stopped by user")
            except Exception as e:
                logger.error(f"❌ Gmail processing workflow error: {e}")
            finally:
                # Close browser after workflow ends
                if automator.driver:
                    try:
                        automator.driver.quit()
                        logger.info("🔚 WebDriver closed after workflow")
                    except Exception as e:
                        logger.warning(f"⚠️ Error closing WebDriver after workflow: {e}")
        
        sys.exit(0 if success else 1) 