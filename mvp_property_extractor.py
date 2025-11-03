#!/usr/bin/env python3

import asyncio
import json
import re
from playwright.async_api import async_playwright
from datetime import datetime

class MVPPropertyExtractor:
    """MVP Property Extractor - Get it working NOW"""
    
    def __init__(self):
        self.base_url = "https://www.property24.co.ke/apartments-flats-to-rent"
        self.results = []
    
    async def extract_properties_mvp(self):
        """Extract properties using direct approach - MVP version"""
        
        print("🚀 MVP PROPERTY EXTRACTOR - GETTING IT DONE!")
        print("=" * 60)
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            
            try:
                # Load page 1
                page_url = f"{self.base_url}?Page=1"
                print(f"🌐 Loading: {page_url}")
                
                await page.goto(page_url, wait_until='domcontentloaded')
                await page.wait_for_timeout(3000)
                
                # Get all property links directly
                print("🔍 Finding property links...")
                
                # Look for property links in the page content
                property_links = await page.evaluate("""
                    () => {
                        const links = [];
                        const allLinks = document.querySelectorAll('a[href]');
                        
                        allLinks.forEach(link => {
                            const href = link.href;
                            const text = link.textContent || '';
                            
                            // Look for property links
                            if (href && (
                                href.includes('/for-rent/') || 
                                href.includes('/apartment') ||
                                href.includes('/house') ||
                                (href.includes('property24.co.ke') && text.includes('bedroom'))
                            )) {
                                links.push({
                                    href: href,
                                    text: text.trim(),
                                    visible: link.offsetParent !== null
                                });
                            }
                        });
                        
                        return links;
                    }
                """)
                
                print(f"   Found {len(property_links)} property links")
                
                # Filter for visible links only
                visible_links = [link for link in property_links if link['visible']]
                print(f"   {len(visible_links)} are visible and clickable")
                
                # Process first 3 properties as MVP
                max_properties = min(3, len(visible_links))
                print(f"   🎯 Processing first {max_properties} properties")
                
                for i, link_data in enumerate(visible_links[:max_properties]):
                    try:
                        print(f"\n   🏠 Processing property {i+1}/{max_properties}")
                        print(f"      Link: {link_data['text'][:50]}...")
                        print(f"      URL: {link_data['href']}")
                        
                        # Navigate to property page
                        await page.goto(link_data['href'], wait_until='domcontentloaded')
                        await page.wait_for_timeout(2000)
                        
                        # Extract property details
                        property_data = await self.extract_property_data(page, link_data)
                        self.results.append(property_data)
                        
                        print(f"      ✅ Property {i+1} processed successfully")
                        
                    except Exception as e:
                        print(f"      ❌ Error processing property {i+1}: {e}")
                        continue
                
                # Save results
                await self.save_results()
                
                print(f"\n🎉 MVP COMPLETE!")
                print("=" * 30)
                print(f"📊 Properties processed: {len(self.results)}")
                print(f"💾 Results saved to: mvp_property_results.json")
                
            except Exception as e:
                print(f"❌ MVP failed: {e}")
            finally:
                await browser.close()
    
    async def extract_property_data(self, page, link_data):
        """Extract data from a property page"""
        try:
            # Get basic info
            title = await page.title()
            
            # Extract price
            price_elem = await page.query_selector('[class*="price"], .price, [class*="amount"]')
            price = await price_elem.text_content() if price_elem else "N/A"
            
            # Extract location
            location_elem = await page.query_selector('[class*="location"], .location, [class*="area"]')
            location = await location_elem.text_content() if location_elem else "N/A"
            
            # Extract description
            desc_elem = await page.query_selector('[class*="description"], .description, [class*="details"]')
            description = await desc_elem.text_content() if desc_elem else "N/A"
            
            # Extract images
            images = await self.extract_images(page)
            
            # Extract external ID from URL
            current_url = page.url
            external_id = None
            if current_url:
                id_match = re.search(r'/(\d+)(?:$|\?)', current_url)
                if id_match:
                    external_id = id_match.group(1)
            
            return {
                'title': title,
                'price': price,
                'location': location,
                'description': description,
                'images': images,
                'source_url': current_url,
                'external_id': external_id,
                'extraction_timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Error extracting property data: {e}")
            return {
                'title': "Error",
                'price': "N/A",
                'location': "N/A",
                'description': "N/A",
                'images': [],
                'source_url': link_data['href'],
                'external_id': None,
                'extraction_timestamp': datetime.now().isoformat()
            }
    
    async def extract_images(self, page):
        """Extract images from the property page"""
        try:
            images = []
            
            # Look for images
            img_elements = await page.query_selector_all('img[src*="images.prop24.com"]')
            
            for img in img_elements:
                try:
                    src = await img.get_attribute('src')
                    alt = await img.get_attribute('alt') or ''
                    if src:
                        images.append({
                            'src': src,
                            'alt': alt
                        })
                except:
                    continue
            
            return images
            
        except Exception as e:
            print(f"Error extracting images: {e}")
            return []
    
    async def save_results(self):
        """Save results to JSON file"""
        try:
            output_data = {
                'extraction_timestamp': datetime.now().isoformat(),
                'total_properties': len(self.results),
                'properties': self.results
            }
            
            with open('mvp_property_results.json', 'w') as f:
                json.dump(output_data, f, indent=2)
            
            print("💾 Results saved successfully")
            
        except Exception as e:
            print(f"❌ Error saving results: {e}")

async def main():
    extractor = MVPPropertyExtractor()
    await extractor.extract_properties_mvp()

if __name__ == "__main__":
    asyncio.run(main())















































