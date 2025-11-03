#!/usr/bin/env python3

import asyncio
import requests
import re
from playwright.async_api import async_playwright

class Property24CaptchaTest:
    """Test 2captcha setup with Property24's reCAPTCHA v2"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.test_url = "https://www.property24.co.ke/3-bedroom-apartment-flat-to-rent-in-kileleshwa-116153975"
    
    async def test_captcha_setup(self):
        """Test the complete CAPTCHA solving flow"""
        
        print("🧪 TESTING 2CAPTCHA SETUP WITH PROPERTY24")
        print("=" * 50)
        
        if not self.api_key or self.api_key == "YOUR_API_KEY_HERE":
            print("❌ Please set your 2captcha API key first!")
            print("")
            print("📝 HOW TO GET YOUR API KEY:")
            print("   1. Go to https://2captcha.com")
            print("   2. Click 'Sign Up' and create account")
            print("   3. Verify your email address")
            print("   4. Add $5 minimum to your account balance")
            print("   5. Go to 'API' section in dashboard")
            print("   6. Copy your API key")
            print("   7. Replace 'YOUR_API_KEY_HERE' in this script")
            print("")
            print("🔧 SETUP EXAMPLE:")
            print("   API_KEY = 'abc123def456...'  # Your actual API key")
            print("")
            return
        
        # Test API key validity
        print("🔑 Testing API key validity...")
        balance = await self.check_balance()
        if balance is None:
            return
        
        print(f"✅ API key valid! Balance: ${balance}")
        
        if float(balance) < 0.5:
            print("⚠️ Low balance! Add funds to continue testing.")
            print("   Go to https://2captcha.com and add funds to your account")
            return
        
        # Test Property24 CAPTCHA detection
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)  # Set to True for headless
            page = await browser.new_page()
            
            try:
                print("🌐 Loading Property24 page...")
                await page.goto(self.test_url, wait_until='domcontentloaded')
                await page.wait_for_timeout(3000)
                
                # Find contact button
                contact_button = await page.query_selector('.ShowContact')
                if not contact_button:
                    print("❌ No contact button found on this property")
                    print("   Trying alternative selectors...")
                    
                    # Try alternative selectors
                    alt_selectors = ['.ShowPhone', '.contact-button', 'text="Show Contact"']
                    for selector in alt_selectors:
                        contact_button = await page.query_selector(selector)
                        if contact_button:
                            print(f"✅ Found contact button with selector: {selector}")
                            break
                    
                    if not contact_button:
                        print("❌ No contact button found with any selector")
                        return
                
                print("✅ Found contact button")
                
                # Click contact button
                print("🖱️ Clicking contact button...")
                await contact_button.click()
                await page.wait_for_timeout(3000)
                
                # Check for reCAPTCHA
                site_key = await self.detect_recaptcha(page)
                if not site_key:
                    print("❌ No reCAPTCHA detected - this property might not be protected")
                    print("   Property24 doesn't protect all properties with CAPTCHA")
                    return
                
                print(f"✅ reCAPTCHA v2 detected! Site key: {site_key[:20]}...")
                
                # Test CAPTCHA solving (costs ~$0.002)
                print("🤖 Testing CAPTCHA solving (this will cost ~$0.002)...")
                result = await self.test_solve_captcha(page.url, site_key)
                
                if result:
                    print("🎉 SUCCESS! 2captcha setup is working correctly")
                    print("💡 You can now use CAPTCHA solving in your scraper")
                    print("💰 Each CAPTCHA solve costs ~$0.002 (very affordable)")
                else:
                    print("❌ CAPTCHA solving failed - check configuration")
                
            except Exception as e:
                print(f"❌ Error during test: {e}")
            finally:
                await browser.close()
    
    async def check_balance(self):
        """Check 2captcha account balance"""
        try:
            url = "http://2captcha.com/res.php"
            params = {
                'key': self.api_key,
                'action': 'getbalance'
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.text.startswith('ERROR'):
                print(f"❌ API Error: {response.text}")
                if "ERROR_WRONG_USER_KEY" in response.text:
                    print("   This means your API key is invalid")
                    print("   Please check your API key from 2captcha dashboard")
                return None
            
            return response.text
            
        except Exception as e:
            print(f"❌ Error checking balance: {e}")
            return None
    
    async def detect_recaptcha(self, page):
        """Detect reCAPTCHA and extract site key"""
        try:
            # Look for reCAPTCHA elements
            recaptcha_element = await page.query_selector('[data-sitekey]')
            if recaptcha_element:
                site_key = await recaptcha_element.get_attribute('data-sitekey')
                return site_key
            
            # Alternative: extract from page source
            content = await page.content()
            site_key_match = re.search(r'data-sitekey="([^"]+)"', content)
            if site_key_match:
                return site_key_match.group(1)
            
            return None
            
        except Exception as e:
            print(f"Error detecting reCAPTCHA: {e}")
            return None
    
    async def test_solve_captcha(self, page_url, site_key):
        """Test solving a single CAPTCHA"""
        try:
            # Submit CAPTCHA to 2captcha
            print("   📤 Submitting CAPTCHA to 2captcha...")
            submit_url = "http://2captcha.com/in.php"
            
            data = {
                'key': self.api_key,
                'method': 'userrecaptcha',  # This is for reCAPTCHA v2
                'googlekey': site_key,
                'pageurl': page_url,
            }
            
            response = requests.post(submit_url, data=data, timeout=30)
            
            if not response.text.startswith('OK|'):
                print(f"   ❌ Submit failed: {response.text}")
                return False
            
            captcha_id = response.text.split('|')[1]
            print(f"   ✅ CAPTCHA submitted (ID: {captcha_id})")
            
            # Wait for solution
            print("   ⏳ Waiting for solution (max 2 minutes)...")
            result_url = "http://2captcha.com/res.php"
            
            for attempt in range(24):  # 24 * 5 seconds = 2 minutes
                await asyncio.sleep(5)
                
                params = {
                    'key': self.api_key,
                    'action': 'get',
                    'id': captcha_id
                }
                
                response = requests.get(result_url, params=params, timeout=10)
                
                if response.text.startswith('OK|'):
                    solution = response.text.split('|')[1]
                    print(f"   ✅ CAPTCHA solved! Solution received")
                    print(f"   💰 Cost: ~$0.002")
                    return True
                elif response.text == 'CAPCHA_NOT_READY':
                    print(f"   ⏳ Attempt {attempt + 1}/24...")
                    continue
                else:
                    print(f"   ❌ Error: {response.text}")
                    return False
            
            print("   ⏰ Timeout waiting for solution")
            return False
            
        except Exception as e:
            print(f"   ❌ Error solving CAPTCHA: {e}")
            return False

async def main():
    # 🔧 REPLACE WITH YOUR ACTUAL 2CAPTCHA API KEY
    # Get your API key from: https://2captcha.com (after registration)
    API_KEY = "79d9722448416056a13129c67d5c2b55"  # ← User's actual API key
    
    tester = Property24CaptchaTest(API_KEY)
    await tester.test_captcha_setup()

if __name__ == "__main__":
    asyncio.run(main()) 