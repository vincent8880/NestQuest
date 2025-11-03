#!/usr/bin/env python3

import asyncio
from playwright.async_api import async_playwright
import json

async def test_detail_extraction():
    """Test detail extraction from a property page"""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Go to listings page
        await page.goto('https://www.property24.co.ke/houses-to-rent-in-kileleshwa-s14529?sortorder=quality')
        await page.wait_for_load_state('domcontentloaded')
        
        # Dismiss any overlays
        for sel in ['button:has-text("Accept")', 'button:has-text("Yes")', 'button:has-text("I Agree")', 'button:has-text("OK")']:
            try:
                await page.locator(sel).first.click(timeout=1500)
                await page.wait_for_timeout(200)
            except:
                pass
        
        # Get property links
        hrefs = await page.evaluate('''() => { 
            const out = []; 
            const as = Array.from(document.querySelectorAll('a[href]')); 
            for (const a of as) { 
                const href = a.getAttribute('href'); 
                if (!href) continue; 
                let u; 
                try { 
                    u = new URL(href, location.href); 
                } catch { 
                    continue; 
                } 
                if (/-\d{6,}\/?$/.test(u.pathname)) { 
                    out.push(u.href); 
                } 
            } 
            return Array.from(new Set(out)); 
        }''')
        
        if hrefs:
            print(f'Found {len(hrefs)} property links')
            print(f'Testing first property: {hrefs[0]}')
            
            # Go to first property
            await page.goto(hrefs[0])
            await page.wait_for_load_state('domcontentloaded')
            
            # Dismiss "Sign In Required" overlay
            try:
                await page.locator('button:has-text("×"), button:has-text("Close"), .close, [aria-label="Close"]').first.click(timeout=2000)
                await page.wait_for_timeout(500)
            except:
                pass
            
            # Extract details
            details = await page.evaluate('''() => { 
                const data = {}; 
                const getText = (sel) => { 
                    const el = document.querySelector(sel); 
                    return el ? (el.textContent || '').trim() : ''; 
                };
                
                // Basic info
                data.price = getText('.p24_price, .price, [class*="price"]');
                data.title = getText('h1.p24_pageTitle, h1[itemprop="name"], h1');
                data.address = getText('.p24_address, [itemprop="address"], .p24_location');
                
                // Extract from full text using regex
                const allText = document.body.textContent || '';
                const m = (re) => { 
                    const r = allText.match(re); 
                    return r ? r[1] : ''; 
                };
                
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
                    if (t && t.length < 60) features.push(t); 
                });
                if (features.length) data.features = features;
                
                // Listing number
                const ln = m(/Listing Number\s*(\d{6,})/i) || m(/Web Ref\s*(\d{6,})/i); 
                if (ln) data.listing_number = ln;
                
                return data; 
            }''')
            
            print('\n=== EXTRACTED DETAILS ===')
            print(json.dumps(details, indent=2, ensure_ascii=False))
            
        else:
            print('No property links found')
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_detail_extraction())