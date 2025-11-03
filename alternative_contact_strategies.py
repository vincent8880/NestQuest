#!/usr/bin/env python3

"""
Alternative Contact Extraction Strategies for Property24
When CAPTCHA solving isn't viable, these approaches can still yield results
"""

import asyncio
import re
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import json

class AlternativeContactExtractor:
    """Alternative contact extraction strategies"""
    
    def __init__(self):
        self.base_url = "https://www.property24.co.ke"
    
    async def extract_contacts_without_captcha(self, page, soup):
        """Extract contacts using alternative methods"""
        contact_info = {}
        
        # Strategy 1: Extract from property description/details
        contact_info.update(await self._extract_from_description(soup))
        
        # Strategy 2: Extract from page metadata
        contact_info.update(await self._extract_from_metadata(soup))
        
        # Strategy 3: Extract from hidden elements
        contact_info.update(await self._extract_from_hidden_elements(soup))
        
        # Strategy 4: Extract from JavaScript variables
        contact_info.update(await self._extract_from_javascript(page))
        
        # Strategy 5: Extract from CSS content
        contact_info.update(await self._extract_from_css(soup))
        
        # Strategy 6: Extract from data attributes
        contact_info.update(await self._extract_from_data_attributes(soup))
        
        return contact_info
    
    async def _extract_from_description(self, soup):
        """Extract contact info from property descriptions"""
        contact_info = {'description_phones': [], 'description_emails': []}
        
        # Look in property description text
        description_elements = soup.find_all(['p', 'div', 'span'], 
                                           class_=re.compile(r'description|detail|content'))
        
        for elem in description_elements:
            text = elem.get_text()
            
            # Phone patterns that might appear in descriptions
            phone_patterns = [
                r'(?:call|contact|phone)[:\s]*(\+?[\d\s\-()]{10,15})',
                r'(?:WhatsApp|wa\.me)[:\s]*(\+?[\d\s\-()]{10,15})',
                r'(\+254[\d\s\-()]{9,})',
                r'(07\d{8})',
                r'(01\d{8})',
            ]
            
            for pattern in phone_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    clean_phone = re.sub(r'[^\d+]', '', match)
                    if len(clean_phone) >= 10:
                        contact_info['description_phones'].append(clean_phone)
            
            # Email patterns
            email_matches = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
            for email in email_matches:
                if not any(word in email.lower() for word in ['noreply', 'admin', 'info@property24']):
                    contact_info['description_emails'].append(email)
        
        return contact_info
    
    async def _extract_from_metadata(self, soup):
        """Extract contact info from page metadata"""
        contact_info = {'meta_phones': [], 'meta_emails': []}
        
        # Check meta tags
        meta_tags = soup.find_all('meta')
        for tag in meta_tags:
            content = tag.get('content', '')
            
            # Phone extraction
            phone_matches = re.findall(r'(\+?[\d\s\-()]{10,15})', content)
            for match in phone_matches:
                clean_phone = re.sub(r'[^\d+]', '', match)
                if len(clean_phone) >= 10:
                    contact_info['meta_phones'].append(clean_phone)
            
            # Email extraction
            email_matches = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', content)
            contact_info['meta_emails'].extend(email_matches)
        
        return contact_info
    
    async def _extract_from_hidden_elements(self, soup):
        """Extract contact info from hidden elements"""
        contact_info = {'hidden_phones': [], 'hidden_emails': []}
        
        # Look for hidden elements that might contain contact info
        hidden_elements = soup.find_all(['div', 'span', 'input'], 
                                      style=re.compile(r'display:\s*none|visibility:\s*hidden'))
        
        for elem in hidden_elements:
            # Check element text and attributes
            text = elem.get_text() + ' ' + str(elem.get('value', '')) + ' ' + str(elem.get('data-phone', ''))
            
            phone_matches = re.findall(r'(\+?[\d\s\-()]{10,15})', text)
            for match in phone_matches:
                clean_phone = re.sub(r'[^\d+]', '', match)
                if len(clean_phone) >= 10:
                    contact_info['hidden_phones'].append(clean_phone)
            
            email_matches = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
            contact_info['hidden_emails'].extend(email_matches)
        
        return contact_info
    
    async def _extract_from_javascript(self, page):
        """Extract contact info from JavaScript variables"""
        contact_info = {'js_phones': [], 'js_emails': []}
        
        try:
            # Extract JavaScript variables that might contain contact info
            js_code = """
            () => {
                let contacts = {};
                
                // Look for global variables
                if (typeof window.agentPhone !== 'undefined') {
                    contacts.agentPhone = window.agentPhone;
                }
                
                if (typeof window.agentEmail !== 'undefined') {
                    contacts.agentEmail = window.agentEmail;
                }
                
                // Look for contact info in common variable names
                const possibleVars = ['contactInfo', 'agentInfo', 'propertyAgent', 'landlordContact'];
                for (const varName of possibleVars) {
                    if (typeof window[varName] !== 'undefined') {
                        contacts[varName] = window[varName];
                    }
                }
                
                return contacts;
            }
            """
            
            js_contacts = await page.evaluate(js_code)
            
            # Extract phone numbers from JavaScript data
            js_text = json.dumps(js_contacts)
            phone_matches = re.findall(r'(\+?[\d\s\-()]{10,15})', js_text)
            for match in phone_matches:
                clean_phone = re.sub(r'[^\d+]', '', match)
                if len(clean_phone) >= 10:
                    contact_info['js_phones'].append(clean_phone)
            
            # Extract emails
            email_matches = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', js_text)
            contact_info['js_emails'].extend(email_matches)
            
        except Exception as e:
            print(f"Error extracting from JavaScript: {e}")
        
        return contact_info
    
    async def _extract_from_css(self, soup):
        """Extract contact info from CSS content"""
        contact_info = {'css_phones': [], 'css_emails': []}
        
        # Look for CSS content that might contain contact info
        style_tags = soup.find_all('style')
        for style in style_tags:
            style_text = style.get_text()
            
            # Extract from CSS content property
            content_matches = re.findall(r'content:\s*["\']([^"\']+)["\']', style_text)
            for content in content_matches:
                phone_matches = re.findall(r'(\+?[\d\s\-()]{10,15})', content)
                for match in phone_matches:
                    clean_phone = re.sub(r'[^\d+]', '', match)
                    if len(clean_phone) >= 10:
                        contact_info['css_phones'].append(clean_phone)
                
                email_matches = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', content)
                contact_info['css_emails'].extend(email_matches)
        
        return contact_info
    
    async def _extract_from_data_attributes(self, soup):
        """Extract contact info from data attributes"""
        contact_info = {'data_phones': [], 'data_emails': []}
        
        # Look for elements with data attributes that might contain contact info
        all_elements = soup.find_all(attrs={'data-phone': True})
        all_elements.extend(soup.find_all(attrs={'data-email': True}))
        all_elements.extend(soup.find_all(attrs={'data-contact': True}))
        
        for elem in all_elements:
            for attr_name, attr_value in elem.attrs.items():
                if attr_name.startswith('data-'):
                    # Extract phone numbers
                    phone_matches = re.findall(r'(\+?[\d\s\-()]{10,15})', str(attr_value))
                    for match in phone_matches:
                        clean_phone = re.sub(r'[^\d+]', '', match)
                        if len(clean_phone) >= 10:
                            contact_info['data_phones'].append(clean_phone)
                    
                    # Extract emails
                    email_matches = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', str(attr_value))
                    contact_info['data_emails'].extend(email_matches)
        
        return contact_info

