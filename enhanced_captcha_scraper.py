#!/usr/bin/env python3

import asyncio
from playwright.async_api import async_playwright
import re
from bs4 import BeautifulSoup
import json

async def scrape_with_captcha_handling():
    """Enhanced Property24 scraper with reCAPTCHA handling"""
    
    base_url = "https://www.property24.co.ke"
    search_url = f"{base_url}/property-to-rent-in-nairobi-p95"  # Start with one page
    
    async with async_playwright() as p:
        # Visible browser for CAPTCHA solving
        browser = await p.chromium.launch(headless=False, slow_mo=500)
        page = await browser.new_page()
        
        print("🚀 Enhanced Property24 Scraper with CAPTCHA Support")
        print("=" * 60)
        
        try:
            # Navigate to search results
            await page.goto(search_url, wait_until='domcontentloaded')
            await page.wait_for_timeout(3000)
            
            print(f"📄 Loaded search page: {search_url}")
            
            # Get property listing URLs
            property_urls = await extract_property_urls(page, base_url)
            print(f"🏠 Found {len(property_urls)} properties to process")
            
            enhanced_properties = []
            
            # Process each property
            for i, prop_url in enumerate(property_urls[:3]):  # Test with first 3
                print(f"\n📍 Processing property {i+1}/{len(property_urls[:3])}")
                print(f"🔗 URL: {prop_url}")
                
                property_data = await scrape_property_with_contact(page, prop_url, browser)
                if property_data:
                    enhanced_properties.append(property_data)
                    print("✅ Property data extracted successfully")
                    
                    # Show summary
                    title = property_data.get('title', 'Unknown')
                    price = property_data.get('price', 'Unknown')
                    contact_count = len(property_data.get('contact_info', {}).get('phones', []))
                    email_count = len(property_data.get('contact_info', {}).get('emails', []))
                    
                    print(f"   📋 {title}")
                    print(f"   💰 {price}")
                    print(f"   📞 {contact_count} phone numbers")
                    print(f"   📧 {email_count} email addresses")
                else:
                    print("❌ Failed to extract property data")
                
                # Brief pause between properties
                await asyncio.sleep(2)
            
            # Summary
            print(f"\n🎉 SCRAPING COMPLETE!")
            print(f"📊 Processed {len(enhanced_properties)} properties successfully")
            
            # Save results
            with open('enhanced_properties_with_contacts.json', 'w') as f:
                json.dump(enhanced_properties, f, indent=2)
            print("💾 Results saved to 'enhanced_properties_with_contacts.json'")
            
        except Exception as e:
            print(f"❌ Error during scraping: {e}")
        
        finally:
            print("\n🔍 Keeping browser open for final inspection...")
            await page.wait_for_timeout(10000)
            await browser.close()

async def extract_property_urls(page, base_url):
    """Extract property URLs from search results"""
    
    property_urls = []
    
    # Get page content and parse with BeautifulSoup for better control
    content = await page.content()
    soup = BeautifulSoup(content, 'html.parser')
    
    # Look for property links with more specific patterns
    # Property24 usually has URLs like /property-to-rent-in-{area}-{id}
    all_links = soup.find_all('a', href=True)
    
    for link in all_links:
        href = link['href']
        
        # Look for individual property URLs (not search URLs)
        if (href.startswith('/') and 
            'property-to-rent' in href and 
            re.search(r'-\d{8,}$', href)):  # Ends with property ID
            
            full_url = base_url + href
            if full_url not in property_urls:
                property_urls.append(full_url)
                print(f"   🔗 Found property: {href}")
    
    # If no individual properties found, try alternative selectors
    if not property_urls:
        print("   🔍 No individual property URLs found, trying alternative selectors...")
        
        # Try to find clickable property cards/listings
        link_selectors = [
            'a[href*="property-to-rent-in-"][href*="-1"]',  # Property URLs with IDs
            '.listing-result a[href*="property-to-rent"]',
            '.property-card a[href*="property-to-rent"]',
            '.js-listing-card a[href*="property-to-rent"]'
        ]
        
        for selector in link_selectors:
            links = soup.select(selector)
            for link in links:
                href = link.get('href', '')
                if href and href.startswith('/'):
                    full_url = base_url + href
                    if full_url not in property_urls and re.search(r'-\d{6,}', href):
                        property_urls.append(full_url)
                        print(f"   🔗 Found property (alt): {href}")
    
    return property_urls

async def scrape_property_with_contact(page, property_url, browser):
    """Scrape individual property with contact extraction"""
    
    try:
        # Navigate to property page
        await page.goto(property_url, wait_until='domcontentloaded')
        await page.wait_for_timeout(3000)
        
        # Extract basic property data first
        property_data = await extract_basic_property_info(page)
        property_data['url'] = property_url
        
        # Attempt contact extraction with CAPTCHA handling
        contact_info = await extract_contact_with_captcha(page)
        property_data['contact_info'] = contact_info
        
        return property_data
        
    except Exception as e:
        print(f"   ❌ Error scraping property: {e}")
        return None

