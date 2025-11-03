#!/usr/bin/env python3

import asyncio
import requests
import json
from playwright.async_api import async_playwright

class ImageVariantTester:
    """Test different Property24 image URL patterns to find clean versions"""
    
    def __init__(self):
        self.test_url = "https://www.property24.co.ke/3-bedroom-apartment-flat-to-rent-in-kileleshwa-116153975"
        self.base_image_id = "220008296"  # From the working image
    
    async def test_image_variants(self):
        """Test different image URL patterns"""
        
        print("🔍 TESTING PROPERTY24 IMAGE VARIANTS")
        print("=" * 50)
        
        # Different URL patterns to test
        image_variants = [
            # Original/Full size
            f"https://images.prop24.com/{self.base_image_id}/Original",
            f"https://images.prop24.com/{self.base_image_id}/Full",
            f"https://images.prop24.com/{self.base_image_id}/Raw",
            
            # Different sizes
            f"https://images.prop24.com/{self.base_image_id}/Fit800x600",
            f"https://images.prop24.com/{self.base_image_id}/Fit1024x768",
            f"https://images.prop24.com/{self.base_image_id}/Fit1200x800",
            f"https://images.prop24.com/{self.base_image_id}/Fit1600x1200",
            
            # Cropped versions
            f"https://images.prop24.com/{self.base_image_id}/Crop800x600",
            f"https://images.prop24.com/{self.base_image_id}/Crop1024x768",
            f"https://images.prop24.com/{self.base_image_id}/Crop1200x800",
            
            # Different aspect ratios
            f"https://images.prop24.com/{self.base_image_id}/Fit16x9",
            f"https://images.prop24.com/{self.base_image_id}/Fit4x3",
            f"https://images.prop24.com/{self.base_image_id}/Fit3x2",
            
            # Quality variations
            f"https://images.prop24.com/{self.base_image_id}/High",
            f"https://images.prop24.com/{self.base_image_id}/Medium",
            f"https://images.prop24.com/{self.base_image_id}/Low",
            
            # Without watermark
            f"https://images.prop24.com/{self.base_image_id}/NoWatermark",
            f"https://images.prop24.com/{self.base_image_id}/Clean",
            f"https://images.prop24.com/{self.base_image_id}/Original",
        ]
        
        working_images = []
        
        print("🧪 Testing image variants...")
        for i, url in enumerate(image_variants, 1):
            try:
                response = requests.head(url, timeout=10)
                if response.status_code == 200:
                    print(f"   ✅ {i:2d}. {url}")
                    working_images.append(url)
                else:
                    print(f"   ❌ {i:2d}. {url} (Status: {response.status_code})")
            except Exception as e:
                print(f"   ❌ {i:2d}. {url} (Error: {str(e)[:30]}...)")
        
        print(f"\n📊 Results: {len(working_images)} working variants found")
        
        # Test the working images in browser
        if working_images:
            await self.test_images_in_browser(working_images)
        
        return working_images
    
    async def test_images_in_browser(self, image_urls):
        """Test images in browser to see which ones look best"""
        
        print("\n🌐 Testing images in browser...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            
            # Create HTML to display all variants
            html_content = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Property24 Image Variants</title>
                <style>
                    body { font-family: Arial, sans-serif; padding: 20px; background: #f5f5f5; }
                    .header { text-align: center; margin-bottom: 30px; }
                    .image-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
                    .image-card { background: white; border-radius: 10px; padding: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                    .image-card img { width: 100%; height: auto; border-radius: 5px; margin-bottom: 10px; }
                    .image-info { font-size: 12px; color: #666; }
                    .image-url { word-break: break-all; font-family: monospace; font-size: 10px; background: #f0f0f0; padding: 5px; border-radius: 3px; }
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>🏠 Property24 Image Variants</h1>
                    <p>Testing different image formats and sizes</p>
                </div>
                <div class="image-grid">
            """
            
            for i, url in enumerate(image_urls, 1):
                # Extract variant name from URL
                variant = url.split('/')[-1]
                
                html_content += f"""
                <div class="image-card">
                    <img src="{url}" alt="Variant {i}" onerror="this.style.display='none'; this.nextElementSibling.style.display='block';">
                    <div style="display:none; color:red; text-align:center; padding:20px;">
                        ❌ Failed to load
                    </div>
                    <div class="image-info">
                        <strong>Variant {i}</strong><br>
                        <strong>Format:</strong> {variant}<br>
                    </div>
                    <div class="image-url">{url}</div>
                </div>
                """
            
            html_content += """
                </div>
                <div style="margin-top: 30px; text-align: center; color: #666;">
                    <p><strong>Instructions:</strong> Look for images without Property24 watermarks at the bottom</p>
                </div>
            </body>
            </html>
            """
            
            # Save and open HTML file
            html_file = 'image_variants.html'
            with open(html_file, 'w') as f:
                f.write(html_content)
            
            print(f"💾 HTML file created: {html_file}")
            print("🌐 Opening image variants in browser...")
            
            # Open in browser
            await page.goto(f'file://{html_file}')
            await page.wait_for_timeout(10000)  # Wait 10 seconds for user to view
            
            await browser.close()
    
    async def find_alternative_image_sources(self):
        """Look for alternative image sources on the page"""
        
        print("\n🔍 Looking for alternative image sources...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            
            try:
                await page.goto(self.test_url, wait_until='domcontentloaded')
                await page.wait_for_timeout(5000)
                
                # Look for images in JavaScript variables
                js_images = await page.evaluate("""
                    () => {
                        const images = [];
                        
                        // Check for images in data attributes
                        document.querySelectorAll('[data-image], [data-src], [data-original]').forEach(el => {
                            const dataImage = el.dataset.image || el.dataset.src || el.dataset.original;
                            if (dataImage && dataImage.includes('images.prop24.com')) {
                                images.push({
                                    type: 'data-attribute',
                                    url: dataImage,
                                    element: el.tagName + '.' + el.className
                                });
                            }
                        });
                        
                        // Check for images in script tags
                        document.querySelectorAll('script').forEach(script => {
                            const content = script.textContent || script.innerHTML;
                            const matches = content.match(/https:\/\/images\.prop24\.com\/[^"'\s]+/g);
                            if (matches) {
                                matches.forEach(url => {
                                    images.push({
                                        type: 'script-content',
                                        url: url,
                                        element: 'script'
                                    });
                                });
                            }
                        });
                        
                        // Check for images in JSON-LD structured data
                        document.querySelectorAll('script[type="application/ld+json"]').forEach(script => {
                            try {
                                const data = JSON.parse(script.textContent);
                                if (data.image) {
                                    if (Array.isArray(data.image)) {
                                        data.image.forEach(img => {
                                            if (typeof img === 'string' && img.includes('images.prop24.com')) {
                                                images.push({
                                                    type: 'json-ld',
                                                    url: img,
                                                    element: 'json-ld'
                                                });
                                            }
                                        });
                                    } else if (typeof data.image === 'string' && data.image.includes('images.prop24.com')) {
                                        images.push({
                                            type: 'json-ld',
                                            url: data.image,
                                            element: 'json-ld'
                                        });
                                    }
                                }
                            } catch (e) {
                                // Ignore JSON parse errors
                            }
                        });
                        
                        return images;
                    }
                """)
                
                if js_images:
                    print(f"   Found {len(js_images)} alternative image sources:")
                    for img in js_images:
                        print(f"      {img['type']}: {img['url']}")
                else:
                    print("   No alternative image sources found")
                
            except Exception as e:
                print(f"   Error finding alternative sources: {e}")
            finally:
                await browser.close()

async def main():
    tester = ImageVariantTester()
    
    # Test different URL patterns
    working_variants = await tester.test_image_variants()
    
    # Look for alternative sources
    await tester.find_alternative_image_sources()
    
    if working_variants:
        print(f"\n✅ Found {len(working_variants)} working image variants!")
        print("💡 Check the browser to see which ones look best without watermarks.")
    else:
        print("\n❌ No working image variants found.")

if __name__ == "__main__":
    asyncio.run(main()) 