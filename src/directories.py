# filename: src/directories.py
"""Functions to search business directories for companies matching industry and location."""

import asyncio
from typing import List, Dict, Optional, AsyncIterator
import httpx
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urljoin
from apify import Actor

from src.utils import normalize_url


# Directory search URLs and selectors
# Using a generic approach that can work with multiple directories
YELLOWPAGES_SEARCH_URL = "https://www.yellowpages.com/search"
YELLOWPAGES_BASE_URL = "https://www.yellowpages.com"


async def search_yellowpages(
    industry: str,
    location: str,
    max_results: int,
    client: httpx.AsyncClient
) -> List[Dict]:
    """
    Search YellowPages for companies matching industry and location.
    
    Args:
        industry: Industry keyword
        location: Location string
        max_results: Maximum number of results
        client: HTTP client
        
    Returns:
        List of company dictionaries with basic info
    """
    companies = []
    
    try:
        # Build search URL
        search_query = f"{industry} {location}"
        search_url = f"{YELLOWPAGES_SEARCH_URL}?search_terms={quote_plus(search_query)}&geo_location_terms={quote_plus(location)}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        
        response = await client.get(search_url, headers=headers, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # YellowPages structure - adjust selectors based on actual page structure
        # Common selectors for business listings
        listings = soup.find_all('div', class_=lambda x: x and ('result' in x.lower() or 'listing' in x.lower()))
        
        if not listings:
            # Try alternative selector
            listings = soup.find_all('div', {'class': 'srp-listing'})
        
        if not listings:
            # Try another common pattern
            listings = soup.find_all('div', {'class': 'search-result'})
        
        for listing in listings[:max_results]:
            try:
                company_data = {}
                
                # Extract company name
                name_elem = listing.find('a', class_=lambda x: x and ('business-name' in x.lower() or 'name' in x.lower()))
                if not name_elem:
                    name_elem = listing.find('h2', class_=lambda x: x and 'name' in x.lower())
                if not name_elem:
                    name_elem = listing.find('a', href=True)
                
                if name_elem:
                    company_data['company_name'] = name_elem.get_text(strip=True)
                    
                    # Try to get website from the same link or nearby
                    href = name_elem.get('href', '')
                    if href:
                        company_data['website_url'] = normalize_url(href, YELLOWPAGES_BASE_URL)
                else:
                    continue
                
                # Extract address
                address_elem = listing.find('div', class_=lambda x: x and 'address' in x.lower())
                if not address_elem:
                    address_elem = listing.find('span', class_=lambda x: x and 'address' in x.lower())
                
                if address_elem:
                    company_data['company_address'] = address_elem.get_text(strip=True)
                
                # Extract website URL (separate from company name link)
                website_elem = listing.find('a', class_=lambda x: x and ('website' in x.lower() or 'url' in x.lower()))
                if website_elem and website_elem.get('href'):
                    company_data['website_url'] = normalize_url(website_elem['href'], YELLOWPAGES_BASE_URL)
                
                # Extract LinkedIn if present
                linkedin_elem = listing.find('a', href=lambda x: x and 'linkedin.com' in x.lower() if x else False)
                if linkedin_elem:
                    company_data['linkedin_url'] = normalize_url(linkedin_elem.get('href', ''))
                
                if company_data.get('company_name'):
                    companies.append(company_data)
                    
            except Exception as e:
                # Skip individual listing errors
                continue
        
    except Exception as e:
        # Log error but continue
        Actor.log.error(f"Error searching YellowPages: {str(e)}")
        Actor.log.debug(f"Search URL was: {search_url}")
    
    Actor.log.info(f"YellowPages search found {len(companies)} companies")
    return companies


async def search_generic_directory(
    industry: str,
    location: str,
    max_results: int,
    client: httpx.AsyncClient
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
    async with httpx.AsyncClient() as client:
        # Try multiple directory sources
        Actor.log.info(f"Searching directories for: {industry} in {location}")
        sources = [
            search_yellowpages(industry, location, max_results, client),
            # Add more directory sources here as needed
        ]
        
        seen_names = set()
        total_found = 0
        
        for source_coro in sources:
            Actor.log.info(f"Trying search source...")
            if total_found >= max_results:
                break
                
            try:
                companies = await source_coro
                
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
                # Continue with next source if one fails
                Actor.log.error(f"Error in search source: {str(e)}")
                continue

