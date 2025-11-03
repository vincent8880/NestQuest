#!/usr/bin/env python3

import asyncio
import json
import re
from urllib.parse import urljoin

from playwright.async_api import async_playwright

LIST_URL = "https://www.property24.co.ke/property-for-sale-in-kileleshwa-s14529?Page=1"


def extract_property_id(url: str) -> str:
    m = re.search(r"/(\d{6,})\b", url)
    return m.group(1) if m else url.rstrip("/").split("/")[-1]


async def collect_first_n_property_links(page, n: int = 3):
    await page.wait_for_load_state("domcontentloaded")
    # Accept/close cookie banners
    for sel in [
        'button:has-text("Accept")',
        'button:has-text("Yes")',
        'button:has-text("I Agree")',
        'button:has-text("OK")'
    ]:
        try:
            await page.locator(sel).first.click(timeout=1500)
            await page.wait_for_timeout(300)
        except Exception:
            pass

    # Collect anchors that look like property detail pages, i.e., end with a numeric ID
    hrefs = await page.evaluate(
        """
        () => {
            const out = [];
            const as = Array.from(document.querySelectorAll('a[href]'));
            for (const a of as) {
                const href = a.getAttribute('href');
                if (!href) continue;
                // normalize
                let u;
                try { u = new URL(href, location.href); } catch { continue; }
                // property detail pages usually end with -<digits>
                if (/-(\d{6,})\/?$/.test(u.pathname)) {
                    out.push(u.href);
                }
            }
            // de-dup preserving order
            return Array.from(new Set(out));
        }
        """
    )

    links = hrefs[:n]
    print(f"Found {len(links)} detail links on listing page")
    for i, u in enumerate(links, 1):
        print(f"  {i}. {u}")
    return links


async def open_slideshow_and_collect_images(page):
    # Accept cookies/overlays if present
    for sel in [
        'button:has-text("Accept")',
        'button:has-text("Yes")',
        'button:has-text("I Agree")',
        'button:has-text("OK")'
    ]:
        try:
            await page.locator(sel).first.click(timeout=1500)
            await page.wait_for_timeout(200)
        except Exception:
            pass

    # Try to open slideshow modal by clicking common triggers
    opened = False
    for selector in [
        '.js_lightboxImageSrc',
        '.p24_galleryThumbnail img',
        '.js_lightboxImageWrapper img',
        '.p24_gallery img',
        '.lightbox img',
        '.gallery img',
        'img'
    ]:
        try:
            loc = page.locator(selector).first
            if await loc.count() > 0:
                await loc.scroll_into_view_if_needed()
                await loc.click(timeout=3000)
                await page.wait_for_timeout(800)
                opened = True
                break
        except Exception:
            continue

    images = []
    if opened:
        # 1) Click through thumbs and use ArrowRight/next to hydrate slides
        try:
            clicked_fullsize = await page.evaluate(
                """
                (async () => {
                    const collected = new Set();
                    const sleep = (ms) => new Promise(r => setTimeout(r, ms));
                    const getFull = () => {
                        const img = document.querySelector('.p24_modal .js_lightboxImage, .p24_modal .img-responsive, .lightbox .js_lightboxImage, .lightbox .img-responsive');
                        return img && img.src ? img.src : null;
                    };

                    let thumbs = document.querySelectorAll('.p24_modal .p24_galleryThumbnail img, .p24_modal .thumbnail img, .p24_modal [class*="thumb"] img');
                    if (!thumbs || thumbs.length === 0) {
                        thumbs = document.querySelectorAll('.p24_galleryThumbnail img, .thumbnail img, [class*="thumb"] img');
                    }

                    for (let i = 0; i < thumbs.length; i++) {
                        try {
                            const el = thumbs[i];
                            el.scrollIntoView({ block: 'center' });
                            el.click();
                            await sleep(600);
                            const full = getFull();
                            if (full) collected.add(full);
                        } catch {}
                    }

                    if (collected.size < 30) {
                        for (let i = 0; i < 60; i++) {
                            try {
                                const next = document.querySelector('.p24_next, .js_pp_next, [id="nextImage"], .js_lightboxNext');
                                if (next) {
                                    next.click();
                                } else {
                                    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' }));
                                }
                                await sleep(600);
                                const full = getFull();
                                if (full) collected.add(full);
                            } catch {}
                        }
                    }

                    return Array.from(collected);
                })();
                """
            )
            images.extend(clicked_fullsize)
        except Exception:
            pass

        # 2) Visible modal images and backgrounds
        try:
            modal_imgs = await page.evaluate(
                """
                () => {
                    const out = [];
                    const imgs = document.querySelectorAll('.p24_modal img, .modal img, .lightbox img');
                    imgs.forEach(img => {
                        const s = img.src || img.dataset.src || img.dataset.lazy || img.dataset.original;
                        if (s && s.includes('images.prop24.com')) out.push(s);
                    });
                    const allEls = document.querySelectorAll('.p24_modal *, .modal *, .lightbox *');
                    allEls.forEach(el => {
                        const bg = getComputedStyle(el).backgroundImage;
                        if (bg && bg.includes('images.prop24.com')) {
                            const m = bg.match(/url\(['\"]?([^'\"]+)['\"]?\)/);
                            if (m && m[1]) out.push(m[1]);
                        }
                    });
                    return out;
                }
                """
            )
            images.extend(modal_imgs)
        except Exception:
            pass

        # 3) JS variables and script contents
        try:
            js_imgs = await page.evaluate(
                """
                () => {
                    const images = [];
                    if (window.galleryImages) {
                        window.galleryImages.forEach(img => { if (img && img.includes('images.prop24.com')) images.push(img); });
                    }
                    const scripts = document.querySelectorAll('script');
                    scripts.forEach(script => {
                        const t = script.textContent || script.innerHTML;
                        const m = t && t.match(/https:\/\/images\.prop24\.com\/[^\"'\s]+/g);
                        if (m) images.push(...m);
                    });
                    return images;
                }
                """
            )
            images.extend(js_imgs)
        except Exception:
            pass

    # Deduplicate
    uniq = []
    seen = set()
    for u in images:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq


