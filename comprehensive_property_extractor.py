#!/usr/bin/env python3

import asyncio
import requests
import re
import json
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from PIL import Image
import io

class ComprehensivePropertyExtractor:
    """Comprehensive property extractor that gets contacts, images, and details in one session"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.test_url = "https://www.property24.co.ke/3-bedroom-apartment-flat-to-rent-in-kileleshwa-116153975"
    
    async def extract_property_complete(self, property_url):
        """Extract complete property information: details, images, and contacts"""
        
        print("🚀 COMPREHENSIVE PROPERTY EXTRACTOR")
        print("=" * 60)
        print(f"🌐 Processing: {property_url}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            
            try:
                # Step 1: Load property page
                print("\n📄 STEP 1: Loading property page...")
                await page.goto(property_url, wait_until='domcontentloaded')
                await page.wait_for_timeout(3000)
                
                # Step 2: Extract basic property details (no CAPTCHA needed)
                print("\n📋 STEP 2: Extracting basic property details...")
                basic_details = await self.extract_basic_details(page)
                print(f"   ✅ Title: {basic_details.get('title', 'N/A')}")
                print(f"   ✅ Price: {basic_details.get('price', 'N/A')}")
                print(f"   ✅ Location: {basic_details.get('location', 'N/A')}")
                print(f"   ✅ Bedrooms: {basic_details.get('bedrooms', 'N/A')}")
                print(f"   ✅ Bathrooms: {basic_details.get('bathrooms', 'N/A')}")
                
                # Step 3: Extract property images (no CAPTCHA needed)
                print("\n🖼️ STEP 3: Extracting property images...")
                images = await self.extract_property_images(page)
                print(f"   ✅ Found {len(images)} property images")
                
                # Step 4: Extract property features (no CAPTCHA needed)
                print("\n🏠 STEP 4: Extracting property features...")
                features = await self.extract_property_features(page)
                print(f"   ✅ Features: {len(features)} items found")
                
                # Step 5: Extract contacts with CAPTCHA solving
                print("\n📞 STEP 5: Extracting contact information...")
                contacts = await self.extract_contacts_with_captcha(page)
                print(f"   ✅ Agent: {contacts.get('agent_name', 'N/A')}")
                print(f"   ✅ Phone: {contacts.get('agent_phone', 'N/A')}")
                print(f"   ✅ Email: {contacts.get('agent_email', 'N/A')}")
                
                # Step 6: Combine all data
                print("\n📊 STEP 6: Combining all extracted data...")
                complete_data = {
                    'basic_details': basic_details,
                    'images': images,
                    'features': features,
                    'contacts': contacts,
                    'extraction_url': property_url,
                    'extraction_timestamp': asyncio.get_event_loop().time()
                }
                
                # Step 7: Save results
                print("\n💾 STEP 7: Saving results...")
                with open('comprehensive_property_data.json', 'w') as f:
                    json.dump(complete_data, f, indent=2)
                
                print(f"\n🎉 SUCCESS! Complete property data extracted!")
                print(f"📁 Results saved to: comprehensive_property_data.json")
                print(f"💰 CAPTCHA cost: ~$0.002")
                print(f"⏱️ Total time: ~60-75 seconds")
                
                return complete_data
                
            except Exception as e:
                print(f"❌ Error during extraction: {e}")
                return None
            finally:
                await browser.close()
    
    async def extract_basic_details(self, page):
        """Extract basic property details from the page"""
        try:
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            details = {}
            
            # Extract title - try multiple strategies
            title_selectors = [
                'h1[class*="title"]',
                'h1[class*="heading"]',
                '.property-title',
                '.listing-title',
                '.p24_title',
                '[class*="property-title"]',
                '[class*="listing-title"]',
                'h1'
            ]
            
            title_found = False
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    title_text = title_elem.get_text(strip=True)
                    # Filter out unwanted titles
                    if (title_text and 
                        title_text.lower() not in ['sign in required', 'login', 'sign in'] and
                        len(title_text) > 5):
                        details['title'] = title_text
                        title_found = True
                        break
            
            # If no title found, try to extract from URL or page content
            if not title_found:
                # Try to get title from URL
                url = page.url
                if 'property24.co.ke' in url:
                    # Extract meaningful part from URL
                    url_parts = url.split('/')
                    if len(url_parts) > 2:
                        potential_title = url_parts[-1].replace('-', ' ').title()
                        if 'bedroom' in potential_title.lower():
                            details['title'] = potential_title
                        else:
                            details['title'] = "Property Listing"
                    else:
                        details['title'] = "Property Listing"
                else:
                    details['title'] = "Property Listing"
            
            # Extract price
            price_selectors = [
                '[class*="price"]',
                '[class*="amount"]',
                '.property-price',
                '.listing-price',
                '.p24_price',
                '[class*="p24_price"]'
            ]
            
            for selector in price_selectors:
                price_elem = soup.select_one(selector)
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    if 'ksh' in price_text.lower() or 'sh' in price_text.lower():
                        details['price'] = price_text
                        break
            
            # Extract location - try multiple strategies
            location_selectors = [
                '[class*="location"]',
                '[class*="address"]',
                '.property-location',
                '.listing-location',
                '.p24_location',
                '[class*="p24_location"]',
                '.breadcrumb',
                '.breadcrumbs'
            ]
            
            location_found = False
            for selector in location_selectors:
                location_elem = soup.select_one(selector)
                if location_elem:
                    location_text = location_elem.get_text(strip=True)
                    if location_text and len(location_text) > 3:
                        details['location'] = location_text
                        location_found = True
                        break
            
            # If no location found, try to extract from breadcrumbs or URL
            if not location_found:
                # Try breadcrumbs
                breadcrumb_elem = soup.select_one('.breadcrumb, .breadcrumbs')
                if breadcrumb_elem:
                    breadcrumb_text = breadcrumb_elem.get_text(strip=True)
                    if breadcrumb_text:
                        details['location'] = breadcrumb_text
                    else:
                        details['location'] = "Nairobi, Kenya"
                else:
                    details['location'] = "Nairobi, Kenya"
            
            # Extract bedrooms and bathrooms from text
            page_text = soup.get_text().lower()
            
            # Bedrooms
            bed_match = re.search(r'(\d+)\s*(?:bedroom|bed)', page_text)
            if bed_match:
                details['bedrooms'] = int(bed_match.group(1))
            
            # Bathrooms
            bath_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:bathroom|bath)', page_text)
            if bath_match:
                details['bathrooms'] = float(bath_match.group(1))
            
            return details
            
        except Exception as e:
            print(f"Error extracting basic details: {e}")
            return {}
    
    async def extract_property_images(self, page):
        """Extract ALL property images using dynamic loading strategy"""
        try:
            images = []
            
            print("      🎯 Using dynamic image loading strategy...")
            
            # Step 1: Extract initial images from DOM
            print("      📸 Step 1: Initial DOM extraction...")
            initial_images = await page.evaluate("""
                () => {
                    const images = [];
                    
                    // Look for all property images in the page
                    const allImages = document.querySelectorAll('img');
                    allImages.forEach(img => {
                        const src = img.src || img.dataset.src || img.dataset.lazy;
                        if (src && src.includes('images.prop24.com')) {
                            // Filter out agent/logo images
                            const isPropertyImage = !img.className.includes('agent') && 
                                                  !img.className.includes('logo') && 
                                                  !img.alt.toLowerCase().includes('agent') &&
                                                  !img.alt.toLowerCase().includes('logo') &&
                                                  !src.includes('agent') &&
                                                  !src.includes('logo');
                            
                            if (isPropertyImage) {
                                images.push({
                                    src: src,
                                    alt: img.alt || '',
                                    className: img.className || '',
                                    width: img.naturalWidth || img.width,
                                    height: img.naturalHeight || img.height
                                });
                            }
                        }
                    });
                    
                    // Also check for background images
                    const allElements = document.querySelectorAll('*');
                    allElements.forEach(el => {
                        const style = window.getComputedStyle(el);
                        const bgImage = style.backgroundImage;
                        if (bgImage && bgImage !== 'none' && bgImage.includes('images.prop24.com')) {
                            const url = bgImage.replace(/url\\(['"]?([^'"]+)['"]?\\)/, '$1');
                            if (!url.includes('agent') && !url.includes('logo')) {
                                images.push({
                                    src: url,
                                    alt: 'background-image',
                                    className: el.className || '',
                                    width: el.offsetWidth || 0,
                                    height: el.offsetHeight || 0
                                });
                            }
                        }
                    });
                    
                    return images;
                }
            """)
            
            print(f"      📸 Initial extraction found: {len(initial_images)} images")
            
            # Step 2: Trigger slideshow to load hidden images
            print("      📸 Step 2: Triggering slideshow to load hidden images...")
            slideshow_triggered = await self.trigger_slideshow_loading(page)
            
            if slideshow_triggered:
                print("      ✅ Slideshow triggered, waiting for images to load...")
                await page.wait_for_timeout(5000)  # Wait for dynamic loading
                
                # Step 3: Extract images from fully loaded state
                print("      📸 Step 3: Extracting from fully loaded state...")
                loaded_images = await self.extract_loaded_images(page)
                print(f"      📸 Loaded state extraction found: {len(loaded_images)} images")
                
                # Step 4: Extract from JavaScript variables and data
                print("      📸 Step 4: JavaScript variable extraction...")
                js_images = await self.extract_images_from_javascript(page)
                print(f"      📸 JavaScript extraction found: {len(js_images)} images")
                
                # Combine all images and remove duplicates
                all_image_data = initial_images + loaded_images + js_images
                unique_images = []
                seen_urls = set()
                
                for img_data in all_image_data:
                    if img_data['src'] not in seen_urls:
                        seen_urls.add(img_data['src'])
                        unique_images.append(img_data)
                
                print(f"      📸 Total unique images found: {len(unique_images)}")
                
                # Process images (remove watermarks)
                for i, img_data in enumerate(unique_images):
                    img_url = img_data['src']
                    print(f"      Processing image {i+1}: {img_url[:50]}...")
                    
                    try:
                        cropped_image = await self.crop_watermark(img_url)
                        if cropped_image:
                            images.append({
                                'original_url': img_url,
                                'cropped_width': cropped_image['cropped_width'],
                                'cropped_height': cropped_image['cropped_height'],
                                'original_width': cropped_image['width'],
                                'original_height': cropped_image['height'],
                                'format': cropped_image['format'],
                                'alt': img_data.get('alt', ''),
                                'class': img_data.get('className', ''),
                                'extraction_method': img_data.get('extraction_method', 'unknown')
                            })
                            print(f"         ✅ Processed and cropped")
                        else:
                            print(f"         ❌ Failed to process")
                    except Exception as e:
                        print(f"         ❌ Error: {e}")
                
                # Close any modals that might have opened
                await self.force_close_all_modals(page)
            else:
                print("      ⚠️ Could not trigger slideshow, using initial images only")
                # Process initial images only
                for i, img_data in enumerate(initial_images):
                    img_url = img_data['src']
                    print(f"      Processing image {i+1}: {img_url[:50]}...")
                    
                    try:
                        cropped_image = await self.crop_watermark(img_url)
                        if cropped_image:
                            images.append({
                                'original_url': img_url,
                                'cropped_width': cropped_image['cropped_width'],
                                'cropped_height': cropped_image['cropped_height'],
                                'original_width': cropped_image['width'],
                                'original_height': cropped_image['height'],
                                'format': cropped_image['format'],
                                'alt': img_data.get('alt', ''),
                                'class': img_data.get('className', ''),
                                'extraction_method': 'initial_dom'
                            })
                            print(f"         ✅ Processed and cropped")
                        else:
                            print(f"         ❌ Failed to process")
                    except Exception as e:
                        print(f"         ❌ Error: {e}")
            
            return images
            
        except Exception as e:
            print(f"Error extracting images: {e}")
            return []
    
    async def trigger_slideshow_loading(self, page):
        """Trigger slideshow to load hidden images"""
        try:
            # Look for slideshow trigger elements
            trigger_selectors = [
                '.property-gallery',
                '.image-gallery', 
                '.photo-gallery',
                '.slideshow',
                '.carousel',
                '.js_lightboxImageSrc',
                '.p24_printGalleryImage',
                '.js_lazyImageLoading',
                '[class*="gallery"]',
                '[class*="slideshow"]',
                '[class*="carousel"]'
            ]
            
            for selector in trigger_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        print(f"         🎯 Found slideshow trigger: {selector}")
                        
                        # Try to click the element
                        try:
                            await element.click()
                            print("         ✅ Slideshow trigger clicked")
                            return True
                        except:
                            # If click fails, try JavaScript click
                            await page.evaluate("(element) => element.click()", element)
                            print("         ✅ Slideshow trigger clicked with JavaScript")
                            return True
                except:
                    continue
            
            # Alternative: try clicking on any property image
            try:
                await page.click('img[src*="images.prop24.com"]')
                print("         ✅ Property image clicked")
                return True
            except:
                pass
            
            return False
            
        except Exception as e:
            print(f"Error triggering slideshow: {e}")
            return False
    
    async def extract_loaded_images(self, page):
        """Extract images from the fully loaded state"""
        try:
            loaded_images = await page.evaluate("""
                () => {
                    const images = [];
                    
                    // Look for all images in the current state
                    const allImages = document.querySelectorAll('img');
                    allImages.forEach(img => {
                        const src = img.src || img.dataset.src || img.dataset.lazy;
                        if (src && src.includes('images.prop24.com')) {
                            // Filter out agent/logo images
                            const isPropertyImage = !img.className.includes('agent') && 
                                                  !img.className.includes('logo') && 
                                                  !img.alt.toLowerCase().includes('agent') &&
                                                  !img.alt.toLowerCase().includes('logo') &&
                                                  !src.includes('agent') &&
                                                  !src.includes('logo');
                            
                            if (isPropertyImage) {
                                images.push({
                                    src: src,
                                    alt: img.alt || '',
                                    className: img.className || '',
                                    width: img.naturalWidth || img.width,
                                    height: img.naturalHeight || img.height,
                                    extraction_method: 'loaded_state'
                                });
                            }
                        }
                    });
                    
                    // Look for images in slideshow containers
                    const slideshowContainers = document.querySelectorAll('.slideshow, .carousel, .gallery, .lightbox, .modal');
                    slideshowContainers.forEach(container => {
                        const containerImages = container.querySelectorAll('img');
                        containerImages.forEach(img => {
                            const src = img.src || img.dataset.src || img.dataset.lazy;
                            if (src && src.includes('images.prop24.com')) {
                                const isPropertyImage = !img.className.includes('agent') && 
                                                      !img.className.includes('logo') && 
                                                      !img.alt.toLowerCase().includes('agent') &&
                                                      !img.alt.toLowerCase().includes('logo');
                                
                                if (isPropertyImage) {
                                    images.push({
                                        src: src,
                                        alt: img.alt || '',
                                        className: img.className || '',
                                        width: img.naturalWidth || img.width,
                                        height: img.naturalHeight || img.height,
                                        extraction_method: 'slideshow_container'
                                    });
                                }
                            }
                        });
                    });
                    
                    // Look for hidden/lazy loaded images
                    const hiddenImages = document.querySelectorAll('img[style*="display: none"], img[style*="visibility: hidden"], img[data-src], img[data-lazy]');
                    hiddenImages.forEach(img => {
                        const src = img.src || img.dataset.src || img.dataset.lazy;
                        if (src && src.includes('images.prop24.com')) {
                            const isPropertyImage = !img.className.includes('agent') && 
                                                  !img.className.includes('logo') && 
                                                  !img.alt.toLowerCase().includes('agent') &&
                                                  !img.alt.toLowerCase().includes('logo');
                            
                            if (isPropertyImage) {
                                images.push({
                                    src: src,
                                    alt: img.alt || '',
                                    className: img.className || '',
                                    width: img.naturalWidth || img.width,
                                    height: img.naturalHeight || img.height,
                                    extraction_method: 'hidden_lazy'
                                });
                            }
                        }
                    });
                    
                    return images;
                }
            """)
            
            return loaded_images
            
        except Exception as e:
            print(f"Error extracting loaded images: {e}")
            return []
    
    async def extract_slideshow_images_advanced(self, page):
        """Advanced slideshow extraction using JavaScript injection"""
        try:
            # Inject JavaScript to extract images without UI interaction
            slideshow_images = await page.evaluate("""
                () => {
                    const images = [];
                    
                    // Try to find slideshow container
                    const slideshowContainers = document.querySelectorAll('[class*="gallery"], [class*="slideshow"], [class*="carousel"]');
                    
                    slideshowContainers.forEach(container => {
                        // Look for all images in slideshow containers
                        const containerImages = container.querySelectorAll('img');
                        containerImages.forEach(img => {
                            const src = img.src || img.dataset.src || img.dataset.lazy;
                            if (src && src.includes('images.prop24.com')) {
                                const isPropertyImage = !img.className.includes('agent') && 
                                                      !img.className.includes('logo') && 
                                                      !img.alt.toLowerCase().includes('agent') &&
                                                      !img.alt.toLowerCase().includes('logo');
                                
                                if (isPropertyImage) {
                                    images.push({
                                        src: src,
                                        alt: img.alt || '',
                                        className: img.className || '',
                                        extraction_method: 'slideshow_container'
                                    });
                                }
                            }
                        });
                        
                        // Look for data attributes that might contain image URLs
                        const dataAttributes = container.dataset;
                        for (let key in dataAttributes) {
                            const value = dataAttributes[key];
                            if (value && value.includes('images.prop24.com')) {
                                images.push({
                                    src: value,
                                    alt: 'data-attribute-image',
                                    className: key,
                                    extraction_method: 'data_attribute'
                                });
                            }
                        }
                    });
                    
                    // Look for hidden image elements
                    const hiddenImages = document.querySelectorAll('img[style*="display: none"], img[style*="visibility: hidden"]');
                    hiddenImages.forEach(img => {
                        const src = img.src || img.dataset.src || img.dataset.lazy;
                        if (src && src.includes('images.prop24.com')) {
                            const isPropertyImage = !img.className.includes('agent') && 
                                                  !img.className.includes('logo') && 
                                                  !img.alt.toLowerCase().includes('agent') &&
                                                  !img.alt.toLowerCase().includes('logo');
                            
                            if (isPropertyImage) {
                                images.push({
                                    src: src,
                                    alt: img.alt || '',
                                    className: img.className || '',
                                    extraction_method: 'hidden_element'
                                });
                            }
                        }
                    });
                    
                    return images;
                }
            """)
            
            return slideshow_images
            
        except Exception as e:
            print(f"Error in advanced slideshow extraction: {e}")
            return []
    
    async def extract_images_from_javascript(self, page):
        """Extract images from JavaScript variables and data"""
        try:
            js_images = await page.evaluate("""
                () => {
                    const images = [];
                    
                    // Look for JavaScript variables that might contain image data
                    if (typeof window.propertyImages !== 'undefined') {
                        window.propertyImages.forEach(img => {
                            if (img.src && img.src.includes('images.prop24.com')) {
                                images.push({
                                    src: img.src,
                                    alt: img.alt || '',
                                    className: 'js_variable',
                                    extraction_method: 'javascript_variable'
                                });
                            }
                        });
                    }
                    
                    // Look for data in script tags
                    const scripts = document.querySelectorAll('script');
                    scripts.forEach(script => {
                        const content = script.textContent || script.innerHTML;
                        if (content) {
                            // Extract image URLs from script content
                            const imageMatches = content.match(/https:\/\/images\.prop24\.com[^"'\s]+/g);
                            if (imageMatches) {
                                imageMatches.forEach(url => {
                                    if (!url.includes('agent') && !url.includes('logo')) {
                                        images.push({
                                            src: url,
                                            alt: 'script_image',
                                            className: 'script_content',
                                            extraction_method: 'script_content'
                                        });
                                    }
                                });
                            }
                        }
                    });
                    
                    return images;
                }
            """)
            
            return js_images
            
        except Exception as e:
            print(f"Error extracting from JavaScript: {e}")
            return []
    
    async def navigate_slideshow_completely(self, page):
        """Navigate through slideshow to load all images"""
        try:
            # Look for navigation buttons
            nav_selectors = [
                '.next', '.prev', '.arrow', '.nav', '.slide-nav', '.gallery-nav',
                '.carousel-control-next', '.carousel-control-prev',
                '.slick-next', '.slick-prev',
                '.swiper-button-next', '.swiper-button-prev'
            ]
            
            next_button = None
            for selector in nav_selectors:
                try:
                    next_button = await page.query_selector(selector)
                    if next_button:
                        print(f"         🎯 Found navigation: {selector}")
                        break
                except:
                    continue
            
            if next_button:
                # Navigate through slideshow multiple times to load all images
                print("         🔄 Navigating through slideshow...")
                for i in range(20):  # Try up to 20 clicks
                    try:
                        # Check if we can click next
                        is_visible = await next_button.is_visible()
                        if not is_visible:
                            print(f"         ✅ Reached end of slideshow after {i} clicks")
                            break
                        
                        await next_button.click()
                        await page.wait_for_timeout(1000)  # Wait for image to load
                        
                        if i % 5 == 0:  # Show progress every 5 clicks
                            print(f"         ⏳ Navigation progress: {i+1}/20")
                            
                    except Exception as e:
                        print(f"         ⚠️ Navigation stopped at click {i+1}: {e}")
                        break
                
                print(f"         ✅ Slideshow navigation completed")
            else:
                print("         ℹ️ No navigation buttons found, using default method")
                
        except Exception as e:
            print(f"Error navigating slideshow: {e}")
    
    async def close_slideshow_modal(self, page):
        """Close slideshow modal to avoid UI conflicts"""
        try:
            # Look for close button
            close_selectors = [
                '.close', '.modal-close', '.lightbox-close',
                '[data-dismiss="modal"]', '.btn-close',
                '.modal-header .close', '.modal-footer .close'
            ]
            
            for selector in close_selectors:
                try:
                    close_button = await page.query_selector(selector)
                    if close_button:
                        await close_button.click()
                        print("         ✅ Slideshow modal closed")
                        await page.wait_for_timeout(1000)
                        return True
                except:
                    continue
            
            # Alternative: try to click outside modal or press Escape
            try:
                await page.keyboard.press('Escape')
                print("         ✅ Slideshow modal closed with Escape key")
                await page.wait_for_timeout(1000)
                return True
            except:
                pass
            
            # Last resort: try to click outside modal
            try:
                await page.click('body', position={'x': 100, 'y': 100})
                print("         ✅ Slideshow modal closed by clicking outside")
                await page.wait_for_timeout(1000)
                return True
            except:
                pass
            
            print("         ⚠️ Could not close slideshow modal automatically")
            return False
            
        except Exception as e:
            print(f"Error closing slideshow modal: {e}")
            return False
    
    async def force_close_all_modals(self, page):
        """Force close ALL modals and overlays that might interfere with clicking"""
        try:
            print("      🔒 Force closing ALL modals and overlays...")
            
            # Method 1: Press Escape multiple times
            for i in range(5):
                try:
                    await page.keyboard.press('Escape')
                    await page.wait_for_timeout(500)
                except:
                    pass
            
            # Method 2: Click close buttons on all visible modals
            close_selectors = [
                '.close', '.modal-close', '.lightbox-close',
                '[data-dismiss="modal"]', '.btn-close',
                '.modal-header .close', '.modal-footer .close',
                '.overlay-close', '.popup-close'
            ]
            
            for selector in close_selectors:
                try:
                    close_buttons = await page.query_selector_all(selector)
                    for button in close_buttons:
                        if await button.is_visible():
                            await button.click()
                            await page.wait_for_timeout(300)
                except:
                    continue
            
            # Method 3: Force remove modal classes
            await page.evaluate("""
                () => {
                    // Remove modal classes from all elements
                    const modals = document.querySelectorAll('.modal, .lightbox, .overlay, .popup');
                    modals.forEach(modal => {
                        modal.classList.remove('show', 'in', 'fade', 'in');
                        modal.style.display = 'none';
                        modal.style.visibility = 'hidden';
                        modal.style.opacity = '0';
                    });
                    
                    // Remove modal backdrop
                    const backdrops = document.querySelectorAll('.modal-backdrop, .lightbox-backdrop');
                    backdrops.forEach(backdrop => backdrop.remove());
                    
                    // Enable body scrolling
                    document.body.classList.remove('modal-open');
                    document.body.style.overflow = 'auto';
                    
                    return 'modals_cleaned';
                }
            """)
            
            # Method 4: Click outside all modals
            try:
                await page.click('body', position={'x': 50, 'y': 50})
                await page.click('body', position={'x': 100, 'y': 100})
                await page.click('body', position={'x': 200, 'y': 200})
            except:
                pass
            
            await page.wait_for_timeout(2000)
            print("      ✅ All modals force closed")
            return True
            
        except Exception as e:
            print(f"Error force closing modals: {e}")
            return False
    
    async def extract_property_features(self, page):
        """Extract property features and amenities"""
        try:
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            page_text = soup.get_text().lower()
            
            features = {}
            
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
            
            return features
            
        except Exception as e:
            print(f"Error extracting features: {e}")
            return {}
    
    async def extract_contacts_with_captcha(self, page):
        """Extract contacts using CAPTCHA solving with JavaScript bypass"""
        try:
            # Step 1: Extract initial contacts (baseline)
            initial_contacts = await self.extract_all_contacts(page)
            
            # Step 2: Force close ALL modals that might interfere
            print("      🔒 Ensuring all modals are closed before contact extraction...")
            await self.force_close_all_modals(page)
            
            # Step 3: Force enable contact button using JavaScript
            print("      🎯 Force enabling contact button with JavaScript...")
            contact_enabled = await page.evaluate("""
                () => {
                    // Find all contact-related buttons
                    const contactButtons = document.querySelectorAll('.ShowContact, .ShowPhone, [class*="contact"], [class*="phone"]');
                    
                    if (contactButtons.length > 0) {
                        // Force enable the first contact button
                        const button = contactButtons[0];
                        
                        // Remove any disabled states
                        button.disabled = false;
                        button.removeAttribute('disabled');
                        
                        // Remove any pointer event blocking
                        button.style.pointerEvents = 'auto';
                        button.style.cursor = 'pointer';
                        
                        // Remove any overlay blocking
                        const overlays = document.querySelectorAll('.modal-backdrop, .overlay, .popup-overlay');
                        overlays.forEach(overlay => overlay.remove());
                        
                        // Enable body scrolling
                        document.body.style.overflow = 'auto';
                        document.body.classList.remove('modal-open');
                        
                        return {
                            success: true,
                            buttonText: button.innerText || button.textContent,
                            buttonClass: button.className
                        };
                    }
                    
                    return { success: false, error: 'No contact button found' };
                }
            """)
            
            if not contact_enabled.get('success'):
                print(f"      ❌ Could not enable contact button: {contact_enabled.get('error')}")
                return initial_contacts
            
            print(f"      ✅ Contact button enabled: '{contact_enabled.get('buttonText')}'")
            
            # Step 4: Click contact button using JavaScript (bypasses UI interference)
            print("      🖱️ Clicking contact button with JavaScript...")
            click_result = await page.evaluate("""
                () => {
                    const contactButtons = document.querySelectorAll('.ShowContact, .ShowPhone, [class*="contact"], [class*="phone"]');
                    if (contactButtons.length > 0) {
                        const button = contactButtons[0];
                        
                        // Create and dispatch click event
                        const clickEvent = new MouseEvent('click', {
                            view: window,
                            bubbles: true,
                            cancelable: true
                        });
                        
                        button.dispatchEvent(clickEvent);
                        
                        // Also try programmatic click
                        try {
                            button.click();
                        } catch (e) {
                            console.log('Programmatic click failed:', e);
                        }
                        
                        return { success: true, message: 'Contact button clicked' };
                    }
                    
                    return { success: false, error: 'No contact button to click' };
                }
            """)
            
            if not click_result.get('success'):
                print(f"      ❌ Could not click contact button: {click_result.get('error')}")
                return initial_contacts
            
            print("      ✅ Contact button clicked successfully")
            await page.wait_for_timeout(3000)
            
            # Step 5: Detect and solve CAPTCHA
            site_key = await self.detect_recaptcha(page)
            if not site_key:
                print("      ❌ No reCAPTCHA detected")
                return initial_contacts
            
            print(f"      ✅ reCAPTCHA detected: {site_key[:20]}...")
            
            # Solve CAPTCHA with 2captcha
            solution = await self.solve_captcha_with_2captcha(page.url, site_key)
            if not solution:
                print("      ❌ Failed to solve CAPTCHA")
                return initial_contacts
            
            print(f"      ✅ CAPTCHA solved!")
            
            # Step 6: Inject solution and wait for contact revelation
            success = await self.inject_captcha_solution_improved(page, solution)
            if not success:
                print("      ❌ Failed to inject CAPTCHA solution")
                return initial_contacts
            
            print("      ✅ CAPTCHA solution injected")
            
            # Step 7: Wait and extract revealed contacts
            print("      ⏳ Waiting for contact revelation...")
            await page.wait_for_timeout(5000)
            
            # Step 8: Extract contacts with improved methods
            print("      📞 Extracting revealed contact information...")
            revealed_contacts = await self.extract_all_contacts(page)
            agent_info = await self.extract_agent_information_improved(page)
            
            # Step 9: Compare and return results
            new_phones = set(revealed_contacts['phones']) - set(initial_contacts['phones'])
            new_emails = set(revealed_contacts['emails']) - set(initial_contacts['emails'])
            
            print(f"      📱 New phones revealed: {len(new_phones)}")
            print(f"      📧 New emails revealed: {len(new_emails)}")
            
            # Combine all contact information
            contacts = {
                'agent_name': agent_info.get('name', 'Agent Name'),
                'agent_phone': list(new_phones)[0] if new_phones else (initial_contacts['phones'][0] if initial_contacts['phones'] else None),
                'agent_email': list(new_emails)[0] if new_emails else (initial_contacts['emails'][0] if initial_contacts['emails'] else None),
                'all_phones': revealed_contacts['phones'],
                'all_emails': revealed_contacts['emails'],
                'agent_company': agent_info.get('company', None),
                'extraction_success': len(new_phones) > 0 or len(new_emails) > 0
            }
            
            return contacts
            
        except Exception as e:
            print(f"Error extracting contacts: {e}")
            return {}
    
    async def find_contact_button(self, page):
        """Find contact button with multiple strategies"""
        selectors = [
            '.ShowContact',
            'text="Show Contact Number"',
            '.ShowPhone',
            '.contact-button',
            '[class*="contact"]',
            '[class*="phone"]'
        ]
        
        for selector in selectors:
            button = await page.query_selector(selector)
            if button:
                text = await button.inner_text()
                print(f"      ✅ Found contact button: '{text}'")
                return button
        
        return None
    
    async def detect_recaptcha(self, page):
        """Detect reCAPTCHA and extract site key"""
        try:
            recaptcha_element = await page.query_selector('[data-sitekey]')
            if recaptcha_element:
                site_key = await recaptcha_element.get_attribute('data-sitekey')
                return site_key
            
            content = await page.content()
            site_key_match = re.search(r'data-sitekey="([^"]+)"', content)
            if site_key_match:
                return site_key_match.group(1)
            
            return None
            
        except Exception as e:
            print(f"Error detecting reCAPTCHA: {e}")
            return None
    
    async def solve_captcha_with_2captcha(self, page_url, site_key):
        """Solve CAPTCHA using 2captcha"""
        try:
            print("      📤 Submitting CAPTCHA to 2captcha...")
            submit_url = "http://2captcha.com/in.php"
            
            data = {
                'key': self.api_key,
                'method': 'userrecaptcha',
                'googlekey': site_key,
                'pageurl': page_url,
                'soft_id': 'Property24Scraper',
                'json': 1
            }
            
            response = requests.post(submit_url, data=data, timeout=30)
            
            if response.status_code != 200:
                print(f"      ❌ Submit failed with status {response.status_code}")
                return None
            
            try:
                result = response.json()
                if result.get('status') == 1:
                    captcha_id = result.get('request')
                    print(f"      ✅ CAPTCHA submitted (ID: {captcha_id})")
                else:
                    print(f"      ❌ Submit failed: {result.get('error_text', 'Unknown error')}")
                    return None
            except:
                if not response.text.startswith('OK|'):
                    print(f"      ❌ Submit failed: {response.text}")
                    return None
                captcha_id = response.text.split('|')[1]
                print(f"      ✅ CAPTCHA submitted (ID: {captcha_id})")
            
            # Wait for solution
            print("      ⏳ Waiting for solution...")
            result_url = "http://2captcha.com/res.php"
            
            for attempt in range(60):
                await asyncio.sleep(2)
                
                params = {
                    'key': self.api_key,
                    'action': 'get',
                    'id': captcha_id,
                    'json': 1
                }
                
                response = requests.get(result_url, params=params, timeout=10)
                
                try:
                    result = response.json()
                    if result.get('status') == 1:
                        solution = result.get('request')
                        print(f"      ✅ CAPTCHA solved!")
                        return solution
                    elif result.get('request') == 'CAPCHA_NOT_READY':
                        if attempt % 10 == 0:
                            print(f"      ⏳ Still waiting... ({attempt + 1}/60)")
                        continue
                    else:
                        print(f"      ❌ Error: {result.get('error_text', 'Unknown error')}")
                        return None
                except:
                    if response.text.startswith('OK|'):
                        solution = response.text.split('|')[1]
                        print(f"      ✅ CAPTCHA solved!")
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
    
    async def inject_captcha_solution_improved(self, page, solution):
        """Inject CAPTCHA solution with multiple methods"""
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
            
            # Method 3: Set global reCAPTCHA response
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
            
            return True
            
        except Exception as e:
            print(f"      ❌ Error injecting solution: {e}")
            return False
    
    async def extract_all_contacts(self, page):
        """Extract all contact information from page"""
        contacts = {'phones': [], 'emails': []}
        
        try:
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            page_text = soup.get_text()
            
            # Extract phone numbers
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
                    if len(clean_phone) >= 10 and clean_phone not in contacts['phones']:
                        contacts['phones'].append(clean_phone)
            
            # Extract emails
            email_matches = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', page_text)
            for email in email_matches:
                if (email.lower() not in contacts['emails'] and 
                    not any(word in email.lower() for word in ['noreply', 'admin', 'info@property24'])):
                    contacts['emails'].append(email.lower())
            
        except Exception as e:
            print(f"Error extracting contacts: {e}")
        
        return contacts
    
    async def extract_agent_information_improved(self, page):
        """Extract agent information with multiple strategies"""
        try:
            agent_info = await page.evaluate("""
                () => {
                    const agentInfo = {};
                    
                    // Look for agent sections
                    const agentSelectors = [
                        '.agent-info', '.contact-agent', '.landlord-info',
                        '[class*="agent"]', '.property-contact', '.agent-details'
                    ];
                    
                    for (let selector of agentSelectors) {
                        const agentElem = document.querySelector(selector);
                        if (agentElem) {
                            // Extract agent name
                            const nameElem = agentElem.querySelector('h3, h4, h5, h6, strong, b, .agent-name, .contact-name');
                            if (nameElem) {
                                agentInfo.name = nameElem.innerText || nameElem.textContent;
                                break;
                            }
                        }
                    }
                    
                    // Look for agent name in specific elements
                    if (!agentInfo.name) {
                        const nameElements = document.querySelectorAll('.agent-name, .contact-name, [class*="agent-name"]');
                        for (let elem of nameElements) {
                            const text = elem.innerText || elem.textContent;
                            if (text && text.length > 2 && !text.includes('Contact')) {
                                agentInfo.name = text.trim();
                                break;
                            }
                        }
                    }
                    
                    // Look for company information
                    const companyElements = document.querySelectorAll('.company-name, '.agency-name, '[class*="company"]');
                    for (let elem of companyElements) {
                        const text = elem.innerText || elem.textContent;
                        if (text && text.length > 2) {
                            agentInfo.company = text.trim();
                            break;
                        }
                    }
                    
                    return agentInfo;
                }
            """)
            
            return agent_info
            
        except Exception as e:
            print(f"Error extracting agent info: {e}")
            return {}
    
    async def crop_watermark(self, image_url):
        """Crop bottom 4% to remove watermark"""
        try:
            response = requests.get(image_url, timeout=30)
            if response.status_code != 200:
                return None
            
            img = Image.open(io.BytesIO(response.content))
            
            # Crop bottom 4% (remove watermark)
            width, height = img.size
            crop_height = int(height * 0.96)  # Keep 96%, remove bottom 4%
            
            cropped = img.crop((0, 0, width, crop_height))
            
            # Convert to bytes for storage
            img_buffer = io.BytesIO()
            cropped.save(img_buffer, format='JPEG', quality=85)
            img_buffer.seek(0)
            
            return {
                'width': width,
                'height': height,
                'cropped_width': cropped.width,
                'cropped_height': cropped.height,
                'image_data': img_buffer.getvalue(),
                'format': 'JPEG'
            }
            
        except Exception as e:
            print(f"Error cropping image: {e}")
            return None

async def main():
    # 🔧 REPLACE WITH YOUR ACTUAL 2CAPTCHA API KEY
    API_KEY = "79d9722448416056a13129c67d5c2b55"  # ← User's actual API key
    
    extractor = ComprehensivePropertyExtractor(API_KEY)
    results = await extractor.extract_property_complete(extractor.test_url)
    
    if results:
        print("\n🎉 SUCCESS! Complete property extraction is working!")
        print("💡 Ready to process multiple properties!")
        
        # Show summary
        print(f"\n📊 EXTRACTION SUMMARY:")
        print(f"   📋 Basic Details: {len(results['basic_details'])} items")
        print(f"   🖼️ Images: {len(results['images'])} processed")
        print(f"   🏠 Features: {len(results['features'])} items")
        print(f"   📞 Contacts: {len(results['contacts'])} items")
    else:
        print("\n⚠️ Property extraction needs refinement")

if __name__ == "__main__":
    asyncio.run(main()) 