# filename: src/directories.py
"""Functions to search business directories for companies matching industry and location."""

import asyncio
from typing import List, Dict, Optional, AsyncIterator
from urllib.parse import quote_plus, urljoin
from apify import Actor
from playwright.async_api import async_playwright, Browser, Page

from src.utils import normalize_url


# Directory search URLs and selectors
GOOGLE_MAPS_SEARCH_URL = "https://www.google.com/maps/search"
LINKEDIN_SEARCH_URL = "https://www.linkedin.com/search/results/companies"


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


async def search_linkedin(
    industry: str,
    location: str,
    max_results: int,
    page: Page
) -> List[Dict]:
    """
    Search LinkedIn for companies matching industry and location.
    
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
        # Build search URL for LinkedIn
        # LinkedIn search format: keywords and location
        search_query = f"{industry} {location}"
        search_url = f"{LINKEDIN_SEARCH_URL}/?keywords={quote_plus(industry)}"
        
        Actor.log.info(f"Navigating to LinkedIn: {search_url}")
        
        # Navigate to LinkedIn
        await page.goto(search_url, wait_until='networkidle', timeout=30000)
        
        # Wait for page to load
        await page.wait_for_timeout(5000)
        
        # Check if we need to log in (LinkedIn often requires authentication)
        page_title = await page.title()
        Actor.log.info(f"Page title: {page_title}")
        
        # Check if we're on a login page
        if 'login' in page_title.lower() or 'sign in' in page_title.lower():
            Actor.log.warning("LinkedIn requires authentication - skipping LinkedIn search")
            return companies
        
        # Try to find company listings
        listings = []
        selectors = [
            'div[class*="entity-result"]',
            'div[class*="search-result"]',
            'li[class*="reusable-search__result-container"]',
            'div[data-chameleon-result-urn]',
            'div[class*="company"]'
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
            Actor.log.warning("No LinkedIn listings found")
            return companies
        
        # Extract data from listings
        for listing in listings[:max_results]:
            try:
                company_data = {}
                
                # Extract company name
                name_elem = await listing.query_selector('a[class*="entity-result__title"], a[class*="search-result__result-link"], h3 a, span[class*="entity-result__title-text"]')
                if name_elem:
                    company_data['company_name'] = await name_elem.inner_text()
                    company_data['company_name'] = company_data['company_name'].strip()
                    
                    # Get LinkedIn URL
                    linkedin_href = await name_elem.get_attribute('href')
                    if linkedin_href:
                        if linkedin_href.startswith('/'):
                            company_data['linkedin_url'] = f"https://www.linkedin.com{linkedin_href}"
                        else:
                            company_data['linkedin_url'] = normalize_url(linkedin_href)
                else:
                    continue
                
                # Extract location/address
                location_elem = await listing.query_selector('div[class*="entity-result__primary-subtitle"], span[class*="entity-result__subtitle"]')
                if location_elem:
                    company_data['company_address'] = await location_elem.inner_text()
                    company_data['company_address'] = company_data['company_address'].strip()
                
                # Extract company size (if available)
                size_elem = await listing.query_selector('div[class*="entity-result__secondary-subtitle"], span[class*="entity-result__insights"]')
                if size_elem:
                    size_text = await size_elem.inner_text()
                    # Look for patterns like "11-50 employees"
                    if 'employee' in size_text.lower():
                        company_data['company_size'] = size_text.strip()
                
                # Extract website if present
                website_elem = await listing.query_selector('a[href^="http"]:not([href*="linkedin"])')
                if website_elem:
                    website_href = await website_elem.get_attribute('href')
                    if website_href and 'http' in website_href:
                        company_data['website_url'] = normalize_url(website_href)
                
                if company_data.get('company_name'):
                    companies.append(company_data)
                    
            except Exception as e:
                Actor.log.debug(f"Error extracting LinkedIn listing data: {str(e)}")
                continue
        
    except Exception as e:
        Actor.log.error(f"Error searching LinkedIn: {str(e)}")
    
    Actor.log.info(f"LinkedIn search found {len(companies)} companies")
    return companies


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
                Actor.log.error(f"Error in Google Maps search: {str(e)}")
            
            # Try LinkedIn for additional data
            if total_found < max_results:
                Actor.log.info("Trying LinkedIn...")
                try:
                    companies = await search_linkedin(industry, location, max_results - total_found, page)
                    
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
                    Actor.log.error(f"Error in LinkedIn search: {str(e)}")
            
        finally:
            await browser.close()

