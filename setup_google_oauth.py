#!/usr/bin/env python3
"""
Google OAuth Setup Helper
This script shows you exactly what to configure in Google Cloud Console
"""

import os

def show_oauth_setup():
    """Display OAuth configuration instructions"""
    
    # Get URLs from environment or use defaults
    render_url = "https://gmail-oauth-automation.onrender.com"
    local_port = "8080"
    
    print("=" * 80)
    print("📋 GOOGLE CLOUD CONSOLE OAUTH CONFIGURATION")
    print("=" * 80)
    print()
    print("🔗 Go to: https://console.cloud.google.com/apis/credentials")
    print()
    print("📝 In your OAuth 2.0 Client ID, add these Authorized Redirect URIs:")
    print()
    
    # Production URLs (Render)
    print("🌐 PRODUCTION (Render) URLs:")
    print(f"   {render_url}/oauth-callback.html")
    print(f"   {render_url}/oauth-callback")
    print()
    
    # Development URLs (Local)
    print("🏠 DEVELOPMENT (Local) URLs:")
    print(f"   http://localhost:{local_port}/oauth-callback.html")
    print(f"   http://127.0.0.1:{local_port}/oauth-callback.html")
    print()
    
    # Additional common variations
    print("🔄 OPTIONAL (Additional variations):")
    print(f"   {render_url}/")
    print(f"   {render_url}/auth/callback")
    print()
    
    print("=" * 80)
    print("🔑 IMPORTANT NOTES:")
    print("=" * 80)
    print("1. Make sure to click 'SAVE' after adding the URIs")
    print("2. It may take a few minutes for changes to take effect")
    print("3. You can have multiple redirect URIs (production + development)")
    print("4. URLs are case-sensitive and must match exactly")
    print("5. HTTPS is required for production, HTTP allowed for localhost only")
    print()
    
    print("🚀 NEXT STEPS:")
    print("1. Add the URIs above to Google Cloud Console")
    print("2. Copy your Client ID and Client Secret")
    print("3. Set them as environment variables in Render:")
    print("   - GOOGLE_CLIENT_ID")
    print("   - GOOGLE_CLIENT_SECRET")
    print()
    
    print("📖 For detailed setup instructions:")
    print("https://developers.google.com/identity/protocols/oauth2/web-server")
    print()

def check_current_config():
    """Check current OAuth configuration"""
    print("=" * 80)
    print("🔍 CURRENT CONFIGURATION CHECK")
    print("=" * 80)
    
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
    redirect_uri = os.getenv('GOOGLE_REDIRECT_URI')
    
    print(f"📧 Client ID: {'✅ Set' if client_id else '❌ Not set'}")
    if client_id:
        print(f"    {client_id[:20]}...{client_id[-10:] if len(client_id) > 30 else client_id}")
    
    print(f"🔐 Client Secret: {'✅ Set' if client_secret else '❌ Not set'}")
    if client_secret:
        print(f"    {client_secret[:10]}...{client_secret[-5:] if len(client_secret) > 15 else 'Hidden'}")
    
    print(f"🔗 Redirect URI: {'✅ Set' if redirect_uri else '❌ Not set'}")
    if redirect_uri:
        print(f"    {redirect_uri}")
    
    print()
    
    if not all([client_id, client_secret, redirect_uri]):
        print("⚠️  Missing OAuth configuration! Please set the environment variables.")
    else:
        print("✅ OAuth configuration appears complete!")
    
    print()

def generate_test_url():
    """Generate a test OAuth URL"""
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    redirect_uri = os.getenv('GOOGLE_REDIRECT_URI', 'https://gmail-oauth-automation.onrender.com/oauth-callback.html')
    
    if not client_id:
        print("❌ Cannot generate test URL: GOOGLE_CLIENT_ID not set")
        return
    
    scopes = [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.modify',
        'https://www.googleapis.com/auth/userinfo.profile',
        'https://www.googleapis.com/auth/userinfo.email'
    ]
    
    scope_string = ' '.join(scopes)
    
    oauth_url = (
        f"https://accounts.google.com/o/oauth2/auth?"
        f"client_id={client_id}&"
        f"redirect_uri={redirect_uri}&"
        f"scope={scope_string}&"
        f"response_type=code&"
        f"access_type=offline&"
        f"prompt=consent"
    )
    
    print("=" * 80)
    print("🧪 TEST OAUTH URL")
    print("=" * 80)
    print("You can test your OAuth configuration by visiting this URL:")
    print()
    print(oauth_url)
    print()
    print("This should redirect you to Google's consent screen.")
    print()

if __name__ == "__main__":
    show_oauth_setup()
    check_current_config()
    generate_test_url()
    
    input("Press Enter to continue...") 