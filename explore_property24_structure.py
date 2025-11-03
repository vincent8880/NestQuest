#!/usr/bin/env python3

import asyncio
from playwright.async_api import async_playwright
import re

class Property24StructureExplorer:
    """Explore Property24's actual structure to find the right way to discover properties"""
    
    def __init__(self):
        self.base_url = "https://www.property24.co.ke"
        
    async def explore_structure(self):
        """Explore Property24's structure to understand how to find properties"""
        
        print("🔍 EXPLORING PROPERTY24 STRUCTURE")
        print("=" * 50)
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            
            try:
                # Step 1: Go to main Property24 page
                print("🌐 Step 1: Exploring main Property24 page...")
                await page.goto(self.base_url, wait_until='domcontentloaded')
                await page.wait_for_timeout(3000)
                
                title = await page.title()
                print(f"   📄 Main page title: {title}")
                
                # Look for navigation menus
                print("\n🔍 Looking for navigation menus...")
                nav_elements = await page.query_selector_all('nav, .nav, .navigation, .menu, [class*="nav"], [class*="menu"]')
                print(f"   Found {len(nav_elements)} navigation elements")
                
                # Look for search forms
                print("\n🔍 Looking for search forms...")
                search_forms = await page.query_selector_all('form, .search, [class*="search"]')
                print(f"   Found {len(search_forms)} search elements")
                
                # Look for area/region links
                print("\n🔍 Looking for area/region links...")
                area_links = await page.query_selector_all('a[href*="area"], a[href*="region"], a[href*="nairobi"], a[href*="kileleshwa"]')
                print(f"   Found {len(area_links)} area-related links")
                
                for link in area_links[:5]:  # Show first 5
                    try:
                        href = await link.get_attribute('href')
                        text = await link.text_content()
                        print(f"      Area link: {text} -> {href}")
                    except:
                        continue
                
                # Step 2: Look for "For Rent" section
                print("\n🔍 Step 2: Looking for 'For Rent' section...")
                rent_links = await page.query_selector_all('a[href*="rent"], a[href*="for-rent"], a[href*="to-rent"]')
                print(f"   Found {len(rent_links)} rent-related links")
                
                for link in rent_links[:5]:  # Show first 5
                    try:
                        href = await link.get_attribute('href')
                        text = await link.text_content()
                        print(f"      Rent link: {text} -> {href}")
                    except:
                        continue
                
                # Step 3: Try to find the actual search functionality
                print("\n🔍 Step 3: Looking for actual search functionality...")
                
                # Look for any input fields
                inputs = await page.query_selector_all('input[type="text"], input[placeholder*="area"], input[placeholder*="location"]')
                print(f"   Found {len(inputs)} text input fields")
                
                for inp in inputs[:3]:  # Show first 3
                    try:
                        placeholder = await inp.get_attribute('placeholder')
                        name = await inp.get_attribute('name')
                        print(f"      Input: placeholder='{placeholder}', name='{name}'")
                    except:
                        continue
                
                # Step 4: Try to find property listings
                print("\n🔍 Step 4: Looking for property listings...")
                
                # Look for property cards/items
                property_elements = await page.query_selector_all('.property, .listing, .item, [class*="property"], [class*="listing"]')
                print(f"   Found {len(property_elements)} property-like elements")
                
                # Step 5: Try to find the correct search URL pattern
                print("\n🔍 Step 5: Analyzing page content for search patterns...")
                
                # Get all links and analyze them
                all_links = await page.query_selector_all('a[href]')
                print(f"   Total links on page: {len(all_links)}")
                
                # Look for patterns in URLs
                url_patterns = {}
                for link in all_links[:20]:  # Analyze first 20 links
                    try:
                        href = await link.get_attribute('href')
                        if href and 'property24.co.ke' in href:
                            # Extract the path structure
                            if href.startswith('http'):
                                path = href.split('property24.co.ke')[1]
                            else:
                                path = href
                            
                            if path not in url_patterns:
                                url_patterns[path] = 0
                            url_patterns[path] += 1
                    except:
                        continue
                
                print(f"\n📊 Most common URL patterns:")
                sorted_patterns = sorted(url_patterns.items(), key=lambda x: x[1], reverse=True)
                for pattern, count in sorted_patterns[:10]:
                    print(f"   {pattern} (appears {count} times)")
                
                # Step 6: Try to find the actual working search URL
                print("\n🔍 Step 6: Testing potential search URLs...")
                
                # Based on what we found, try some common patterns
                test_urls = [
                    f"{self.base_url}/search",
                    f"{self.base_url}/properties",
                    f"{self.base_url}/listings",
                    f"{self.base_url}/rent",
                    f"{self.base_url}/for-rent"
                ]
                
                for test_url in test_urls:
                    try:
                        print(f"   Testing: {test_url}")
                        await page.goto(test_url, wait_until='domcontentloaded', timeout=10000)
                        await page.wait_for_timeout(2000)
                        
                        title = await page.title()
                        print(f"      ✅ Success! Title: {title}")
                        
                        # Look for search functionality on this page
                        search_inputs = await page.query_selector_all('input[type="text"]')
                        print(f"      Found {len(search_inputs)} text inputs")
                        
                        break
                        
                    except Exception as e:
                        print(f"      ❌ Failed: {e}")
                        continue
                
                print(f"\n🎯 EXPLORATION COMPLETE")
                print("=" * 30)
                print("💡 Check the output above to understand Property24's structure")
                print("🔍 Look for working search URLs and navigation patterns")
                
            except Exception as e:
                print(f"❌ Exploration failed: {e}")
            finally:
                await browser.close()

async def main():
    explorer = Property24StructureExplorer()
    await explorer.explore_structure()

if __name__ == "__main__":
    asyncio.run(main())



