#!/usr/bin/env python3

import asyncio
import requests
import re
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

class FocusedShowContactTest:
    """Focused test specifically for 'Show Contact Number' button"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.test_url = "https://www.property24.co.ke/3-bedroom-apartment-flat-to-rent-in-kileleshwa-116153975"
    
    async def test_show_contact_flow(self):
        """Test the complete 'Show Contact Number' flow"""
        
        print("🎯 FOCUSED TEST: 'Show Contact Number' Button")
        print("=" * 60)
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            
            try:
                print("🌐 Loading property page...")
                await page.goto(self.test_url, wait_until='domcontentloaded')
                await page.wait_for_timeout(3000)
                
                # Step 1: Find the exact "Show Contact Number" button
                print("\n🔍 STEP 1: Finding 'Show Contact Number' button...")
                contact_button = await page.query_selector('text="Show Contact Number"')
                
                if not contact_button:
                    # Try alternative selectors
                    print("   Trying alternative selectors...")
                    contact_button = await page.query_selector('.ShowContact')
                    
                    if contact_button:
                        button_text = await contact_button.inner_text()
                        print(f"   ✅ Found button with text: '{button_text}'")
                    else:
                        print("   ❌ No 'Show Contact Number' button found")
                        return False
                else:
                    print("   ✅ Found 'Show Contact Number' button")
                
                # Step 2: Examine button properties
                print("\n🔍 STEP 2: Examining button properties...")
                classes = await contact_button.get_attribute('class')
                href = await contact_button.get_attribute('href')
                onclick = await contact_button.get_attribute('onclick')
                
                print(f"   Button classes: {classes}")
                print(f"   Button href: {href}")
                print(f"   Button onclick: {onclick}")
                
                # Step 3: Click the button and monitor closely
                print("\n🖱️ STEP 3: Clicking 'Show Contact Number' button...")
                
                # Set up network monitoring
                responses = []
                
                async def handle_response(response):
                    if 'contact' in response.url.lower() or 'phone' in response.url.lower():
                        responses.append({
                            'url': response.url,
                            'status': response.status,
                            'headers': dict(response.headers)
                        })
                        print(f"   🌐 Network request: {response.url} -> {response.status}")
                
                page.on("response", handle_response)
                
                # Click the button
                await contact_button.click()
                print("   ✅ Button clicked")
                
                # Wait and monitor what happens
                print("\n⏳ STEP 4: Monitoring page changes...")
                await page.wait_for_timeout(3000)
                
                # Check for reCAPTCHA
                print("\n🤖 STEP 5: Checking for reCAPTCHA...")
                captcha_info = await self.analyze_captcha(page)
                
                if captcha_info['present']:
                    print(f"   ✅ reCAPTCHA detected: {captcha_info['site_key'][:20]}...")
                    
                    # Solve the CAPTCHA
                    print("\n🧩 STEP 6: Solving reCAPTCHA...")
                    solution = await self.solve_captcha_step_by_step(page.url, captcha_info['site_key'])
                    
                    if solution:
                        print("   ✅ CAPTCHA solved successfully")
                        
                        # Inject solution with detailed monitoring
                        print("\n💉 STEP 7: Injecting CAPTCHA solution...")
                        await self.inject_solution_with_monitoring(page, solution)
                        
                        # Wait for contact revelation
                        print("\n⏳ STEP 8: Waiting for contact information...")
                        await page.wait_for_timeout(5000)
                        
                        # Extract contact information
                        print("\n📞 STEP 9: Extracting revealed contact information...")
                        contacts = await self.extract_contact_info_detailed(page)
                        
                        if contacts['phones'] or contacts['emails']:
                            print("   🎉 SUCCESS! Contact information revealed:")
                            for phone in contacts['phones']:
                                print(f"      📞 {phone}")
                            for email in contacts['emails']:
                                print(f"      📧 {email}")
                            return True
                        else:
                            print("   ⚠️ No contact information found after CAPTCHA solving")
                            
                            # Debug: Show what's on the page now
                            print("\n🔍 DEBUG: Page content after CAPTCHA...")
                            await self.debug_page_content(page)
                            
                            return False
                    else:
                        print("   ❌ Failed to solve CAPTCHA")
                        return False
                else:
                    print("   ℹ️ No reCAPTCHA detected")
                    
                    # Check if contact info was revealed directly
                    print("\n📞 STEP 6: Checking for directly revealed contact...")
                    contacts = await self.extract_contact_info_detailed(page)
                    
                    if contacts['phones'] or contacts['emails']:
                        print("   🎉 SUCCESS! Contact information revealed directly:")
                        for phone in contacts['phones']:
                            print(f"      📞 {phone}")
                        for email in contacts['emails']:
                            print(f"      📧 {email}")
                        return True
                    else:
                        print("   ⚠️ No contact information revealed")
                        return False
                
                # Show network requests
                if responses:
                    print(f"\n🌐 Network requests made: {len(responses)}")
                    for resp in responses:
                        print(f"   {resp['url']} -> {resp['status']}")
                
            except Exception as e:
                print(f"❌ Error in test: {e}")
                return False
            finally:
                await browser.close()
    
    async def analyze_captcha(self, page):
        """Analyze reCAPTCHA presence and details"""
        captcha_info = {'present': False, 'site_key': None}
        
        try:
            # Look for reCAPTCHA elements
            recaptcha_element = await page.query_selector('[data-sitekey]')
            if recaptcha_element:
                is_visible = await recaptcha_element.is_visible()
                if is_visible:
                    site_key = await recaptcha_element.get_attribute('data-sitekey')
                    captcha_info = {'present': True, 'site_key': site_key}
            
            # Alternative: check page source
            if not captcha_info['present']:
                content = await page.content()
                site_key_match = re.search(r'data-sitekey="([^"]+)"', content)
                if site_key_match:
                    captcha_info = {'present': True, 'site_key': site_key_match.group(1)}
            
        except Exception as e:
            print(f"   ⚠️ Error analyzing CAPTCHA: {e}")
        
        return captcha_info
    
    async def solve_captcha_step_by_step(self, page_url, site_key):
        """Solve CAPTCHA with detailed step tracking"""
        try:
            # Submit to 2captcha
            print("   📤 Submitting to 2captcha...")
            submit_url = "http://2captcha.com/in.php"
            
            data = {
                'key': self.api_key,
                'method': 'userrecaptcha',
                'googlekey': site_key,
                'pageurl': page_url,
            }
            
            response = requests.post(submit_url, data=data, timeout=30)
            
            if not response.text.startswith('OK|'):
                print(f"   ❌ Submit failed: {response.text}")
                return None
            
            captcha_id = response.text.split('|')[1]
            print(f"   ✅ Submitted (ID: {captcha_id})")
            
            # Wait for solution
            print("   ⏳ Waiting for solution...")
            result_url = "http://2captcha.com/res.php"
            
            for attempt in range(30):
                await asyncio.sleep(4)
                
                params = {
                    'key': self.api_key,
                    'action': 'get',
                    'id': captcha_id
                }
                
                response = requests.get(result_url, params=params, timeout=10)
                
                if response.text.startswith('OK|'):
                    solution = response.text.split('|')[1]
                    print(f"   ✅ Solution received: {solution[:20]}...")
                    return solution
                elif response.text == 'CAPCHA_NOT_READY':
                    if attempt % 5 == 0:  # Print progress every 5 attempts
                        print(f"   ⏳ Still waiting... ({attempt + 1}/30)")
                    continue
                else:
                    print(f"   ❌ Error: {response.text}")
                    return None
            
            print("   ⏰ Timeout waiting for solution")
            return None
            
        except Exception as e:
            print(f"   ❌ Error solving CAPTCHA: {e}")
            return None
    
    async def inject_solution_with_monitoring(self, page, solution):
        """Inject CAPTCHA solution with detailed monitoring"""
        try:
            # Method 1: Direct textarea injection
            print("   🎯 Method 1: Setting textarea value...")
            
            js_code = f"""
            (() => {{
                const textarea = document.querySelector('textarea[name="g-recaptcha-response"]');
                if (textarea) {{
                    textarea.value = '{solution}';
                    textarea.style.display = 'block';
                    console.log('✅ Textarea value set:', textarea.value.substring(0, 20));
                    return 'textarea_set';
                }}
                return 'textarea_not_found';
            }})()
            """
            
            result1 = await page.evaluate(js_code)
            print(f"   Result: {result1}")
            
            # Method 2: Trigger callback
            print("   🎯 Method 2: Triggering reCAPTCHA callback...")
            
            js_code2 = f"""
            (() => {{
                if (typeof window.grecaptcha !== 'undefined') {{
                    const widgets = document.querySelectorAll('.g-recaptcha');
                    if (widgets.length > 0) {{
                        const callback = widgets[0].getAttribute('data-callback');
                        if (callback && typeof window[callback] === 'function') {{
                            window[callback]('{solution}');
                            console.log('✅ Callback triggered:', callback);
                            return 'callback_triggered';
                        }}
                    }}
                }}
                return 'callback_not_found';
            }})()
            """
            
            result2 = await page.evaluate(js_code2)
            print(f"   Result: {result2}")
            
            # Method 3: Submit form
            print("   🎯 Method 3: Submitting form...")
            
            js_code3 = f"""
            (() => {{
                const forms = document.querySelectorAll('form');
                for (const form of forms) {{
                    const recaptchaField = form.querySelector('textarea[name="g-recaptcha-response"]');
                    if (recaptchaField) {{
                        recaptchaField.value = '{solution}';
                        
                        // Try to submit
                        const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
                        if (submitBtn) {{
                            submitBtn.click();
                            console.log('✅ Form submitted');
                            return 'form_submitted';
                        }}
                    }}
                }}
                return 'form_not_found';
            }})()
            """
            
            result3 = await page.evaluate(js_code3)
            print(f"   Result: {result3}")
            
        except Exception as e:
            print(f"   ❌ Error injecting solution: {e}")
    
    async def extract_contact_info_detailed(self, page):
        """Extract contact information with detailed analysis"""
        contacts = {'phones': [], 'emails': []}
        
        try:
            # Method 1: Check specific contact elements
            print("   🔍 Method 1: Checking specific contact elements...")
            
            contact_selectors = [
                '.agentPhone',
                '.contactPhone', 
                '.contact-info',
                '.phone-number',
                '[class*="phone"]',
                '[class*="contact"]'
            ]
            
            for selector in contact_selectors:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    text = await element.inner_text()
                    if text.strip():
                        print(f"      Found element {selector}: {text}")
            
            # Method 2: Full page text search
            print("   🔍 Method 2: Full page text search...")
            
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            page_text = soup.get_text()
            
            # Extract phones
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
            
            print(f"   Found {len(contacts['phones'])} phones, {len(contacts['emails'])} emails")
            
        except Exception as e:
            print(f"   ⚠️ Error extracting contacts: {e}")
        
        return contacts
    
    async def debug_page_content(self, page):
        """Debug what's currently on the page"""
        try:
            # Check for any elements that might contain contact info
            print("   🔍 Checking for contact-related elements...")
            
            all_elements = await page.query_selector_all('*')
            contact_keywords = ['phone', 'contact', 'agent', 'call', 'email']
            
            found_elements = []
            for element in all_elements[:50]:  # Limit to avoid spam
                try:
                    text = await element.inner_text()
                    classes = await element.get_attribute('class') or ''
                    
                    if any(keyword in text.lower() or keyword in classes.lower() for keyword in contact_keywords):
                        if text.strip():
                            found_elements.append(f"{classes}: {text[:50]}")
                except:
                    continue
            
            print(f"   Found {len(found_elements)} potentially relevant elements:")
            for elem in found_elements[:10]:  # Show first 10
                print(f"      {elem}")
                
        except Exception as e:
            print(f"   ⚠️ Error debugging page: {e}")

async def main():
    api_key = "79d9722448416056a13129c67d5c2b55"
    
    tester = FocusedShowContactTest(api_key)
    success = await tester.test_show_contact_flow()
    
    if success:
        print("\n🎉 SUCCESS! 'Show Contact Number' flow is working!")
        print("💰 Cost: ~$0.002 per property contact extraction")
        print("🚀 Ready to integrate into your scraper!")
    else:
        print("\n⚠️ 'Show Contact Number' flow needs refinement")
        print("🔧 Will need to investigate the specific revelation mechanism")

if __name__ == "__main__":
    asyncio.run(main()) 