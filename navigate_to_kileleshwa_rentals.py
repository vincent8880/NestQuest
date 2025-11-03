#!/usr/bin/env python3

import asyncio
from playwright.async_api import async_playwright
import re
from urllib.parse import urljoin

class NairobiKileleshwaNavigator:
    """Navigate to Nairobi rentals and search for Kileleshwa properties"""
    
    def __init__(self):
        self.base_url = "https://www.property24.co.ke"
        
    async def navigate_and_search(self):
        """Navigate to Nairobi rentals and search for Kileleshwa"""
        
        print("🏠 NAVIGATING TO NAIROBI RENTALS & SEARCHING KILELESHWA")
        print("=" * 60)
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            
            try:
                # Step 1: Go to main Property24 page
                print("🌐 Step 1: Loading main Property24 page...")
                await page.goto(self.base_url, wait_until='domcontentloaded')
                await page.wait_for_timeout(3000)
                
                title = await page.title()
                print(f"   📄 Main page title: {title}")
                
                # Step 2: Click on "Nairobi" link first
                print("\n🖱️ Step 2: Clicking on 'Nairobi' link...")
                try:
                    # Look for the Nairobi link we found earlier
                    nairobi_links = await page.query_selector_all('a[href*="nairobi"]')
                    print(f"   Found {len(nairobi_links)} Nairobi-related links")
                    
                    for i, link in enumerate(nairobi_links):
                        try:
                            href = await link.get_attribute('href')
                            text = await link.text_content()
                            print(f"      Nairobi link {i+1}: {text} -> {href}")
                        except:
                            continue
                    
                    # Try to click on the first Nairobi link
                    if nairobi_links:
                        print("   🎯 Clicking first Nairobi link...")
                        await nairobi_links[0].click()
                        await page.wait_for_timeout(3000)
                        print("   ✅ Clicked Nairobi link")
                    else:
                        print("   ❌ No Nairobi links found")
                        return
                        
                except Exception as e:
                    print(f"   ❌ Error clicking Nairobi link: {e}")
                    return
                
                # Check what page we're on now
                current_title = await page.title()
                print(f"   📄 Current page title: {current_title}")
                
                # Step 3: Explore what's on the Nairobi page
                print("\n🔍 Step 3: Exploring Nairobi page content...")
                
                # Look for any text that mentions "Kileleshwa"
                page_content = await page.content()
                if 'kileleshwa' in page_content.lower():
                    print("   ✅ Found 'Kileleshwa' mentioned on Nairobi page")
                else:
                    print("   ❌ 'Kileleshwa' not found on this page")
                
                # Look for property listings
                print("\n🔍 Step 4: Looking for property listings...")
                property_elements = await page.query_selector_all('.property, .listing, .item, [class*="property"], [class*="listing"]')
                print(f"   Found {len(property_elements)} property-like elements")
                
                # Look for area/region filters
                print("\n🔍 Step 5: Looking for area/region filters...")
                area_filters = await page.query_selector_all('select, [class*="area"], [class*="region"], [class*="location"], [class*="suburb"]')
                print(f"   Found {len(area_filters)} area filter elements")
                
                for i, filter_elem in enumerate(area_filters[:5]):
                    try:
                        if filter_elem.tag_name == 'select':
                            options = await filter_elem.query_selector_all('option')
                            print(f"      Filter {i+1} (select): {len(options)} options")
                            for opt in options[:3]:  # Show first 3 options
                                opt_text = await opt.text_content()
                                print(f"         Option: {opt_text}")
                        else:
                            text = await filter_elem.text_content()
                            print(f"      Filter {i+1}: {text[:100]}...")
                    except:
                        continue
                
                # Look for search functionality
                print("\n🔍 Step 6: Looking for search functionality...")
                search_inputs = await page.query_selector_all('input[type="text"], input[placeholder*="area"], input[placeholder*="location"], input[placeholder*="search"]')
                print(f"   Found {len(search_inputs)} text input fields")
                
                for i, inp in enumerate(search_inputs):
                    try:
                        placeholder = await inp.get_attribute('placeholder')
                        name = await inp.get_attribute('name')
                        id_attr = await inp.get_attribute('id')
                        print(f"      Input {i+1}: placeholder='{placeholder}', name='{name}', id='{id_attr}'")
                    except:
                        continue
                
                # Look for any buttons that might be search-related
                print("\n🔍 Step 7: Looking for search buttons...")
                search_buttons = await page.query_selector_all('button, input[type="submit"], [class*="search"], [class*="filter"]')
                print(f"   Found {len(search_buttons)} potential search/filter buttons")
                
                for i, btn in enumerate(search_buttons[:5]):
                    try:
                        text = await btn.text_content()
                        btn_type = await btn.get_attribute('type')
                        btn_class = await btn.get_attribute('class')
                        print(f"      Button {i+1}: text='{text}', type='{btn_type}', class='{btn_class}'")
                    except:
                        continue
                
                # Step 8: Look for any existing property links
                print("\n🔍 Step 8: Looking for existing property links...")
                current_links = await page.query_selector_all('a[href]')
                print(f"   Total links on current page: {len(current_links)}")
                
                # Look for property links
                property_links = []
                for link in current_links[:20]:  # Check first 20 links
                    try:
                        href = await link.get_attribute('href')
                        text = await link.text_content()
                        if href and any(word in href.lower() for word in ['apartment', 'house', 'flat', 'rent']) and 'property24.co.ke' in href:
                            property_links.append((text, href))
                    except:
                        continue
                
                print(f"   Found {len(property_links)} property-related links")
                for text, href in property_links[:5]:  # Show first 5
                    print(f"      Property link: {text} -> {href}")
                
                # Step 9: Try to find any dropdown or filter that might contain Kileleshwa
                print("\n🔍 Step 9: Looking for Kileleshwa in filters...")
                
                # Look for any text content that might contain area names
                all_text_elements = await page.query_selector_all('div, span, p, label')
                kileleshwa_mentions = []
                
                for elem in all_text_elements[:100]:  # Check first 100 elements
                    try:
                        text = await elem.text_content()
                        if text and 'kileleshwa' in text.lower():
                            kileleshwa_mentions.append(text.strip())
                    except:
                        continue
                
                if kileleshwa_mentions:
                    print(f"   ✅ Found {len(kileleshwa_mentions)} mentions of Kileleshwa:")
                    for mention in kileleshwa_mentions[:3]:
                        print(f"      - {mention}")
                else:
                    print("   ❌ No Kileleshwa mentions found in text elements")
                
                print(f"\n🎯 EXPLORATION COMPLETE")
                print("=" * 30)
                print("💡 Check the output above to see what we discovered on the Nairobi page")
                print("🔍 Look for area filters, search functionality, or property listings")
                
            except Exception as e:
                print(f"❌ Navigation failed: {e}")
            finally:
                await browser.close()

async def main():
    navigator = NairobiKileleshwaNavigator()
    await navigator.navigate_and_search()

if __name__ == "__main__":
    asyncio.run(main())
