import asyncio
import re
from urllib.parse import urlparse

from django.core.management.base import BaseCommand
from django.utils import timezone
from asgiref.sync import sync_to_async

from playwright.async_api import async_playwright

from properties.models import Source, Property, Image


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


class Command(BaseCommand):
    help = "Scrape Property24 listing pages: save properties with provenance and slideshow images"

    def add_arguments(self, parser):
        parser.add_argument("--start-url", required=True, help="Listings URL to start from (Page 1)")
        parser.add_argument("--start-page", type=int, default=1, help="Page number to start from (default: 1)")
        parser.add_argument("--max-pages", type=int, default=1, help="Pages to process starting at start-page (default: 1)")
        parser.add_argument("--limit-per-page", type=int, default=20, help="Max listings per page (default: 20)")
        parser.add_argument("--start-index", type=int, default=0, help="Zero-based index within the page to start from (default: 0)")
        parser.add_argument("--headless", action="store_true", default=True, help="Run browser headless (default: true)")
        parser.add_argument("--no-headless", action="store_true", help="Run browser headed")
        parser.add_argument("--screenshots", action="store_true", help="Capture screenshots for audit (hero/summary)")
        parser.add_argument("--urls-only", action="store_true", help="Store image URLs only (no download)")

    def handle(self, *args, **options):
        start_url = options["start_url"]
        start_page = options["start_page"]
        max_pages = options["max_pages"]
        limit_per_page = options["limit_per_page"]
        start_index = options["start_index"]
        headless = not options.get("no_headless")
        screenshots = options.get("screenshots")

        source, _ = Source.objects.get_or_create(name="Property24", defaults={"url": "https://www.property24.co.ke"})

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

        async def collect_links_on_page(page, max_items: int):
            await page.wait_for_load_state("domcontentloaded")
            await accept_overlays(page)
            # Ensure cards render and lazy content hydrates
            try:
                await page.locator('a[href*="-"i]').first.wait_for(timeout=4000)
            except Exception:
                pass
            # Scroll to bottom to trigger lazy loading (if any)
            try:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(400)
            except Exception:
                pass
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
                        // Accept any detail path that ends with -<digits>
                        if (/-\d{6,}\/?$/i.test(u.pathname)) {
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
                                try { const el = thumbs[i]; el.scrollIntoView({ block: 'center' }); el.click(); await sleep(600); const full = getFull(); if (full) collected.add(full); } catch {}
                            }
                            if (collected.size < 30) {
                                for (let i = 0; i < 60; i++) {
                                    try {
                                        const next = document.querySelector('.p24_next, .js_pp_next, [id="nextImage"], .js_lightboxNext');
                                        if (next) next.click(); else document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' }));
                                        await sleep(600);
                                        const full = getFull(); if (full) collected.add(full);
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

            uniq, seen = [], set()
            for u in images:
                if u not in seen:
                    seen.add(u)
                    uniq.append(u)
            return uniq

        async def upsert_property_async(source, external_id, defaults, retries: int = 3):
            last_exc = None
            for attempt in range(retries):
                try:
                    return await sync_to_async(Property.objects.update_or_create, thread_sensitive=True)(
                        source=source, external_id=external_id, defaults=defaults
                    )
                except Exception as e:
                    last_exc = e
                    await asyncio.sleep(0.6 * (attempt + 1))
            raise last_exc

        async def get_or_create_image_async(prop, base_id, variant, defaults, retries: int = 3):
            last_exc = None
            for attempt in range(retries):
                try:
                    return await sync_to_async(Image.objects.get_or_create, thread_sensitive=True)(
                        property=prop, image_base_id=base_id, variant=variant or "", defaults=defaults
                    )
                except Exception as e:
                    last_exc = e
                    await asyncio.sleep(0.6 * (attempt + 1))
            raise last_exc

        async def save_image_fields_async(obj, update_fields, retries: int = 3):
            last_exc = None
            for attempt in range(retries):
                try:
                    return await sync_to_async(obj.save, thread_sensitive=True)(update_fields=update_fields)
                except Exception as e:
                    last_exc = e
                    await asyncio.sleep(0.6 * (attempt + 1))
            raise last_exc

        async def run():
            processed = 0
            skipped = 0
            total_images = 0

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=headless)
                context = await browser.new_context(viewport={"width": 1366, "height": 900})
                page = await context.new_page()
                await page.goto(start_url, wait_until="domcontentloaded")

                # Navigate forward to start_page if needed
                if start_page > 1:
                    self.stdout.write(self.style.NOTICE(f"Navigating to start page {start_page}..."))
                    for _ in range(1, start_page):
                        try:
                            next_btn = page.locator('.pagination a:has-text("Next"), a[rel="next"]').first
                            if await next_btn.count() == 0:
                                break
                            await next_btn.click()
                            await page.wait_for_load_state("domcontentloaded")
                        except Exception:
                            break

                for page_offset in range(max_pages):
                    current_page_num = start_page + page_offset
                    self.stdout.write(self.style.HTTP_INFO(f"Page {current_page_num}: collecting links..."))
                    links = await collect_links_on_page(page, limit_per_page)
                    self.stdout.write(self.style.HTTP_INFO(f"Page {current_page_num}: {len(links)} links"))
                    for idx, url in enumerate(links):
                        if idx < start_index:
                            continue
                        self.stdout.write(f"[{current_page_num}:{idx+1}/{len(links)}] {url}")
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
                                "listing_url": start_url,
                                "listing_page": current_page_num,
                                "card_index": idx,
                                "last_crawled_at": timezone.now(),
                            }
                            prop, _ = await upsert_property_async(source, external_id, defaults)

                            images = await open_slideshow_and_collect_images(detail)
                            if not images:
                                skipped += 1
                                self.stdout.write(self.style.WARNING(f"No images: {url}"))
                                continue

                            primary_marked = False
                            order_index = 0
                            for img_url in images:
                                if "images.prop24.com" not in img_url:
                                    continue
                                base_id, variant = image_identity(img_url)
                                obj, _created = await get_or_create_image_async(
                                    prop, base_id, variant, {
                                        "url": img_url,
                                        "order_index": order_index,
                                        "is_thumbnail": False,
                                    }
                                )
                                if obj.order_index != order_index or obj.url != img_url:
                                    obj.order_index = order_index
                                    obj.url = img_url
                                    await save_image_fields_async(obj, ["order_index", "url"])
                                if not primary_marked:
                                    obj.is_thumbnail = True
                                    await save_image_fields_async(obj, ["is_thumbnail"])
                                    primary_marked = True
                                order_index += 1
                                total_images += 1

                            processed += 1
                            self.stdout.write(self.style.SUCCESS(f"Saved {len(images)} images for {external_id}"))
                        finally:
                            await detail.close()

                    # go to next page if requested
                    if page_offset < max_pages - 1:
                        try:
                            next_btn = page.locator('.pagination a:has-text("Next"), a[rel="next"]').first
                            if await next_btn.count() == 0:
                                break
                            await next_btn.click()
                            await page.wait_for_load_state("domcontentloaded")
                        except Exception:
                            break

                await browser.close()

            self.stdout.write(self.style.SUCCESS(f"Processed listings: {processed}"))
            self.stdout.write(self.style.WARNING(f"Skipped listings: {skipped}"))
            self.stdout.write(self.style.SUCCESS(f"Saved images: {total_images}"))

        asyncio.run(run())


