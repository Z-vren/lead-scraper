# filename: src/directories.py
"""Functions to search business directories for companies matching industry and location."""

import asyncio
from typing import List, Dict, Optional, AsyncIterator
from urllib.parse import quote_plus, urljoin
from apify import Actor
from playwright.async_api import async_playwright, Browser, Page

from src.utils import normalize_url


# Directory search URLs and selectors
# Using a generic approach that can work with multiple directories
YELLOWPAGES_SEARCH_URL = "https://www.yellowpages.com/search"
YELLOWPAGES_BASE_URL = "https://www.yellowpages.com"


async def search_yellowpages(
    industry: str,
    location: str,
    max_results: int,
    page: Page
) -> List[Dict]:
    """
    Search YellowPages for companies matching industry and location using browser automation.
    
    Args:
        industry: Industry keyword
        location: Location string
        max_results: Maximum number of results
        page: Playwright page object
        
    Returns:
        List of company dictionaries with basic info
    """
    companies = []
    
    try:
        # Build search URL
        search_query = f"{industry} {location}"
        search_url = f"{YELLOWPAGES_SEARCH_URL}?search_terms={quote_plus(search_query)}&geo_location_terms={quote_plus(location)}"
        
        Actor.log.info(f"Navigating to YellowPages: {search_url}")
        
        # Navigate to the page with browser automation
        await page.goto(search_url, wait_until='networkidle', timeout=30000)
        
        # Wait for listings to load - give more time for dynamic content
        await page.wait_for_timeout(5000)  # Increased wait time
        
        # Check if page loaded correctly (look for common YellowPages elements)
        page_title = await page.title()
        Actor.log.info(f"Page title: {page_title}")
        
        # Check for CAPTCHA or error pages
        page_content = await page.content()
        if 'captcha' in page_content.lower() or 'robot' in page_content.lower():
            Actor.log.warning("Possible CAPTCHA or bot detection on page")
        
        # Try multiple selectors for listings
        listings = []
        selectors = [
            'div[class*="result"]',
            'div[class*="listing"]',
            'div.srp-listing',
            'div.search-result',
            'div[data-dotcom="result"]',
            'div.result',
            'div[class*="organic"]',
            'div[class*="business"]',
            'article[class*="result"]',
            'div[class*="search-listing"]'
        ]
        
        for selector in selectors:
            try:
                listings = await page.query_selector_all(selector)
                if listings:
                    Actor.log.info(f"Found {len(listings)} listings with selector: {selector}")
                    break
            except Exception as e:
                Actor.log.debug(f"Selector {selector} failed: {str(e)}")
                continue
        
        if not listings:
            Actor.log.warning("No listings found with any selector")
            # Try to get a screenshot or HTML snippet for debugging
            try:
                # Check what's actually on the page
                body_text = await page.evaluate('() => document.body.innerText')
                Actor.log.debug(f"Page body text preview: {body_text[:500]}")
            except:
                pass
            return companies
        
        # Extract data from listings
        for listing in listings[:max_results]:
            try:
                company_data = {}
                
                # Extract company name
                name_elem = await listing.query_selector('a[class*="business-name"], a[class*="name"], h2 a, a[href]')
                if name_elem:
                    company_data['company_name'] = await name_elem.inner_text()
                    company_data['company_name'] = company_data['company_name'].strip()
                    
                    # Try to get website URL
                    href = await name_elem.get_attribute('href')
                    if href:
                        company_data['website_url'] = normalize_url(href, YELLOWPAGES_BASE_URL)
                else:
                    continue
                
                # Extract address
                address_elem = await listing.query_selector('div[class*="address"], span[class*="address"]')
                if address_elem:
                    company_data['company_address'] = await address_elem.inner_text()
                    company_data['company_address'] = company_data['company_address'].strip()
                
                # Extract website URL (separate from company name link)
                website_elem = await listing.query_selector('a[class*="website"], a[class*="url"]')
                if website_elem:
                    website_href = await website_elem.get_attribute('href')
                    if website_href:
                        company_data['website_url'] = normalize_url(website_href, YELLOWPAGES_BASE_URL)
                
                # Extract LinkedIn if present
                linkedin_elem = await listing.query_selector('a[href*="linkedin.com"]')
                if linkedin_elem:
                    linkedin_href = await linkedin_elem.get_attribute('href')
                    if linkedin_href:
                        company_data['linkedin_url'] = normalize_url(linkedin_href)
                
                if company_data.get('company_name'):
                    companies.append(company_data)
                    
            except Exception as e:
                Actor.log.debug(f"Error extracting listing data: {str(e)}")
                continue
        
    except Exception as e:
        Actor.log.error(f"Error searching YellowPages: {str(e)}")
        Actor.log.debug(f"Search URL was: {search_url}")
    
    Actor.log.info(f"YellowPages search found {len(companies)} companies")
    return companies


async def search_generic_directory(
    industry: str,
    location: str,
    max_results: int,
    page: Page
) -> List[Dict]:
    """
    Generic directory search using a simple web search approach.
    This is a fallback that can be extended with other directories.
    
    Args:
        industry: Industry keyword
        location: Location string
        max_results: Maximum number of results
        client: HTTP client
        
    Returns:
        List of company dictionaries
    """
    # This is a placeholder for additional directory sources
    # You can add more directory scrapers here
    return []


async def search_companies(
    industry: str,
    location: str,
    max_results: int
) -> AsyncIterator[Dict]:
    """
    Search multiple directories for companies matching industry and location.
    Yields company dictionaries as they are found.
    
    Args:
        industry: Industry to search for
        location: Location to search in
        max_results: Maximum number of results
        
    Yields:
        Company dictionaries with basic information
    """
    async with async_playwright() as p:
        # Launch browser with stealth settings
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()
        
        try:
            # Try multiple directory sources
            Actor.log.info(f"Searching directories for: {industry} in {location}")
            
            seen_names = set()
            total_found = 0
            
            # Try YellowPages
            Actor.log.info("Trying YellowPages...")
            try:
                companies = await search_yellowpages(industry, location, max_results, page)
                
                for company in companies:
                    if total_found >= max_results:
                        break
                    
                    # Deduplicate by company name
                    company_name = company.get('company_name', '').lower().strip()
                    if company_name and company_name not in seen_names:
                        seen_names.add(company_name)
                        total_found += 1
                        yield company
            except Exception as e:
                Actor.log.error(f"Error in YellowPages search: {str(e)}")
            
            # Add more directory sources here as needed
            
        finally:
            await browser.close()

