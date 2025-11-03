import asyncio
import re
from typing import List

from django.core.management.base import BaseCommand
from django.utils import timezone
from asgiref.sync import sync_to_async

from playwright.async_api import async_playwright

from properties.models import Property, Contact, Source

# Reuse the API key we’ve been using
CAPTCHA_API_KEY = "79d9722448416056a13129c67d5c2b55"


class Command(BaseCommand):
    help = "Update contacts for Property24 properties using 2captcha to reveal phone and email"

    def add_arguments(self, parser):
        parser.add_argument(
            '--property-ids',
            type=str,
            help='Comma-separated list of external IDs (e.g., 108944549,116153975)'
        )
        parser.add_argument(
            '--listing-page',
            type=int,
            help='Update all properties previously scraped from this listing page number'
        )
        parser.add_argument(
            '--all-with-detail-url',
            action='store_true',
            help='Update all properties that have a detail_url'
        )
        parser.add_argument(
            '--headless',
            action='store_true',
            help='Run browser headless'
        )

    def handle(self, *args, **options):
        asyncio.run(self.run(options))

    async def run(self, options):
        source_name = 'Property24'

        target_external_ids: List[str] = []
        if options.get('property_ids'):
            target_external_ids = [s.strip() for s in options['property_ids'].split(',') if s.strip()]

        properties = []
        if target_external_ids:
            for ext_id in target_external_ids:
                prop = await sync_to_async(self._get_property_by_external_id)(source_name, ext_id)
                if prop:
                    properties.append(prop)
        elif options.get('listing_page') is not None:
            properties = await sync_to_async(self._get_properties_by_listing_page)(source_name, options['listing_page'])
        elif options.get('all_with_detail_url'):
            properties = await sync_to_async(self._get_properties_with_detail_url)(source_name)
        else:
            self.stdout.write('Please provide --property-ids, --listing-page, or --all-with-detail-url')
            return

        if not properties:
            self.stdout.write('No properties matched the criteria')
            return

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=bool(options.get('headless')) is True)
            context = await browser.new_context(viewport={"width": 1366, "height": 900})
            page = await context.new_page()

            for prop in properties:
                if not prop.detail_url:
                    self.stdout.write(f"Skipping {prop.external_id}: no detail_url saved")
                    continue

                self.stdout.write(f"🔎 Updating contacts for external_id={prop.external_id} …")

                try:
                    await page.goto(prop.detail_url, wait_until='domcontentloaded')
                    await page.wait_for_load_state('networkidle')

                    # Try to reveal contacts
                    revealed = await self._reveal_contacts_with_captcha(page)

                    # Extract phones/emails from DOM after solving
                    phones, emails = await self._extract_contacts_from_page(page)

                    if (phones or emails) and revealed:
                        await sync_to_async(self._upsert_contact)(prop, phones, emails)
                        self.stdout.write(f"✅ Saved contact for {prop.external_id}: phones={phones}, emails={emails}")
                    else:
                        self.stdout.write(f"⚠️ No contacts found for {prop.external_id}")
                except Exception as e:
                    self.stdout.write(f"❌ Error on {prop.external_id}: {e}")

            await browser.close()

    def _get_property_by_external_id(self, source_name: str, external_id: str):
        try:
            source = Source.objects.get_or_create(name=source_name)[0]
            return Property.objects.filter(source=source, external_id=external_id).first()
        except Exception:
            return None

    def _get_properties_by_listing_page(self, source_name: str, listing_page: int):
        source = Source.objects.get_or_create(name=source_name)[0]
        return list(Property.objects.filter(source=source, listing_page=listing_page).order_by('id'))

    def _get_properties_with_detail_url(self, source_name: str):
        source = Source.objects.get_or_create(name=source_name)[0]
        return list(Property.objects.filter(
            source=source
        ).exclude(
            detail_url__isnull=True
        ).exclude(
            detail_url=''
        ).order_by('id'))

    def _upsert_contact(self, prop: Property, phones: list, emails: list):
        primary_phone = phones[0] if phones else ''
        primary_email = emails[0] if emails else ''
        contact, _ = Contact.objects.update_or_create(
            property=prop,
            defaults={
                'name': '',
                'phone': primary_phone,
                'email': primary_email,
            }
        )
        return contact

    async def _reveal_contacts_with_captcha(self, page) -> bool:
        # Click show contact button if present
        selectors = ['.ShowContact', 'text="Show Contact Number"', '.ShowPhone']
        clicked = False
        for sel in selectors:
            try:
                btn = await page.query_selector(sel)
                if btn:
                    await btn.click()
                    await page.wait_for_timeout(1500)
                    clicked = True
                    break
            except Exception:
                continue

        # Detect reCAPTCHA
        site_key = await self._get_recaptcha_site_key(page)
        if not site_key:
            # Maybe no CAPTCHA; proceed
            return clicked

        # Solve via 2captcha
        solution = await self._solve_recaptcha_with_2captcha(page, site_key)
        if not solution:
            return False

        # Inject solution and verify
        await self._inject_captcha_solution(page, solution)
        await page.wait_for_timeout(2000)

        # Re-click contact button in case site requires post-solve action
        try:
            btn = await page.query_selector('.ShowContact')
            if btn:
                await btn.click()
                await page.wait_for_timeout(1500)
        except Exception:
            pass

        return await self._verify_captcha_solution(page)

    async def _get_recaptcha_site_key(self, page) -> str:
        try:
            el = await page.query_selector('[data-sitekey]')
            if el:
                return await el.get_attribute('data-sitekey')
            content = await page.content()
            m = re.search(r'data-sitekey="([^"]+)"', content)
            return m.group(1) if m else None
        except Exception:
            return None

    async def _solve_recaptcha_with_2captcha(self, page, site_key: str) -> str:
        try:
            import requests
            submit_url = 'http://2captcha.com/in.php'
            data = {
                'key': CAPTCHA_API_KEY,
                'method': 'userrecaptcha',
                'googlekey': site_key,
                'pageurl': page.url,
                'soft_id': 'Property24Scraper',
                'json': 1,
            }
            resp = requests.post(submit_url, data=data, timeout=30)
            captcha_id = None
            try:
                j = resp.json()
                if j.get('status') == 1:
                    captcha_id = j.get('request')
                else:
                    self.stdout.write(f"❌ 2captcha submit failed: {j.get('error_text')}")
                    return None
            except Exception:
                if not resp.text.startswith('OK|'):
                    self.stdout.write(f"❌ 2captcha submit failed: {resp.text}")
                    return None
                captcha_id = resp.text.split('|')[1]

            # Poll for solution
            result_url = 'http://2captcha.com/res.php'
            for attempt in range(60):
                await asyncio.sleep(2)
                params = {'key': CAPTCHA_API_KEY, 'action': 'get', 'id': captcha_id, 'json': 1}
                r = requests.get(result_url, params=params, timeout=10)
                try:
                    jj = r.json()
                    if jj.get('status') == 1:
                        return jj.get('request')
                    if jj.get('request') == 'CAPCHA_NOT_READY':
                        continue
                    self.stdout.write(f"❌ 2captcha error: {jj.get('error_text')}")
                    return None
                except Exception:
                    if r.text.startswith('OK|'):
                        return r.text.split('|')[1]
                    if r.text == 'CAPCHA_NOT_READY':
                        continue
                    self.stdout.write(f"❌ 2captcha error: {r.text}")
                    return None
            self.stdout.write('⏰ Timeout waiting for 2captcha solution')
            return None
        except Exception as e:
            self.stdout.write(f"❌ Error solving recaptcha: {e}")
            return None

    async def _inject_captcha_solution(self, page, solution: str):
        # Multiple strategies
        js1 = f"""
        (() => {{
            const textarea = document.querySelector('textarea[name="g-recaptcha-response"]');
            if (textarea) {{ textarea.value = '{solution}'; textarea.style.display = 'block'; return 'textarea_set'; }}
            return 'textarea_not_found';
        }})()
        """
        res1 = await page.evaluate(js1)
        self.stdout.write(f"   Inject method 1: {res1}")

        js2 = f"""
        (() => {{
            if (typeof window.grecaptcha !== 'undefined') {{
                const widgets = document.querySelectorAll('.g-recaptcha');
                if (widgets.length > 0) {{
                    const cb = widgets[0].getAttribute('data-callback');
                    if (cb && typeof window[cb] === 'function') {{ window[cb]('{solution}'); return 'callback_triggered'; }}
                }}
            }}
            return 'callback_not_found';
        }})()
        """
        res2 = await page.evaluate(js2)
        self.stdout.write(f"   Inject method 2: {res2}")

        js3 = f"""
        (() => {{
            if (typeof window.grecaptcha !== 'undefined') {{ window.grecaptcha.getResponse = function() {{ return '{solution}'; }}; return 'global_set'; }}
            return 'grecaptcha_not_found';
        }})()
        """
        res3 = await page.evaluate(js3)
        self.stdout.write(f"   Inject method 3: {res3}")

        js4 = f"""
        (() => {{
            const forms = document.querySelectorAll('form');
            for (let form of forms) {{
                const recaptchaField = form.querySelector('textarea[name="g-recaptcha-response"]');
                if (recaptchaField) {{
                    recaptchaField.value = '{solution}';
                    const btn = form.querySelector('button[type="submit"], input[type="submit"]');
                    if (btn) {{ btn.click(); return 'form_submitted'; }}
                }}
            }}
            return 'no_form_found';
        }})()
        """
        res4 = await page.evaluate(js4)
        self.stdout.write(f"   Inject method 4: {res4}")
        await page.wait_for_timeout(1500)

    async def _verify_captcha_solution(self, page) -> bool:
        try:
            try:
                if not await page.is_visible('.g-recaptcha'):
                    return True
            except Exception:
                pass
            nodes = await page.query_selector_all('.agentPhone, .contactPhone, .phone-number, [class*="phone"]')
            for n in nodes:
                txt = (await n.inner_text()).strip()
                if re.search(r'(\+254|07|01)\d{8,9}', txt):
                    return True
            return False
        except Exception:
            return False

    async def _extract_contacts_from_page(self, page):
        content = await page.content()
        phones = list({m[0] if isinstance(m, tuple) else m for m in re.findall(r'(\+254\s*\d{3}\s*\d{3}\s*\d{3}|\+254\d{9}|07\d{8}|01\d{8})', content)})
        emails = list(set(re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', content)))
        return phones, emails












