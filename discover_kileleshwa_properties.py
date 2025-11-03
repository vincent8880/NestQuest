#!/usr/bin/env python3

import asyncio
from playwright.async_api import async_playwright
import re
from urllib.parse import urljoin, urlparse

class KileleshwaPropertyDiscoverer:
    """Discover and count Kileleshwa rental properties on Property24"""
    
    def __init__(self):
        # Property24 search patterns for Kileleshwa rentals
        self.search_urls = [
            "https://www.property24.co.ke/for-rent/kileleshwa",
            "https://www.property24.co.ke/for-rent/nairobi/kileleshwa",
            "https://www.property24.co.ke/for-rent/apartment-flat/kileleshwa",
            "https://www.property24.co.ke/for-rent/house/kileleshwa"
        ]
        
    async def discover_properties(self):
        """Discover all Kileleshwa rental properties"""
        
        print("🔍 DISCOVERING KILELESHWA RENTAL PROPERTIES")
        print("=" * 60)
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            
            try:
                all_properties = []
                
                for search_url in self.search_urls:
                    print(f"\n🌐 Testing search URL: {search_url}")
                    
                    try:
                        await page.goto(search_url, wait_until='domcontentloaded')
                        await page.wait_for_timeout(3000)
                        
                        # Check if page loaded successfully
                        title = await page.title()
                        print(f"   📄 Page title: {title}")
                        
                        # Look for property count indicators
                        count_info = await self.extract_property_count(page)
                        print(f"   📊 Property count info: {count_info}")
                        
                        # Extract property URLs from this page
                        page_properties = await self.extract_property_urls(page, search_url)
                        print(f"   🏠 Found {len(page_properties)} properties on this page")
                        
                        all_properties.extend(page_properties)
                        
                        # Check for pagination
                        pagination_info = await self.check_pagination(page)
                        print(f"   📄 Pagination: {pagination_info}")
                        
                        # If there are multiple pages, let's explore a few more
                        if pagination_info.get('has_pagination'):
                            print(f"   🔄 Exploring additional pages...")
                            additional_properties = await self.explore_pagination(page, search_url, max_pages=3)
                            all_properties.extend(additional_properties)
                            print(f"   📊 Total from this search: {len(additional_properties)} properties")
                        
                    except Exception as e:
                        print(f"   ❌ Error with {search_url}: {e}")
                        continue
                
                # Remove duplicates and analyze results
                unique_properties = list(set(all_properties))
                print(f"\n🎯 DISCOVERY RESULTS")
                print("=" * 40)
                print(f"📊 Total unique properties found: {len(unique_properties)}")
                print(f"🔍 Searched {len(self.search_urls)} different URL patterns")
                
                # Show sample property URLs
                print(f"\n📋 Sample Property URLs (first 10):")
                for i, url in enumerate(unique_properties[:10]):
                    print(f"   {i+1}. {url}")
                
                if len(unique_properties) > 10:
                    print(f"   ... and {len(unique_properties) - 10} more")
                
                # Save results for later use
                results = {
                    'total_properties': len(unique_properties),
                    'search_urls_tested': self.search_urls,
                    'property_urls': unique_properties,
                    'discovery_timestamp': asyncio.get_event_loop().time()
                }
                
                import json
                with open('kileleshwa_discovery_results.json', 'w') as f:
                    json.dump(results, f, indent=2)
                
                print(f"\n💾 Results saved to: kileleshwa_discovery_results.json")
                print(f"🚀 Ready for Phase 1: Basic data extraction!")
                
                return unique_properties
                
            except Exception as e:
                print(f"❌ Discovery failed: {e}")
                return []
            finally:
                await browser.close()
    
    async def extract_property_count(self, page):
        """Extract property count information from the page"""
        try:
            # Look for common property count selectors
            count_selectors = [
                '.p24_resultsCount',
                '.results-count',
                '.property-count',
                '[class*="count"]',
                '[class*="total"]',
                'h1, h2, h3'  # Sometimes count is in headings
            ]
            
            for selector in count_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    for element in elements:
                        text = await element.text_content()
                        if text and any(word in text.lower() for word in ['property', 'result', 'found', 'rent', 'kileleshwa']):
                            return text.strip()
                except:
                    continue
            
            return "Count not found"
            
        except Exception as e:
            return f"Error: {e}"
    
    async def extract_property_urls(self, page, base_url):
        """Extract property URLs from the current page"""
        try:
            # Look for property links
            property_selectors = [
                'a[href*="/for-rent/"]',
                'a[href*="/apartment"]',
                'a[href*="/house"]',
                '.p24_content a',
                '.property-item a',
                '[class*="property"] a'
            ]
            
            property_urls = []
            
            for selector in property_selectors:
                try:
                    links = await page.query_selector_all(selector)
                    for link in links:
                        href = await link.get_attribute('href')
                        if href:
                            # Make sure it's a full property URL
                            if '/for-rent/' in href and any(word in href.lower() for word in ['apartment', 'house', 'flat']):
                                full_url = urljoin(base_url, href)
                                if 'property24.co.ke' in full_url:
                                    property_urls.append(full_url)
                except:
                    continue
            
            return property_urls
            
        except Exception as e:
            print(f"Error extracting property URLs: {e}")
            return []
    
    async def check_pagination(self, page):
        """Check if the page has pagination"""
        try:
            # Look for pagination elements
            pagination_selectors = [
                '.p24_pager',
                '.pagination',
                '.pager',
                '[class*="page"]',
                'a[href*="page="]',
                'a[href*="p="]'
            ]
            
            for selector in pagination_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        # Check if there are next/previous buttons
                        next_buttons = await page.query_selector_all('a[href*="next"], .next, .p24_next')
                        prev_buttons = await page.query_selector_all('a[href*="prev"], .prev, .p24_prev')
                        
                        return {
                            'has_pagination': True,
                            'next_buttons': len(next_buttons),
                            'prev_buttons': len(prev_buttons),
                            'total_elements': len(elements)
                        }
                except:
                    continue
            
            return {'has_pagination': False}
            
        except Exception as e:
            return {'has_pagination': False, 'error': str(e)}
    
    async def explore_pagination(self, page, base_url, max_pages=3):
        """Explore additional pages to find more properties"""
        additional_properties = []
        
        try:
            for page_num in range(2, max_pages + 1):
                print(f"      📄 Exploring page {page_num}...")
                
                # Try different pagination patterns
                pagination_patterns = [
                    f"{base_url}?page={page_num}",
                    f"{base_url}?p={page_num}",
                    f"{base_url}page-{page_num}/",
                    f"{base_url}?start={page_num * 20}"
                ]
                
                page_found = False
                for pattern in pagination_patterns:
                    try:
                        await page.goto(pattern, wait_until='domcontentloaded')
                        await page.wait_for_timeout(2000)
                        
                        # Check if page loaded successfully
                        title = await page.title()
                        if 'error' not in title.lower() and 'not found' not in title.lower():
                            page_properties = await self.extract_property_urls(page, base_url)
                            additional_properties.extend(page_properties)
                            print(f"         ✅ Page {page_num}: Found {len(page_properties)} properties")
                            page_found = True
                            break
                    except:
                        continue
                
                if not page_found:
                    print(f"         ⚠️ Page {page_num}: Not accessible")
                    break
                    
        except Exception as e:
            print(f"Error exploring pagination: {e}")
        
        return additional_properties

async def main():
    discoverer = KileleshwaPropertyDiscoverer()
    properties = await discoverer.discover_properties()
    
    if properties:
        print(f"\n🎉 SUCCESS! Found {len(properties)} Kileleshwa rental properties")
        print("💡 Next step: Create Phase 1 extraction script")
    else:
        print("\n❌ No properties discovered. Check Property24 structure.")

if __name__ == "__main__":
    asyncio.run(main())



