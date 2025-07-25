#!/usr/bin/env python3
"""
Test script to verify environment variables are loaded correctly
"""

import os
from dotenv import load_dotenv

# Try to load environment variables
print("🔍 Testing environment variable loading...")

if os.path.exists('env.local'):
    load_dotenv('env.local')
    print("✅ Loaded env.local file")
elif os.path.exists('.env'):
    load_dotenv('.env')
    print("✅ Loaded .env file")
else:
    print("⚠️ No environment file found")

# Check key variables
variables_to_check = [
    'GOOGLE_CLIENT_ID',
    'GOOGLE_CLIENT_SECRET', 
    'GOOGLE_REDIRECT_URI',
    'SUPABASE_URL',
    'SUPABASE_ANON_KEY'
]

print("\n📋 Environment Variables:")
for var in variables_to_check:
    value = os.getenv(var, 'NOT SET')
    if value == 'NOT SET':
        print(f"❌ {var}: {value}")
    else:
        # Show only first and last few characters for security
        if len(value) > 20:
            masked_value = value[:10] + "..." + value[-10:]
        else:
            masked_value = value[:5] + "..." if len(value) > 5 else value
        print(f"✅ {var}: {masked_value}")

print("\n🔧 Testing Supabase import...")
try:
    from supabase import create_client
    print("✅ Supabase import successful")
    
    # Test Supabase initialization
    supabase_url = os.getenv('SUPABASE_URL', '')
    supabase_key = os.getenv('SUPABASE_ANON_KEY', '')
    
    if supabase_url and supabase_key:
        try:
            supabase = create_client(supabase_url, supabase_key)
            print("✅ Supabase client created successfully")
        except Exception as e:
            print(f"❌ Supabase client creation failed: {e}")
    else:
        print("❌ Supabase URL or KEY not set")
        
except ImportError:
    print("❌ Supabase not installed. Install with: pip install supabase")

print("\n✅ Environment test completed") 