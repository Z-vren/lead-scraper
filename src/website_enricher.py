# filename: src/website_enricher.py
"""Functions to enrich company data by visiting their websites."""

from typing import Dict, Optional
import httpx
from bs4 import BeautifulSoup

from src.utils import extract_emails, extract_social_links, normalize_url, deduplicate_list


async def enrich_company_website(
    company: Dict,
    client: httpx.AsyncClient,
    timeout: float = 15.0
) -> Dict:
    """
    Enrich company data by visiting their website.
    Extracts emails and social links from the homepage.
    
    Args:
        company: Company dictionary with at least 'website_url'
        client: HTTP client for making requests
        timeout: Request timeout in seconds
        
    Returns:
        Updated company dictionary with enriched data
    """
    website_url = company.get('website_url')
    
    if not website_url:
        return company
    
    # Normalize URL
    website_url = normalize_url(website_url)
    if not website_url or not website_url.startswith(('http://', 'https://')):
        return company
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        
        response = await client.get(
            website_url,
            headers=headers,
            timeout=timeout,
            follow_redirects=True
        )
        response.raise_for_status()
        
        html_content = response.text
        
        # Extract emails from HTML
        emails = extract_emails(html_content)
        
        # Also check mailto links
        soup = BeautifulSoup(html_content, 'lxml')
        for mailto_link in soup.find_all('a', href=lambda x: x and x.startswith('mailto:') if x else False):
            email = mailto_link.get('href', '').replace('mailto:', '').split('?')[0].strip()
            if email:
                emails.append(email.lower())
        
        # Deduplicate emails
        company['company_emails'] = deduplicate_list(emails)
        
        # Extract social links
        social_links = extract_social_links(html_content, website_url)
        
        # Merge with existing social links
        existing_socials = company.get('social_links', [])
        if not isinstance(existing_socials, list):
            existing_socials = []
        
        all_socials = existing_socials + social_links
        company['social_links'] = deduplicate_list(all_socials)
        
        # Extract LinkedIn URL specifically if found
        for link in company['social_links']:
            if 'linkedin.com' in link.lower() and not company.get('linkedin_url'):
                company['linkedin_url'] = normalize_url(link)
                break
        
    except httpx.TimeoutException:
        # Timeout - skip enrichment but keep existing data
        pass
    except httpx.HTTPStatusError:
        # HTTP error - skip enrichment
        pass
    except Exception:
        # Any other error - skip enrichment
        pass
    
    return company

