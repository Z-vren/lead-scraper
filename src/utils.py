# filename: src/utils.py
"""Utility functions for email extraction, URL normalization, and deduplication."""

import re
from typing import List, Set
from urllib.parse import urlparse, urlunparse, urljoin


# Email regex pattern
EMAIL_PATTERN = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
)

# Social media domains
SOCIAL_DOMAINS = {
    'linkedin.com',
    'www.linkedin.com',
    'instagram.com',
    'www.instagram.com',
    'facebook.com',
    'www.facebook.com',
    'x.com',
    'www.x.com',
    'twitter.com',
    'www.twitter.com',
    'youtube.com',
    'www.youtube.com',
    'tiktok.com',
    'www.tiktok.com',
}


def extract_emails(text: str) -> List[str]:
    """
    Extract email addresses from text using regex.
    
    Args:
        text: Text to search for emails
        
    Returns:
        List of unique email addresses found
    """
    if not text:
        return []
    
    emails = EMAIL_PATTERN.findall(text.lower())
    # Deduplicate while preserving order
    seen = set()
    unique_emails = []
    for email in emails:
        if email not in seen:
            seen.add(email)
            unique_emails.append(email)
    return unique_emails


def normalize_url(url: str, base_url: str = None) -> str:
    """
    Normalize a URL by removing fragments and normalizing the scheme.
    
    Args:
        url: URL to normalize
        base_url: Optional base URL for relative URLs
        
    Returns:
        Normalized URL string
    """
    if not url:
        return ""
    
    # Handle mailto and other non-http schemes
    if url.startswith('mailto:') or url.startswith('tel:'):
        return url
    
    # Make relative URLs absolute if base_url is provided
    if base_url and not url.startswith(('http://', 'https://')):
        url = urljoin(base_url, url)
    
    try:
        parsed = urlparse(url)
        # Reconstruct without fragment
        normalized = urlunparse((
            parsed.scheme or 'https',
            parsed.netloc.lower(),
            parsed.path,
            parsed.params,
            parsed.query,
            ''  # Remove fragment
        ))
        return normalized
    except Exception:
        return url


def is_social_link(url: str) -> bool:
    """
    Check if a URL is a social media link.
    
    Args:
        url: URL to check
        
    Returns:
        True if URL is a social media link
    """
    if not url:
        return False
    
    try:
        parsed = urlparse(url.lower())
        domain = parsed.netloc.lower()
        # Remove www. prefix for comparison
        domain = domain.replace('www.', '')
        return domain in SOCIAL_DOMAINS
    except Exception:
        return False


def extract_social_links(html_content: str, base_url: str) -> List[str]:
    """
    Extract social media links from HTML content.
    
    Args:
        html_content: HTML content to parse
        base_url: Base URL for resolving relative links
        
    Returns:
        List of unique social media URLs
    """
    from bs4 import BeautifulSoup
    
    social_links = []
    
    try:
        soup = BeautifulSoup(html_content, 'lxml')
        # Find all anchor tags
        for anchor in soup.find_all('a', href=True):
            href = anchor.get('href', '')
            normalized = normalize_url(href, base_url)
            
            if normalized and is_social_link(normalized):
                social_links.append(normalized)
    except Exception as e:
        pass  # Silently fail if parsing fails
    
    # Deduplicate
    seen = set()
    unique_links = []
    for link in social_links:
        if link not in seen:
            seen.add(link)
            unique_links.append(link)
    
    return unique_links


def deduplicate_list(items: List[str]) -> List[str]:
    """
    Remove duplicates from a list while preserving order.
    
    Args:
        items: List of strings
        
    Returns:
        Deduplicated list
    """
    seen = set()
    unique = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            unique.append(item)
    return unique

