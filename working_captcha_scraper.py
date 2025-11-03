#!/usr/bin/env python3

import asyncio
from playwright.async_api import async_playwright
import re
from bs4 import BeautifulSoup
import json

async def working_captcha_scraper():
    """Working Property24 scraper with CAPTCHA support - uses known working property URLs"""
    
    # Use actual working property URLs we know have contact buttons
    test_properties = [
        "https://www.property24.co.ke/3-bedroom-apartment-flat-to-rent-in-kileleshwa-116153975",
        "https://www.property24.co.ke/2-bedroom-apartment-flat-to-rent-in-westlands-115998234",
        "https://www.property24.co.ke/1-bedroom-apartment-flat-to-rent-in-kilimani-116087654"
    ]
    
    async with async_playwright() as p:
        # Visible browser for CAPTCHA solving
        browser = await p.chromium.launch(headless=False, slow_mo=500)
        page = await browser.new_page()
        
        print("🚀 Working Property24 CAPTCHA Scraper")
        print("=" * 50)
        print("💡 This version tests with known property URLs that have contact buttons")
        
        enhanced_properties = []
        
        try:
            for i, prop_url in enumerate(test_properties):
                print(f"\n📍 Processing property {i+1}/{len(test_properties)}")
                print(f"🔗 URL: {prop_url}")
                
                property_data = await scrape_property_with_captcha(page, prop_url)
                
                if property_data:
                    enhanced_properties.append(property_data)
                    
                    # Show results
                    title = property_data.get('title', 'Unknown Property')
                    price = property_data.get('price', 'Price not found')
                    phones = property_data.get('contact_info', {}).get('phones', [])
                    emails = property_data.get('contact_info', {}).get('emails', [])
                    captcha_solved = property_data.get('contact_info', {}).get('captcha_solved', False)
                    
                    print(f"✅ SUCCESS: {title}")
                    print(f"   💰 {price}")
                    print(f"   📞 {len(phones)} phone numbers: {phones}")
                    print(f"   📧 {len(emails)} emails: {emails}")
                    print(f"   🤖 CAPTCHA solved: {captcha_solved}")
                    
                    if phones or emails:
                        print("   🎉 CONTACT INFORMATION SUCCESSFULLY EXTRACTED!")
                else:
                    print("❌ Failed to extract property data")
                
                # Pause between properties
                await asyncio.sleep(3)
            
            # Final summary
            total_contacts = sum(len(prop.get('contact_info', {}).get('phones', [])) + 
                               len(prop.get('contact_info', {}).get('emails', [])) 
                               for prop in enhanced_properties)
            
            print(f"\n🎊 FINAL RESULTS:")
            print(f"📊 Processed: {len(enhanced_properties)} properties")
            print(f"📞 Total contacts extracted: {total_contacts}")
            
            # Save results
            with open('captcha_scraper_results.json', 'w') as f:
                json.dump(enhanced_properties, f, indent=2)
            print("💾 Results saved to 'captcha_scraper_results.json'")
            
        except Exception as e:
            print(f"❌ Error during scraping: {e}")
        
        finally:
            print("\n🔍 Keeping browser open for 10 seconds...")
            await page.wait_for_timeout(10000)
            await browser.close()

async def scrape_property_with_captcha(page, property_url):
    """Scrape individual property with full CAPTCHA handling"""
    
    try:
        print(f"   🌐 Navigating to property page...")
        await page.goto(property_url, wait_until='domcontentloaded')
        await page.wait_for_timeout(3000)
        
        # Extract basic property info
        property_data = await extract_property_info(page)
        property_data['url'] = property_url
        
        # Try to extract contact information with CAPTCHA handling
        print(f"   🔍 Looking for contact reveal buttons...")
        contact_info = await handle_contact_extraction_with_captcha(page)
        property_data['contact_info'] = contact_info
        
        return property_data
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None

async def extract_property_info(page):
    """Extract basic property information"""
    
    property_data = {}
    
    try:
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        page_text = soup.get_text()
        
        # Title - try multiple selectors
        title = None
        title_selectors = ['h1', '.property-title', '.listing-title', 'title']
        for selector in title_selectors:
            elem = soup.select_one(selector)
            if elem and len(elem.get_text(strip=True)) > 5:
                title = elem.get_text(strip=True)
                break
        
        property_data['title'] = title or 'Property Title Not Found'
        
        # Price extraction
        price_patterns = [
            r'KSh\s*(\d{2,3}(?:\s+\d{3})+)',  # KSh 120 000
            r'KSh\s*(\d+(?:,\d{3})+)',        # KSh 120,000
            r'KSh\s*(\d{4,7})'                # KSh 120000
        ]
        
        for pattern in price_patterns:
            match = re.search(pattern, page_text)
            if match:
                price_str = re.sub(r'[\s,]', '', match.group(1))
                try:
                    price_num = int(price_str)
                    if 10000 <= price_num <= 10000000:  # Reasonable range
                        property_data['price'] = f"KSh {price_num:,}"
                        break
                except:
                    continue
        
        # Location
        location_patterns = [
            r'(?:in|at)\s+([A-Za-z\s]+),?\s*Nairobi',
            r'([A-Za-z\s]+),\s*Nairobi'
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                location = match.group(1).strip()
                if len(location) < 30:  # Reasonable location length
                    property_data['location'] = location
                    break
        
        # Bedrooms and bathrooms
        bed_match = re.search(r'(\d+)\s*(?:bed|bedroom)', page_text.lower())
        if bed_match:
            property_data['bedrooms'] = int(bed_match.group(1))
        
        bath_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:bath|bathroom)', page_text.lower())
        if bath_match:
            property_data['bathrooms'] = float(bath_match.group(1))
        
        print(f"   📋 Extracted: {property_data.get('title', 'Unknown')}")
        print(f"   💰 Price: {property_data.get('price', 'Not found')}")
        
    except Exception as e:
        print(f"   ⚠️ Error extracting basic info: {e}")
    
    return property_data

