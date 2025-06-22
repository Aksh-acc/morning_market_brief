import requests
import os
import time
import logging
from dotenv import load_dotenv
from typing import Dict, Any, Optional, List

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class AlphaVantageAPI:
    """
    A client for interacting with the Alpha Vantage financial API.
    Handles API key management, rate limiting, and basic error handling.
    """
    BASE_URL = "https://www.alphavantage.co/query"
    # Free tier limit: 5 calls per minute, 500 calls per day
    # We'll implement a simple per-call delay to respect the minute limit.
    CALL_INTERVAL_SECONDS = 12.1 # Slightly more than 60 seconds / 5 calls

    def __init__(self):
        self.api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        if not self.api_key:
            logging.error("ALPHA_VANTAGE_API_KEY not found in environment variables.")
            raise ValueError("ALPHA_VANTAGE_API_KEY is not set. Please set it in your .env file.")
        self._last_call_time = 0

    def _make_api_call(self, params: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """
        Internal method to make a GET request to Alpha Vantage API,
        handling rate limiting and common errors.
        """
        # Enforce rate limit
        current_time = time.time()
        elapsed_time = current_time - self._last_call_time
        if elapsed_time < self.CALL_INTERVAL_SECONDS:
            wait_time = self.CALL_INTERVAL_SECONDS - elapsed_time
            logging.info(f"Rate limit: Waiting {wait_time:.2f} seconds before next API call.")
            time.sleep(wait_time)

        params['apikey'] = self.api_key
        try:
            response = requests.get(self.BASE_URL, params=params, timeout=15)
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            data = response.json()

            if "Error Message" in data:
                logging.error(f"Alpha Vantage API Error: {data['Error Message']}")
                return None
            if "Note" in data and "rate limit" in data["Note"].lower():
                logging.warning(f"Alpha Vantage Rate Limit Note: {data['Note']}. Consider increasing delay or upgrading plan.")
                return None # Or implement more robust retry logic

            self._last_call_time = time.time() # Update last call time only on successful request
            return data
        except requests.exceptions.Timeout:
            logging.error(f"Alpha Vantage API call timed out after 15 seconds for params: {params}")
            return None
        except requests.exceptions.RequestException as e:
            logging.error(f"Error during Alpha Vantage API request: {e}")
            return None
        except ValueError as e: # For json.JSONDecodeError
            logging.error(f"Failed to decode JSON from Alpha Vantage response: {e}. Raw response: {response.text[:200]}...")
            return None

    def get_global_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Fetches the global quote for a given stock symbol.
        https://www.alphavantage.co/documentation/#latestquote

        Args:
            symbol (str): The stock ticker symbol (e.g., "AAPL").

        Returns:
            Optional[Dict[str, Any]]: A dictionary containing quote data, or None if failed.
        """
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": symbol
        }
        data = self._make_api_call(params)
        if data and "Global Quote" in data:
            quote = data["Global Quote"]
            # Clean up keys by removing the "0X." prefixes
            cleaned_quote = {k.split('. ')[-1]: v for k, v in quote.items()}
            logging.info(f"Successfully retrieved global quote for {symbol}.")
            return cleaned_quote
        logging.warning(f"Could not retrieve global quote for {symbol}.")
        return None

    def get_daily_time_series(self, symbol: str, outputsize: str = "compact") -> Optional[Dict[str, Any]]:
        """
        Fetches daily time series data for a given stock symbol.
        https://www.alphavantage.co/documentation/#daily

        Args:
            symbol (str): The stock ticker symbol.
            outputsize (str): "compact" returns the last 100 data points, "full" returns all.

        Returns:
            Optional[Dict[str, Any]]: A dictionary containing daily time series, or None.
        """
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol,
            "outputsize": outputsize
        }
        data = self._make_api_call(params)
        if data and "Time Series (Daily)" in data:
            logging.info(f"Successfully retrieved daily time series for {symbol}.")
            return data["Time Series (Daily)"]
        logging.warning(f"Could not retrieve daily time series for {symbol}.")
        return None

    def get_news_sentiment(self, tickers: Optional[str] = None, topics: Optional[str] = None,
                           time_from: Optional[str] = None, time_to: Optional[str] = None,
                           limit: int = 50) -> Optional[List[Dict[str, Any]]]:
        """
        Fetches news and sentiment data.
        https://www.alphavantage.co/documentation/#news-sentiment

        Args:
            tickers (str, optional): Comma-separated list of stock tickers (e.g., "AAPL,MSFT").
            topics (str, optional): Comma-separated list of news topics (e.g., "technology,finance").
                                     See Alpha Vantage docs for full list.
            time_from (str, optional): YYYYMMDDTHHMM format (e.g., "20240101T0000").
            time_to (str, optional): YYYYMMDDTHHMM format.
            limit (int): Number of news articles to retrieve (max 200).

        Returns:
            Optional[List[Dict[str, Any]]]: A list of news articles, or None.
        """
        params = {
            "function": "NEWS_SENTIMENT",
            "sort": "LATEST", # Most recent first
            "limit": str(min(limit, 200)) # Max 200 for free tier
        }
        if tickers:
            params["tickers"] = tickers
        if topics:
            params["topics"] = topics
        if time_from:
            params["time_from"] = time_from
        if time_to:
            params["time_to"] = time_to

        data = self._make_api_call(params)
        if data and "feed" in data:
            logging.info(f"Successfully retrieved {len(data['feed'])} news articles.")
            return data["feed"]
        logging.warning(f"Could not retrieve news sentiment data with params: {params}.")
        return None

# --- Example Usage (for testing this module independently) ---
if __name__ == "__main__":
    av_api = AlphaVantageAPI()

    print("\n--- Testing Global Quote ---")
    quote_data = av_api.get_global_quote("IBM")
    if quote_data:
        print(f"IBM Quote: {quote_data}")

    print("\n--- Testing Daily Time Series ---")
    daily_data = av_api.get_daily_time_series("MSFT", outputsize="compact")
    if daily_data:
        # Print a few recent dates
        print(f"MSFT Daily Data (recent 5 days):")
        for date, values in list(daily_data.items())[:5]:
            print(f"  {date}: Close {values['4. close']}, Volume {values['6. volume']}")

    print("\n--- Testing News & Sentiment ---")
    # Get news for Apple, recent 2 articles
    news_data = av_api.get_news_sentiment(tickers="AAPL", limit=2)
    if news_data:
        print(f"AAPL News (first 2 articles):")
        for article in news_data:
            print(f"  Title: {article.get('title')}")
            print(f"  Source: {article.get('source')}")
            print(f"  URL: {article.get('url')}")
            print(f"  Summary: {article.get('summary', '')[:100]}...") # Print first 100 chars
            print("-" * 20)

    print("\n--- Testing News for a specific topic (e.g., 'energy') ---")
    energy_news = av_api.get_news_sentiment(topics="energy", limit=1)
    if energy_news:
        print(f"Energy News (1 article):")
        for article in energy_news:
            print(f"  Title: {article.get('title')}")
            print(f"  Source: {article.get('source')}")
            print(f"  URL: {article.get('url')}")
            print("-" * 20)
