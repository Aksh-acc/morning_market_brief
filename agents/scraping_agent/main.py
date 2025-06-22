# agents/scraping_agent/main.py

from fastapi import FastAPI, HTTPException, Query, status
from typing import List, Dict, Any, Optional
import logging
from urllib.parse import urlparse # For basic URL validation

# Import the WebScraper client
from data_ingestion.web_scrapper import WebScraper

# Configure logging for the FastAPI app
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI(
    title="Web Scraping Agent",
    description="Microservice to perform web scraping tasks for financial insights.",
    version="1.0.0"
)

# Initialize the WebScraper globally
# It's crucial to set appropriate delays here to be a polite scraper.
# These delays will apply between consecutive calls made by this agent.
scraper_client = WebScraper(delay_min=3, delay_max=7)
logging.info("WebScraper client initialized successfully.")

@app.get("/")
async def root():
    """Root endpoint for the Scraping Agent."""
    return {"message": "Web Scraping Agent is running. Use /docs for API documentation."}

def _is_valid_url(url: str) -> bool:
    """Basic validation to check if a string is a well-formed HTTP/HTTPS URL."""
    try:
        result = urlparse(url)
        return all([result.scheme in ('http', 'https'), result.netloc])
    except ValueError:
        return False

@app.get("/scrape_article", response_model=Optional[Dict[str, Any]])
async def scrape_single_article(url: str = Query(..., description="The URL of the article to scrape.")):
    """
    Scrapes a single news article to extract its title, publication date, and main content.
    """
    if not _is_valid_url(url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid URL provided: {url}. Must be a valid http or https URL."
        )

    logging.info(f"Received request to scrape article: {url}")
    scraped_data = scraper_client.scrape_article(url)

    if scraped_data:
        logging.info(f"Successfully scraped article from {url}.")
        return scraped_data
    else:
        # The scraper returns None on failure, which means we couldn't extract enough data
        # or there was a network error/block.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, # Or 404 if content truly not found
            detail=f"Failed to scrape article content from {url}. "
                   "This might be due to anti-scraping measures, dynamic content, or an invalid URL structure."
        )

@app.get("/scrape_links", response_model=List[str])
async def scrape_links_from_page(
    url: str = Query(..., description="The URL of the page to scrape links from."),
    link_contains_text: Optional[str] = Query(None, description="Only return links where the href contains this text."),
    domain_filter: Optional[str] = Query(None, description="Only return links belonging to this domain (e.g., 'reuters.com')."),
    max_links: Optional[int] = Query(None, description="Maximum number of links to return. Defaults to all if not specified.")
):
    """
    Scrapes all unique absolute URLs from a given page, with optional filters.
    """
    if not _is_valid_url(url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid URL provided: {url}. Must be a valid http or https URL."
        )

    logging.info(f"Received request to scrape links from: {url} "
                 f"(contains: {link_contains_text}, domain: {domain_filter}, max: {max_links})")
    
    links = scraper_client.scrape_links_from_page(
        url=url,
        link_contains_text=link_contains_text,
        domain_filter=domain_filter,
        max_links=max_links
    )

    if links:
        logging.info(f"Successfully scraped {len(links)} links from {url}.")
        return links
    else:
        logging.warning(f"No links found or failed to scrape links from {url}.")
        # Return an empty list or 404 depending on desired behavior. Empty list is often fine.
        return []