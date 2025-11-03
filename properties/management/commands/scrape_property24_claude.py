import asyncio
import json
import re
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import requests
from urllib.parse import urljoin

class ImprovedProperty24Scraper:
    def __init__(self):
        self.base_url = "https://www.property24.co.ke"
        self.captcha_api_key = "79d9722448416056a13129c67d5c2b55"
        self.session = requests.Session()
        
    async def scrape_properties_efficiently(self, area_url: str, max_pages: int = 5):
        """More efficient scraping approach"""
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
            )
            
            try:
                # Strategy 1: Direct API calls (fastest)
                api_properties = await self._try_api_extraction(area_url)
                if api_properties:
                    print(f"✅ Got {len(api_properties)} properties via API")
                    return api_properties
                
                # Strategy 2: Single-page extraction with network monitoring
                properties = await self._extract_with_network_monitoring(context, area_url, max_pages)
                if properties:
                    print(f"✅ Got {len(properties)} properties via network monitoring")
                    return properties
                
                # Strategy 3: Optimized contact extraction (fallback)
                properties = await self._optimized_contact_extraction(context, area_url, max_pages)
                return properties
                
            finally:
                await browser.close()

    async def _try_api_extraction(self, area_url: str) -> List[Dict]:
        """Try to find and use internal APIs"""
        try:
            # Many property sites load data via AJAX/API calls
            # Let's intercept these calls instead of scraping HTML
            
            # Common Property24 API patterns to try
            api_endpoints = [
                f"/api/properties/search",
                f"/ajax/search",
                f"/search/results",
                f"/api/listings"
            ]
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
                'Accept': 'application/json, */*',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': f"{self.base_url}{area_url}"
            }
            
            for endpoint in api_endpoints:
                try:
                    # Extract area ID from URL
                    area_match = re.search(r's(\d+)', area_url)
                    if not area_match:
                        continue
                        
                    area_id = area_match.group(1)
                    
                    # Try different API parameter formats
                    api_params = [
                        {'area': area_id, 'type': 'rent'},
                        {'locationId': area_id, 'listingType': 'rent'},
                        {'searchLocationId': area_id}
                    ]
                    
                    for params in api_params:
                        response = self.session.get(
                            f"{self.base_url}{endpoint}",
                            params=params,
                            headers=headers,
                            timeout=10
                        )
                        
                        if response.status_code == 200:
                            try:
                                data = response.json()
                                properties = self._parse_api_response(data)
                                if properties:
                                    return properties
                            except:
                                continue
                                
                except Exception as e:
                    continue
            
            return []
            
        except Exception as e:
            print(f"API extraction failed: {e}")
            return []

    def _parse_api_response(self, data: dict) -> List[Dict]:
        """Parse API response to extract property data"""
        properties = []
        
        try:
            # Common API response structures
            listings_keys = ['listings', 'properties', 'results', 'data', 'items']
            
            listings = None
            for key in listings_keys:
                if key in data and isinstance(data[key], list):
                    listings = data[key]
                    break
            
            if not listings:
                return []
            
            for item in listings:
                try:
                    prop = {
                        'title': self._safe_get(item, ['title', 'headline', 'description']),
                        'price': self._extract_price(item),
                        'location': self._safe_get(item, ['location', 'address', 'area']),
                        'property_type': self._safe_get(item, ['type', 'propertyType', 'category']),
                        'bedrooms': self._safe_get(item, ['bedrooms', 'beds', 'bedroomCount']),
                        'bathrooms': self._safe_get(item, ['bathrooms', 'baths', 'bathroomCount']),
                        'url': self._build_property_url(item),
                        'images': self._extract_images_from_api(item),
                        'contact': self._extract_contact_from_api(item),
                        'external_id': self._safe_get(item, ['id', 'listingId', 'propertyId'])
                    }
                    
                    if prop['price'] and prop['external_id']:
                        properties.append(prop)
                        
                except Exception as e:
                    continue
            
            return properties
            
        except Exception as e:
            return []

    async def _extract_with_network_monitoring(self, context, area_url: str, max_pages: int) -> List[Dict]:
        """Extract data by monitoring network requests"""
        properties = []
        captured_data = []
        
        page = await context.new_page()
        
        # Setup network interception
        async def capture_response(response):
            if response.status == 200 and any(keyword in response.url.lower() 
                                           for keyword in ['api', 'ajax', 'search', 'listing']):
                try:
                    if 'json' in response.headers.get('content-type', ''):
                        data = await response.json()
                        captured_data.append(data)
                except:
                    pass
        
        page.on('response', capture_response)
        
        try:
            # Load the search page
            await page.goto(f"{self.base_url}{area_url}", wait_until='networkidle')
            
            # Wait for any AJAX requests to complete
            await page.wait_for_timeout(5000)
            
            # Try pagination to capture more API calls
            for page_num in range(2, min(max_pages + 1, 4)):  # Limit to avoid detection
                try:
                    # Look for pagination elements
                    next_btn = await page.query_selector('a[href*="page="]')
                    if next_btn:
                        await next_btn.click()
                        await page.wait_for_timeout(3000)
                except:
                    break
            
            # Process captured API data
            for data in captured_data:
                api_properties = self._parse_api_response(data)
                properties.extend(api_properties)
            
            # If no API data captured, fall back to HTML parsing
            if not properties:
                properties = await self._parse_html_efficiently(page)
            
            return properties
            
        finally:
            await page.close()

    async def _parse_html_efficiently(self, page) -> List[Dict]:
        """Efficient HTML parsing without individual page navigation"""
        properties = []
        
        try:
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # Find property cards
            property_cards = soup.select('.js_listingTile')
            
            for card in property_cards:
                try:
                    # Extract data directly from card HTML
                    prop = await self._extract_card_data_efficiently(card, page)
                    if prop:
                        properties.append(prop)
                        
                except Exception as e:
                    continue
            
            return properties
            
        except Exception as e:
            print(f"HTML parsing error: {e}")
            return []

    async def _extract_card_data_efficiently(self, card, page) -> Optional[Dict]:
        """Extract maximum data from property card without navigation"""
        try:
            card_text = card.get_text()
            
            # Extract price
            price_match = re.search(r'KSh\s*([\d,]+)', card_text)
            price = int(price_match.group(1).replace(',', '')) if price_match else None
            
            # Extract property type and location
            property_type = self._extract_property_type(card_text)
            location = self._extract_location(card_text)
            
            # Extract bedrooms/bathrooms
            bedrooms = self._extract_number(card_text, r'(\d+)\s*bed')
            bathrooms = self._extract_number(card_text, r'(\d+)\s*bath')
            
            # Try to extract property URL from card
            link = card.find('a', href=True)
            property_url = None
            if link:
                href = link['href']
                if href.startswith('/'):
                    property_url = f"{self.base_url}{href}"
                else:
                    property_url = href
            
            # Extract images from card
            images = []
            img_tags = card.find_all('img', src=True)
            for img in img_tags:
                src = img['src']
                if 'static.sa-property' in src or 'property24' in src:
                    if src.startswith('//'):
                        src = 'https:' + src
                    images.append(src)
            
            # Extract contact info if visible in card (some sites show partial info)
            contact_info = self._extract_visible_contact(card_text)
            
            if not price:
                return None
                
            return {
                'title': f"{property_type} in {location}" if property_type and location else "Property",
                'price': price,
                'location': location or "Unknown",
                'property_type': property_type or "unknown",
                'bedrooms': bedrooms,
                'bathrooms': bathrooms,
                'url': property_url,
                'images': images,
                'contact': contact_info,
                'external_id': self._extract_id_from_url(property_url) if property_url else None
            }
            
        except Exception as e:
            return None

    async def _optimized_contact_extraction(self, context, area_url: str, max_pages: int) -> List[Dict]:
        """Optimized contact extraction - only for high-value properties"""
        
        # First, get all properties efficiently
        page = await context.new_page()
        await page.goto(f"{self.base_url}{area_url}", wait_until='domcontentloaded')
        
        properties = await self._parse_html_efficiently(page)
        await page.close()
        
        # Sort by price (descending) and only extract contacts for top properties
        high_value_properties = sorted(
            [p for p in properties if p.get('price', 0) > 50000],  # Above 50k KSh
            key=lambda x: x.get('price', 0), 
            reverse=True
        )[:10]  # Top 10 only
        
        print(f"🎯 Extracting contacts for {len(high_value_properties)} high-value properties")
        
        # Extract contacts for high-value properties only
        for prop in high_value_properties:
            if prop.get('url'):
                contact_info = await self._extract_single_property_contact(context, prop['url'])
                if contact_info:
                    prop.update(contact_info)
                    print(f"✅ Got contact for {prop['title']} - KSh{prop['price']:,}")
                
                # Add delay to avoid detection
                await asyncio.sleep(2)
        
        return properties

    async def _extract_single_property_contact(self, context, property_url: str) -> Dict:
        """Extract contact info from single property page"""
        page = await context.new_page()
        contact_info = {}
        
        try:
            await page.goto(property_url, wait_until='domcontentloaded')
            await page.wait_for_timeout(2000)
            
            # Strategy 1: Look for visible contact info first
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            visible_contact = self._extract_all_visible_contact(soup)
            if visible_contact.get('phone_numbers') or visible_contact.get('email_addresses'):
                contact_info.update(visible_contact)
                return contact_info
            
            # Strategy 2: Try clicking contact buttons (optimized)
            contact_buttons = await page.query_selector_all('.ShowContact')
            
            for i, button in enumerate(contact_buttons[:2]):  # Limit to 2 attempts
                try:
                    await button.click()
                    await page.wait_for_timeout(3000)
                    
                    # Check for CAPTCHA
                    if await self._has_recaptcha(page):
                        print(f"🛡️ CAPTCHA detected on {property_url}")
                        
                        # Only solve CAPTCHA for very high-value properties
                        price = await self._get_property_price_from_page(page)
                        if price and price > 100000:  # Above 100k KSh
                            solved = await self._solve_captcha_optimized(page)
                            if solved:
                                revealed = await self._get_revealed_contact(page)
                                contact_info.update(revealed)
                                break
                        else:
                            print(f"⏭️ Skipping CAPTCHA for lower-value property")
                            break
                    else:
                        # No CAPTCHA, extract revealed info
                        revealed = await self._get_revealed_contact(page)
                        contact_info.update(revealed)
                        if revealed.get('phone_numbers'):
                            break
                            
                except Exception as e:
                    continue
            
            return contact_info
            
        finally:
            await page.close()

    async def _solve_captcha_optimized(self, page) -> bool:
        """Optimized CAPTCHA solving with better error handling"""
        try:
            # Get site key
            site_key_elem = await page.query_selector('[data-sitekey]')
            if not site_key_elem:
                return False
                
            site_key = await site_key_elem.get_attribute('data-sitekey')
            if not site_key:
                return False
            
            print(f"🔑 Solving CAPTCHA with site key: {site_key[:20]}...")
            
            # Submit to 2captcha with timeout
            captcha_id = await self._submit_captcha_with_timeout(page.url, site_key)
            if not captcha_id:
                return False
            
            # Get solution with timeout
            solution = await self._get_solution_with_timeout(captcha_id)
            if not solution:
                return False
            
            # Submit solution
            return await self._submit_solution_optimized(page, solution)
            
        except Exception as e:
            print(f"❌ CAPTCHA solving error: {e}")
            return False

    async def _submit_captcha_with_timeout(self, page_url: str, site_key: str, timeout: int = 30) -> Optional[str]:
        """Submit CAPTCHA with timeout"""
        try:
            import requests
            
            response = requests.post(
                "http://2captcha.com/in.php",
                data={
                    'key': self.captcha_api_key,
                    'method': 'userrecaptcha',
                    'googlekey': site_key,
                    'pageurl': page_url,
                },
                timeout=timeout
            )
            
            if response.text.startswith('OK|'):
                return response.text.split('|')[1]
            else:
                print(f"❌ 2captcha submit error: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ CAPTCHA submit timeout: {e}")
            return None

    async def _get_solution_with_timeout(self, captcha_id: str, max_wait: int = 120) -> Optional[str]:
        """Get CAPTCHA solution with timeout"""
        try:
            import requests
            
            for attempt in range(max_wait // 5):  # Check every 5 seconds
                await asyncio.sleep(5)
                
                response = requests.get(
                    "http://2captcha.com/res.php",
                    params={'key': self.captcha_api_key, 'action': 'get', 'id': captcha_id},
                    timeout=10
                )
                
                if response.text.startswith('OK|'):
                    return response.text.split('|')[1]
                elif response.text != 'CAPCHA_NOT_READY':
                    print(f"❌ 2captcha error: {response.text}")
                    return None
                    
            print("⏰ CAPTCHA solution timeout")
            return None
            
        except Exception as e:
            print(f"❌ Solution retrieval error: {e}")
            return None

    # Helper methods
    def _safe_get(self, data: dict, keys: List[str]) -> Optional[str]:
        """Safely get value from dict using multiple possible keys"""
        for key in keys:
            if key in data and data[key]:
                return str(data[key])
        return None

    def _extract_price(self, item: dict) -> Optional[int]:
        """Extract price from API item"""
        price_keys = ['price', 'rentAmount', 'amount', 'cost']
        for key in price_keys:
            if key in item:
                try:
                    price_str = str(item[key])
                    # Remove currency symbols and extract number
                    price_num = re.sub(r'[^\d]', '', price_str)
                    if price_num:
                        return int(price_num)
                except:
                    continue
        return None

    def _extract_property_type(self, text: str) -> Optional[str]:
        """Extract property type from text"""
        types = ['apartment', 'house', 'villa', 'townhouse', 'flat', 'studio']
        text_lower = text.lower()
        for prop_type in types:
            if prop_type in text_lower:
                return prop_type
        return None

    def _extract_location(self, text: str) -> Optional[str]:
        """Extract location from text"""
        # Look for common Nairobi areas
        areas = ['karen', 'lavington', 'kileleshwa', 'kilimani', 'westlands', 
                'spring valley', 'loresho', 'runda', 'muthaiga', 'south b', 'south c']
        
        text_lower = text.lower()
        for area in areas:
            if area in text_lower:
                return area.title()
        return None

    def _extract_number(self, text: str, pattern: str) -> Optional[int]:
        """Extract number using regex pattern"""
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except:
                pass
        return None

# Usage example:
async def main():
    scraper = ImprovedProperty24Scraper()
    
    # Karen area URL
    karen_url = '/property-to-rent-in-karen-s14524'
    
    properties = await scraper.scrape_properties_efficiently(karen_url, max_pages=3)
    
    print(f"\n🎉 Scraped {len(properties)} properties")
    
    for prop in properties[:3]:  # Show first 3
        print(f"📍 {prop['title']} - KSh{prop['price']:,}")
        if prop.get('contact', {}).get('phone_numbers'):
            print(f"   📞 {len(prop['contact']['phone_numbers'])} phone numbers")

if __name__ == "__main__":
    asyncio.run(main()) 