async def handle_contact_extraction_with_captcha(page):
    """Handle contact extraction with CAPTCHA solving"""
    
    contact_info = {
        'phones': [],
        'emails': [],
        'captcha_solved': False,
        'contact_buttons_found': False
    }
    
    try:
        # Look for contact reveal buttons
        contact_buttons = await page.query_selector_all('text="Show Contact Number"')
        
        if not contact_buttons:
            print("   ⚠️ No 'Show Contact Number' buttons found")
            return contact_info
        
        contact_info['contact_buttons_found'] = True
        print(f"   ✅ Found {len(contact_buttons)} contact buttons")
        
        # Click the first contact button
        print("   🖱️ Clicking contact button...")
        await contact_buttons[0].click()
        await page.wait_for_timeout(2000)
        
        # Check for reCAPTCHA
        recaptcha_present = await detect_recaptcha(page)
        
        if recaptcha_present:
            print("   🤖 reCAPTCHA detected!")
            print("   " + "="*50)
            print("   🚨 MANUAL ACTION REQUIRED:")
            print("   👆 Please solve the reCAPTCHA in the browser window")
            print("   ⏰ Script will wait up to 60 seconds")
            print("   " + "="*50)
            
            # Wait for manual CAPTCHA solving
            captcha_solved = await wait_for_captcha_completion(page, timeout=60)
            contact_info['captcha_solved'] = captcha_solved
            
            if captcha_solved:
                print("   🎉 reCAPTCHA appears to be solved!")
                await page.wait_for_timeout(3000)  # Wait for contact info to load
            else:
                print("   ⚠️ CAPTCHA not solved within timeout")
                return contact_info
        else:
            print("   ✅ No CAPTCHA detected - contact info should be visible")
        
        # Extract contact information
        contact_data = await extract_contact_information(page)
        contact_info.update(contact_data)
        
        if contact_info['phones'] or contact_info['emails']:
            print(f"   🎊 SUCCESS! Found {len(contact_info['phones'])} phones, {len(contact_info['emails'])} emails")
        else:
            print("   ⚠️ No contact information found after CAPTCHA")
        
    except Exception as e:
        print(f"   ❌ Error in contact extraction: {e}")
    
    return contact_info

async def detect_recaptcha(page):
    """Detect if reCAPTCHA is present"""
    
    try:
        selectors = [
            '.g-recaptcha',
            'iframe[src*="recaptcha"]',
            '[data-sitekey]'
        ]
        
        for selector in selectors:
            elements = await page.query_selector_all(selector)
            if elements:
                return True
        
        return False
    except:
        return False

async def wait_for_captcha_completion(page, timeout=60):
    """Wait for user to solve reCAPTCHA manually"""
    
    for i in range(timeout):
        try:
            # Check if contact info appeared (indicates CAPTCHA solved)
            contact_appeared = await quick_contact_check(page)
            if contact_appeared:
                return True
            
            # Check if reCAPTCHA disappeared
            recaptcha_visible = await page.query_selector('iframe[src*="recaptcha"]:visible')
            if not recaptcha_visible:
                return True
            
            # Progress indicator
            if i % 10 == 0 and i > 0:
                print(f"   ⏳ Still waiting for CAPTCHA... ({i}/{timeout}s)")
            
            await page.wait_for_timeout(1000)
            
        except:
            pass
    
    return False

async def quick_contact_check(page):
    """Quick check if contact info appeared"""
    
    try:
        content = await page.content()
        kenyan_phone_pattern = r'(?:\+254|0)(?:7\d{8}|1\d{8})'
        return bool(re.search(kenyan_phone_pattern, content))
    except:
        return False

async def extract_contact_information(page):
    """Extract contact information from page"""
    
    contact_data = {'phones': [], 'emails': []}
    
    try:
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        page_text = soup.get_text()
        
        # Phone extraction
        phone_patterns = [
            r'(?:\+254|0)(?:7\d{8}|1\d{8})',  # Standard Kenyan
            r'(\+254\d{9})',                   # International
            r'(07\d{8})',                      # Mobile
            r'(01\d{8})',                      # Landline
        ]
        
        for pattern in phone_patterns:
            matches = re.findall(pattern, page_text)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0] if match[0] else match[1]
                clean_phone = re.sub(r'[^\d+]', '', match)
                if len(clean_phone) >= 10 and clean_phone not in contact_data['phones']:
                    contact_data['phones'].append(clean_phone)
        
        # Email extraction
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, page_text)
        
        # Filter out system emails
        filtered_emails = [email for email in emails if not any(
            word in email.lower() for word in [
                'noreply', 'admin', 'info@property24', 'system', 'support'
            ]
        )]
        
        contact_data['emails'] = list(set(filtered_emails))
        
    except Exception as e:
        print(f"   ⚠️ Error extracting contact: {e}")
    
    return contact_data

if __name__ == "__main__":
    asyncio.run(working_captcha_scraper()) 