# Strategy 7: Multi-page approach
class MultiPageContactExtractor:
    """Extract contacts from multiple related pages"""
    
    async def extract_from_agent_profiles(self, page, property_url):
        """Extract contact info from agent profile pages"""
        contact_info = {'agent_phones': [], 'agent_emails': []}
        
        try:
            # Navigate to property page
            await page.goto(property_url)
            await page.wait_for_timeout(2000)
            
            # Look for agent profile links
            agent_links = await page.query_selector_all('a[href*="agent"]')
            
            for link in agent_links[:3]:  # Check first 3 agent links
                try:
                    href = await link.get_attribute('href')
                    if href and '/agent/' in href:
                        # Navigate to agent profile
                        await page.goto(href)
                        await page.wait_for_timeout(2000)
                        
                        # Extract contact info from agent profile
                        content = await page.content()
                        soup = BeautifulSoup(content, 'html.parser')
                        
                        # Agent profiles might have less protection
                        page_text = soup.get_text()
                        
                        phone_matches = re.findall(r'(\+?[\d\s\-()]{10,15})', page_text)
                        for match in phone_matches:
                            clean_phone = re.sub(r'[^\d+]', '', match)
                            if len(clean_phone) >= 10:
                                contact_info['agent_phones'].append(clean_phone)
                        
                        email_matches = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', page_text)
                        for email in email_matches:
                            if not any(word in email.lower() for word in ['noreply', 'admin', 'info@property24']):
                                contact_info['agent_emails'].append(email)
                
                except Exception as e:
                    print(f"Error processing agent link: {e}")
        
        except Exception as e:
            print(f"Error extracting from agent profiles: {e}")
        
        return contact_info

