#!/usr/bin/env python3

import asyncio
import re
import requests
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# 2captcha API key
CAPTCHA_API_KEY = "79d9722448416056a13129c67d5c2b55"

async def test_contact_extraction():
    """Test contact extraction on a working property"""
    
    # Test specific property URLs directly
    test_urls = [
        "https://www.property24.co.ke/6-bedroom-house-to-rent-in-kileleshwa-108944549",
        "https://www.property24.co.ke/3-bedroom-apartment-flat-to-rent-in-kileleshwa-116153975",
    ]
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=1000)
        context = await browser.new_context(viewport={"width": 1366, "height": 900})
        page = await context.new_page()
        
        try:
            print("🚀 Testing Contact Extraction")
            print("=" * 50)
            
            for property_url in test_urls:
                print(f"📍 Testing property: {property_url}")
                # Navigate to property detail page
                await page.goto(property_url, wait_until="domcontentloaded")
                await page.wait_for_load_state("networkidle")
                
                # Dismiss overlays
                await dismiss_overlays(page)
                
                # Extract contact information
                contact_info = await extract_contact_info(page)
                
                print(f"\n=== CONTACT EXTRACTION RESULTS ===")
                print(f"📞 Phones: {contact_info.get('phones', [])}")
                print(f"📧 Emails: {contact_info.get('emails', [])}")
                print(f"👤 Agent: {contact_info.get('agent_name', 'Not found')}")
                print(f"🏢 Company: {contact_info.get('company', 'Not found')}")
                print(f"✅ Success: {contact_info.get('success', False)}")
                print("")
        
        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            await browser.close()

async def dismiss_overlays(page):
    """Dismiss common overlays"""
    try:
        # Cookie banner
        cookie_btn = page.locator('button:has-text("Accept"), button:has-text("OK"), [data-testid="cookie-accept"]').first
        if await cookie_btn.count() > 0:
            await cookie_btn.click()
            await page.wait_for_timeout(1000)
    except:
        pass

    try:
        # Sign in popup
        signin_close = page.locator('button:has-text("×"), [aria-label="Close"], .close').first
        if await signin_close.count() > 0:
            await signin_close.click()
            await page.wait_for_timeout(1000)
    except:
        pass

async def extract_contact_info(page):
    """Extract contact information using multiple strategies"""
    contact_info = {
        'phones': [],
        'emails': [],
        'agent_name': None,
        'company': None,
        'success': False
    }
    
    try:
        # Strategy 1: Look for contact button and click it
        print("🔍 Strategy 1: Looking for contact button...")
        contact_button = await find_contact_button(page)
        
        if contact_button:
            print("✅ Found contact button, clicking...")
            await contact_button.click()
            await page.wait_for_timeout(3000)
            
            # Wait for any modal or popup to appear
            try:
                await page.wait_for_selector('.modal, .popup, .overlay, [class*="modal"]', timeout=5000)
                print("🔍 Modal/popup detected, waiting for content...")
                await page.wait_for_timeout(2000)
            except:
                print("ℹ️ No modal detected, continuing...")
            
            # Check if contact info was revealed
            revealed = await check_contact_revealed(page)
            if revealed:
                print("✅ Contact info revealed after clicking button")
                contact_info['success'] = True
            else:
                print("⚠️ Contact button clicked but no info revealed (may need CAPTCHA solving)")
                
                # Try to solve CAPTCHA if present
                site_key = await detect_recaptcha(page)
                if site_key:
                    print(f"🔍 reCAPTCHA detected! Site key: {site_key[:20]}...")
                    solution = await solve_captcha_with_2captcha(page.url, site_key)
                    if solution:
                        print("✅ CAPTCHA solved! Injecting solution...")
                        await inject_captcha_solution(page, solution)
                        await page.wait_for_timeout(2000)
                        
                        # Check again for contact info
                        revealed = await check_contact_revealed(page)
                        if revealed:
                            print("✅ Contact info revealed after CAPTCHA solving!")
                            contact_info['success'] = True
                        else:
                            print("⚠️ CAPTCHA solved but contact info still not revealed")
                            print("   Trying to trigger contact display...")
                            
                            # Try clicking the contact button again after CAPTCHA
                            try:
                                contact_button = await page.query_selector('.ShowContact')
                                if contact_button:
                                    await contact_button.click()
                                    await page.wait_for_timeout(2000)
                                    
                                    # Check one more time
                                    revealed = await check_contact_revealed(page)
                                    if revealed:
                                        print("✅ Contact info revealed after second click!")
                                        contact_info['success'] = True
                            except Exception as e:
                                print(f"   Error with second click: {e}")
                    else:
                        print("❌ Failed to solve CAPTCHA")
                else:
                    print("ℹ️ No reCAPTCHA detected")
        
        # Strategy 2: Extract from page content
        print("🔍 Strategy 2: Extracting from page content...")
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        page_text = soup.get_text()
        
        # Extract phones
        phone_patterns = [
            r'(\+254\d{9})',  # +254XXXXXXXXX
            r'(07\d{8})',     # 07XXXXXXXX
            r'(01\d{8})',     # 01XXXXXXXX
            r'(\+254\s*\d{3}\s*\d{3}\s*\d{3})',  # +254 XXX XXX XXX
            r'(0\d{3}\s*\d{3}\s*\d{3})',         # 0XXX XXX XXX
        ]
        
        for pattern in phone_patterns:
            matches = re.findall(pattern, page_text)
            for match in matches:
                clean_phone = re.sub(r'[^\d+]', '', match)
                if len(clean_phone) >= 10 and clean_phone not in contact_info['phones']:
                    contact_info['phones'].append(clean_phone)
        
        # Extract emails
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, page_text)
        
        # Filter out system emails
        filtered_emails = [email for email in emails if not any(
            word in email.lower() for word in [
                'noreply', 'admin', 'info@property24', 'system', 'support', 'no-reply'
            ]
        )]
        
        contact_info['emails'] = list(set(filtered_emails))
        
        # Extract agent name
        agent_selectors = [
            '.agent-name', '.contact-name', '.agentName', 
            '[class*="agent"]', '[class*="contact"]'
        ]
        
        for selector in agent_selectors:
            element = soup.select_one(selector)
            if element and element.get_text().strip():
                contact_info['agent_name'] = element.get_text().strip()
                break
        
        # Extract company
        company_selectors = [
            '.company-name', '.agent-company', '.companyName',
            '[class*="company"]', '[class*="agency"]'
        ]
        
        for selector in company_selectors:
            element = soup.select_one(selector)
            if element and element.get_text().strip():
                contact_info['company'] = element.get_text().strip()
                break
        
        # Check if we found any contact info
        if contact_info['phones'] or contact_info['emails']:
            contact_info['success'] = True
            
    except Exception as e:
        print(f"❌ Error extracting contact info: {e}")
    
    return contact_info

