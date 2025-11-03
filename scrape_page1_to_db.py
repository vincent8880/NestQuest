#!/usr/bin/env python3

import os
import re
import asyncio
from urllib.parse import urljoin, urlparse

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "nestquest.settings")
import django
django.setup()

from django.utils import timezone
from playwright.async_api import async_playwright
from properties.models import Source, Property, Image


LIST_URL = "https://www.property24.co.ke/houses-to-rent-in-kileleshwa-s14529?sortorder=quality"


def parse_external_id(detail_url: str) -> str:
    path = urlparse(detail_url).path.rstrip("/")
    m = re.search(r"-(\d{6,})$", path)
    return m.group(1) if m else path.split("-")[-1]


def image_identity(image_url: str):
    path = urlparse(image_url).path.strip("/")
    parts = path.split("/")
    base_id = parts[0] if parts else ""
    variant = parts[1] if len(parts) > 1 else ""
    return base_id, variant


async def accept_overlays(page):
    for sel in [
        'button:has-text("Accept")',
        'button:has-text("Yes")',
        'button:has-text("I Agree")',
        'button:has-text("OK")',
        'button:has-text("Continue")',
    ]:
        try:
            await page.locator(sel).first.click(timeout=1200)
            await page.wait_for_timeout(200)
        except Exception:
            pass


async def collect_first_page_links(page, max_items: int = 20):
    await page.wait_for_load_state("domcontentloaded")
    await accept_overlays(page)
    hrefs = await page.evaluate(
        """
        () => {
            const out = [];
            const as = Array.from(document.querySelectorAll('a[href]'));
            for (const a of as) {
                const href = a.getAttribute('href');
                if (!href) continue;
                let u;
                try { u = new URL(href, location.href); } catch { continue; }
                if (/-(\d{6,})\/?$/.test(u.pathname)) {
                    out.push(u.href);
                }
            }
            return Array.from(new Set(out));
        }
        """
    )
    return hrefs[:max_items]


async def open_slideshow_and_collect_images(page):
    await accept_overlays(page)
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
        # Click thumbs and ArrowRight to hydrate slides
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
                                if (next) next.click();
                                else document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' }));
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

        # Modal images and backgrounds
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

    # Deduplicate preserving order
    uniq = []
    seen = set()
    for u in images:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq


async def main():
    # Ensure Source exists
    source, _ = Source.objects.get_or_create(name="Property24", defaults={"url": "https://www.property24.co.ke"})

    processed = 0
    skipped = 0
    total_images = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1366, "height": 900})
        page = await context.new_page()
        await page.goto(LIST_URL, wait_until="domcontentloaded")

        links = await collect_first_page_links(page, 20)

        for idx, url in enumerate(links):
            detail = await context.new_page()
            try:
                await detail.goto(url, wait_until="domcontentloaded")
                await detail.wait_for_load_state("networkidle")
                await accept_overlays(detail)

                external_id = parse_external_id(url)
                defaults = {
                    "title": f"Property {external_id}",
                    "property_type": "house",
                    "detail_url": url,
                    "listing_url": LIST_URL,
                    "listing_page": 1,
                    "card_index": idx,
                    "last_crawled_at": timezone.now(),
                }
                prop, created = Property.objects.update_or_create(
                    source=source, external_id=external_id, defaults=defaults
                )

                images = await open_slideshow_and_collect_images(detail)
                if not images:
                    skipped += 1
                    continue

                # Save images
                primary_marked = False
                order_index = 0
                for img_url in images:
                    if "images.prop24.com" not in img_url:
                        continue
                    base_id, variant = image_identity(img_url)
                    try:
                        obj, _ = Image.objects.get_or_create(
                            property=prop,
                            image_base_id=base_id,
                            variant=variant or "",
                            defaults={
                                "url": img_url,
                                "order_index": order_index,
                                "is_thumbnail": False,
                            },
                        )
                        # Update order/url on re-run
                        if obj.order_index != order_index or obj.url != img_url:
                            obj.order_index = order_index
                            obj.url = img_url
                            obj.save(update_fields=["order_index", "url"])
                        if not primary_marked:
                            obj.is_thumbnail = True
                            obj.save(update_fields=["is_thumbnail"])
                            primary_marked = True
                        order_index += 1
                        total_images += 1
                    except Exception:
                        continue

                processed += 1
            finally:
                await detail.close()

        await browser.close()

    print(f"Processed listings: {processed}")
    print(f"Skipped listings: {skipped}")
    print(f"Saved images: {total_images}")


if __name__ == "__main__":
    asyncio.run(main())




























