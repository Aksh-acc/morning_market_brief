# agents/llm_agent/main.py

from fastapi import FastAPI, HTTPException, status , Query
from typing import Dict, Any, List, Optional
import logging
import requests
import json # For pretty printing JSON in logs

# LangChain for LLM integration
from langchain.prompts import PromptTemplate
from langchain_community.llms import HuggingFacePipeline
from transformers import pipeline, AutoModelForSeq2SeqLM, AutoTokenizer # Removed BitsAndBytesConfig as it's not used here
import torch 

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI(
    title="LLM Market Brief Agent",
    description="Orchestrates data collection and generates daily morning market briefs.",
    version="1.0.0"
)

# --- Configuration for other Agents (adjust ports if necessary) ---
API_AGENT_URL = "http://127.0.0.1:8001"
SCRAPING_AGENT_URL = "http://127.0.0.1:8002"
ANALYTICS_AGENT_URL = "http://127.0.0.1:8003"

# --- LLM Setup ---
llm_model_name = "google/flan-t5-base"
device = "cuda" if torch.cuda.is_available() else "cpu"
logging.info(f"LLM will run on device: {device}")

llm_pipeline = None # Will be initialized on startup


@app.on_event("startup")
async def startup_event():
    """Load the LLM model when the FastAPI application starts up."""
    global llm_pipeline
    try:
        logging.info(f"Loading LLM model: {llm_model_name} on {device}...")
        
        tokenizer = AutoTokenizer.from_pretrained(llm_model_name)
        
        model = AutoModelForSeq2SeqLM.from_pretrained(
            llm_model_name,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32
        )
        model.to(device) 

        llm_pipeline_instance = pipeline(
            "text2text-generation", 
            model=model,
            tokenizer=tokenizer,
            max_new_tokens=512,
            repetition_penalty=1.7,
            top_p=0.95,
            temperature=0.7,
            do_sample=True, # Crucially, add this for sampling to work
            device=0 if device == "cuda" else -1
        )
        
        llm_pipeline = HuggingFacePipeline(
            pipeline=llm_pipeline_instance,
            model_kwargs={ # Pass generation arguments as model_kwargs
                "temperature": 0.7,
                "top_p": 0.95,
                "num_beams": 1,
                "do_sample": True
            }
        )

        logging.info(f"LLM model '{llm_model_name}' loaded successfully.")
    except Exception as e:
        logging.error(f"Failed to load LLM model: {e}", exc_info=True)
        llm_pipeline = None 
        raise RuntimeError(f"Failed to load LLM model on startup: {e}")

@app.get("/")
async def root():
    """Root endpoint for the LLM Market Brief Agent."""
    return {"message": "LLM Market Brief Agent is running. Use /docs for API documentation."}

async def _call_agent(agent_url: str, endpoint: str, method: str = "GET", params: Optional[Dict] = None, json_data: Optional[Dict] = None) -> Optional[Any]:
    """Helper to call other internal FastAPI agents."""
    url = f"{agent_url}/{endpoint}"
    logging.info(f"Calling {method} {url} with params: {params}, data: {json_data}")
    try:
        if method == "GET":
            response = requests.get(url, params=params, timeout=30)
        elif method == "POST":
            response = requests.post(url, params=params, json=json_data, timeout=30)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to call agent {agent_url}: {e}")
        return None
    except json.JSONDecodeError as e:
        logging.error(f"Failed to decode JSON response from {agent_url}: {e}. Response text: {response.text[:200]}...")
        return None