async def find_contact_button(page):
    """Find contact button with multiple strategies"""
    selectors = [
        '.ShowContact',
        'text="Show Contact Number"',
        '.ShowPhone',
        '.contact-button',
        '[class*="contact"]',
        '[class*="phone"]',
        'button:has-text("Contact")',
        'button:has-text("Phone")',
        'button:has-text("Call")'
    ]
    
    for selector in selectors:
        try:
            button = await page.query_selector(selector)
            if button:
                text = await button.inner_text()
                print(f"      ✅ Found contact button: '{text}'")
                return button
        except:
            continue
    
    return None

async def check_contact_revealed(page):
    """Check if contact information was revealed after clicking button"""
    try:
        # Look for phone numbers in specific contact elements
        contact_selectors = [
            '.agentPhone', '.contactPhone', '.phone-number', 
            '[class*="phone"]', '.contact-info', '.agent-info',
            '.modal .phone', '.popup .phone', '.overlay .phone'
        ]
        
        for selector in contact_selectors:
            elements = await page.query_selector_all(selector)
            for element in elements:
                text = await element.inner_text()
                if re.search(r'(\+254|07|01)\d{8,9}', text):
                    print(f"      ✅ Found phone in {selector}: {text}")
                    return True
        
        # Also check the entire page content for newly revealed phones
        content = await page.content()
        phone_matches = re.findall(r'(\+254|07|01)\d{8,9}', content)
        if phone_matches:
            print(f"      ✅ Found {len(phone_matches)} phone numbers in page content")
            return True
        
        return False
    except Exception as e:
        print(f"      ❌ Error checking contact revealed: {e}")
        return False

async def detect_recaptcha(page):
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