# Strategy 8: Pattern-based contact prediction
class ContactPatternPredictor:
    """Predict contact information based on patterns"""
    
    def __init__(self):
        self.common_patterns = {
            'agent_names': ['Daniel Ochieng', 'John Kamau', 'Mary Wanjiku'],
            'agency_patterns': [
                r'([A-Z][a-z]+ [A-Z][a-z]+) Properties',
                r'([A-Z][a-z]+ [A-Z][a-z]+) Realty',
                r'([A-Z][a-z]+ [A-Z][a-z]+) Estates'
            ]
        }
    
    async def predict_contact_patterns(self, soup, property_data):
        """Predict contact information based on property patterns"""
        predictions = {'predicted_phones': [], 'predicted_emails': []}
        
        page_text = soup.get_text()
        
        # Extract agent names
        for pattern in self.common_patterns['agency_patterns']:
            matches = re.findall(pattern, page_text)
            for match in matches:
                # Generate potential email based on name
                name_parts = match.lower().split()
                if len(name_parts) >= 2:
                    potential_emails = [
                        f"{name_parts[0]}.{name_parts[1]}@property24.co.ke",
                        f"{name_parts[0]}{name_parts[1]}@gmail.com",
                        f"{name_parts[0]}__{name_parts[1]}@yahoo.com"
                    ]
                    predictions['predicted_emails'].extend(potential_emails)
        
        return predictions

# Usage example
async def main():
    """Example usage of alternative contact extraction methods"""
    
    test_url = "https://www.property24.co.ke/3-bedroom-apartment-flat-to-rent-in-kileleshwa-116153975"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        await page.goto(test_url)
        await page.wait_for_timeout(3000)
        
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        
        # Initialize extractors
        alt_extractor = AlternativeContactExtractor()
        multi_page_extractor = MultiPageContactExtractor()
        pattern_predictor = ContactPatternPredictor()
        
        # Extract using different strategies
        print("🔍 Extracting contacts using alternative methods...")
        
        # Strategy 1: Alternative extraction
        alt_contacts = await alt_extractor.extract_contacts_without_captcha(page, soup)
        print("Alternative extraction results:")
        print(json.dumps(alt_contacts, indent=2))
        
        # Strategy 2: Multi-page extraction
        multi_page_contacts = await multi_page_extractor.extract_from_agent_profiles(page, test_url)
        print("\nMulti-page extraction results:")
        print(json.dumps(multi_page_contacts, indent=2))
        
        # Strategy 3: Pattern prediction
        predicted_contacts = await pattern_predictor.predict_contact_patterns(soup, {})
        print("\nPattern prediction results:")
        print(json.dumps(predicted_contacts, indent=2))
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main()) 