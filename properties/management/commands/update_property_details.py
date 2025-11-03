import asyncio
import re
from urllib.parse import urlparse

from django.core.management.base import BaseCommand
from django.utils import timezone
from asgiref.sync import sync_to_async

from playwright.async_api import async_playwright

from properties.models import Property, PropertyDetail


def parse_external_id(detail_url: str) -> str:
    path = urlparse(detail_url).path.rstrip("/")
    m = re.search(r"-(\d{6,})$", path)
    return m.group(1) if m else path.split("-")[-1]


class Command(BaseCommand):
    help = "Update existing Property records with detailed information from their detail pages"

    def add_arguments(self, parser):
        parser.add_argument("--property-ids", nargs="+", help="Specific external IDs to update (optional)")
        parser.add_argument("--listing-page", type=int, help="Update all properties from specific listing page")
        parser.add_argument("--limit", type=int, default=50, help="Maximum number of properties to update")
        parser.add_argument("--headless", action="store_true", default=True, help="Run browser headless")
        parser.add_argument("--no-headless", action="store_true", help="Run browser headed")

    def handle(self, *args, **options):
        property_ids = options.get("property_ids")
        listing_page = options.get("listing_page")
        limit = options["limit"]
        headless = options["headless"] and not options["no_headless"]

        asyncio.run(self.update_properties(property_ids, listing_page, limit, headless))

    async def update_properties(self, property_ids, listing_page, limit, headless):
        # Get properties to update
        if property_ids:
            properties = await sync_to_async(list)(
                Property.objects.filter(external_id__in=property_ids)
            )
        elif listing_page:
            properties = await sync_to_async(list)(
                Property.objects.filter(listing_page=listing_page)[:limit]
            )
        else:
            properties = await sync_to_async(list)(
                Property.objects.filter(detail_url__isnull=False)[:limit]
            )

        if not properties:
            self.stdout.write(self.style.WARNING("No properties found to update"))
            return

        self.stdout.write(self.style.SUCCESS(f"Found {len(properties)} properties to update"))

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context(viewport={"width": 1366, "height": 900})
            page = await context.new_page()

            updated = 0
            failed = 0

            for i, prop in enumerate(properties, 1):
                self.stdout.write(f"[{i}/{len(properties)}] Updating {prop.external_id}...")
                
                try:
                    await page.goto(prop.detail_url, wait_until="domcontentloaded")
                    await page.wait_for_load_state("networkidle")
                    await self.accept_overlays(page)

                    # Extract detailed information
                    details = await self.extract_property_details(page)
                    
                    # Update Property record
                    await self.update_property_record(prop, details)
                    
                    # Create/update PropertyDetail records
                    await self.update_property_details(prop, details)
                    
                    updated += 1
                    self.stdout.write(self.style.SUCCESS(f"  ✅ Updated {prop.external_id}"))
                    
                except Exception as e:
                    failed += 1
                    self.stdout.write(self.style.ERROR(f"  ❌ Failed {prop.external_id}: {str(e)}"))

            await browser.close()
            
            self.stdout.write(self.style.SUCCESS(f"\n=== UPDATE COMPLETE ==="))
            self.stdout.write(f"Updated: {updated}")
            self.stdout.write(f"Failed: {failed}")

    async def accept_overlays(self, page):
        """Dismiss common overlays that might block content"""
        try:
            # Cookie banner
            cookie_btn = page.locator('button:has-text("Accept"), button:has-text("OK"), [data-testid="cookie-accept"]').first
            if await cookie_btn.count() > 0:
                await cookie_btn.click()
                await page.wait_for_timeout(1000)
        except:
            pass

        try:
            # Sign in required popup
            signin_close = page.locator('button:has-text("×"), [aria-label="Close"], .close').first
            if await signin_close.count() > 0:
                await signin_close.click()
                await page.wait_for_timeout(1000)
        except:
            pass

    async def extract_property_details(self, page):
        """Extract detailed property information from the page"""
        return await page.evaluate('''() => {
            const getText = (selector) => {
                const el = document.querySelector(selector);
                return el ? el.textContent.trim() : '';
            };
            
            const m = (regex) => {
                const text = document.body.textContent || '';
                const match = text.match(regex);
                return match ? match[1] : '';
            };
            
            const data = {};
            
            // Basic info
            data.price = getText('.p24_price, .price, [class*="price"]') || '';
            data.title = getText('h1, .p24_title, .title, [class*="title"]') || '';
            data.address = getText('.p24_address, .address, [class*="address"]') || '';
            
            // Extract from price text
            const priceText = data.price;
            const priceMatch = priceText.match(/KSh\s*([\d,]+)/);
            data.price_numeric = priceMatch ? priceMatch[1].replace(/,/g, '') : '';
            
            // Property details
            data.beds = m(/(\d+)\s*(?:bed|bedroom)s?/i);
            data.baths = m(/(\d+)\s*(?:bath|bathroom)s?/i);
            data.parking = m(/(\d+)\s*(?:parking|garage)s?/i);
            data.floor_size = m(/Floor Size[:\s]*(\d+(?:,\d+)*)\s*m²/i) || m(/Floor Area[:\s]*(\d+(?:,\d+)*)\s*m²/i);
            data.erf_size = m(/Erf Size[:\s]*(\d+(?:,\d+)*)\s*m²/i);
            
            // Description - try multiple approaches
            data.description = getText('.p24_description, .description, [class*="description"]') ||
                             getText('.p24_propertyDescription, .property-description') ||
                             getText('.p24_content, .content, .property-content') ||
                             '';
            
            // If still empty, try to find description in the main content area
            if (!data.description) {
                const descEl = document.querySelector('.p24_mainContent, .main-content, .property-details, .p24_propertyDetails');
                if (descEl) {
                    const paragraphs = descEl.querySelectorAll('p');
                    for (const p of paragraphs) {
                        const text = p.textContent.trim();
                        if (text.length > 50 && (text.includes('bedroom') || text.includes('house') || text.includes('amazing'))) {
                            data.description = text;
                            break;
                        }
                    }
                }
            }
            
            // Last resort: search all text for description-like content
            if (!data.description) {
                const allText = document.body.textContent || '';
                const descMatch = allText.match(/An amazing[^.]*\./i) || 
                                allText.match(/Get [^.]*\./i) ||
                                allText.match(/This [^.]*\./i) ||
                                allText.match(/(?:house|apartment|property)[^.]*\./i);
                if (descMatch) {
                    data.description = descMatch[0].trim();
                }
            }
            
            // Features
            const features = []; 
            document.querySelectorAll('[class*="feature"], [class*="amenity"]').forEach(el => { 
                const t = (el.textContent || '').trim(); 
                if (t && t.length > 2 && !t.match(/^\d+$/)) features.push(t); 
            });
            data.features = features;
            
            // Listing number
            data.listing_number = m(/Listing Number[:\s]*(\d+)/i) || m(/Web Ref[:\s]*(\d+)/i);
            
            return data;
        }''')

    async def update_property_record(self, prop, details):
        """Update the Property record with extracted details"""
        update_fields = []
        
        # Update title if we got a better one
        if details.get('title') and details['title'] != 'Sign In Required':
            prop.title = details['title']
            update_fields.append('title')
        
        # Update price
        if details.get('price_numeric'):
            try:
                prop.price = float(details['price_numeric'])
                update_fields.append('price')
            except ValueError:
                pass
        
        # Update location if we got address
        if details.get('address'):
            prop.location = details['address']
            update_fields.append('location')
        
        # Update timestamp
        prop.last_crawled_at = timezone.now()
        update_fields.append('last_crawled_at')
        
        if update_fields:
            await sync_to_async(prop.save, thread_sensitive=True)(update_fields=update_fields)

    async def update_property_details(self, prop, details):
        """Create/update PropertyDetail records"""
        detail_mappings = {
            'beds': details.get('beds'),
            'baths': details.get('baths'),
            'parking': details.get('parking'),
            'floor_size': details.get('floor_size'),
            'erf_size': details.get('erf_size'),
            'description': details.get('description'),
            'listing_number': details.get('listing_number'),
        }
        
        # Add features as individual details
        if details.get('features'):
            for i, feature in enumerate(details['features']):
                detail_mappings[f'feature_{i}'] = feature
        
        for key, value in detail_mappings.items():
            if value:
                await sync_to_async(PropertyDetail.objects.update_or_create, thread_sensitive=True)(
                    property=prop,
                    key=key,
                    defaults={'value': str(value)}
                )















