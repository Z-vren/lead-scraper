# filename: src/main.py
"""Main entry point for the Apify Actor."""

import asyncio
from apify import Actor
from apify.log import logger

from src.models import ActorInput, OutputCompany
from src.directories import search_companies
from src.website_enricher import enrich_company_website
from src.utils import normalize_url, deduplicate_list
import httpx


async def main():
    """Main async function that runs the Actor."""
    async with Actor:
        # Read Actor input
        actor_input = await Actor.get_input() or {}
        
        try:
            # Validate input
            input_model = ActorInput(**actor_input)
            industry = input_model.industry
            location = input_model.location
            max_results = input_model.max_results
            
            Actor.log.info(f"Starting lead scraper for industry: {industry}, location: {location}, max_results: {max_results}")
            
            # Track processed companies to avoid duplicates
            processed_companies = set()
            results_count = 0
            
            # Create HTTP client for website enrichment
            async with httpx.AsyncClient() as client:
                # Search directories for companies
                async for company in search_companies(industry, location, max_results):
                    if results_count >= max_results:
                        break
                    
                    try:
                        # Create a unique key for deduplication
                        company_name_key = company.get('company_name', '').lower().strip()
                        if not company_name_key or company_name_key in processed_companies:
                            continue
                        
                        processed_companies.add(company_name_key)
                        
                        # Enrich company data by visiting website
                        Actor.log.info(f"Enriching data for: {company.get('company_name', 'Unknown')}")
                        company = await enrich_company_website(company, client)
                        
                        # Normalize website URL
                        if company.get('website_url'):
                            company['website_url'] = normalize_url(company['website_url'])
                        
                        # Ensure all required fields are present
                        output_company = OutputCompany(
                            company_name=company.get('company_name', 'Unknown'),
                            website_url=company.get('website_url'),
                            linkedin_url=company.get('linkedin_url'),
                            social_links=deduplicate_list(company.get('social_links', [])),
                            company_size=company.get('company_size'),
                            company_address=company.get('company_address'),
                            company_emails=deduplicate_list(company.get('company_emails', []))
                        )
                        
                        # Push to dataset
                        await Actor.push_data(output_company.model_dump())
                        results_count += 1
                        
                        Actor.log.info(f"Processed {results_count}/{max_results} companies")
                        
                    except Exception as e:
                        Actor.log.error(f"Error processing company {company.get('company_name', 'Unknown')}: {str(e)}")
                        continue
            
            Actor.log.info(f"Completed! Processed {results_count} companies")
            
        except Exception as e:
            Actor.log.error(f"Fatal error in Actor: {str(e)}")
            raise


if __name__ == '__main__':
    asyncio.run(main())

