# filename: src/directories.py
"""Functions to search business directories for companies matching industry and location."""

import asyncio
from typing import List, Dict, Optional, AsyncIterator
from urllib.parse import quote_plus, urljoin
from apify import Actor
from playwright.async_api import async_playwright, Browser, Page

from src.utils import normalize_url


# Directory search URLs and selectors
# Using Google Maps as primary source (more reliable than YellowPages)
GOOGLE_MAPS_SEARCH_URL = "https://www.google.com/maps/search"


async def search_google_maps(
    industry: str,
    location: str,
    max_results: int,
    page: Page
) -> List[Dict]:
    """
    Search Google Maps for companies matching industry and location using browser automation.
    
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
        # Build search URL for Google Maps
        search_query = f"{industry} in {location}"
        search_url = f"{GOOGLE_MAPS_SEARCH_URL}/{quote_plus(search_query)}"
        
        Actor.log.info(f"Navigating to Google Maps: {search_url}")
        
        # Navigate to the page with browser automation
        await page.goto(search_url, wait_until='networkidle', timeout=30000)
        
        # Wait for listings to load
        await page.wait_for_timeout(5000)
        
        # Check page title
        page_title = await page.title()
        Actor.log.info(f"Page title: {page_title}")
        
        # Google Maps uses a side panel with results
        # Wait for the results panel to appear
        try:
            await page.wait_for_selector('div[role="article"], div[data-value], div[jsaction*="mouseover"]', timeout=10000)
        except:
            Actor.log.warning("Results panel did not appear")
        
        # Try multiple selectors for Google Maps listings
        listings = []
        selectors = [
            'div[role="article"]',
            'div[data-value]',
            'div[jsaction*="mouseover"]',
            'a[data-value]',
            'div[class*="result"]',
            'div[class*="place"]'
        ]
        
        for selector in selectors:
            try:
                listings = await page.query_selector_all(selector)
                if listings and len(listings) > 0:
                    Actor.log.info(f"Found {len(listings)} listings with selector: {selector}")
                    break
            except Exception as e:
                Actor.log.debug(f"Selector {selector} failed: {str(e)}")
                continue
        
        if not listings:
            Actor.log.warning("No listings found with any selector")
            return companies
        
        # Extract data from listings (limit to max_results)
        for listing in listings[:max_results]:
            try:
                company_data = {}
                
                # Extract company name - Google Maps typically has it in a link or heading
                name_elem = await listing.query_selector('a[data-value], div[data-value] a, h3, div[role="button"]')
                if not name_elem:
                    # Try getting text directly
                    name_text = await listing.evaluate('el => el.innerText')
                    if name_text:
                        # First line is usually the company name
                        company_data['company_name'] = name_text.split('\n')[0].strip()
                else:
                    company_data['company_name'] = await name_elem.inner_text()
                    company_data['company_name'] = company_data['company_name'].strip()
                
                if not company_data.get('company_name'):
                    continue
                
                # Extract address - usually in the listing text
                address_elem = await listing.query_selector('span[class*="address"], div[class*="address"]')
                if address_elem:
                    company_data['company_address'] = await address_elem.inner_text()
                    company_data['company_address'] = company_data['company_address'].strip()
                else:
                    # Try to extract from full text
                    full_text = await listing.evaluate('el => el.innerText')
                    lines = full_text.split('\n')
                    if len(lines) > 1:
                        # Address is usually on second or third line
                        company_data['company_address'] = lines[1].strip() if len(lines) > 1 else ''
                
                # Extract website URL if present
                website_elem = await listing.query_selector('a[href*="http"]:not([href*="google"]):not([href*="maps"])')
                if website_elem:
                    website_href = await website_elem.get_attribute('href')
                    if website_href and 'http' in website_href:
                        company_data['website_url'] = normalize_url(website_href)
                
                if company_data.get('company_name'):
                    companies.append(company_data)
                    
            except Exception as e:
                Actor.log.debug(f"Error extracting listing data: {str(e)}")
                continue
        
    except Exception as e:
        Actor.log.error(f"Error searching Google Maps: {str(e)}")
        Actor.log.debug(f"Search URL was: {search_url}")
    
    Actor.log.info(f"Google Maps search found {len(companies)} companies")
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
            
            # Try Google Maps
            Actor.log.info("Trying Google Maps...")
            try:
                companies = await search_google_maps(industry, location, max_results, page)
                
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

