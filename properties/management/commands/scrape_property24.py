import asyncio
import time
import re
import random
import json
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.db import transaction
from asgiref.sync import sync_to_async
from properties.models import Property, Source, Image, Contact, PropertyDetail, ScrapingProgress
import logging
from playwright.async_api import async_playwright, Browser, Page
from urllib.parse import urljoin, urlparse
from django.utils import timezone

logger = logging.getLogger(__name__)

# Nairobi areas with their Property24 URL patterns
NAIROBI_AREAS = {
    'Karen': '/property-to-rent-in-karen-s14524',
    'Lavington': '/property-to-rent-in-lavington-s14525',
    'Kileleshwa': '/property-to-rent-in-kileleshwa-s14526',
    'Kilimani': '/property-to-rent-in-kilimani-s14527',
    'Westlands': '/property-to-rent-in-westlands-s14528',
    'Spring Valley': '/property-to-rent-in-spring-valley-s14529',
    'Loresho': '/property-to-rent-in-loresho-s14530',
    'Runda': '/property-to-rent-in-runda-s14531',
    'Muthaiga': '/property-to-rent-in-muthaiga-s14532',
    'South B': '/property-to-rent-in-south-b-s14533',
    'South C': '/property-to-rent-in-south-c-s14534',
    'Kasarani': '/property-to-rent-in-kasarani-s14535',
    'Embakasi': '/property-to-rent-in-embakasi-s14536',
    'Syokimau': '/property-to-rent-in-syokimau-s14537',
    'Langata': '/property-to-rent-in-langata-s14538',
}

# Add 2captcha API key (hardcoded for now)
CAPTCHA_API_KEY = "79d9722448416056a13129c67d5c2b55"

