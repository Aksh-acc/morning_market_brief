# agents/analytics_agent/main.py

from fastapi import FastAPI, HTTPException, status
from typing import List, Dict, Any, Optional # Ensure 'Any' is imported
import logging
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI(
    title="Analytics Agent",
    description="Provides data analysis and summarization functionalities.",
    version="1.0.0"
)

@app.get("/")
async def root():
    return {"message": "Analytics Agent is running. Use /docs for API documentation."}

@app.post("/analyze_global_quote")
async def analyze_global_quote(quote: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyzes a global stock quote and provides a summary and sentiment.
    """
    try:
        symbol = quote.get("symbol", "N/A")
        # Ensure numeric values are floats for calculations
        price = float(quote.get("price", 0.0))
        change = float(quote.get("change", 0.0))
        change_percent_str = quote.get("change percent", "0.0%").replace('%', '')
        change_percent = float(change_percent_str)
        open_price = float(quote.get("open", 0.0))
        high = float(quote.get("high", 0.0))
        low = float(quote.get("low", 0.0))
        volume = int(quote.get("volume", 0))

        sentiment = "neutral"
        if change > 0:
            sentiment = "positive"
        elif change < 0:
            sentiment = "negative"

        summary = (
            f"{symbol} is currently trading at {price:.2f}. "
            f"It opened at {open_price:.2f}, with a daily high of {high:.2f} and a low of {low:.2f}. "
            f"The stock is {sentiment} today, {'up' if change > 0 else 'down' if change < 0 else 'unchanged'} by {abs(change):.2f} ({change_percent:.2f}%). "
            f"Trading volume is {volume:,}."
        )

        return {
            "symbol": symbol,
            "current_price": price,
            "change": change,
            "change_percent": change_percent,
            "sentiment": sentiment,
            "summary": summary,
            "raw_data": quote
        }
    except Exception as e:
        logging.error(f"Error analyzing global quote: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing quote: {e}"
        )


@app.post("/summarize_news_articles")
async def summarize_news_articles(articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Provides a basic summary and aggregation of a list of news articles.
    This is NOT an LLM-based summarization. It extracts key metadata.
    Expected `articles` is a list of dicts, each with 'title', 'summary', 'source', 'time_published',
    and potentially 'overall_sentiment_score', 'overall_sentiment_label', 'topics'.
    """
    if not articles:
        return {"total_articles": 0, "summary": "No articles provided."}

    total_articles = len(articles)
    sources = {}
    topics_count = {} 
    # Use direct sentiment labels if available, as they are often more nuanced than score ranges
    sentiments_by_label = {
        "Bullish": 0, "Somewhat-Bullish": 0, "Neutral": 0,
        "Somewhat-Bearish": 0, "Bearish": 0
    }
    
    # Track raw numeric scores for average if needed
    total_sentiment_score = 0
    articles_with_score = 0

    for article in articles:
        source = article.get('source', 'Unknown')
        sources[source] = sources.get(source, 0) + 1

        # Process sentiment
        overall_sentiment_label = article.get('overall_sentiment_label')
        overall_sentiment_score_str = article.get('overall_sentiment_score')

        if overall_sentiment_label in sentiments_by_label:
            sentiments_by_label[overall_sentiment_label] += 1
        
        try:
            score = float(overall_sentiment_score_str) if overall_sentiment_score_str is not None else 0.0
            total_sentiment_score += score
            articles_with_score += 1
        except (ValueError, TypeError):
            logging.warning(f"Could not convert sentiment score '{overall_sentiment_score_str}' to float for article: {article.get('title', 'Untitled')}")
            pass # Continue if conversion fails

        # Process topics
        article_topics = article.get('topics', [])
        for topic_obj in article_topics:
            topic_name = topic_obj.get('topic', 'Unknown Topic')
            topics_count[topic_name] = topics_count.get(topic_name, 0) + 1

    # Calculate average sentiment if scores were found
    average_sentiment_score = total_sentiment_score / articles_with_score if articles_with_score > 0 else 0.0
    
    # Construct a more readable summary string
    sentiment_parts = []
    for label, count in sentiments_by_label.items():
        if count > 0:
            sentiment_parts.append(f"{count} {label}")
    
    sentiment_summary = ", ".join(sentiment_parts) if sentiment_parts else "No clear sentiment detected."

    summary_text = (
        f"Analyzed {total_articles} news articles. "
        f"Key sources include: {', '.join([f'{s} ({c})' for s, c in sources.items()])}. "
        f"Overall sentiment distribution: {sentiment_summary}. "
    )
    
    if topics_count:
        sorted_topics = sorted(topics_count.items(), key=lambda item: item[1], reverse=True)[:3] # Top 3 topics
        summary_text += f"Top topics discussed: {', '.join([f'{t} ({c})' for t,c in sorted_topics])}."

    logging.info(f"Summarized {total_articles} news articles.")
    return {
        "total_articles": total_articles,
        "sources_distribution": sources,
        "topics_distribution": topics_count,
        "sentiment_distribution": sentiments_by_label, # Return the detailed sentiment counts
        "average_sentiment_score": average_sentiment_score, # Optional: include average score
        "summary": summary_text
    }