async def extract_basic_details(page):
    def first_text(selectors):
        return page.evaluate(
            """
            (sels) => {
                for (const sel of sels) {
                    const el = document.querySelector(sel);
                    if (el) {
                        const t = (el.textContent || '').trim();
                        if (t) return t;
                    }
                }
                return '';
            }
            """,
            selectors,
        )

    title = await first_text([
        'h1', '.title', '.details-header h1', '.p24_propertyHeading h1'
    ])
    price = await first_text([
        '.price', '.p24_price', '.details-header .price'
    ])
    # Beds / baths often appear as icons + numbers
    beds = await first_text([
        '[class*=bed] .p24_featureValue', '.features .bedrooms', 'li:has(i[class*=bed])'
    ])
    baths = await first_text([
        '[class*=bath] .p24_featureValue', '.features .bathrooms', 'li:has(i[class*=bath])'
    ])
    address = await first_text([
        '.address', '.breadcrumbs + *', '.location', '.p24_breadcrumbs ~ *'
    ])
    agency = await first_text([
        '.agency', '.agent', '.p24_agencyInfo', '.agent-details'
    ])
    # Web ref: avoid unsupported :has-text in querySelector; search by text content
    try:
        web_ref = await page.evaluate(
            """
            () => {
                const nodes = Array.from(document.querySelectorAll('.p24_propertyReference, li, dt, dd, p, span, div'));
                for (const el of nodes) {
                    const t = (el.textContent || '').trim();
                    if (!t) continue;
                    if (/\b(web\s*ref|reference)\b/i.test(t)) {
                        return t;
                    }
                }
                return '';
            }
            """
        )
    except Exception:
        web_ref = ''

    return {
        'title': title,
        'price': price,
        'beds': beds,
        'baths': baths,
        'address': address,
        'agency': agency,
        'web_ref': web_ref,
    }


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1366, "height": 900})
        page = await context.new_page()
        await page.goto(LIST_URL, wait_until="domcontentloaded")

        links = await collect_first_n_property_links(page, 3)
        results = []

        for idx, url in enumerate(links, 1):
            detail = await context.new_page()
            try:
                await detail.goto(url, wait_until="domcontentloaded")
                await detail.wait_for_load_state("networkidle")
                print(f"\n=== Listing {idx}: {url}")
                details = await extract_basic_details(detail)
                imgs = await open_slideshow_and_collect_images(detail)
                print(f"Title: {details.get('title','')}")
                print(f"Price: {details.get('price','')}")
                print(f"Beds: {details.get('beds','')}, Baths: {details.get('baths','')}")
                print(f"Address: {details.get('address','')}")
                print(f"Agency: {details.get('agency','')}")
                print(f"Web Ref: {details.get('web_ref','')}")
                print(f"Images: {len(imgs)}")
                for i, u in enumerate(imgs, 1):
                    print(f"  {i:2d}. {u}")
                results.append({"url": url, "details": details, "images": imgs})
            finally:
                await detail.close()

        with open('listing_to_slideshow_results.json', 'w') as f:
            json.dump(results, f, indent=2)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())


