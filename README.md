# Lead Scraper Actor

A production-ready Apify Actor for B2B lead discovery that searches business directories and enriches company information from websites.

## Features

- Searches public business directories for companies matching industry and location
- Extracts company information: name, website, LinkedIn, social links, address, emails
- Enriches data by visiting company websites to find additional emails and social links
- Respects robots.txt and site terms of service
- Handles errors gracefully and continues processing

## Input

The Actor accepts the following input JSON:

```json
{
  "industry": "Software as a Service",
  "location": "Berlin, Germany",
  "max_results": 50
}
```

### Input Fields

- `industry` (required): Industry keyword to search for (e.g., "Software as a Service", "Marketing Agency")
- `location` (required): Location string (e.g., "Berlin, Germany", "New York, NY")
- `max_results` (optional): Maximum number of results to return (default: 50, max: 1000)

## Output

The Actor outputs one record per company to the default Apify dataset with the following schema:

```json
{
  "company_name": "Example Company Inc.",
  "website_url": "https://example.com",
  "linkedin_url": "https://linkedin.com/company/example",
  "social_links": [
    "https://instagram.com/example",
    "https://facebook.com/example"
  ],
  "company_size": "11-50",
  "company_address": "123 Main St, Berlin, Germany",
  "company_emails": [
    "contact@example.com",
    "info@example.com"
  ]
}
```

### Output Fields

- `company_name` (string): Name of the company
- `website_url` (string | null): Company website URL
- `linkedin_url` (string | null): LinkedIn company page URL
- `social_links` (string[]): Array of social media URLs (Instagram, Facebook, X/Twitter, etc.)
- `company_size` (string | null): Company size range (e.g., "1-10", "11-50", "51-200")
- `company_address` (string | null): Company physical address
- `company_emails` (string[]): Array of email addresses found on the website

## Local Development

### Prerequisites

- Python 3.10 or higher
- Apify CLI (`npm install -g apify-cli`)

### Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the actor locally:
```bash
apify run
```

3. Test with input:
```bash
apify run --input-json='{"industry": "Software as a Service", "location": "Berlin, Germany", "max_results": 10}'
```

## Deployment to Apify

1. Push your code to GitHub (or use Apify's Git integration)

2. Create a new Actor on Apify Platform:
   - Go to [Apify Console](https://console.apify.com)
   - Click "Create new" → "Actor"
   - Connect your GitHub repository or upload the code

3. Configure the Actor:
   - Set the build environment to Python 3.10
   - The `Dockerfile` and `.actor/actor.json` are already configured

4. Run the Actor:
   - Use the input JSON format shown above
   - Results will be available in the Actor's dataset

## Project Structure

```
lead-scraper-actor/
├── .actor/
│   └── actor.json          # Apify Actor configuration
├── src/
│   ├── main.py            # Main entry point
│   ├── models.py          # Pydantic models for input/output
│   ├── directories.py     # Directory scraping logic
│   ├── website_enricher.py # Website enrichment functions
│   └── utils.py           # Utility functions
├── requirements.txt       # Python dependencies
├── Dockerfile            # Docker configuration
└── README.md             # This file
```

## Implementation Details

### Directory Scraping

The actor currently searches:
- YellowPages (with fallback to generic search)

Additional directory sources can be added in `src/directories.py` by implementing new search functions and adding them to the `search_companies()` function.

### Website Enrichment

For each company found:
1. Visits the company website (if available)
2. Extracts email addresses using regex and mailto links
3. Extracts social media links from anchor tags
4. Normalizes and deduplicates all URLs and emails

### Error Handling

- Individual company processing errors are logged but don't stop the actor
- Directory search failures fall back to other sources
- Website enrichment failures preserve existing data
- All errors are logged with `Actor.log.error()`

## Limitations

- Respects robots.txt and terms of service
- Does not bypass CAPTCHAs
- Does not scrape Google Maps directly
- Rate limiting and politeness delays should be configured based on target sites
- Some directories may require authentication or have anti-scraping measures

## License

This project is provided as-is for use as an Apify Actor.

