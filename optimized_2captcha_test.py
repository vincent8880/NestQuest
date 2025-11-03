#!/usr/bin/env python3

import asyncio
import requests
import re
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

class Optimized2CaptchaTest:
    """Optimized 2captcha test with faster solving and better error handling"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.test_url = "https://www.property24.co.ke/3-bedroom-apartment-flat-to-rent-in-kileleshwa-116153975"
    
    async def test_optimized_captcha_flow(self):
        """Test optimized CAPTCHA solving flow"""
        
        print("🚀 OPTIMIZED 2CAPTCHA TEST")
        print("=" * 50)
        
        if not self.api_key or self.api_key == "YOUR_API_KEY_HERE":
            print("❌ Please set your 2captcha API key first!")
            return
        
        # Test API key validity
        print("🔑 Testing API key validity...")
        balance = await self.check_balance()
        if balance is None:
            return
        
        print(f"✅ API key valid! Balance: ${balance}")
        
        if float(balance) < 0.5:
            print("⚠️ Low balance! Add funds to continue testing.")
            return
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            
            try:
                print("🌐 Loading Property24 page...")
                await page.goto(self.test_url, wait_until='domcontentloaded')
                await page.wait_for_timeout(3000)
                
                # Find contact button
                contact_button = await page.query_selector('.ShowContact')
                if not contact_button:
                    print("❌ No contact button found")
                    return
                
                print("✅ Found contact button")
                
                # Click contact button
                print("🖱️ Clicking contact button...")
                await contact_button.click()
                await page.wait_for_timeout(3000)
                
                # Check for reCAPTCHA
                site_key = await self.detect_recaptcha(page)
                if not site_key:
                    print("❌ No reCAPTCHA detected")
                    return
                
                print(f"✅ reCAPTCHA v2 detected! Site key: {site_key[:20]}...")
                
                # Test optimized CAPTCHA solving
                print("🤖 Testing optimized CAPTCHA solving...")
                result = await self.solve_captcha_optimized(page.url, site_key)
                
                if result:
                    print("🎉 SUCCESS! Optimized 2captcha solving works!")
                    print("💡 Ready to extract contact information!")
                    
                    # Try to extract contacts
                    contacts = await self.extract_contacts_after_captcha(page)
                    if contacts['phones'] or contacts['emails']:
                        print("📞 CONTACT INFORMATION EXTRACTED!")
                        print(f"   📱 Phones: {contacts['phones']}")
                        print(f"   📧 Emails: {contacts['emails']}")
                    else:
                        print("⚠️ No contact information found after CAPTCHA solving")
                else:
                    print("❌ CAPTCHA solving failed")
                
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
    
    async def solve_captcha_optimized(self, page_url, site_key):
        """Optimized CAPTCHA solving with faster polling and better error handling"""
        try:
            # Submit CAPTCHA to 2captcha with optimized parameters
            print("   📤 Submitting CAPTCHA to 2captcha...")
            submit_url = "http://2captcha.com/in.php"
            
            data = {
                'key': self.api_key,
                'method': 'userrecaptcha',
                'googlekey': site_key,
                'pageurl': page_url,
                'soft_id': 'Property24Scraper',  # Helps with solving speed
                'json': 1  # Get JSON response for better error handling
            }
            
            response = requests.post(submit_url, data=data, timeout=30)
            
            # Handle JSON response
            if response.status_code != 200:
                print(f"   ❌ Submit failed with status {response.status_code}")
                return False
            
            try:
                result = response.json()
                if result.get('status') == 1:
                    captcha_id = result.get('request')
                    print(f"   ✅ CAPTCHA submitted (ID: {captcha_id})")
                else:
                    print(f"   ❌ Submit failed: {result.get('error_text', 'Unknown error')}")
                    return False
            except:
                # Fallback to text response
                if not response.text.startswith('OK|'):
                    print(f"   ❌ Submit failed: {response.text}")
                    return False
                captcha_id = response.text.split('|')[1]
                print(f"   ✅ CAPTCHA submitted (ID: {captcha_id})")
            
            # Wait for solution with optimized polling
            print("   ⏳ Waiting for solution (optimized polling)...")
            result_url = "http://2captcha.com/res.php"
            
            for attempt in range(60):  # 60 * 2 seconds = 2 minutes max
                await asyncio.sleep(2)  # Faster polling (2 seconds instead of 4)
                
                params = {
                    'key': self.api_key,
                    'action': 'get',
                    'id': captcha_id,
                    'json': 1
                }
                
                response = requests.get(result_url, params=params, timeout=10)
                
                try:
                    result = response.json()
                    if result.get('status') == 1:
                        solution = result.get('request')
                        print(f"   ✅ CAPTCHA solved! Solution received")
                        print(f"   💰 Cost: ~$0.002")
                        return solution
                    elif result.get('request') == 'CAPCHA_NOT_READY':
                        if attempt % 10 == 0:  # Print progress every 10 attempts (20 seconds)
                            print(f"   ⏳ Still waiting... ({attempt + 1}/60)")
                        continue
                    else:
                        print(f"   ❌ Error: {result.get('error_text', 'Unknown error')}")
                        return False
                except:
                    # Fallback to text response
                    if response.text.startswith('OK|'):
                        solution = response.text.split('|')[1]
                        print(f"   ✅ CAPTCHA solved! Solution received")
                        print(f"   💰 Cost: ~$0.002")
                        return solution
                    elif response.text == 'CAPCHA_NOT_READY':
                        if attempt % 10 == 0:
                            print(f"   ⏳ Still waiting... ({attempt + 1}/60)")
                        continue
                    else:
                        print(f"   ❌ Error: {response.text}")
                        return False
            
            print("   ⏰ Timeout waiting for solution (2 minutes)")
            return False
            
        except Exception as e:
            print(f"   ❌ Error solving CAPTCHA: {e}")
            return False
    
    async def extract_contacts_after_captcha(self, page):
        """Extract contact information after CAPTCHA solving"""
        contacts = {'phones': [], 'emails': []}
        
        try:
            # Get page content
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            page_text = soup.get_text()
            
            # Extract phone numbers
            phone_patterns = [
                r'(\+254\d{9})',
                r'(07\d{8})',
                r'(01\d{8})',
                r'(\+254\s*\d{3}\s*\d{3}\s*\d{3})',
                r'(0\d{3}\s*\d{3}\s*\d{3})',
            ]
            
            for pattern in phone_patterns:
                matches = re.findall(pattern, page_text)
                for match in matches:
                    clean_phone = re.sub(r'[^\d+]', '', match)
                    if len(clean_phone) >= 10 and clean_phone not in contacts['phones']:
                        contacts['phones'].append(clean_phone)
            
            # Extract emails
            email_matches = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', page_text)
            for email in email_matches:
                if (email.lower() not in contacts['emails'] and 
                    not any(word in email.lower() for word in ['noreply', 'admin', 'info@property24'])):
                    contacts['emails'].append(email.lower())
            
        except Exception as e:
            print(f"Error extracting contacts: {e}")
        
        return contacts

async def main():
    # 🔧 REPLACE WITH YOUR ACTUAL 2CAPTCHA API KEY
    API_KEY = "79d9722448416056a13129c67d5c2b55"  # ← User's actual API key
    
    tester = Optimized2CaptchaTest(API_KEY)
    await tester.test_optimized_captcha_flow()

if __name__ == "__main__":
    asyncio.run(main()) 