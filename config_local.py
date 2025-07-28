"""
Local Configuration for Gmail OAuth Automation
This file contains settings for running the automation locally instead of on Render.
"""

import os
import socket

def get_local_ip():
    """Get the local IP address of this machine"""
    try:
        # Connect to a remote address to get local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except:
        return "localhost"

# Local configuration
LOCAL_IP = get_local_ip()
LOCAL_PORT = 8080
LOCAL_BASE_URL = f"http://{LOCAL_IP}:{LOCAL_PORT}"

# OAuth Configuration for Local Development
LOCAL_OAUTH_CONFIG = {
    "redirect_uri": f"{LOCAL_BASE_URL}/oauth-callback.html",
    "base_url": LOCAL_BASE_URL,
    "port": LOCAL_PORT,
    "environment": "local",
    "headless": False  # Show browser for easier debugging
}

def setup_local_environment():
    """Set up environment variables for local development"""
    env_vars = {
        "ENVIRONMENT": "local",
        "BROWSER_HEADLESS": "false",
        "PORT": str(LOCAL_PORT),
        "APP_BASE_URL": LOCAL_BASE_URL,
        "GOOGLE_REDIRECT_URI": LOCAL_OAUTH_CONFIG["redirect_uri"]
    }
    
    for key, value in env_vars.items():
        os.environ[key] = value
    
    print(f"✅ Local environment configured:")
    print(f"   📍 Base URL: {LOCAL_BASE_URL}")
    print(f"   🔗 OAuth Redirect: {LOCAL_OAUTH_CONFIG['redirect_uri']}")
    print(f"   🌐 Local IP: {LOCAL_IP}")
    print(f"   🔌 Port: {LOCAL_PORT}")
    
    return LOCAL_OAUTH_CONFIG

def get_google_oauth_url():
    """Generate the Google OAuth URL for local development"""
    # You'll need to update your Google Cloud Console settings to include this redirect URI
    redirect_uri = LOCAL_OAUTH_CONFIG["redirect_uri"]
    
    print("\n" + "="*60)
    print("📋 GOOGLE CLOUD CONSOLE CONFIGURATION REQUIRED")
    print("="*60)
    print("To use local mode, you need to update your Google Cloud Console:")
    print("")
    print("1. Go to: https://console.cloud.google.com/apis/credentials")
    print("2. Select your OAuth 2.0 Client ID")
    print("3. Add this to 'Authorized redirect URIs':")
    print(f"   {redirect_uri}")
    print("4. Also add these for testing:")
    print(f"   http://localhost:{LOCAL_PORT}/oauth-callback.html")
    print(f"   http://127.0.0.1:{LOCAL_PORT}/oauth-callback.html")
    print("")
    print("💡 You can have both local and production redirect URIs configured")
    print("="*60)
    
    return redirect_uri

if __name__ == "__main__":
    config = setup_local_environment()
    get_google_oauth_url()
    
    print(f"\n🚀 Ready to run locally!")
    print(f"Run: python web_service.py")
    print(f"Then open: {LOCAL_BASE_URL}") 