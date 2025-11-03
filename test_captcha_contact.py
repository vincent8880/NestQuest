#!/usr/bin/env python3

import asyncio
from playwright.async_api import async_playwright
import re
from bs4 import BeautifulSoup

async def test_captcha_contact_extraction():
    """Test CAPTCHA handling for contact information extraction"""
    
    test_url = "https://www.property24.co.ke/3-bedroom-apartment-flat-to-rent-in-kileleshwa-116153975"
    
    async with async_playwright() as p:
        # Run in visible mode so we can see CAPTCHAs
        browser = await p.chromium.launch(headless=False, slow_mo=1000)
        page = await browser.new_page()
        
        print(f"🔍 Testing CAPTCHA handling for contact extraction")
        print(f"🌐 URL: {test_url}")
        print("=" * 80)
        
        try:
            # Navigate to the page
            await page.goto(test_url, wait_until='domcontentloaded')
            await page.wait_for_timeout(3000)
            
            print("📋 Looking for contact reveal buttons...")
            
            # Find contact reveal buttons
            contact_buttons = await page.query_selector_all('text="Show Contact Number"')
            
            if contact_buttons:
                print(f"✅ Found {len(contact_buttons)} contact reveal buttons")
                
                for i, button in enumerate(contact_buttons):
                    print(f"\n🖱️  Attempting to click button {i+1}...")
                    
                    try:
                        # Click the button
                        await button.click()
                        print("   ⏳ Waiting for response...")
                        await page.wait_for_timeout(2000)
                        
                        # Check for different types of CAPTCHAs or challenges
                        await detect_captcha_types(page)
                        
                        # Check if contact info was revealed
                        contact_revealed = await check_contact_revealed(page)
                        if contact_revealed:
                            print("   🎉 Contact information revealed!")
                            break
                        else:
                            print("   ⚠️  No contact info revealed yet")
                            
                    except Exception as e:
                        print(f"   ❌ Error clicking button {i+1}: {e}")
            else:
                print("❌ No contact reveal buttons found")
            
            # Wait for manual interaction if needed
            print("\n⏳ Keeping browser open for manual CAPTCHA solving...")
            print("   💡 If you see a CAPTCHA, please solve it manually")
            print("   🔍 Watching for contact information changes...")
            
            # Monitor for contact info changes
            for attempt in range(30):  # 30 seconds of monitoring
                contact_info = await extract_contact_info(page)
                if contact_info['phones'] or contact_info['emails']:
                    print("🎉 CONTACT INFORMATION FOUND!")
                    print(f"   📞 Phones: {contact_info['phones']}")
                    print(f"   📧 Emails: {contact_info['emails']}")
                    break
                
                await page.wait_for_timeout(1000)  # Check every second
            
        except Exception as e:
            print(f"❌ Error during test: {e}")
        
        finally:
            print("\n🔍 Browser will stay open for 30 more seconds...")
            await page.wait_for_timeout(30000)
            await browser.close()

async def detect_captcha_types(page):
    """Detect what type of CAPTCHA or challenge is present"""
    
    print("🕵️  Detecting CAPTCHA types...")
    
    # Check for common CAPTCHA indicators
    captcha_indicators = [
        # reCAPTCHA
        {'selector': '[data-sitekey]', 'type': 'reCAPTCHA'},
        {'selector': '.g-recaptcha', 'type': 'reCAPTCHA'},
        {'selector': 'iframe[src*="recaptcha"]', 'type': 'reCAPTCHA'},
        
        # hCaptcha
        {'selector': '.h-captcha', 'type': 'hCaptcha'},
        {'selector': '[data-hcaptcha-site-key]', 'type': 'hCaptcha'},
        
        # Simple image CAPTCHA
        {'selector': 'img[src*="captcha"]', 'type': 'Image CAPTCHA'},
        {'selector': '.captcha-image', 'type': 'Image CAPTCHA'},
        
        # Text-based challenges
        {'selector': 'input[name*="captcha"]', 'type': 'Text CAPTCHA'},
        
        # Custom challenges
        {'selector': '.verification', 'type': 'Custom Verification'},
        {'selector': '.challenge', 'type': 'Custom Challenge'},
    ]
    
    found_captchas = []
    
    for indicator in captcha_indicators:
        try:
            elements = await page.query_selector_all(indicator['selector'])
            if elements:
                found_captchas.append(indicator['type'])
                print(f"   🔍 Found: {indicator['type']} (selector: {indicator['selector']})")
        except:
            pass
    
    if found_captchas:
        print(f"   ⚠️  CAPTCHA types detected: {', '.join(set(found_captchas))}")
        return found_captchas
    else:
        print("   ✅ No obvious CAPTCHAs detected")
        return []

async def check_contact_revealed(page):
    """Check if contact information was revealed after interaction"""
    
    try:
        # Get page content
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        page_text = soup.get_text()
        
        # Look for phone numbers
        phone_patterns = [
            r'(?:\+254|0)(?:7\d{8}|1\d{8})',
            r'(\+254\d{9})',
            r'(07\d{8})',
            r'(01\d{8})',
        ]
        
        for pattern in phone_patterns:
            if re.search(pattern, page_text):
                return True
        
        # Look for emails
        if re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', page_text):
            return True
        
        return False
        
    except Exception as e:
        print(f"   ⚠️  Error checking contact info: {e}")
        return False

async def extract_contact_info(page):
    """Extract any contact information visible on the page"""
    
    contact_info = {'phones': [], 'emails': []}
    
    try:
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        page_text = soup.get_text()
        
        # Extract phone numbers
        phone_patterns = [
            r'(?:\+254|0)(?:7\d{8}|1\d{8})',
            r'(\+254\d{9})',
            r'(07\d{8})',
            r'(01\d{8})',
        ]
        
        for pattern in phone_patterns:
            matches = re.findall(pattern, page_text)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0] if match[0] else match[1]
                clean_phone = re.sub(r'[^\d+]', '', match)
                if len(clean_phone) >= 10 and clean_phone not in contact_info['phones']:
                    contact_info['phones'].append(clean_phone)
        
        # Extract emails
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, page_text)
        filtered_emails = [email for email in emails if not any(word in email.lower() 
                         for word in ['noreply', 'admin', 'info@property24', 'system', 'support'])]
        
        contact_info['emails'] = list(set(filtered_emails))
        
    except Exception as e:
        print(f"Error extracting contact info: {e}")
    
    return contact_info

# Enhanced version with CAPTCHA automation options
async def automated_captcha_solver(page, captcha_type):
    """Automated CAPTCHA solving strategies"""
    
    print(f"🤖 Attempting to solve {captcha_type}...")
    
    if captcha_type == 'reCAPTCHA':
        print("   🔧 reCAPTCHA detected - this requires human interaction or paid service")
        print("   💡 Options:")
        print("      1. Manual solving (current approach)")
        print("      2. 2captcha service integration")
        print("      3. Anti-captcha service integration")
        return False
    
    elif captcha_type == 'Image CAPTCHA':
        print("   🖼️  Image CAPTCHA detected - analyzing...")
        # Could implement OCR here
        return False
    
    elif captcha_type == 'Text CAPTCHA':
        print("   📝 Text CAPTCHA detected - could implement OCR")
        return False
    
    else:
        print("   ❓ Unknown CAPTCHA type")
        return False

if __name__ == "__main__":
    asyncio.run(test_captcha_contact_extraction()) 