class Command(BaseCommand):
    help = 'Scrape rental properties from Property24 Kenya using Playwright'

    def add_arguments(self, parser):
        parser.add_argument(
            '--pages',
            type=int,
            default=5,
            help='Number of pages to scrape per area (default: 5)'
        )
        parser.add_argument(
            '--area',
            type=str,
            help='Specific area to scrape (e.g., "Karen", "Lavington"). If not provided, picks next pending area.'
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=0.5,
            help='Delay between requests in seconds (default: 0.5)'
        )
        parser.add_argument(
            '--debug',
            action='store_true',
            help='Enable debug logging'
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset progress for the specified area'
        )
        parser.add_argument(
            '--test-single',
            action='store_true',
            help='Test scraping just one property with 2captcha contact extraction'
        )

    def handle(self, *args, **options):
        self.pages = options['pages']
        self.delay = options['delay']
        self.debug = options['debug']
        self.reset = options['reset']
        
        # Setup logging
        if self.debug:
            logging.basicConfig(level=logging.DEBUG)
        
        # Create or get Property24 source
        self.source, created = Source.objects.get_or_create(
            name='Property24',
            defaults={'url': 'https://www.property24.co.ke'}
        )
        
        # Initialize areas in database if not exists
        self._initialize_areas()
        
        # Get area to scrape
        area = options['area']
        if area:
            if area not in NAIROBI_AREAS:
                self.stdout.write(self.style.ERROR(f'Invalid area: {area}'))
                self.stdout.write(f'Available areas: {", ".join(NAIROBI_AREAS.keys())}')
                return
            progress = ScrapingProgress.objects.get(area=area)
        else:
            # Get next pending area
            progress = ScrapingProgress.objects.filter(
                status__in=['pending', 'failed']
            ).order_by('last_scraped_at').first()
            
            if not progress:
                self.stdout.write(self.style.SUCCESS('All areas have been scraped! 🎉'))
                return
            
            area = progress.area
        
        # Reset progress if requested
        if self.reset:
            progress.last_page_scraped = 0
            progress.total_properties = 0
            progress.status = 'pending'
            progress.error_message = ''
            progress.save()
        
        self.stdout.write(
            self.style.SUCCESS(f'🚀 Starting Property24 Kenya scraper for {area}...')
        )
        
        # User agent pool for rotation
        self.user_agents = [
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) Firefox/120.0',
            'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0',
        ]
        
        # Run the async scraper
        try:
            progress.status = 'in_progress'
            progress.save()
            
            if options['test_single']:
                asyncio.run(self.test_single_property(progress))
            else:
                asyncio.run(self.run_scraper(progress))
            
            progress.status = 'completed'
            progress.save()
            
        except Exception as e:
            progress.status = 'failed'
            progress.error_message = str(e)
            progress.save()
            raise

    async def test_single_property(self, progress: ScrapingProgress):
        """Test scraping just one property with 2captcha contact extraction"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,  # Show browser for debugging
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            
            try:
                page = await browser.new_page()
                
                # Set user agent
                await page.set_extra_http_headers({
                    'User-Agent': random.choice(self.user_agents)
                })
                
                # Go to Karen search page
                base_url = "https://www.property24.co.ke/property-to-rent-in-karen-s14524"
                self.stdout.write(f'🌐 Loading: {base_url}')
                
                await page.goto(base_url, wait_until='domcontentloaded', timeout=30000)
                await page.wait_for_timeout(3000)
                
                # Find first property card
                property_cards = await page.query_selector_all('.js_listingTile')
                if not property_cards:
                    self.stdout.write('❌ No property cards found')
                    return
                
                self.stdout.write(f'🏠 Found {len(property_cards)} property cards')
                
                # Click on first property card
                first_card = property_cards[0]
                card_text = await first_card.text_content()
                self.stdout.write(f'🖱️ Clicking on: {card_text[:100]}...')
                
                await first_card.click()
                await page.wait_for_timeout(5000)
                
                # Get property detail URL
                property_url = page.url
                self.stdout.write(f'📍 Property URL: {property_url}')
                
                # Extract images
                content = await page.content()
                soup = BeautifulSoup(content, 'html.parser')
                
                images = await self.extract_all_images(soup, property_url, page)
                self.stdout.write(f'📸 Found {len(images)} images')
                for i, img in enumerate(images[:3]):
                    self.stdout.write(f'  Image {i+1}: {img}')
                
                # Extract contact information with 2captcha
                self.stdout.write('📞 Looking for "Show Contact Number" buttons...')
                
                # Find contact buttons - specifically look for .ShowContact elements
                show_contact_elements = await page.query_selector_all('.ShowContact')
                contact_found = False
                
                self.stdout.write(f'🎯 Found {len(show_contact_elements)} .ShowContact elements')
                
                for i, elem in enumerate(show_contact_elements):
                    try:
                        # Check if element is visible before clicking
                        is_visible = await elem.is_visible()
                        if not is_visible:
                            self.stdout.write(f'⚠️ Element {i+1} is not visible, skipping...')
                            continue
                            
                        button_text = await elem.text_content()
                        self.stdout.write(f'🖱️ Clicking on .ShowContact element {i+1}: "{button_text.strip()}"')
                        
                        # Scroll element into view before clicking
                        await elem.scroll_into_view_if_needed()
                        await page.wait_for_timeout(1000)
                        
                        # Click the contact button
                        await elem.click()
                        
                        # Wait longer for AJAX response and CAPTCHA to appear
                        self.stdout.write('⏳ Waiting for AJAX response and potential CAPTCHA...')
                        await page.wait_for_timeout(8000)  # Wait 8 seconds for AJAX
                        
                        # Check for CAPTCHA multiple times with delays
                        captcha_detected = False
                        for check_attempt in range(5):  # Increased to 5 attempts
                            captcha_detected = await self._detect_recaptcha(page)
                            if captcha_detected:
                                self.stdout.write(f'🛡️ CAPTCHA detected on attempt {check_attempt + 1}!')
                                break
                            else:
                                self.stdout.write(f'⏳ CAPTCHA check {check_attempt + 1}/5 - not detected yet...')
                                await page.wait_for_timeout(2000)  # Wait 2 more seconds
                        
                        if captcha_detected:
                            self.stdout.write('🛡️ CAPTCHA detected! Solving with 2captcha...')
                            
                            # Solve CAPTCHA with 2captcha
                            captcha_solved = await self._solve_recaptcha_with_2captcha(page)
                            
                            if captcha_solved:
                                self.stdout.write('✅ CAPTCHA solved successfully!')
                                
                                # Wait for contact info to be revealed
                                await page.wait_for_timeout(3000)
                                
                                # Extract revealed contact info
                                revealed_contacts = await self._extract_revealed_contacts(page)
                                
                                if revealed_contacts.get('phone_numbers'):
                                    self.stdout.write(f'📞 Found phone numbers: {revealed_contacts["phone_numbers"]}')
                                    contact_found = True
                                    break
                                else:
                                    self.stdout.write('ℹ️ No contact info revealed yet, trying next element...')
                            else:
                                self.stdout.write('❌ Failed to solve CAPTCHA')
                        else:
                            self.stdout.write('ℹ️ No CAPTCHA detected, checking for revealed contact info...')
                            
                            # Check if contact info was revealed without CAPTCHA
                            revealed_contacts = await self._extract_revealed_contacts(page)
                            if revealed_contacts.get('phone_numbers'):
                                self.stdout.write(f'📞 Found phone numbers: {revealed_contacts["phone_numbers"]}')
                                contact_found = True
                                break
                            else:
                                self.stdout.write('ℹ️ No contact info revealed yet, trying next element...')
                                
                    except Exception as e:
                        self.stdout.write(f'⚠️ Error clicking element {i+1}: {e}')
                        continue
                
                if not contact_found:
                    self.stdout.write('⚠️ No contact information found or extracted')
                
                # Wait for user to see results
                self.stdout.write('⏸️ Browser will stay open for 30 seconds...')
                await page.wait_for_timeout(30000)
                
            finally:
                await browser.close()

    def _initialize_areas(self):
        """Initialize scraping progress for all areas"""
        for area in NAIROBI_AREAS.keys():
            ScrapingProgress.objects.get_or_create(
                area=area,
                defaults={
                    'status': 'pending'
                }
            )

    async def run_scraper(self, progress: ScrapingProgress):
        """Main async scraping function"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            
            try:
                # Start from last page scraped + 1
                start_page = progress.last_page_scraped + 1
                end_page = start_page + self.pages - 1
                
                # Update progress status
                await sync_to_async(self._update_progress_status)(progress, 'in_progress')
                
                # Scrape pages in parallel
                tasks = []
                for page_num in range(start_page, end_page + 1):
                    tasks.append(self.scrape_page_async(browser, page_num, progress))
                
                # Wait for all pages to complete
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                all_properties = []
                for result in results:
                    if isinstance(result, list):
                        all_properties.extend(result)
                    elif isinstance(result, Exception):
                        self.stdout.write(self.style.ERROR(f'Page error: {result}'))
                
                # Bulk save properties
                saved_count = await self.bulk_save_properties(all_properties)
                
                # Update progress
                await sync_to_async(self._update_progress)(
                    progress, end_page, saved_count, 'completed'
                )
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'🎉 Successfully scraped {saved_count} properties from {progress.area}! '
                        f'(Pages {start_page}-{end_page})'
                    )
                )
                
            finally:
                await browser.close()

    def _update_progress_status(self, progress: ScrapingProgress, status: str):
        """Update progress status synchronously"""
        progress.status = status
        progress.save()

    def _update_progress(self, progress: ScrapingProgress, last_page: int, total_properties: int, status: str):
        """Update progress synchronously"""
        progress.last_page_scraped = last_page
        progress.total_properties += total_properties
        progress.status = status
        progress.save()

    async def scrape_page_async(self, browser: Browser, page_num: int, progress: ScrapingProgress) -> List[Dict]:
        """Scrape a single page asynchronously"""
        page = await browser.new_page()
        
        try:
            # Set random user agent
            await page.set_extra_http_headers({
                'User-Agent': random.choice(self.user_agents)
            })
            
            # Construct URL dynamically based on area
            base_url = "https://www.property24.co.ke"
            area_url_pattern = NAIROBI_AREAS.get(progress.area, '/property-to-rent-in-nairobi')
            url = f"{base_url}{area_url_pattern}"
            if page_num > 1:
                url += f"?page={page_num}"
            
            self.stdout.write(f'📄 Scraping {progress.area} page {page_num}: {url}')
            
            # Navigate with retry logic
            properties = await self.fetch_page_with_retry(page, url, browser)
            
            # Add random delay
            await asyncio.sleep(self.delay + random.uniform(0, 0.5))
            
            return properties
            
        finally:
            await page.close()

    async def fetch_page_with_retry(self, page: Page, url: str, browser: Browser, max_retries: int = 3) -> List[Dict]:
        """Fetch page with retry logic for handling errors"""
        for attempt in range(max_retries):
            try:
                # Navigate to page
                response = await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                
                if response.status == 503:
                    if attempt < max_retries - 1:
                        wait_time = 10 + attempt * 5
                        self.stdout.write(f'⏳ 503 error, waiting {wait_time}s... (attempt {attempt + 1})')
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        raise Exception(f"503 Service Unavailable after {max_retries} attempts")
                
                # Wait for content to load
                await page.wait_for_timeout(2000)
                
                # Get page content
                content = await page.content()
                
                # Parse properties with browser context
                property_cards = await self.parse_properties(content, url)
                
                # Process each property card to extract detailed data
                properties = []
                for i, card in enumerate(property_cards):
                    try:
                        prop_data = await self.extract_property_data(card, url, browser)
                        if prop_data:
                            properties.append(prop_data)
                            if self.debug and i < 3:  # Debug first 3 properties
                                self.stdout.write(f'🔍 Property {i+1}: {json.dumps(prop_data, indent=2)}')
                    except Exception as e:
                        if self.debug:
                            self.stdout.write(f'⚠️ Error extracting property {i+1}: {e}')
                        continue
                
                return properties
                
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 5 + attempt * 2
                    self.stdout.write(f'⚠️ Error: {e}, retrying in {wait_time}s...')
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    self.stdout.write(self.style.ERROR(f'❌ Failed to fetch {url}: {e}'))
                    return []

    async def parse_properties(self, html_content: str, base_url: str) -> List:
        """Parse property listings from HTML content."""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Use the correct selector for Property24 Kenya property cards
        property_cards = soup.select('.js_listingTile')
        
        self.stdout.write(f"Found {len(property_cards)} property cards")
        
        # Return the BeautifulSoup elements directly for processing
        return property_cards

    async def extract_property_data(self, card, base_url: str, browser: Browser) -> Optional[Dict]:
        """Extract property data by clicking on card and navigating to detail page"""
        try:
            # Extract basic data from card HTML
            basic_data = await self.extract_basic_property_data(card, base_url)
            if not basic_data:
                return None
            
            # Create a new page to click on the property card
            page = await browser.new_page()
            try:
                # Set user agent
                await page.set_extra_http_headers({
                    'User-Agent': random.choice(self.user_agents)
                })
                
                # Navigate to the search page
                await page.goto(base_url, wait_until='domcontentloaded', timeout=30000)
                await page.wait_for_timeout(3000)
                
                # Find all property cards
                property_cards = await page.query_selector_all('.js_listingTile')
                
                # Find the card that matches our basic data (by price or title)
                target_card = None
                for i, card_elem in enumerate(property_cards):
                    card_text = await card_elem.text_content()
                    if basic_data['price'] in card_text or basic_data['property_type'] in card_text:
                        target_card = card_elem
                        break
                
                if target_card:
                    self.stdout.write(f"🖱️ Clicking on property: {basic_data['title']}")
                    
                    # Click on the property card
                    await target_card.click()
                    await page.wait_for_timeout(5000)
                    
                    # Get the current URL (this is now the property detail page)
                    property_url = page.url
                    self.stdout.write(f"📍 Property detail URL: {property_url}")
                    
                    # Update basic data with the URL
                    basic_data['url'] = property_url
                    basic_data['external_id'] = self._extract_property_id(property_url)
                    
                    # Get detailed information from the property page
                    detailed_data = await self.scrape_property_details(property_url, browser)
                    if detailed_data:
                        # Merge basic and detailed data
                        basic_data.update(detailed_data)
                        self.stdout.write(f"✅ Extracted {len(detailed_data.get('all_images', []))} images and {len(detailed_data.get('phone_numbers', []))} phone numbers")
                    
                    return basic_data
                else:
                    self.stdout.write(f"⚠️ Could not find matching property card for: {basic_data['title']}")
                    return basic_data
                    
            finally:
                await page.close()
                
        except Exception as e:
            self.stdout.write(f"Error extracting property data: {e}")
            return None

    async def extract_basic_property_data(self, card, base_url: str) -> Optional[Dict]:
        """Extract basic property data from a property card."""
        try:
            # For Property24 Kenya, the entire card is clickable
            # We need to simulate clicking on the card to get the property URL
            # Since we're in a static parsing context, we'll extract what we can from the card HTML
            
            # Extract price information
            price = "Price not available"
            price_elements = card.find_all(string=lambda text: text and 'KSh' in text)
            if price_elements:
                price = price_elements[0].strip()
            
            # Extract property type
            property_type = "Unknown"
            type_elements = card.find_all(string=lambda text: text and any(word in text.lower() for word in ['house', 'apartment', 'commercial', 'property']))
            if type_elements:
                property_type = type_elements[0].strip()
            
            # Extract location (default to area name)
            location = "Karen, Nairobi"  # Will be updated based on area
            
            # Extract availability status
            availability = "Available"
            status_elements = card.find_all(string=lambda text: text and any(word in text.lower() for word in ['available', 'now', 'ready']))
            if status_elements:
                availability = status_elements[0].strip()
            
            # For Property24 Kenya, we need to click the card to get the detail URL
            # This will be handled in the browser context
            property_url = None  # Will be set when card is clicked
            
            return {
                'title': f"{property_type} in {location}",
                'price': price,
                'property_type': property_type,
                'location': location,
                'availability': availability,
                'url': property_url,
                'external_id': None,  # Will be extracted from URL after clicking
                'images': [],
                'contacts': []
            }
            
        except Exception as e:
            self.stdout.write(f"Error extracting basic property data: {e}")
            return None

    async def scrape_property_details(self, property_url: str, browser: Browser) -> Optional[Dict]:
        """Scrape detailed information from individual property page"""
        page = await browser.new_page()
        
        try:
            # Set user agent
            await page.set_extra_http_headers({
                'User-Agent': random.choice(self.user_agents)
            })
            
            self.stdout.write(f'🔍 Getting detailed info from: {property_url}')
            
            # Navigate to property detail page
            response = await page.goto(property_url, wait_until='domcontentloaded', timeout=30000)
            
            if response.status != 200:
                return None
            
            # Wait for content to load
            await page.wait_for_timeout(2000)
            
            # Get page content
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            detailed_data = {}
            
            # 1. EXTRACT FULL DESCRIPTION
            description_selectors = [
                '.property-description',
                '[class*="description"]',
                '.property-details-text',
                '.listing-description',
                'div[class*="detail"] p',
                '.property-content p'
            ]
            
            full_description = []
            for selector in description_selectors:
                desc_elements = soup.select(selector)
                for elem in desc_elements:
                    text = elem.get_text(strip=True)
                    if len(text) > 50 and text not in full_description:
                        full_description.append(text)
            
            if full_description:
                detailed_data['full_description'] = ' '.join(full_description)[:1000]
            
            # 2. EXTRACT CONTACT INFORMATION
            contact_info = await self.extract_contact_information(soup, page)
            if contact_info:
                detailed_data.update(contact_info)
            
            # 3. EXTRACT ALL IMAGES (including slideshow)
            image_urls = await self.extract_all_images(soup, property_url, page)
            if image_urls:
                detailed_data['all_images'] = image_urls
            
            # 4. EXTRACT PROPERTY FEATURES AND AMENITIES
            features = await self.extract_property_features(soup)
            if features:
                detailed_data.update(features)
            
            # 5. EXTRACT AGENT/LANDLORD DETAILS
            agent_info = await self.extract_agent_information(soup)
            if agent_info:
                detailed_data['agent_info'] = agent_info
            
            return detailed_data
            
        except Exception as e:
            if self.debug:
                logger.error(f"Error scraping property details from {property_url}: {e}")
            return None
        finally:
            await page.close()

    async def extract_contact_information(self, soup, page) -> Dict:
        """Enhanced contact information extraction with multiple strategies, now with 2captcha support"""
        contact_info = {}
        try:
            # Strategy 1: Static content extraction (existing method)
            static_contacts = await self._extract_static_contact_info(soup)
            contact_info.update(static_contacts)

            # Strategy 2: JavaScript variables extraction
            js_contacts = await self._extract_from_javascript_variables(page)
            contact_info.update(js_contacts)

            # Strategy 3: Hidden elements extraction
            hidden_contacts = await self._extract_from_hidden_elements(soup)
            contact_info.update(hidden_contacts)

            # Strategy 4: Data attributes extraction
            data_contacts = await self._extract_from_data_attributes(soup)
            contact_info.update(data_contacts)

            # Strategy 5: Network request interception
            await self._setup_network_interception(page, contact_info)

            # Strategy 6: Description pattern extraction
            desc_contacts = await self._extract_from_descriptions(soup)
            contact_info.update(desc_contacts)

            # Strategy 7: Contact button clicking (with CAPTCHA solving)
            button_contacts = await self._extract_via_button_clicks(page)
            contact_info.update(button_contacts)

            # Strategy 8: If contact info is still missing, try 2captcha solving
            if CAPTCHA_API_KEY and (not contact_info.get('phone_numbers') and not contact_info.get('email_addresses')):
                # Try to click the contact button and solve CAPTCHA if present
                contact_info.update(await self._extract_dynamic_contact_info_with_2captcha(page))

            # Clean and deduplicate contact information
            contact_info = self._clean_and_deduplicate_contacts(contact_info)
        except Exception as e:
            if self.debug:
                logger.error(f"Error extracting contact info: {e}")
        return contact_info

    async def _extract_static_contact_info(self, soup) -> Dict:
        """Extract contact info from static HTML content"""
        contact_info = {'phone_numbers': [], 'email_addresses': []}
        
        # Look for phone numbers in various formats
        page_text = soup.get_text()
        
        # Phone number patterns for Kenya
        phone_patterns = [
            r'(?:\+254|0)(?:7\d{8}|1\d{8})',  # Kenyan mobile/landline
            r'(?:\+254|0)[17]\d{8}',  # Kenyan numbers
            r'(?:Call|Phone|Tel|Contact)[:\s]*([+\d\s\-()]{10,15})',  # Labeled phone numbers
            r'(\+254\s*\d{3}\s*\d{3}\s*\d{3})',  # International format
            r'(0\d{3}\s*\d{3}\s*\d{3})',  # Local format with spaces
        ]
        
        phone_numbers = []
        for pattern in phone_patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            for match in matches:
                phone = re.sub(r'[^\d+]', '', match)  # Clean phone number
                if len(phone) >= 10 and phone not in phone_numbers:
                    phone_numbers.append(phone)
        
        if phone_numbers:
            contact_info['phone_numbers'] = phone_numbers
        
        # Look for email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, page_text)
        # Filter out common non-contact emails
        filtered_emails = [email for email in emails if not any(word in email.lower() 
                         for word in ['noreply', 'admin', 'info@property24', 'system'])]
        
        if filtered_emails:
            contact_info['email_addresses'] = list(set(filtered_emails))
        
        # Look for WhatsApp links
        whatsapp_links = soup.find_all('a', href=re.compile(r'wa\.me|whatsapp', re.I))
        if whatsapp_links:
            whatsapp_numbers = []
            for link in whatsapp_links:
                href = link.get('href', '')
                wa_match = re.search(r'(?:wa\.me/|whatsapp.*phone=)(\+?\d+)', href)
                if wa_match:
                    whatsapp_numbers.append(wa_match.group(1))
            
            if whatsapp_numbers:
                contact_info['whatsapp_numbers'] = list(set(whatsapp_numbers))
        
        return contact_info

    async def _extract_from_javascript_variables(self, page) -> Dict:
        """Extract contact info from JavaScript variables"""
        contact_info = {'js_phone_numbers': [], 'js_email_addresses': []}
        
        try:
            # Extract JavaScript variables that might contain contact info
            js_code = """
            () => {
                let contacts = {};
                
                // Look for common global variables
                const commonVars = [
                    'agentPhone', 'agentEmail', 'contactPhone', 'contactEmail',
                    'landlordPhone', 'landlordEmail', 'propertyContact',
                    'listingContact', 'agentInfo', 'contactInfo'
                ];
                
                for (const varName of commonVars) {
                    if (typeof window[varName] !== 'undefined') {
                        contacts[varName] = window[varName];
                    }
                }
                
                // Look for contact info in data objects
                if (typeof window.propertyData !== 'undefined') {
                    contacts.propertyData = window.propertyData;
                }
                
                if (typeof window.listingData !== 'undefined') {
                    contacts.listingData = window.listingData;
                }
                
                return contacts;
            }
            """
            
            js_contacts = await page.evaluate(js_code)
            
            # Extract phone numbers from JavaScript data
            js_text = json.dumps(js_contacts)
            phone_matches = re.findall(r'(\+?[\d\s\-()]{10,15})', js_text)
            for match in phone_matches:
                clean_phone = re.sub(r'[^\d+]', '', match)
                if len(clean_phone) >= 10:
                    contact_info['js_phone_numbers'].append(clean_phone)
            
            # Extract emails
            email_matches = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', js_text)
            for email in email_matches:
                if not any(word in email.lower() for word in ['noreply', 'admin', 'info@property24']):
                    contact_info['js_email_addresses'].append(email)
            
        except Exception as e:
            if self.debug:
                logger.error(f"Error extracting from JavaScript: {e}")
        
        return contact_info

    async def _extract_from_hidden_elements(self, soup) -> Dict:
        """Extract contact info from hidden elements"""
        contact_info = {'hidden_phone_numbers': [], 'hidden_email_addresses': []}
        
        try:
            # Look for hidden elements that might contain contact info
            hidden_selectors = [
                '[style*="display: none"]',
                '[style*="visibility: hidden"]',
                '[data-phone]',
                '[data-email]',
                '[data-contact]',
                '.hidden',
                '.sr-only'
            ]
            
            for selector in hidden_selectors:
                elements = soup.select(selector)
                for elem in elements:
                    # Check element text and attributes
                    text = elem.get_text()
                    for attr_name, attr_value in elem.attrs.items():
                        text += f' {attr_value}'
                    
                    # Extract phone numbers
                    phone_matches = re.findall(r'(\+?[\d\s\-()]{10,15})', text)
                    for match in phone_matches:
                        clean_phone = re.sub(r'[^\d+]', '', match)
                        if len(clean_phone) >= 10:
                            contact_info['hidden_phone_numbers'].append(clean_phone)
                    
                    # Extract emails
                    email_matches = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
                    for email in email_matches:
                        if not any(word in email.lower() for word in ['noreply', 'admin', 'info@property24']):
                            contact_info['hidden_email_addresses'].append(email)
        
        except Exception as e:
            if self.debug:
                logger.error(f"Error extracting from hidden elements: {e}")
        
        return contact_info

    async def _extract_from_data_attributes(self, soup) -> Dict:
        """Extract contact info from data attributes"""
        contact_info = {'data_phone_numbers': [], 'data_email_addresses': []}
        
        try:
            # Look for elements with data attributes
            data_elements = soup.find_all(attrs=lambda x: x and any(
                attr.startswith('data-') and any(word in attr for word in ['phone', 'email', 'contact', 'tel'])
                for attr in x.keys()
            ))
            
            for elem in data_elements:
                for attr_name, attr_value in elem.attrs.items():
                    if attr_name.startswith('data-') and isinstance(attr_value, str):
                        # Extract phone numbers
                        phone_matches = re.findall(r'(\+?[\d\s\-()]{10,15})', attr_value)
                        for match in phone_matches:
                            clean_phone = re.sub(r'[^\d+]', '', match)
                            if len(clean_phone) >= 10:
                                contact_info['data_phone_numbers'].append(clean_phone)
                        
                        # Extract emails
                        email_matches = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', attr_value)
                        for email in email_matches:
                            if not any(word in email.lower() for word in ['noreply', 'admin', 'info@property24']):
                                contact_info['data_email_addresses'].append(email)
        
        except Exception as e:
            if self.debug:
                logger.error(f"Error extracting from data attributes: {e}")
        
        return contact_info

    async def _setup_network_interception(self, page, contact_info: Dict):
        """Setup network interception for contact info"""
        try:
            async def handle_response(response):
                # Look for contact-related API calls
                if any(keyword in response.url.lower() for keyword in ['contact', 'phone', 'email', 'agent']):
                    try:
                        if response.status == 200:
                            # Try to parse JSON response
                            try:
                                data = await response.json()
                                json_text = json.dumps(data)
                                
                                # Extract phone numbers from JSON
                                phone_matches = re.findall(r'(\+?[\d\s\-()]{10,15})', json_text)
                                for match in phone_matches:
                                    clean_phone = re.sub(r'[^\d+]', '', match)
                                    if len(clean_phone) >= 10:
                                        if 'network_phone_numbers' not in contact_info:
                                            contact_info['network_phone_numbers'] = []
                                        if clean_phone not in contact_info['network_phone_numbers']:
                                            contact_info['network_phone_numbers'].append(clean_phone)
                                
                                # Extract emails
                                email_matches = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', json_text)
                                for email in email_matches:
                                    if not any(word in email.lower() for word in ['noreply', 'admin', 'info@property24']):
                                        if 'network_email_addresses' not in contact_info:
                                            contact_info['network_email_addresses'] = []
                                        if email not in contact_info['network_email_addresses']:
                                            contact_info['network_email_addresses'].append(email)
                            
                            except Exception:
                                # If not JSON, try text extraction
                                text = await response.text()
                                
                                phone_matches = re.findall(r'(\+?[\d\s\-()]{10,15})', text)
                                for match in phone_matches:
                                    clean_phone = re.sub(r'[^\d+]', '', match)
                                    if len(clean_phone) >= 10:
                                        if 'network_phone_numbers' not in contact_info:
                                            contact_info['network_phone_numbers'] = []
                                        if clean_phone not in contact_info['network_phone_numbers']:
                                            contact_info['network_phone_numbers'].append(clean_phone)
                    
                    except Exception as e:
                        if self.debug:
                            logger.debug(f"Error processing network response: {e}")
            
            page.on("response", handle_response)
            
        except Exception as e:
            if self.debug:
                logger.error(f"Error setting up network interception: {e}")

    async def _extract_from_descriptions(self, soup) -> Dict:
        """Extract contact info from property descriptions"""
        contact_info = {'description_phone_numbers': [], 'description_email_addresses': []}
        
        try:
            # Look in property description elements
            description_selectors = [
                '.property-description',
                '.listing-description',
                '.description',
                '.details',
                '.content',
                '[class*="description"]',
                '[class*="detail"]'
            ]
            
            for selector in description_selectors:
                elements = soup.select(selector)
                for elem in elements:
                    text = elem.get_text()
                    
                    # Phone patterns that might appear in descriptions
                    phone_patterns = [
                        r'(?:call|contact|phone|tel|mobile|cell)[:\s]*(\+?[\d\s\-()]{10,15})',
                        r'(?:WhatsApp|wa\.me|whatsapp)[:\s]*(\+?[\d\s\-()]{10,15})',
                        r'(\+254[\d\s\-()]{9,})',
                        r'(07\d{8})',
                        r'(01\d{8})',
                    ]
                    
                    for pattern in phone_patterns:
                        matches = re.findall(pattern, text, re.IGNORECASE)
                        for match in matches:
                            clean_phone = re.sub(r'[^\d+]', '', match)
                            if len(clean_phone) >= 10:
                                contact_info['description_phone_numbers'].append(clean_phone)
                    
                    # Email patterns
                    email_matches = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
                    for email in email_matches:
                        if not any(word in email.lower() for word in ['noreply', 'admin', 'info@property24']):
                            contact_info['description_email_addresses'].append(email)
        
        except Exception as e:
            if self.debug:
                logger.error(f"Error extracting from descriptions: {e}")
        
        return contact_info

    async def _extract_via_button_clicks(self, page) -> Dict:
        """Extract contact info by clicking contact buttons - Property24 Kenya specific"""
        contact_info = {'button_phone_numbers': [], 'button_email_addresses': []}
        
        try:
            # Property24 Kenya specific contact button selectors
            contact_button_selectors = [
                'button:contains("Show contact number")',
                'button:contains("Show contact")',
                'button:contains("Reveal contact")',
                'button:contains("Contact agent")',
                'button:contains("Call agent")',
                'a:contains("Show contact number")',
                'a:contains("Show contact")',
                'a:contains("Contact agent")',
                'a:contains("Call agent")',
                '[class*="contact"] button',
                '[class*="phone"] button',
                '[class*="call"] button',
                '.contact-button',
                '.phone-button',
                '.call-button',
                '.show-contact',
                '.reveal-contact'
            ]
            
            # Try to find and click contact buttons
            for selector in contact_button_selectors:
                try:
                    # Use JavaScript to find elements by text content
                    js_code = f"""
                    () => {{
                        const elements = document.querySelectorAll('button, a, div[role="button"]');
                        const contactElements = [];
                        
                        for (const elem of elements) {{
                            const text = elem.textContent.toLowerCase();
                            if (text.includes('show contact') || 
                                text.includes('reveal contact') || 
                                text.includes('contact agent') || 
                                text.includes('call agent') ||
                                text.includes('phone') ||
                                text.includes('call')) {{
                                contactElements.push(elem);
                            }}
                        }}
                        
                        return contactElements.length;
                    }}
                    """
                    
                    contact_elements_count = await page.evaluate(js_code)
                    
                    if contact_elements_count > 0:
                        self.stdout.write(f'🎯 Found {contact_elements_count} contact buttons')
                        
                        # Click each contact button
                        for i in range(contact_elements_count):
                            try:
                                # Click the button
                                click_js = f"""
                                () => {{
                                    const elements = document.querySelectorAll('button, a, div[role="button"]');
                                    const contactElements = [];
                                    
                                    for (const elem of elements) {{
                                        const text = elem.textContent.toLowerCase();
                                        if (text.includes('show contact') || 
                                            text.includes('reveal contact') || 
                                            text.includes('contact agent') || 
                                            text.includes('call agent') ||
                                            text.includes('phone') ||
                                            text.includes('call')) {{
                                            contactElements.push(elem);
                                        }}
                                    }}
                                    
                                    if (contactElements[{i}]) {{
                                        contactElements[{i}].click();
                                        return true;
                                    }}
                                    return false;
                                }}
                                """
                                
                                clicked = await page.evaluate(click_js)
                                
                                if clicked:
                                    self.stdout.write(f'🖱️ Clicked contact button {i+1}')
                                    
                                    # Wait for contact info to appear
                                    await page.wait_for_timeout(2000)
                                    
                                    # Check for CAPTCHA
                                    captcha_detected = await self._detect_recaptcha(page)
                                    
                                    if captcha_detected and CAPTCHA_API_KEY:
                                        self.stdout.write('🛡️ CAPTCHA detected, solving with 2captcha...')
                                        
                                        # Solve CAPTCHA with 2captcha
                                        captcha_solved = await self._solve_recaptcha_with_2captcha(page)
                                        
                                        if captcha_solved:
                                            self.stdout.write('✅ CAPTCHA solved successfully')
                                            
                                            # Wait for contact info to be revealed
                                            await page.wait_for_timeout(3000)
                                            
                                            # Extract revealed contact info
                                            revealed_contacts = await self._extract_revealed_contacts(page)
                                            contact_info.update(revealed_contacts)
                                        else:
                                            self.stdout.write('❌ Failed to solve CAPTCHA')
                                    else:
                                        # No CAPTCHA, extract contact info directly
                                        revealed_contacts = await self._extract_revealed_contacts(page)
                                        contact_info.update(revealed_contacts)
                                    
                                    # Check if we got contact info
                                    if contact_info.get('phone_numbers') or contact_info.get('email_addresses'):
                                        self.stdout.write('✅ Contact info extracted successfully')
                                        break
                                
                            except Exception as e:
                                if self.debug:
                                    self.stdout.write(f'⚠️ Error clicking contact button {i+1}: {e}')
                                continue
                        
                        # If we found contact info, break out of selector loop
                        if contact_info.get('phone_numbers') or contact_info.get('email_addresses'):
                            break
                    
                except Exception as e:
                    if self.debug:
                        self.stdout.write(f'⚠️ Error with selector {selector}: {e}')
                    continue
            
        except Exception as e:
            if self.debug:
                self.stdout.write(f'❌ Error in button click extraction: {e}')
        
        return contact_info

    async def _detect_recaptcha(self, page) -> bool:
        """Detect if reCAPTCHA is present on page"""
        try:
            # Method 1: Check for reCAPTCHA elements
            recaptcha_selectors = [
                '.g-recaptcha',
                '#g-recaptcha',
                '[data-sitekey]',
                'iframe[src*="recaptcha"]',
                '.recaptcha',
                '#recaptcha',
                'iframe[src*="google.com/recaptcha"]',
                'div[class*="recaptcha"]',
                'div[id*="recaptcha"]'
            ]
            
            for selector in recaptcha_selectors:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    if self.debug:
                        self.stdout.write(f'🛡️ CAPTCHA detected via selector: {selector}')
                    return True
            
            # Method 2: Check page source for reCAPTCHA references
            content = await page.content()
            recaptcha_indicators = [
                'recaptcha',
                'g-recaptcha',
                'data-sitekey',
                'google.com/recaptcha',
                'recaptcha/api'
            ]
            
            for indicator in recaptcha_indicators:
                if indicator.lower() in content.lower():
                    if self.debug:
                        self.stdout.write(f'🛡️ CAPTCHA detected via page source: {indicator}')
                    return True
            
            # Method 3: Check for CAPTCHA-related text
            page_text = await page.text_content()
            captcha_text_indicators = [
                'captcha',
                'verify you are human',
                'i am not a robot',
                'security check',
                'prove you are human'
            ]
            
            for indicator in captcha_text_indicators:
                if indicator.lower() in page_text.lower():
                    if self.debug:
                        self.stdout.write(f'🛡️ CAPTCHA detected via text: {indicator}')
                    return True
            
            return False
            
        except Exception as e:
            if self.debug:
                self.stdout.write(f'❌ Error detecting reCAPTCHA: {e}')
            return False

    def _clean_and_deduplicate_contacts(self, contact_info: Dict) -> Dict:
        """Clean and deduplicate contact information"""
        cleaned_contacts = {}
        
        # Combine all phone numbers
        all_phones = []
        for key, value in contact_info.items():
            if 'phone' in key.lower() and isinstance(value, list):
                all_phones.extend(value)
        
        # Clean and deduplicate phones
        cleaned_phones = []
        for phone in all_phones:
            clean_phone = re.sub(r'[^\d+]', '', str(phone))
            if len(clean_phone) >= 10 and clean_phone not in cleaned_phones:
                # Standardize Kenyan numbers
                if clean_phone.startswith('0'):
                    clean_phone = '+254' + clean_phone[1:]
                elif clean_phone.startswith('254'):
                    clean_phone = '+' + clean_phone
                cleaned_phones.append(clean_phone)
        
        if cleaned_phones:
            cleaned_contacts['phone_numbers'] = cleaned_phones
        
        # Combine all email addresses
        all_emails = []
        for key, value in contact_info.items():
            if 'email' in key.lower() and isinstance(value, list):
                all_emails.extend(value)
        
        # Clean and deduplicate emails
        cleaned_emails = []
        for email in all_emails:
            email = str(email).lower().strip()
            if email and email not in cleaned_emails:
                # Validate email format
                if re.match(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$', email, re.IGNORECASE):
                    cleaned_emails.append(email)
        
        if cleaned_emails:
            cleaned_contacts['email_addresses'] = cleaned_emails
        
        # Combine WhatsApp numbers
        whatsapp_numbers = contact_info.get('whatsapp_numbers', [])
        if whatsapp_numbers:
            cleaned_contacts['whatsapp_numbers'] = list(set(whatsapp_numbers))
        
        return cleaned_contacts

    async def extract_all_images(self, soup, base_url: str, page=None) -> List[str]:
        """Extract all property images including slideshow images"""
        image_urls = []
        
        try:
            # Method 1: Extract static images
            static_images = await self._extract_static_images(soup, base_url)
            image_urls.extend(static_images)
            
            # Method 2: Extract slideshow images (if page is provided)
            slideshow_images = []
            if page:
                slideshow_images = await self._extract_slideshow_images(page)
                image_urls.extend(slideshow_images)
            
            # Remove duplicates
            unique_images = list(set(image_urls))
            
            if self.debug:
                self.stdout.write(f"📸 Found {len(unique_images)} total images ({len(static_images)} static, {len(slideshow_images)} slideshow)")
                for i, img_url in enumerate(unique_images[:3]):
                    self.stdout.write(f"  Image {i+1}: {img_url}")
            
            return unique_images
            
        except Exception as e:
            if self.debug:
                logger.error(f"Error extracting images: {e}")
            return []

    async def _extract_static_images(self, soup, base_url: str) -> List[str]:
        """Extract static images from the page"""
        image_urls = []
        
        try:
            # Use the correct selector for Property24 Kenya images
            image_selectors = [
                'img[src*="static.sa-property"]',  # Main Property24 images
                'img[src*="property24"]',  # Alternative Property24 images
                'img[data-src*="static.sa-property"]',  # Lazy-loaded images
                'img[data-lazy*="static.sa-property"]',  # Alternative lazy loading
                'img[src*="images.prop24.com"]',  # Property24 image CDN
            ]
            
            for selector in image_selectors:
                images = soup.select(selector)
                for img in images:
                    src = img.get('src') or img.get('data-src') or img.get('data-lazy')
                    if src:
                        # Filter out non-property images (logos, icons, etc.)
                        if not any(exclude in src.lower() for exclude in [
                            'close_grey', 'navbar_caret', 'logo', 'icon', 'button', 'arrow'
                        ]):
                            # Ensure URL is absolute
                            if src.startswith('//'):
                                src = 'https:' + src
                            elif src.startswith('/'):
                                src = urljoin(base_url, src)
                            elif not src.startswith('http'):
                                src = urljoin(base_url, src)
                            
                            if src not in image_urls:
                                image_urls.append(src)
            
            return image_urls
            
        except Exception as e:
            if self.debug:
                logger.error(f"Error extracting static images: {e}")
            return []

    async def _extract_slideshow_images(self, page) -> List[str]:
        """Extract all slideshow images by clicking and navigating"""
        image_urls = []
        
        try:
            # Step 1: Try to open slideshow modal
            try:
                await page.click('.js_lightboxImageSrc')
                await page.wait_for_timeout(3000)
                if self.debug:
                    self.stdout.write("   ✅ Slideshow modal opened")
            except Exception as e:
                if self.debug:
                    self.stdout.write(f"   ❌ Failed to open slideshow: {e}")
                return image_urls
            
            # Step 2: Extract all images from modal
            modal_images = await page.evaluate("""
                () => {
                    const images = [];
                    
                    // Get ALL images from modal (including hidden)
                    const allModalImages = document.querySelectorAll('.p24_modal img, .modal img, .lightbox img, .js_lightboxImageWrapper img');
                    allModalImages.forEach((img, index) => {
                        const src = img.src || img.dataset.src || img.dataset.lazy || img.dataset.original;
                        if (src && src.includes('images.prop24.com')) {
                            images.push(src);
                        }
                    });
                    
                    // Get background images from all modal elements
                    const allModalElements = document.querySelectorAll('.p24_modal *, .modal *, .lightbox *, .js_lightboxImageWrapper *');
                    allModalElements.forEach((el, index) => {
                        const style = window.getComputedStyle(el);
                        const bgImage = style.backgroundImage;
                        if (bgImage && bgImage !== 'none' && bgImage.includes('images.prop24.com')) {
                            const url = bgImage.replace(/url\\(['"]?([^'"]+)['"]?\\)/, '$1');
                            images.push(url);
                        }
                    });
                    
                    return images;
                }
            """)
            
            image_urls.extend(modal_images)
            
            # Step 3: Try JavaScript navigation to get more images
            navigation_attempts = 0
            max_attempts = 10
            
            while navigation_attempts < max_attempts:
                navigation_attempts += 1
                
                try:
                    # Try JavaScript next navigation
                    next_result = await page.evaluate("""
                        () => {
                            const nextSelectors = ['.p24_next', '.js_pp_next', '.js_lightboxNext', '[id="nextImage"]'];
                            for (const selector of nextSelectors) {
                                const element = document.querySelector(selector);
                                if (element) {
                                    try {
                                        element.click();
                                        return { success: true, selector: selector };
                                    } catch (e) {
                                        const clickEvent = new MouseEvent('click', {
                                            bubbles: true,
                                            cancelable: true,
                                            view: window
                                        });
                                        element.dispatchEvent(clickEvent);
                                        return { success: true, selector: selector };
                                    }
                                }
                            }
                            return { success: false };
                        }
                    """)
                    
                    if next_result.get('success'):
                        await page.wait_for_timeout(2000)
                        
                        # Extract new images after navigation
                        new_images = await page.evaluate("""
                            () => {
                                const images = [];
                                const modalImages = document.querySelectorAll('.p24_modal img, .modal img, .lightbox img');
                                modalImages.forEach((img, index) => {
                                    const src = img.src || img.dataset.src || img.dataset.lazy || img.dataset.original;
                                    if (src && src.includes('images.prop24.com')) {
                                        images.push(src);
                                    }
                                });
                                return images;
                            }
                        """)
                        
                        for img_url in new_images:
                            if img_url not in image_urls:
                                image_urls.append(img_url)
                    else:
                        break
                        
                except Exception as e:
                    if self.debug:
                        self.stdout.write(f"   ❌ Navigation error: {e}")
                    break
            
            if self.debug:
                self.stdout.write(f"   📸 Extracted {len(image_urls)} slideshow images")
            
            return image_urls
            
        except Exception as e:
            if self.debug:
                logger.error(f"Error extracting slideshow images: {e}")
            return []

    async def _crop_image_watermark(self, image_url: str) -> Optional[Dict]:
        """Download and crop image to remove watermark"""
        try:
            import requests
            from PIL import Image
            import io
            import base64
            
            # Download image
            response = requests.get(image_url, timeout=30)
            if response.status_code != 200:
                return None
            
            # Open with PIL
            img = Image.open(io.BytesIO(response.content))
            
            # Convert RGBA to RGB if needed
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            
            # Crop bottom 4% (remove watermark)
            width, height = img.size
            crop_height = int(height * 0.96)  # Keep 96%, remove bottom 4%
            
            cropped = img.crop((0, 0, width, crop_height))
            
            # Convert to base64 for storage
            img_buffer = io.BytesIO()
            cropped.save(img_buffer, format='JPEG', quality=85)
            img_buffer.seek(0)
            base64_data = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
            
            return {
                'original_url': image_url,
                'cropped_width': cropped.width,
                'cropped_height': cropped.height,
                'original_width': width,
                'original_height': height,
                'image_data': base64_data,
                'format': 'JPEG'
            }
            
        except Exception as e:
            if self.debug:
                logger.error(f"Error cropping image {image_url}: {e}")
            return None

    async def extract_property_features(self, soup) -> Dict:
        """Extract detailed property features and amenities"""
        features = {}
        
        try:
            page_text = soup.get_text().lower()
            
            # Extract detailed property information
            # Parking details
            parking_match = re.search(r'(\d+)\s*(?:parking|garage|carport)', page_text)
            if parking_match:
                features['parking_spaces'] = int(parking_match.group(1))
            
            # Swimming pool
            if any(word in page_text for word in ['pool', 'swimming']):
                features['has_pool'] = True
            
            # Garden
            if any(word in page_text for word in ['garden', 'yard', 'landscaped']):
                features['has_garden'] = True
            
            # Security features
            security_features = []
            security_terms = ['security', 'alarm', 'cctv', 'gate', 'fence', 'guard']
            for term in security_terms:
                if term in page_text:
                    security_features.append(term)
            
            if security_features:
                features['security_features'] = security_features
            
            # Furnished status
            if any(word in page_text for word in ['furnished', 'furniture']):
                if 'unfurnished' in page_text:
                    features['furnished'] = 'unfurnished'
                elif 'semi-furnished' in page_text:
                    features['furnished'] = 'semi-furnished'
                else:
                    features['furnished'] = 'furnished'
            
            # Utilities included
            utilities = []
            if 'water' in page_text and any(word in page_text for word in ['included', 'free']):
                utilities.append('water')
            if 'electricity' in page_text and any(word in page_text for word in ['included', 'free']):
                utilities.append('electricity')
            if 'internet' in page_text or 'wifi' in page_text:
                utilities.append('internet')
            
            if utilities:
                features['utilities_included'] = utilities
            
        except Exception as e:
            if self.debug:
                logger.error(f"Error extracting features: {e}")
        
        return features

    async def extract_agent_information(self, soup) -> Dict:
        """Extract agent/landlord contact information"""
        agent_info = {}
        
        try:
            # Look for agent sections
            agent_selectors = [
                '.agent-info',
                '.contact-agent',
                '.landlord-info',
                '[class*="agent"]',
                '.property-contact'
            ]
            
            for selector in agent_selectors:
                agent_elem = soup.select_one(selector)
                if agent_elem:
                    agent_text = agent_elem.get_text()
                    
                    # Extract agent name
                    name_elem = agent_elem.find(['h3', 'h4', 'h5', 'strong', 'b'])
                    if name_elem:
                        agent_info['agent_name'] = name_elem.get_text(strip=True)
                    
                    # Extract agent phone
                    phone_match = re.search(r'(\+?[\d\s\-()]{10,15})', agent_text)
                    if phone_match:
                        agent_info['agent_phone'] = re.sub(r'[^\d+]', '', phone_match.group())
                    
                    # Extract agent email
                    email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', agent_text)
                    if email_match:
                        agent_info['agent_email'] = email_match.group()
                    
                    break
            
        except Exception as e:
            if self.debug:
                logger.error(f"Error extracting agent info: {e}")
        
        return agent_info

    async def bulk_save_properties(self, properties: List[Dict]) -> int:
        """Save properties to database in bulk"""
        if not properties:
            return 0
        
        # Use sync_to_async to handle database operations
        return await sync_to_async(self._save_properties_sync)(properties)
    
    def _save_properties_sync(self, properties: List[Dict]) -> int:
        """Synchronous method to save properties to database"""
        saved_count = 0
        
        with transaction.atomic():
            for prop_data in properties:
                try:
                    # Skip if missing critical data
                    if not prop_data.get('rent_amount'):
                        continue
                    
                    # Extract external_id from property URL
                    property_url = prop_data.get('url', '')
                    external_id = self._extract_property_id(property_url)
                    if not external_id:
                        continue
                    
                    # Format location
                    location_text = prop_data.get('location', 'Unknown, Nairobi')
                    if not isinstance(location_text, str):
                        location_text = 'Unknown, Nairobi'
                    
                    # Create property with new model structure
                    property_obj, created = Property.objects.update_or_create(
                        source=self.source,
                        external_id=external_id,
                        defaults={
                            'title': prop_data.get('title', '')[:255],
                            'price': prop_data['rent_amount'],
                            'location': location_text[:255],
                            'property_type': prop_data.get('property_type', 'other')[:50],
                        }
                    )
                    
                    # Save property details
                    self._save_property_details(property_obj, prop_data)
                    
                    # Save images
                    self._save_property_images(property_obj, prop_data)
                    
                    # Save contact information
                    self._save_contact_info(property_obj, prop_data)
                    
                    # Log success
                    contact_summary = ""
                    if 'phone_numbers' in prop_data:
                        contact_summary = f" | {len(prop_data['phone_numbers'])} phone(s)"
                    if 'email_addresses' in prop_data:
                        contact_summary += f" | {len(prop_data['email_addresses'])} email(s)"
                    
                    action = "Updated" if not created else "Created"
                    self.stdout.write(
                        f'✅ {action}: {property_obj.title} - KSh{property_obj.price:,.0f} in {property_obj.location}{contact_summary}'
                    )
                    saved_count += 1
                    
                except Exception as e:
                    if self.debug:
                        logger.error(f"Error saving property: {e}")
                    continue
        
        return saved_count

    def _extract_property_id(self, url: str) -> Optional[str]:
        """Extract property ID from URL"""
        if not url:
            return None
        
        # Try to extract ID from URL patterns
        patterns = [
            r'property-(\d+)',  # matches property-123456
            r'listing/(\d+)',   # matches listing/123456
            r'-(\d{6,})$',      # matches any 6+ digit number at end
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        # Fallback: use URL path as ID
        parsed = urlparse(url)
        path = parsed.path.strip('/')
        if path:
            return path[:100]  # Limit length
        
        return None

    def _save_property_details(self, property_obj: Property, prop_data: Dict):
        """Save property details"""
        # Map of property attributes to save as details
        detail_mappings = {
            'bedrooms': 'bedrooms',
            'bathrooms': 'bathrooms',
            'parking_spaces': 'parking',
            'square_meters': 'size',
            'furnished': 'furnished',
            'utilities_included': 'utilities',
            'has_pool': 'pool',
            'has_garden': 'garden',
        }
        
        # Clear existing details to prevent duplicates
        property_obj.details.all().delete()
        
        # Save mapped details
        for prop_key, detail_key in detail_mappings.items():
            value = prop_data.get(prop_key)
            if value is not None:
                if isinstance(value, bool):
                    value = 'Yes' if value else 'No'
                elif isinstance(value, (list, tuple)):
                    value = ', '.join(map(str, value))
                else:
                    value = str(value)
                
                PropertyDetail.objects.create(
                    property=property_obj,
                    key=detail_key,
                    value=value
                )
        
        # Save any security features
        if 'security_features' in prop_data:
            features = prop_data['security_features']
            if isinstance(features, (list, tuple)):
                PropertyDetail.objects.create(
                    property=property_obj,
                    key='security',
                    value=', '.join(features)
                )

    def _save_property_images(self, property_obj: Property, prop_data: Dict):
        """Save property images with watermark cropping"""
        # Clear existing images to prevent duplicates
        property_obj.images.all().delete()
        
        # Save all images if available
        if 'all_images' in prop_data and prop_data['all_images']:
            for i, img_url in enumerate(prop_data['all_images'][:10]):  # Limit to 10 images
                try:
                    # Try to crop watermark from image
                    cropped_data = None
                    try:
                        # Import here to avoid dependency issues
                        import asyncio
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        cropped_data = loop.run_until_complete(self._crop_image_watermark(img_url))
                        loop.close()
                    except Exception as crop_error:
                        if self.debug:
                            logger.error(f"Error cropping image {img_url}: {crop_error}")
                    
                    if cropped_data:
                        # Save cropped image data
                        Image.objects.create(
                            property=property_obj,
                            url=img_url,
                            is_thumbnail=(i == 0),  # First image is thumbnail
                            # Store cropped data in additional fields if available
                            # Note: You may need to add these fields to your Image model
                            # cropped_data=cropped_data['image_data'],
                            # cropped_width=cropped_data['cropped_width'],
                            # cropped_height=cropped_data['cropped_height']
                        )
                        if self.debug:
                            self.stdout.write(f"   ✅ Saved cropped image {i+1}: {cropped_data['cropped_width']}x{cropped_data['cropped_height']}")
                    else:
                        # Save original image if cropping failed
                        Image.objects.create(
                            property=property_obj,
                            url=img_url,
                            is_thumbnail=(i == 0)  # First image is thumbnail
                        )
                        if self.debug:
                            self.stdout.write(f"   📸 Saved original image {i+1}")
                            
                except Exception as e:
                    if self.debug:
                        logger.error(f"Error saving image {img_url}: {e}")
        
        # Fallback to single image
        elif 'image_url' in prop_data and prop_data['image_url']:
            try:
                Image.objects.create(
                    property=property_obj,
                    url=prop_data['image_url'],
                    is_thumbnail=True
                )
            except Exception as e:
                if self.debug:
                    logger.error(f"Error saving image: {e}")

    def _save_contact_info(self, property_obj: Property, prop_data: Dict):
        """Save contact information"""
        # Clear existing contacts to prevent duplicates
        property_obj.contacts.all().delete()
        
        # Save agent info if available
        if 'agent_info' in prop_data:
            agent = prop_data['agent_info']
            if any(agent.get(key) for key in ['agent_name', 'agent_phone', 'agent_email']):
                Contact.objects.create(
                    property=property_obj,
                    name=agent.get('agent_name', ''),
                    phone=agent.get('agent_phone', ''),
                    email=agent.get('agent_email', '')
                )
        
        # Save other contact information
        phones = prop_data.get('phone_numbers', [])
        emails = prop_data.get('email_addresses', [])
        
        # Create contact entries for each unique combination
        for i in range(max(len(phones), len(emails))):
            phone = phones[i] if i < len(phones) else ''
            email = emails[i] if i < len(emails) else ''
            
            if phone or email:
                Contact.objects.create(
                    property=property_obj,
                    phone=phone,
                    email=email
                ) 

    async def _extract_dynamic_contact_info_with_2captcha(self, page) -> dict:
        """Extract contact info that requires CAPTCHA solving using 2captcha"""
        contact_info = {'dynamic_phone_numbers': [], 'dynamic_emails': []}
        try:
            # Look for contact buttons
            contact_buttons = await page.query_selector_all('.ShowContact, text="Show Contact Number"')
            if not contact_buttons:
                if self.debug:
                    logger.info("No contact buttons found for 2captcha flow")
                return contact_info
            if self.debug:
                logger.info(f"Found {len(contact_buttons)} contact buttons for 2captcha flow")
            await contact_buttons[0].click()
            await page.wait_for_timeout(2000)
            # Check for reCAPTCHA
            recaptcha_present = await self._detect_recaptcha(page)
            if recaptcha_present:
                if self.debug:
                    logger.info("reCAPTCHA detected - attempting automated solving with 2captcha")
                solved = await self._solve_recaptcha_with_2captcha(page)
                if solved:
                    if self.debug:
                        logger.info("reCAPTCHA solved successfully via 2captcha")
                    await page.wait_for_timeout(3000)
                    # Extract revealed contact info
                    revealed_contacts = await self._extract_revealed_contacts(page)
                    contact_info.update(revealed_contacts)
                else:
                    if self.debug:
                        logger.error("Failed to solve reCAPTCHA with 2captcha")
            return contact_info
        except Exception as e:
            if self.debug:
                logger.error(f"Error extracting dynamic contact info with 2captcha: {e}")
            return contact_info

    async def _solve_recaptcha_with_2captcha(self, page) -> bool:
        """Solve reCAPTCHA using 2captcha service - using proven working implementation"""
        try:
            # Get reCAPTCHA site key
            site_key = await self._get_recaptcha_site_key(page)
            if not site_key:
                if self.debug:
                    self.stdout.write("❌ Could not find reCAPTCHA site key")
                return False
            
            self.stdout.write(f"🔑 Found reCAPTCHA site key: {site_key[:20]}...")
            
            # Submit CAPTCHA to 2captcha
            captcha_id = await self._submit_captcha_to_2captcha(page.url, site_key)
            if not captcha_id:
                return False
            
            # Wait for solution
            solution = await self._get_captcha_solution(captcha_id)
            if not solution:
                return False
            
            # Submit solution to page
            return await self._submit_captcha_solution(page, solution)
            
        except Exception as e:
            if self.debug:
                self.stdout.write(f"❌ Error solving reCAPTCHA with 2captcha: {e}")
            return False

    async def _get_recaptcha_site_key(self, page) -> str:
        """Extract reCAPTCHA site key from page - using proven method"""
        try:
            # Look for reCAPTCHA elements
            recaptcha_elements = await page.query_selector_all('[data-sitekey]')
            if recaptcha_elements:
                site_key = await recaptcha_elements[0].get_attribute('data-sitekey')
                return site_key
            
            # Alternative: extract from page source
            content = await page.content()
            site_key_match = re.search(r'data-sitekey="([^"]+)"', content)
            if site_key_match:
                return site_key_match.group(1)
            
            return None
            
        except Exception as e:
            if self.debug:
                self.stdout.write(f"❌ Error getting reCAPTCHA site key: {e}")
            return None

    async def _submit_captcha_to_2captcha(self, page_url: str, site_key: str) -> str:
        """Submit CAPTCHA to 2captcha service - using proven working method"""
        try:
            import requests
            
            submit_url = "http://2captcha.com/in.php"
            
            data = {
                'key': CAPTCHA_API_KEY,
                'method': 'userrecaptcha',
                'googlekey': site_key,
                'pageurl': page_url,
                'soft_id': 'Property24Scraper',  # Helps with solving speed
                'json': 1  # Get JSON response for better error handling
            }
            
            response = requests.post(submit_url, data=data, timeout=30)
            
            # Handle JSON response
            if response.status_code != 200:
                if self.debug:
                    self.stdout.write(f"❌ Submit failed with status {response.status_code}")
                return None
            
            try:
                result = response.json()
                if result.get('status') == 1:
                    captcha_id = result.get('request')
                    if self.debug:
                        self.stdout.write(f"✅ CAPTCHA submitted (ID: {captcha_id})")
                    return captcha_id
                else:
                    if self.debug:
                        self.stdout.write(f"❌ Submit failed: {result.get('error_text', 'Unknown error')}")
                    return None
            except:
                # Fallback to text response
                if not response.text.startswith('OK|'):
                    if self.debug:
                        self.stdout.write(f"❌ Submit failed: {response.text}")
                    return None
                captcha_id = response.text.split('|')[1]
                if self.debug:
                    self.stdout.write(f"✅ CAPTCHA submitted (ID: {captcha_id})")
                return captcha_id
                
        except Exception as e:
            if self.debug:
                self.stdout.write(f"❌ Error submitting CAPTCHA: {e}")
            return None

    async def _get_captcha_solution(self, captcha_id: str) -> str:
        """Get CAPTCHA solution from 2captcha - using proven working method"""
        try:
            import requests
            
            result_url = "http://2captcha.com/res.php"
            
            # Wait for solution with optimized polling (2 seconds instead of 5)
            for attempt in range(60):  # 60 * 2 seconds = 2 minutes max
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
                        solution = result.get('request')
                        if self.debug:
                            self.stdout.write("✅ CAPTCHA solved!")
                        return solution
                    elif result.get('request') == 'CAPCHA_NOT_READY':
                        if attempt % 10 == 0:  # Print progress every 10 attempts (20 seconds)
                            if self.debug:
                                self.stdout.write(f"⏳ Still waiting... ({attempt + 1}/60)")
                        continue
                    else:
                        if self.debug:
                            self.stdout.write(f"❌ Error: {result.get('error_text', 'Unknown error')}")
                        return None
                except:
                    # Fallback to text response
                    if response.text.startswith('OK|'):
                        solution = response.text.split('|')[1]
                        if self.debug:
                            self.stdout.write("✅ CAPTCHA solved!")
                        return solution
                    elif response.text == 'CAPCHA_NOT_READY':
                        if attempt % 10 == 0:
                            if self.debug:
                                self.stdout.write(f"⏳ Still waiting... ({attempt + 1}/60)")
                        continue
                    else:
                        if self.debug:
                            self.stdout.write(f"❌ Error: {response.text}")
                        return None
            
            if self.debug:
                self.stdout.write("⏰ Timeout waiting for solution (2 minutes)")
            return None
            
        except Exception as e:
            if self.debug:
                self.stdout.write(f"❌ Error getting CAPTCHA solution: {e}")
            return None

    async def _submit_captcha_solution(self, page, solution: str) -> bool:
        """Submit CAPTCHA solution to the page - using proven working method"""
        try:
            if self.debug:
                self.stdout.write("🎯 Injecting solution with multiple methods...")
            
            # Method 1: Set textarea value
            js_code1 = f"""
            (() => {{
                const textarea = document.querySelector('textarea[name="g-recaptcha-response"]');
                if (textarea) {{
                    textarea.value = '{solution}';
                    textarea.style.display = 'block';
                    console.log('✅ Textarea value set');
                    return 'textarea_set';
                }}
                return 'textarea_not_found';
            }})()
            """
            
            result1 = await page.evaluate(js_code1)
            if self.debug:
                self.stdout.write(f"   Method 1 (textarea): {result1}")
            
            # Method 2: Trigger reCAPTCHA callback
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
            if self.debug:
                self.stdout.write(f"   Method 2 (callback): {result2}")
            
            # Method 3: Set global reCAPTCHA response
            js_code3 = f"""
            (() => {{
                if (typeof window.grecaptcha !== 'undefined') {{
                    window.grecaptcha.getResponse = function() {{ return '{solution}'; }};
                    console.log('✅ Global response set');
                    return 'global_set';
                }}
                return 'grecaptcha_not_found';
            }})()
            """
            
            result3 = await page.evaluate(js_code3)
            if self.debug:
                self.stdout.write(f"   Method 3 (global): {result3}")
            
            # Method 4: Try to submit any forms with reCAPTCHA
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
                            console.log('✅ Form submitted');
                            return 'form_submitted';
                        }}
                    }}
                }}
                return 'no_form_found';
            }})()
            """
            
            result4 = await page.evaluate(js_code4)
            if self.debug:
                self.stdout.write(f"   Method 4 (form): {result4}")
            
            await page.wait_for_timeout(2000)
            
            # Check if CAPTCHA was accepted
            return await self._verify_captcha_solution(page)
            
        except Exception as e:
            if self.debug:
                self.stdout.write(f"❌ Error submitting CAPTCHA solution: {e}")
            return False

    async def _verify_captcha_solution(self, page) -> bool:
        """Verify if CAPTCHA solution was accepted - using proven method"""
        try:
            # Look for signs that CAPTCHA was solved
            # This depends on Property24's implementation
            
            # Method 1: Check if reCAPTCHA element is no longer visible
            recaptcha_visible = await page.is_visible('.g-recaptcha')
            if not recaptcha_visible:
                return True
            
            # Method 2: Check for success indicators
            success_indicators = [
                '.contact-revealed',
                '.phone-revealed',
                '.captcha-success'
            ]
            
            for indicator in success_indicators:
                if await page.is_visible(indicator):
                    return True
            
            # Method 3: Check if contact info has been revealed
            phone_elements = await page.query_selector_all('.agentPhone')
            for elem in phone_elements:
                text = await elem.text_content()
                if re.search(r'\+?\d{10,}', text):
                    return True
            
            return False
            
        except Exception as e:
            if self.debug:
                self.stdout.write(f"❌ Error verifying CAPTCHA solution: {e}")
            return False

    async def _extract_revealed_contacts(self, page) -> dict:
        """Extract revealed contact information after CAPTCHA solving - using proven working method"""
        contact_info = {'dynamic_phone_numbers': [], 'dynamic_emails': []}
        
        try:
            if self.debug:
                self.stdout.write("🔍 Extracting revealed contacts with multiple strategies...")
            
            # Strategy 1: Check for dynamic content
            if self.debug:
                self.stdout.write("   🔍 Strategy 1: Checking for dynamic content...")
            
            # Look for contact-specific elements
            contact_selectors = [
                '.agentPhone',
                '.contactPhone',
                '.contact-info',
                '.phone-number',
                '[class*="phone"]',
                '[class*="contact"]',
                '.ShowContact + *',  # Element after contact button
                '.contact-details'
            ]
            
            for selector in contact_selectors:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    text = await element.inner_text()
                    if text.strip():
                        if self.debug:
                            self.stdout.write(f"      Found element {selector}: {text}")
            
            # Strategy 2: Full page text extraction
            if self.debug:
                self.stdout.write("   🔍 Strategy 2: Full page text extraction...")
            
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            page_text = soup.get_text()
            
            # Extract phone numbers with proven patterns
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
                    if len(clean_phone) >= 10 and clean_phone not in contact_info['dynamic_phone_numbers']:
                        contact_info['dynamic_phone_numbers'].append(clean_phone)
                        if self.debug:
                            self.stdout.write(f"      📞 Found phone: {clean_phone}")
            
            # Extract emails
            email_matches = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', page_text)
            for email in email_matches:
                if (email.lower() not in contact_info['dynamic_emails'] and 
                    not any(word in email.lower() for word in ['noreply', 'admin', 'info@property24'])):
                    contact_info['dynamic_emails'].append(email.lower())
                    if self.debug:
                        self.stdout.write(f"      📧 Found email: {email}")
            
            # Strategy 3: Check for iframes
            if self.debug:
                self.stdout.write("   🔍 Strategy 3: Checking iframes...")
            
            iframes = await page.query_selector_all('iframe')
            for iframe in iframes:
                try:
                    iframe_src = await iframe.get_attribute('src')
                    if iframe_src and ('contact' in iframe_src.lower() or 'phone' in iframe_src.lower()):
                        if self.debug:
                            self.stdout.write(f"      Found contact iframe: {iframe_src}")
                except:
                    continue
            
            if self.debug:
                self.stdout.write(f"   📊 Extracted {len(contact_info['dynamic_phone_numbers'])} phones, {len(contact_info['dynamic_emails'])} emails")
            
        except Exception as e:
            if self.debug:
                self.stdout.write(f"Error in improved contact extraction: {e}")
        
        return contact_info