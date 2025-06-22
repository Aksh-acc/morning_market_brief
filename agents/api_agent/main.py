# agents/api_agent/main.py

from fastapi import FastAPI, HTTPException, status, Query
from typing import Optional, Dict, Any, List
import requests
import os
import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI(
    title="API Agent",
    description="Connects to external APIs for financial data.",
    version="1.0.0"
)

# Load Alpha Vantage API Key from environment variables
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")

@app.on_event("startup")
async def startup_event():
    if not ALPHA_VANTAGE_API_KEY:
        logging.error("ALPHA_VANTAGE_API_KEY environment variable not set!")
        raise RuntimeError("ALPHA_VANTAGE_API_KEY is required for the API Agent.")
    else:
        logging.info("Alpha Vantage API key loaded successfully.")

@app.get("/")
async def root():
    return {"message": "API Agent is running. Use /docs for API documentation."}

@app.get("/quote/{symbol}")
async def get_global_quote(symbol: str) -> Dict[str, Any]:
    """
    Retrieves global quote data for a given stock symbol from Alpha Vantage.
    """
    if not ALPHA_VANTAGE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key not configured."
        )

    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={ALPHA_VANTAGE_API_KEY}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if "Global Quote" in data:
            quote_data = data["Global Quote"]
            # Clean up keys: remove "1. ", "2. ", etc., and map to cleaner names
            cleaned_quote = {
                "symbol": quote_data.get("01. symbol"),
                "open": quote_data.get("02. open"),
                "high": quote_data.get("03. high"),
                "low": quote_data.get("04. low"),
                "price": quote_data.get("05. price"),
                "volume": quote_data.get("06. volume"),
                "latest_trading_day": quote_data.get("07. latest trading day"),
                "previous_close": quote_data.get("08. previous close"),
                "change": quote_data.get("09. change"),
                "change_percent": quote_data.get("10. change percent")
            }
            logging.info(f"Successfully fetched quote for {symbol}")
            return cleaned_quote
        elif "Error Message" in data:
            logging.error(f"Alpha Vantage API error for {symbol}: {data['Error Message']}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Alpha Vantage API error: {data['Error Message']}"
            )
        else:
            logging.warning(f"Unexpected API response for {symbol}: {data}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unexpected API response."
            )
    except requests.exceptions.RequestException as e:
        logging.error(f"Network or API call error for {symbol}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch quote due to network or API error: {e}"
        )
    except Exception as e:
        logging.error(f"An unexpected error occurred while fetching quote for {symbol}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An internal error occurred: {e}"
        )


@app.get("/news")
async def get_financial_news(
    tickers: Optional[str] = Query(None, description="Comma-separated symbols (e.g., 'AAPL,MSFT')"),
    topics: Optional[str] = Query(None, description="Comma-separated topics (e.g., 'blockchain,earnings')"),
    time_from: Optional[str] = Query(None, description="YYYYMMDDTHHMM (e.g., '20240101T0000')"),
    time_to: Optional[str] = Query(None, description="YYYYMMDDTHHMM"),
    limit: int = Query(default=20, ge=1, le=200, description="Max number of articles (default 20, max 200 for free tier).")
) -> Dict[str, Any]:
    """
    Retrieves financial news and sentiment data from Alpha Vantage.
    """
    if not ALPHA_VANTAGE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key not configured."
        )

    base_url = "https://www.alphavantage.co/query"
    params = {
        "function": "NEWS_SENTIMENT",
        "apikey": ALPHA_VANTAGE_API_KEY,
        "limit": limit
    }

    if tickers:
        params["tickers"] = tickers
    if topics:
        params["topics"] = topics
    if time_from:
        params["time_from"] = time_from
    if time_to:
        params["time_to"] = time_to

    # Ensure at least one filter (tickers or topics) is provided for the Alpha Vantage API to work optimally
    if not tickers and not topics:
        # Default to a general market overview if no specific filters are given
        # You might want to remove this if you only want news for specified topics/tickers
        logging.warning("No tickers or topics provided. Fetching general market news.")
        params["topics"] = "blockchain,earnings,economy,financial_markets,manufacturing,technology,real_estate" # Example broad topics

    try:
        response = requests.get(base_url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        if "feed" in data:
            logging.info(f"Successfully fetched {len(data['feed'])} news articles.")
            return {"articles": data["feed"], "items_count": data.get("items", 0)}
        elif "Information" in data:
            logging.warning(f"Alpha Vantage API Information message: {data['Information']}")
            return {"articles": [], "items_count": 0, "message": data['Information']}
        elif "Error Message" in data:
            logging.error(f"Alpha Vantage API error for news: {data['Error Message']}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Alpha Vantage API error: {data['Error Message']}"
            )
        else:
            logging.warning(f"Unexpected API response for news: {data}")
            return {"articles": [], "items_count": 0, "message": "Unexpected API response."}

    except requests.exceptions.RequestException as e:
        logging.error(f"Network or API call error for news: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch news due to network or API error: {e}"
        )
    except Exception as e:
        logging.error(f"An unexpected error occurred while fetching news: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An internal error occurred: {e}"
        )