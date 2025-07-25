#!/usr/bin/env python3
"""
Test script to verify button selectors for the 20-minute filter
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time

def test_button_selectors():
    """Test the button selectors against a mock HTML page"""
    
    # The specific HTML element you provided
    test_html = '''
    <!DOCTYPE html>
    <html>
    <head><title>Test Page</title></head>
    <body>
        <h1>Gmail Filter Test</h1>
        <button type="button" class="btn" title="Filter emails from the last 20 minutes" style="background-color: rgb(40, 167, 69); color: white; padding: 6px 12px; font-size: 12px; border: none; border-radius: 4px; cursor: pointer;">🕐 Last 20 min</button>
        <p>Other content here</p>
    </body>
    </html>
    '''
    
    # Our button selectors from the script
    selectors = [
        "//button[contains(text(), '🕐 Last 20 min')]",
        "//button[contains(@title, 'Filter emails from the last 20 minutes')]",
        "//button[@class='btn' and contains(text(), 'Last 20 min')]",
        "//button[@class='btn' and contains(text(), '20 min')]",
        "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'last 20 min')]",
        "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '20 min')]",
        "//button[contains(@title, '20 min')]",
        "//button[contains(@title, 'last 20')]"
    ]
    
    print("🧪 Testing button selectors against your specific HTML element...")
    print(f"📝 Target button text: '🕐 Last 20 min'")
    print(f"📝 Target button title: 'Filter emails from the last 20 minutes'")
    print(f"📝 Target button class: 'btn'")
    print("=" * 70)
    
    # Setup Chrome driver
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    try:
        driver = webdriver.Chrome(options=options)
        
        # Create a temporary HTML file with the test content
        with open('temp_test.html', 'w', encoding='utf-8') as f:
            f.write(test_html)
        
        # Load the test page
        driver.get(f"file://{abs_path}/temp_test.html")
        time.sleep(1)
        
        # Test each selector
        working_selectors = []
        for i, selector in enumerate(selectors):
            try:
                elements = driver.find_elements(By.XPATH, selector)
                if elements:
                    button = elements[0]
                    button_text = button.text.strip()
                    button_class = button.get_attribute('class')
                    button_title = button.get_attribute('title')
                    
                    print(f"✅ Selector {i+1}: WORKS")
                    print(f"   XPath: {selector}")
                    print(f"   Found text: '{button_text}'")
                    print(f"   Found class: '{button_class}'")
                    print(f"   Found title: '{button_title}'")
                    working_selectors.append(selector)
                else:
                    print(f"❌ Selector {i+1}: No elements found")
                    print(f"   XPath: {selector}")
            except Exception as e:
                print(f"❌ Selector {i+1}: Error - {e}")
                print(f"   XPath: {selector}")
            print()
        
        print("=" * 70)
        print(f"📊 Results: {len(working_selectors)}/{len(selectors)} selectors work")
        
        if working_selectors:
            print("✅ These selectors successfully found your button:")
            for i, selector in enumerate(working_selectors):
                print(f"   {i+1}. {selector}")
        else:
            print("❌ No selectors found your button!")
        
        driver.quit()
        
        # Clean up temp file
        import os
        if os.path.exists('temp_test.html'):
            os.remove('temp_test.html')
            
        return len(working_selectors) > 0
        
    except Exception as e:
        print(f"❌ Test error: {e}")
        return False

if __name__ == "__main__":
    import os
    abs_path = os.path.abspath('.')
    
    print("🧪 Button Selector Test")
    print("Testing if our XPath selectors can find your specific button element")
    print()
    
    success = test_button_selectors()
    
    if success:
        print("🎉 Test completed successfully! The selectors should work.")
    else:
        print("⚠️  Test failed. The selectors may need adjustment.") 