async def solve_captcha_with_2captcha(page_url, site_key):
    """Solve CAPTCHA using 2captcha (JSON responses, soft_id, optimized polling)"""
    try:
        print("      📤 Submitting CAPTCHA to 2captcha...")
        submit_url = "http://2captcha.com/in.php"
        
        data = {
            'key': CAPTCHA_API_KEY,
            'method': 'userrecaptcha',
            'googlekey': site_key,
            'pageurl': page_url,
            'soft_id': 'Property24Scraper',
            'json': 1
        }
        
        response = requests.post(submit_url, data=data, timeout=30)
        
        captcha_id = None
        try:
            result = response.json()
            if result.get('status') == 1:
                captcha_id = result.get('request')
            else:
                print(f"      ❌ Submit failed: {result.get('error_text', 'Unknown error')}")
                return None
        except Exception:
            if not response.text.startswith('OK|'):
                print(f"      ❌ Submit failed: {response.text}")
                return None
            captcha_id = response.text.split('|')[1]
        
        print(f"      ✅ CAPTCHA submitted (ID: {captcha_id})")
        
        # Wait for solution (optimized polling)
        print("      ⏳ Waiting for solution...")
        result_url = "http://2captcha.com/res.php"
        
        for attempt in range(60):  # ~2 minutes
            await asyncio.sleep(2)
            params = {
                'key': CAPTCHA_API_KEY,
                'action': 'get',
                'id': captcha_id,
                'json': 1
            }
            response = requests.get(result_url, params=params, timeout=10)
            try:
                result = response.json()
                if result.get('status') == 1:
                    print("      ✅ CAPTCHA solved! Solution received")
                    return result.get('request')
                elif result.get('request') == 'CAPCHA_NOT_READY':
                    if attempt % 10 == 0:
                        print(f"      ⏳ Still waiting... ({attempt + 1}/60)")
                    continue
                else:
                    print(f"      ❌ Error: {result.get('error_text', 'Unknown error')}")
                    return None
            except Exception:
                if response.text.startswith('OK|'):
                    solution = response.text.split('|')[1]
                    print("      ✅ CAPTCHA solved! Solution received")
                    return solution
                elif response.text == 'CAPCHA_NOT_READY':
                    if attempt % 10 == 0:
                        print(f"      ⏳ Still waiting... ({attempt + 1}/60)")
                    continue
                else:
                    print(f"      ❌ Error: {response.text}")
                    return None
        
        print("      ⏰ Timeout waiting for solution")
        return None
        
    except Exception as e:
        print(f"      ❌ Error solving CAPTCHA: {e}")
        return None

async def inject_captcha_solution(page, solution):
    """Inject CAPTCHA solution into the page (multiple methods + verify)"""
    try:
        # Method 1: Set textarea value
        js_code1 = f"""
        (() => {{
            const textarea = document.querySelector('textarea[name="g-recaptcha-response"]');
            if (textarea) {{
                textarea.value = '{solution}';
                textarea.style.display = 'block';
                return 'textarea_set';
            }}
            return 'textarea_not_found';
        }})()
        """
        result1 = await page.evaluate(js_code1)
        print(f"      Method 1 (textarea): {result1}")

        # Method 2: Trigger reCAPTCHA callback
        js_code2 = f"""
        (() => {{
            if (typeof window.grecaptcha !== 'undefined') {{
                const widgets = document.querySelectorAll('.g-recaptcha');
                if (widgets.length > 0) {{
                    const callback = widgets[0].getAttribute('data-callback');
                    if (callback && typeof window[callback] === 'function') {{
                        window[callback]('{solution}');
                        return 'callback_triggered';
                    }}
                }}
            }}
            return 'callback_not_found';
        }})()
        """
        result2 = await page.evaluate(js_code2)
        print(f"      Method 2 (callback): {result2}")

        # Method 3: Set global grecaptcha.getResponse
        js_code3 = f"""
        (() => {{
            if (typeof window.grecaptcha !== 'undefined') {{
                window.grecaptcha.getResponse = function() {{ return '{solution}'; }};
                return 'global_set';
            }}
            return 'grecaptcha_not_found';
        }})()
        """
        result3 = await page.evaluate(js_code3)
        print(f"      Method 3 (global): {result3}")

        # Method 4: Submit any form containing the recaptcha response
        js_code4 = f"""
        (() => {{
            const forms = document.querySelectorAll('form');
            for (let form of forms) {{
                const recaptchaField = form.querySelector('textarea[name="g-recaptcha-response"]');
                if (recaptchaField) {{
                    recaptchaField.value = '{solution}';
                    const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
                    if (submitBtn) {{
                        submitBtn.click();
                        return 'form_submitted';
                    }}
                }}
            }}
            return 'no_form_found';
        }})()
        """
        result4 = await page.evaluate(js_code4)
        print(f"      Method 4 (form): {result4}")

        await page.wait_for_timeout(2000)
        print("      ✅ CAPTCHA solution injected")
    except Exception as e:
        print(f"      ❌ Error injecting solution: {e}")

async def verify_captcha_accepted(page) -> bool:
    """Heuristic checks to verify CAPTCHA is accepted"""
    try:
        # If reCAPTCHA widget disappears
        try:
            if not await page.is_visible('.g-recaptcha'):
                return True
        except:
            pass
        # If contact modal shows phone nodes
        candidates = await page.query_selector_all('.agentPhone, .contactPhone, .phone-number, [class*="phone"]')
        for el in candidates:
            txt = (await el.inner_text()).strip()
            if re.search(r'(\+254|07|01)\d{8,9}', txt):
                return True
        return False
    except Exception:
        return False

if __name__ == "__main__":
    asyncio.run(test_contact_extraction())
