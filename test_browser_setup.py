#!/usr/bin/env python3
"""
Test script to verify browser setup works correctly in production
"""

import os
import sys
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_browser_setup():
    """Test browser setup with current configuration"""
    logger.info("🧪 Testing browser setup...")
    logger.info(f"🖥️ Display environment: {os.getenv('DISPLAY', 'Not set')}")
    
    chrome_options = Options()
    
    # Production environment detection
    is_production = os.getenv('ENVIRONMENT', '').lower() == 'production'
    is_docker = os.path.exists('/.dockerenv')
    headless_mode = os.getenv('BROWSER_HEADLESS', 'false').lower() in ['true', '1', 'yes']
    
    logger.info(f"🏭 Production environment: {is_production}")
    logger.info(f"🐳 Docker environment: {is_docker}")
    logger.info(f"👻 Headless mode: {headless_mode}")
    
    if headless_mode:
        chrome_options.add_argument("--headless")
        logger.info("👻 Running in headless mode")
    else:
        logger.info("🖼️ Running with visible browser")
    
    # Enhanced Docker/Production configuration
    if is_production or is_docker:
        logger.info("🐳 Applying Docker/Production-specific Chrome options...")
        
        # Virtual display configuration
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--remote-debugging-port=9222")
        chrome_options.add_argument("--disable-software-rasterizer")
        
        # For non-headless mode in Docker, ensure proper display
        if not headless_mode:
            display = os.getenv('DISPLAY', ':99')
            chrome_options.add_argument(f"--display={display}")
            logger.info(f"🖥️ Setting Chrome display to: {display}")
    else:
        # Standard options for local development
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Basic configuration
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--window-size=1200,800")
    
    # Additional production stability options
    if is_production or is_docker:
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        chrome_options.add_argument("--disable-renderer-backgrounding")
    
    # Try to initialize browser
    driver = None
    try:
        logger.info("🚀 Initializing Chrome WebDriver...")
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)
        
        # Test basic functionality
        initial_url = driver.current_url or "about:blank"
        logger.info(f"✅ Browser initialized successfully!")
        logger.info(f"🌐 Initial URL: {initial_url}")
        
        # Test navigation
        logger.info("🔍 Testing navigation to Google...")
        driver.get("https://www.google.com")
        
        # Wait for page to load
        import time
        time.sleep(3)
        
        current_url = driver.current_url
        page_title = driver.title
        logger.info(f"🌐 Current URL: {current_url}")
        logger.info(f"📄 Page title: {page_title}")
        
        # Test screenshot capability
        logger.info("📸 Testing screenshot capability...")
        try:
            screenshot_png = driver.get_screenshot_as_png()
            logger.info(f"✅ Screenshot captured successfully - Size: {len(screenshot_png)} bytes")
        except Exception as screenshot_error:
            logger.error(f"❌ Screenshot failed: {screenshot_error}")
        
        logger.info("✅ Browser test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Browser test failed: {e}")
        return False
        
    finally:
        if driver:
            try:
                driver.quit()
                logger.info("🛑 Browser closed")
            except:
                pass

if __name__ == "__main__":
    success = test_browser_setup()
    sys.exit(0 if success else 1) 