#!/usr/bin/env python3

import asyncio
import requests
from playwright.async_api import async_playwright
from PIL import Image
import io
import json

class JavaScriptSlideshowNavigator:
    """Use JavaScript to navigate slideshow and extract all 26 images"""
    
    def __init__(self):
        self.test_url = "https://www.property24.co.ke/5-bedroom-house-to-rent-in-kileleshwa-116393360"
    
    async def navigate_with_javascript(self):
        """Use JavaScript to navigate slideshow"""
        
        print("🖼️ JAVASCRIPT SLIDESHOW NAVIGATION")
        print("=" * 50)
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            
            try:
                print("🌐 Loading Property24 page...")
                await page.goto(self.test_url, wait_until='domcontentloaded')
                await page.wait_for_timeout(5000)
                
                # Step 1: Open slideshow modal
                print("🖱️ Step 1: Opening slideshow modal...")
                try:
                    await page.click('.js_lightboxImageSrc')
                    await page.wait_for_timeout(3000)
                    print("   ✅ Slideshow modal opened")
                except Exception as e:
                    print(f"   ❌ Failed to open slideshow: {e}")
                    return []
                
                # Step 2: Use JavaScript to navigate through slideshow
                print("\n🔄 Step 2: Using JavaScript to navigate slideshow...")
                all_images = []
                seen_urls = set()
                
                # Start with current image
                current_images = await self.extract_current_images(page)
                all_images.extend(current_images)
                for img in current_images:
                    seen_urls.add(img['src'])
                
                print(f"   Starting with {len(current_images)} images")
                
                # Step 2a: Detect total photo count if present
                print("\n🔢 Step 2a: Detecting total photo count...")
                try:
                    total_photos = await page.evaluate("""
                        () => {
                            // Try common counters like "1 of 33"
                            const text = document.body.innerText;
                            const m = text.match(/\b(\d+)\s*of\s*(\d+)\b/i);
                            if (m && m[2]) return parseInt(m[2]);
                            // Try counting thumbnails in modal
                            const thumbs = document.querySelectorAll('.p24_modal .p24_galleryThumbnail img, .p24_modal .thumbnail img, .p24_modal [class*="thumb"] img');
                            if (thumbs && thumbs.length > 0) return thumbs.length;
                            // Fallback: 0 (unknown)
                            return 0;
                        }
                    """)
                    if total_photos:
                        print(f"   Detected total photos: {total_photos}")
                    else:
                        print("   Could not detect total photo count (will proceed heuristically)")
                except Exception as e:
                    print(f"   Counter detection error: {e}")
                    total_photos = 0

                # Step 2b: Thumbnail-driven extraction (programmatic clicking)
                print("\n🖼️ Step 2b: Thumbnail-driven extraction...")
                try:
                    thumb_urls = await page.evaluate("""
                        () => {
                            const urls = new Set();
                            const thumbs = document.querySelectorAll(
                                '.p24_modal .p24_galleryThumbnail img, .p24_modal .thumbnail img, .p24_modal [class*="thumb"] img,\
                                 .p24_galleryThumbnail img, .thumbnail img, [class*="thumb"] img'
                            );
                            thumbs.forEach(img => {
                                const u = img.src || img.dataset.src || img.dataset.lazy || img.dataset.original;
                                if (u) urls.add(u);
                            });
                            return Array.from(urls);
                        }
                    """)
                    print(f"   Found {len(thumb_urls)} thumbnail candidates")

                    # Click through thumbnails and collect full-size
                    clicked_fullsize = await page.evaluate("""
                        (async () => {
                            const collected = new Set();
                            const sleep = (ms) => new Promise(r => setTimeout(r, ms));
                            const getFull = () => {
                                const img = document.querySelector('.p24_modal .js_lightboxImage, .p24_modal .img-responsive, .lightbox .js_lightboxImage, .lightbox .img-responsive');
                                return img && img.src ? img.src : null;
                            };

                            // Prefer modal thumbnails
                            let thumbs = document.querySelectorAll('.p24_modal .p24_galleryThumbnail img, .p24_modal .thumbnail img, .p24_modal [class*="thumb"] img');
                            if (!thumbs || thumbs.length === 0) {
                                // Fallback to any thumbs
                                thumbs = document.querySelectorAll('.p24_galleryThumbnail img, .thumbnail img, [class*="thumb"] img');
                            }

                            // Try clicking each thumb
                            for (let i = 0; i < thumbs.length; i++) {
                                try {
                                    const el = thumbs[i];
                                    el.scrollIntoView({ block: 'center', behavior: 'instant' });
                                    el.click();
                                    await sleep(700);
                                    const full = getFull();
                                    if (full) collected.add(full);
                                } catch {}
                            }

                            // If still low count, try pressing right arrow repeatedly
                            if (collected.size < 25) {
                                for (let i = 0; i < 50; i++) {
                                    try {
                                        const next = document.querySelector('.p24_next, .js_pp_next, [id="nextImage"], .js_lightboxNext');
                                        if (next) {
                                            next.click();
                                        } else {
                                            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' }));
                                        }
                                        await sleep(700);
                                        const full = getFull();
                                        if (full) collected.add(full);
                                    } catch {}
                                }
                            }

                            return Array.from(collected);
                        })();
                    """)

                    new_from_clicks = 0
                    for u in clicked_fullsize:
                        if u not in seen_urls:
                            seen_urls.add(u)
                            all_images.append({
                                'src': u,
                                'alt': 'thumb-click',
                                'className': 'thumb-click',
                                'wrapperClass': 'thumb-click',
                                'isVisible': True
                            })
                            new_from_clicks += 1
                    print(f"   Added {new_from_clicks} images via thumbnail clicking")
                except Exception as e:
                    print(f"   Thumbnail-driven extraction error: {e}")

                # Use JavaScript to trigger next/previous navigation
                navigation_attempts = 0
                max_attempts = 30  # Prevent infinite loop
                
                while navigation_attempts < max_attempts:
                    navigation_attempts += 1
                    print(f"\n   🔄 JavaScript navigation attempt {navigation_attempts}")
                    
                    # Try JavaScript next navigation
                    try:
                        next_result = await page.evaluate("""
                            () => {
                                // Try multiple ways to trigger next
                                const nextSelectors = [
                                    '.p24_next', '.js_pp_next', '.js_lightboxNext',
                                    '[id="nextImage"]', '.next', '.slick-next'
                                ];
                                
                                for (const selector of nextSelectors) {
                                    const element = document.querySelector(selector);
                                    if (element) {
                                        console.log('Found next element:', selector);
                                        
                                        // Try different trigger methods
                                        try {
                                            // Method 1: Direct click
                                            element.click();
                                            return { success: true, method: 'click', selector: selector };
                                        } catch (e) {
                                            console.log('Click failed, trying dispatchEvent');
                                            
                                            // Method 2: Dispatch event
                                            const clickEvent = new MouseEvent('click', {
                                                bubbles: true,
                                                cancelable: true,
                                                view: window
                                            });
                                            element.dispatchEvent(clickEvent);
                                            return { success: true, method: 'dispatchEvent', selector: selector };
                                        }
                                    }
                                }
                                
                                return { success: false, error: 'No next element found' };
                            }
                        """)
                        
                        if next_result.get('success'):
                            print(f"      ✅ JavaScript next navigation: {next_result['method']} on {next_result['selector']}")
                            await page.wait_for_timeout(2000)
                            
                            # Extract new images
                            new_images = await self.extract_current_images(page)
                            new_count = 0
                            for img in new_images:
                                if img['src'] not in seen_urls:
                                    seen_urls.add(img['src'])
                                    all_images.append(img)
                                    new_count += 1
                            
                            print(f"      Found {new_count} new images")
                            
                            if new_count == 0:
                                print("      ⚠️ No new images found, trying previous navigation")
                                break
                        else:
                            print(f"      ❌ JavaScript next failed: {next_result.get('error')}")
                            break
                            
                    except Exception as e:
                        print(f"      ❌ JavaScript navigation error: {e}")
                        break
                
                # Try JavaScript previous navigation
                print("\n   🔄 Trying JavaScript previous navigation...")
                prev_attempts = 0
                while prev_attempts < 10:
                    prev_attempts += 1
                    try:
                        prev_result = await page.evaluate("""
                            () => {
                                // Try multiple ways to trigger previous
                                const prevSelectors = [
                                    '.p24_prev', '.js_pp_prev', '.js_lightboxPrevious',
                                    '[id="previousImage"]', '.prev', '.slick-prev'
                                ];
                                
                                for (const selector of prevSelectors) {
                                    const element = document.querySelector(selector);
                                    if (element) {
                                        console.log('Found prev element:', selector);
                                        
                                        // Try different trigger methods
                                        try {
                                            // Method 1: Direct click
                                            element.click();
                                            return { success: true, method: 'click', selector: selector };
                                        } catch (e) {
                                            console.log('Click failed, trying dispatchEvent');
                                            
                                            // Method 2: Dispatch event
                                            const clickEvent = new MouseEvent('click', {
                                                bubbles: true,
                                                cancelable: true,
                                                view: window
                                            });
                                            element.dispatchEvent(clickEvent);
                                            return { success: true, method: 'dispatchEvent', selector: selector };
                                        }
                                    }
                                }
                                
                                return { success: false, error: 'No prev element found' };
                            }
                        """)
                        
                        if prev_result.get('success'):
                            print(f"      ✅ JavaScript prev navigation: {prev_result['method']} on {prev_result['selector']}")
                            await page.wait_for_timeout(2000)
                            
                            # Extract new images
                            new_images = await self.extract_current_images(page)
                            new_count = 0
                            for img in new_images:
                                if img['src'] not in seen_urls:
                                    seen_urls.add(img['src'])
                                    all_images.append(img)
                                    new_count += 1
                            
                            print(f"      Found {new_count} new images")
                        else:
                            print(f"      ❌ JavaScript prev failed: {prev_result.get('error')}")
                            break
                            
                    except Exception as e:
                        print(f"      ❌ JavaScript prev navigation error: {e}")
                        break
                
                # Step 3: Try to extract all images from JavaScript variables
                print("\n🔍 Step 3: Extracting images from JavaScript variables...")
                js_images = await page.evaluate("""
                    () => {
                        const images = [];
                        
                        // Look for images in global variables
                        if (window.galleryImages) {
                            console.log('Found galleryImages:', window.galleryImages);
                            window.galleryImages.forEach((img, index) => {
                                if (img && img.includes('images.prop24.com')) {
                                    images.push({
                                        src: img,
                                        alt: 'js-gallery',
                                        className: 'js-gallery',
                                        wrapperClass: 'javascript-variable',
                                        isVisible: true
                                    });
                                }
                            });
                        }
                        
                        // Look for images in data attributes
                        const dataImages = document.querySelectorAll('[data-images], [data-gallery], [data-photos]');
                        dataImages.forEach(el => {
                            try {
                                const data = JSON.parse(el.dataset.images || el.dataset.gallery || el.dataset.photos);
                                if (Array.isArray(data)) {
                                    data.forEach(img => {
                                        if (img && img.includes('images.prop24.com')) {
                                            images.push({
                                                src: img,
                                                alt: 'data-attribute',
                                                className: el.className,
                                                wrapperClass: 'data-attribute',
                                                isVisible: true
                                            });
                                        }
                                    });
                                }
                            } catch (e) {
                                // Ignore JSON parse errors
                            }
                        });
                        
                        // Look for images in script tags
                        const scripts = document.querySelectorAll('script');
                        scripts.forEach(script => {
                            const content = script.textContent || script.innerHTML;
                            const matches = content.match(/https:\/\/images\.prop24\.com\/[^"'\s]+/g);
                            if (matches) {
                                matches.forEach(url => {
                                    images.push({
                                        src: url,
                                        alt: 'script-content',
                                        className: 'script',
                                        wrapperClass: 'script-content',
                                        isVisible: true
                                    });
                                });
                            }
                        });
                        
                        return images;
                    }
                """)
                
                print(f"   Found {len(js_images)} JavaScript images")
                for img in js_images:
                    if img['src'] not in seen_urls:
                        seen_urls.add(img['src'])
                        all_images.append(img)
                
                # Step 4: Final extraction from modal
                print("\n📸 Step 4: Final extraction from modal...")
                final_images = await self.extract_all_modal_images(page)
                for img in final_images:
                    if img['src'] not in seen_urls:
                        seen_urls.add(img['src'])
                        all_images.append(img)
                
                print(f"\n📊 Total unique images found: {len(all_images)}")
                
                # Display all found images
                print("\n📸 All found images:")
                for i, img in enumerate(all_images):
                    print(f"   {i+1:2d}. {img['src']}")
                    print(f"       Type: {img['wrapperClass']}, Visible: {img['isVisible']}")
                
                # Process and crop images
                processed_images = []
                for i, img_data in enumerate(all_images):
                    img_url = img_data['src']
                    print(f"\n   Processing image {i+1}: {img_url}")
                    
                    # Download and crop image
                    try:
                        cropped_image = await self.crop_watermark(img_url)
                        if cropped_image:
                            processed_images.append({
                                'original_url': img_url,
                                'cropped_width': cropped_image['cropped_width'],
                                'cropped_height': cropped_image['cropped_height'],
                                'original_width': cropped_image['width'],
                                'original_height': cropped_image['height'],
                                'format': cropped_image['format'],
                                'alt': img_data.get('alt', ''),
                                'class': img_data.get('className', ''),
                                'wrapper_class': img_data.get('wrapperClass', ''),
                                'is_visible': img_data.get('isVisible', False)
                            })
                            print(f"      ✅ Cropped and processed")
                        else:
                            print(f"      ❌ Failed to process")
                    except Exception as e:
                        print(f"      ❌ Error processing: {e}")
                
                # Save results
                results = {
                    'all_images': all_images,
                    'processed_images': processed_images,
                    'total_found': len(all_images),
                    'total_processed': len(processed_images),
                    'navigation_attempts': navigation_attempts
                }
                
                with open('javascript_slideshow_results.json', 'w') as f:
                    json.dump(results, f, indent=2)
                
                print(f"\n📊 Results: {len(processed_images)} images processed")
                print("💾 Results saved to 'javascript_slideshow_results.json'")
                
                return processed_images
                
            except Exception as e:
                print(f"❌ Error: {e}")
                return []
            finally:
                await browser.close()
    
    async def extract_current_images(self, page):
        """Extract images currently visible in modal"""
        return await page.evaluate("""
            () => {
                const images = [];
                
                // Get all images from modal
                const modalImages = document.querySelectorAll('.p24_modal img, .modal img, .lightbox img');
                modalImages.forEach((img, index) => {
                    const src = img.src || img.dataset.src || img.dataset.lazy || img.dataset.original;
                    if (src && src.includes('images.prop24.com')) {
                        images.push({
                            src: src,
                            alt: img.alt || '',
                            className: img.className || '',
                            wrapperClass: 'modal',
                            isVisible: img.offsetWidth > 0 && img.offsetHeight > 0
                        });
                    }
                });
                
                // Get background images from modal
                const modalElements = document.querySelectorAll('.p24_modal *, .modal *, .lightbox *');
                modalElements.forEach((el, index) => {
                    const style = window.getComputedStyle(el);
                    const bgImage = style.backgroundImage;
                    if (bgImage && bgImage !== 'none' && bgImage.includes('images.prop24.com')) {
                        const url = bgImage.replace(/url\\(['"]?([^'"]+)['"]?\\)/, '$1');
                        images.push({
                            src: url,
                            alt: 'background-image',
                            className: el.className || '',
                            wrapperClass: 'modal-background',
                            isVisible: el.offsetWidth > 0 && el.offsetHeight > 0
                        });
                    }
                });
                
                return images;
            }
        """)
    
    async def extract_all_modal_images(self, page):
        """Extract all images from modal including hidden ones"""
        return await page.evaluate("""
            () => {
                const images = [];
                
                // Get ALL images from modal (including hidden)
                const allModalImages = document.querySelectorAll('.p24_modal img, .modal img, .lightbox img, .js_lightboxImageWrapper img');
                allModalImages.forEach((img, index) => {
                    const src = img.src || img.dataset.src || img.dataset.lazy || img.dataset.original;
                    if (src && src.includes('images.prop24.com')) {
                        images.push({
                            src: src,
                            alt: img.alt || '',
                            className: img.className || '',
                            wrapperClass: 'modal-all',
                            isVisible: img.offsetWidth > 0 && img.offsetHeight > 0
                        });
                    }
                });
                
                // Get background images from all modal elements
                const allModalElements = document.querySelectorAll('.p24_modal *, .modal *, .lightbox *, .js_lightboxImageWrapper *');
                allModalElements.forEach((el, index) => {
                    const style = window.getComputedStyle(el);
                    const bgImage = style.backgroundImage;
                    if (bgImage && bgImage !== 'none' && bgImage.includes('images.prop24.com')) {
                        const url = bgImage.replace(/url\\(['"]?([^'"]+)['"]?\\)/, '$1');
                        images.push({
                            src: url,
                            alt: 'background-image',
                            className: el.className || '',
                            wrapperClass: 'modal-background-all',
                            isVisible: el.offsetWidth > 0 && el.offsetHeight > 0
                        });
                    }
                });
                
                return images;
            }
        """)
    
    async def crop_watermark(self, image_url):
        """Crop bottom 4% to remove watermark"""
        try:
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
    navigator = JavaScriptSlideshowNavigator()
    results = await navigator.navigate_with_javascript()
    
    if results:
        print(f"\n✅ Successfully extracted {len(results)} slideshow images!")
        print("💡 Images have been cropped to remove watermarks.")
    else:
        print("\n❌ No slideshow images extracted.")

if __name__ == "__main__":
    asyncio.run(main()) 