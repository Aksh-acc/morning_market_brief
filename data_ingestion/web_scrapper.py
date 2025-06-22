# data_ingestion/web_scraper.py

import requests
from bs4 import BeautifulSoup
import time
import random
import re
from urllib.parse import urljoin, urlparse

class WebScraper:
    """
    A class for scraping web content, focusing on financial news and general articles.
    Includes basic rate limiting and error handling.
    """
    def __init__(self, user_agent=None, delay_min=2, delay_max=5):
        """
        Initializes the WebScraper.

        Args:
            user_agent (str, optional): The User-Agent string to use for requests.
                                        If None, a default common one is used.
            delay_min (int): Minimum delay in seconds between requests.
            delay_max (int): Maximum delay in seconds between requests.
        """
        self.headers = {
            'User-Agent': user_agent or 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
        }
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.session = requests.Session() # Use a session for persistent connections

    def _apply_delay(self):
        """Applies a random delay between requests to be polite."""
        delay = random.uniform(self.delay_min, self.delay_max)
        print(f"Applying delay of {delay:.2f} seconds...")
        time.sleep(delay)

    def _fetch_html(self, url):
        """Fetches the HTML content of a given URL."""
        self._apply_delay() # Apply delay before each request
        try:
            response = self.session.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None

    def _is_valid_url(self, url):
        """Checks if a URL is well-formed."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except ValueError:
            return False

    def scrape_article(self, url):
        """
        Scrapes a single news article to extract its title, publication date, and main content.
        This function uses common heuristics and might need adjustment for specific websites.

        Args:
            url (str): The URL of the article to scrape.

        Returns:
            dict: A dictionary containing 'title', 'date', 'content', and 'url'
                  or None if scraping fails.
        """
        if not self._is_valid_url(url):
            print(f"Invalid URL provided: {url}")
            return None

        print(f"Attempting to scrape article from: {url}")
        html_content = self._fetch_html(url)
        if not html_content:
            return None

        soup = BeautifulSoup(html_content, 'html.parser')

        # --- Extract Title ---
        title = None
        for tag in ['h1', 'title']:
            potential_title = soup.find(tag)
            if potential_title and potential_title.text:
                title = potential_title.text.strip()
                # Remove common website suffixes from title
                title = re.sub(r' \| .*$', '', title)
                title = re.sub(r' - .*$', '', title)
                break
        if not title:
            print(f"Could not find a suitable title for {url}")
            # Fallback: look for meta tag title
            meta_title = soup.find('meta', attrs={'property': 'og:title'}) or \
                         soup.find('meta', attrs={'name': 'title'})
            if meta_title and meta_title.get('content'):
                title = meta_title['content'].strip()


        # --- Extract Publication Date ---
        date = None
        # Common patterns for date (meta tags, time tags, specific classes)
        for tag_name in ['time', 'span', 'div']:
            potential_dates = soup.find_all(tag_name, attrs={'datetime': True})
            if potential_dates:
                for pd in potential_dates:
                    date = pd.get('datetime')
                    if date: break
                if date: break

            # Search for common date classes/attributes
            date_patterns = ['date', 'time', 'published', 'article-date', 'post-date', 'timestamp']
            for pattern in date_patterns:
                potential_dates = soup.find_all(lambda tag: tag.has_attr('class') and pattern in ' '.join(tag['class']) or tag.has_attr('id') and pattern in tag['id'])
                for pd in potential_dates:
                    if pd.text and len(pd.text.strip()) > 5: # Basic check for meaningful text
                        date = pd.text.strip()
                        # Try to parse and reformat if possible (e.g., "May 29, 2025")
                        try:
                            from dateutil.parser import parse as date_parse
                            date = date_parse(date).strftime('%Y-%m-%d %H:%M:%S')
                        except ImportError:
                            pass # dateutil not installed, keep raw text
                        except ValueError:
                            pass # Parsing failed, keep raw text
                        break
                if date: break
            if date: break

        if not date:
            print(f"Could not find a suitable date for {url}")
            # Fallback: look for meta tag date
            meta_date = soup.find('meta', attrs={'property': 'article:published_time'}) or \
                        soup.find('meta', attrs={'name': 'date'})
            if meta_date and meta_date.get('content'):
                date = meta_date['content'].strip()


        # --- Extract Main Content ---
        # This is the trickiest part and highly site-dependent.
        # We'll try common article-like tags/classes.
        content_div = None
        content_selectors = [
            'div[itemprop="articleBody"]',
            'div.article-content',
            'div.entry-content',
            'div.post-content',
            'article',
            'div[role="main"]',
            'div.body-content',
            'section.article-body'
        ]

        for selector in content_selectors:
            content_div = soup.select_one(selector)
            if content_div:
                break

        if not content_div:
            # Fallback: Try to find a large paragraph block
            paragraphs = soup.find_all('p')
            if paragraphs:
                # Heuristic: Find the div/section with the most paragraph tags
                # This is a very crude fallback and might pick up comments/ads
                parent_counts = {}
                for p in paragraphs:
                    current_parent = p.find_parent()
                    while current_parent and current_parent.name not in ['html', 'body']:
                        parent_counts[current_parent] = parent_counts.get(current_parent, 0) + 1
                        current_parent = current_parent.find_parent()

                if parent_counts:
                    content_div = max(parent_counts, key=parent_counts.get)
            else:
                print(f"Could not find main content for {url} using common selectors or paragraphs.")
                return None # Failed to find content


        # Extract text from the identified content_div, excluding script/style tags
        if content_div:
            # Remove scripts and style elements
            for script_or_style in content_div(['script', 'style', 'noscript', 'form', 'img', 'header', 'footer', 'nav', 'aside']):
                script_or_style.extract()

            # Get text and clean it up
            content_text = content_div.get_text(separator='\n', strip=True)
            # Remove excessive newlines and whitespace
            content_text = re.sub(r'\n\s*\n', '\n\n', content_text).strip()
        else:
            content_text = ""

        if not title and not content_text:
            print(f"Scraping failed to extract meaningful data from {url}")
            return None

        print(f"Successfully scraped: {title[:50]}...")
        return {
            'url': url,
            'title': title,
            'date': date,
            'content': content_text
        }

    def scrape_links_from_page(self, url, link_contains_text=None, domain_filter=None, max_links=None):
        """
        Scrapes all links from a given page, with optional filters.

        Args:
            url (str): The URL of the page to scrape links from.
            link_contains_text (str, optional): Only return links where the href contains this text.
            domain_filter (str, optional): Only return links belonging to this domain (e.g., 'reuters.com').
            max_links (int, optional): Maximum number of links to return.

        Returns:
            list: A list of unique absolute URLs found.
        """
        print(f"Scraping links from: {url}")
        html_content = self._fetch_html(url)
        if not html_content:
            return []

        soup = BeautifulSoup(html_content, 'html.parser')
        links = set()
        base_domain = urlparse(url).netloc

        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href'].strip()
            absolute_url = urljoin(url, href)
            parsed_link = urlparse(absolute_url)

            # Check if it's a valid http/https link
            if parsed_link.scheme not in ('http', 'https'):
                continue

            # Apply domain filter if specified
            if domain_filter and not parsed_link.netloc.endswith(domain_filter):
                continue

            # Apply link_contains_text filter if specified
            if link_contains_text and link_contains_text not in absolute_url:
                continue

            # Filter out internal anchor links, mailto, tel, etc.
            if '#' in absolute_url and urlparse(absolute_url).path == urlparse(url).path:
                continue
            if absolute_url.startswith('mailto:') or absolute_url.startswith('tel:'):
                continue

            links.add(absolute_url)
            if max_links and len(links) >= max_links:
                break
        
        print(f"Found {len(links)} unique links.")
        return list(links)


# --- Example Usage (for testing the module) ---
if __name__ == "__main__":
    scraper = WebScraper(delay_min=3, delay_max=7) # Be more polite with delays

    # --- Test 1: Scrape a general news article ---
    print("\n--- Testing article scraping ---")
    article_url = "https://finance.yahoo.com/news/live/nvidia-earnings-live-nvidia-beats-on-q1-revenue-sees-8-billion-impact-from-china-export-rules-203749071.html"
    # For testing, pick a specific article URL that you know exists and is accessible.
    # Replace with a current article if this one becomes stale.
    # Note: Reuters sometimes has anti-scraping measures.
    
    # Try another source if Reuters gives trouble:
    # article_url = "https://www.cnbc.com/2024/05/29/stocks-making-the-biggest-moves-midday-ge-hp-salesforce-more.html"
    # article_url = "https://finance.yahoo.com/news/bank-of-america-sees-strong-ai-demand-boosting-chip-stocks-160000030.html"

    scraped_data = scraper.scrape_article(article_url)
    if scraped_data:
        print("\nScraped Article Data:")
        print(f"URL: {scraped_data['url']}")
        print(f"Title: {scraped_data['title']}")
        print(f"Date: {scraped_data['date']}")
        print(f"Content (first 500 chars):\n{scraped_data['content'][:500]}...")
    else:
        print(f"Failed to scrape article from {article_url}")

    # --- Test 2: Scrape links from a news portal's homepage ---
    print("\n--- Testing link scraping from a news portal ---")
    news_homepage_url = "https://finance.yahoo.com/"
    # Get links that contain "news" and are from yahoo.com
    news_links = scraper.scrape_links_from_page(
        news_homepage_url,
        link_contains_text='/news/',
        domain_filter='yahoo.com',
        max_links=5
    )
    if news_links:
        print("\nFound these news links:")
        for link in news_links:
            print(link)
    else:
        print("No news links found or failed to scrape links.")

    # --- Test 3: Scrape links from a specific company's investor relations page (example) ---
    # This often involves dynamic content or specific file types like PDFs.
    # This example just shows how you might approach it, actual implementation for PDFs
    # would involve a document loader.
    print("\n--- Testing link scraping for investor relations (PDFs often involved) ---")
    investor_url = "https://www.marketwatch.com/latest-news" # Example AT&T investor page
    pdf_links = scraper.scrape_links_from_page(
        investor_url,
        link_contains_text='.pdf', # Look for PDF links
        domain_filter='att.com', # Ensure it's from AT&T
        max_links=3
    )
    if pdf_links:
        print("\nFound these PDF links:")
        for link in pdf_links:
            print(link)
    else:
        print("No PDF links found or failed to scrape links from investor page.")