@app.post("/generate_brief")
async def generate_market_brief(
    symbols: Optional[str] = Query("SPY,QQQ,^IXIC,^DJI,AAPL,MSFT,NVDA,GOOGL,TSLA,AMZN", description="Comma-separated stock symbols for overview."),
    news_topics: Optional[str] = Query("earnings,technology,markets,economy", description="Comma-separated news topics."),
    news_limit: int = Query(10, description="Max number of news articles to fetch per symbol/topic."),
    full_brief: bool = Query(True, description="Generate a more comprehensive brief.")
) -> Dict[str, Any]:
    """
    Generates a comprehensive morning market brief by leveraging other agents.
    """
    if not llm_pipeline:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM model not initialized. Check server logs for errors during startup."
        )

    logging.info("Starting market brief generation process...")
    brief_data = {}

    # --- 1. Get Global Stock Quotes and Analyze ---
    logging.info("Fetching and analyzing global stock quotes...")
    stock_symbols = [s.strip().upper() for s in symbols.split(',') if s.strip()]
    brief_data['stock_quotes_analysis'] = []
    
    stock_analysis_text = "" # New variable to build concise text for LLM
    for symbol in stock_symbols:
        quote = await _call_agent(API_AGENT_URL, f"quote/{symbol}")
        if quote:
            analysis = await _call_agent(ANALYTICS_AGENT_URL, "analyze_global_quote", method="POST", json_data=quote)
            if analysis:
                brief_data['stock_quotes_analysis'].append(analysis)
                stock_analysis_text += f"- {analysis['summary']}\n" # Use the summary from analytics agent
                logging.info(f"Analyzed quote for {symbol}.")
            else:
                logging.warning(f"Failed to analyze quote for {symbol}.")
        else:
            logging.warning(f"Failed to fetch quote for {symbol}.")
    
    if not stock_analysis_text:
        stock_analysis_text = "No real-time stock data available or fetched for analysis."


    # --- 2. Get Financial News and Summarize ---
    logging.info("Fetching and summarizing financial news...")
    all_news_articles = [] # This list will collect ALL fetched articles
    
    # Fetch news by tickers
    if stock_symbols:
        news_response = await _call_agent(
            API_AGENT_URL, 
            "news", 
            params={"tickers": ",".join(stock_symbols), "limit": news_limit}
        )
        if news_response and isinstance(news_response, dict) and "articles" in news_response:
            ticker_news_articles = news_response.get("articles", [])
            if not isinstance(ticker_news_articles, list):
                logging.error(f"API Agent returned non-list for ticker articles: {type(ticker_news_articles)}")
                ticker_news_articles = []
            all_news_articles.extend(ticker_news_articles)
        else:
            logging.warning("No news articles fetched from API agent by tickers or malformed response.")

    # Fetch news by topics
    if news_topics:
        topics_list = [t.strip() for t in news_topics.split(',') if t.strip()]
        news_response = await _call_agent(
            API_AGENT_URL, 
            "news", 
            params={"topics": ",".join(topics_list), "limit": news_limit}
        )
        if news_response and isinstance(news_response, dict) and "articles" in news_response:
            topic_news_articles = news_response.get("articles", [])
            if not isinstance(topic_news_articles, list):
                logging.error(f"API Agent returned non-list for topic articles: {type(topic_news_articles)}")
                topic_news_articles = []
            all_news_articles.extend(topic_news_articles) # Correct: just extend, no inner deduplication here
        else:
            logging.warning("No news articles fetched from API agent by topics or malformed response.")


    # --- Deduplicate news articles based on URL (SINGLE, CORRECT BLOCK) ---
    unique_news_articles = []
    existing_urls = set()
    for article in all_news_articles:
        if isinstance(article, dict) and article.get('url'):
            url = article['url']
            if url not in existing_urls:
                unique_news_articles.append(article)
                existing_urls.add(url)
        elif not isinstance(article, dict):
            logging.warning(f"Skipping non-dictionary article during deduplication: {article}")
        else: # article is a dict but doesn't have 'url'
            logging.warning(f"Skipping article without URL during deduplication: {article.get('title', 'Untitled')}")


    news_summary_text = "" # New variable to build concise text for LLM
    # Initialize news_summary_response (your previous fix for UnboundLocalError)
    news_summary_response = {}

    if unique_news_articles:
        news_summary_analysis = await _call_agent(ANALYTICS_AGENT_URL, "summarize_news_articles", method="POST", json_data=unique_news_articles)
        if news_summary_analysis:
            brief_data['news_summary'] = news_summary_analysis
            news_summary_text = news_summary_analysis.get('summary', 'No detailed news summary available.')
            logging.info(f"Summarized {news_summary_analysis.get('total_articles', 0)} news articles.")
        else:
            logging.warning("Failed to summarize news articles.")
            news_summary_text = "Failed to generate a concise news summary."
    else:
        brief_data['news_summary'] = {"total_articles": 0, "summary": "No relevant news found from API agent."}
        news_summary_text = "No relevant news found for today's brief."
        logging.warning("No news articles fetched from API agent.")


    # --- 3. (Optional) Get additional data via scraping or RAG for a full brief ---
    # ... (Keep this section as a placeholder for future expansion if needed) ...

    # --- 4. Synthesize with LLM ---
    logging.info("Synthesizing brief with LLM...")
    prompt_template = PromptTemplate.from_template("""
        You are a financial analyst generating a concise and informative morning market brief.
        **Avoid repetition.** Focus on delivering key insights clearly.

        Here is the financial data analysis and news summary:

        --- Stock Market Overview ---
        {financial_data_summary}

        --- Key News Headlines & Sentiment ---
        {news_summary_text}

        --- Generate Market Brief ---
        Based on the information above, provide a morning market brief.
        Start with an overall market sentiment. Then, discuss major stock movements and key news.
        Ensure clarity, conciseness, and professionalism.

        Morning Market Brief:
    """)

    # Prepare data for LLM
    llm_context = {
        "financial_data_summary": stock_analysis_text, # Use the human-readable summary
        "news_summary_text": news_summary_text, # Use the human-readable summary
    }

    try:
        final_prompt = prompt_template.format(**llm_context)
        llm_response = llm_pipeline.invoke(final_prompt)
        generated_brief = llm_response.strip()

        logging.info("Market brief generated successfully by LLM.")
        return {
            "status": "success",
            "brief": generated_brief,
            "raw_data_used": brief_data
        }
    except Exception as e:
        logging.error(f"Error during LLM generation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during LLM brief generation: {e}"
        )