async def extract_basic_property_info(page):
    """Extract basic property information"""
    
    data = {}
    
    try:
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        page_text = soup.get_text()
        
        # Title
        title_selectors = ['h1', '.property-title', '.listing-title']
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                data['title'] = title_elem.get_text(strip=True)
                break
        
        # Price
        price_patterns = [
            r'KSh\s*(\d{2,3}(?:\s+\d{3})+)',
            r'KSh\s*(\d+(?:,\d{3})+)',
            r'KSh\s*(\d{4,7})'
        ]
        
        for pattern in price_patterns:
            match = re.search(pattern, page_text)
            if match:
                price_str = re.sub(r'[\s,]', '', match.group(1))
                data['price'] = f"KSh {int(price_str):,}"
                break
        
        # Location
        location_elem = soup.select_one('.location, .address, .suburb')
        if location_elem:
            data['location'] = location_elem.get_text(strip=True)
        
        # Property details
        bed_match = re.search(r'(\d+)\s*(?:bed|bedroom)', page_text.lower())
        if bed_match:
            data['bedrooms'] = int(bed_match.group(1))
        
        bath_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:bath|bathroom)', page_text.lower())
        if bath_match:
            data['bathrooms'] = float(bath_match.group(1))
        
    except Exception as e:
        print(f"   ⚠️ Error extracting basic info: {e}")
    
    return data

async def extract_contact_with_captcha(page):
    """Extract contact info with CAPTCHA handling"""
    
    contact_info = {'phones': [], 'emails': [], 'captcha_solved': False}
    
    try:
        print("   🔍 Looking for contact reveal buttons...")
        
        # Find contact buttons
        contact_buttons = await page.query_selector_all('text="Show Contact Number"')
        
        if not contact_buttons:
            print("   ⚠️ No contact reveal buttons found")
            return contact_info
        
        print(f"   ✅ Found {len(contact_buttons)} contact buttons")
        
        # Click the first contact button
        await contact_buttons[0].click()
        await page.wait_for_timeout(2000)
        
        # Check for reCAPTCHA
        captcha_present = await detect_recaptcha(page)
        
        if captcha_present:
            print("   🤖 reCAPTCHA detected!")
            print("   ⏳ PLEASE SOLVE THE reCAPTCHA MANUALLY")
            print("   💡 The script will wait for you to complete it...")
            
            # Wait for CAPTCHA to be solved
            captcha_solved = await wait_for_captcha_solution(page)
            contact_info['captcha_solved'] = captcha_solved
            
            if captcha_solved:
                print("   🎉 reCAPTCHA appears to be solved!")
                # Wait a bit more for contact info to load
                await page.wait_for_timeout(3000)
            else:
                print("   ⚠️ reCAPTCHA may not be solved yet")
        
        # Extract any revealed contact information
        revealed_contact = await extract_revealed_contact_info(page)
        contact_info.update(revealed_contact)
        
    except Exception as e:
        print(f"   ❌ Error in contact extraction: {e}")
    
    return contact_info

async def detect_recaptcha(page):
    """Detect if reCAPTCHA is present"""
    
    try:
        recaptcha_selectors = [
            '.g-recaptcha',
            'iframe[src*="recaptcha"]',
            '[data-sitekey]'
        ]
        
        for selector in recaptcha_selectors:
            elements = await page.query_selector_all(selector)
            if elements:
                return True
        
        return False
        
    except Exception:
        return False

async def wait_for_captcha_solution(page, timeout_seconds=60):
    """Wait for user to solve reCAPTCHA"""
    
    print(f"   ⏰ Waiting up to {timeout_seconds} seconds for CAPTCHA solution...")
    
    for i in range(timeout_seconds):
        try:
            # Check if reCAPTCHA is solved by looking for success indicators
            # reCAPTCHA typically disappears or shows success state when solved
            
            # Method 1: Check if reCAPTCHA iframe is still visible
            recaptcha_visible = await page.query_selector('iframe[src*="recaptcha"]:visible')
            
            # Method 2: Check for any contact information that might have appeared
            contact_revealed = await check_for_revealed_contact(page)
            
            # Method 3: Look for success indicators
            success_indicators = await page.query_selector_all('.recaptcha-success, .captcha-success')
            
            if not recaptcha_visible or contact_revealed or success_indicators:
                return True
            
            # Show progress every 10 seconds
            if i % 10 == 0 and i > 0:
                print(f"   ⏳ Still waiting... ({i}/{timeout_seconds} seconds)")
            
            await page.wait_for_timeout(1000)  # Wait 1 second
            
        except Exception:
            pass
    
    print("   ⚠️ Timeout waiting for CAPTCHA solution")
    return False

async def check_for_revealed_contact(page):
    """Quick check if contact info was revealed"""
    
    try:
        content = await page.content()
        # Look for phone number patterns
        kenyan_phone_pattern = r'(?:\+254|0)(?:7\d{8}|1\d{8})'
        if re.search(kenyan_phone_pattern, content):
            return True
        return False
    except:
        return False

async def extract_revealed_contact_info(page):
    """Extract contact information after CAPTCHA is solved"""
    
    contact_data = {'phones': [], 'emails': []}
    
    try:
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        page_text = soup.get_text()
        
        # Phone number extraction
        phone_patterns = [
            r'(?:\+254|0)(?:7\d{8}|1\d{8})',  # Kenyan mobile/landline
            r'(\+254\d{9})',  # +254xxxxxxxxx
            r'(07\d{8})',  # 07xxxxxxxx
            r'(01\d{8})',  # 01xxxxxxxx
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
        filtered_emails = [email for email in emails if not any(word in email.lower() 
                         for word in ['noreply', 'admin', 'info@property24', 'system'])]
        
        contact_data['emails'] = list(set(filtered_emails))
        
        if contact_data['phones'] or contact_data['emails']:
            print(f"   📞 Found {len(contact_data['phones'])} phone numbers")
            print(f"   📧 Found {len(contact_data['emails'])} email addresses")
        
    except Exception as e:
        print(f"   ⚠️ Error extracting revealed contact: {e}")
    
    return contact_data

if __name__ == "__main__":
    asyncio.run(scrape_with_captcha_handling()) 