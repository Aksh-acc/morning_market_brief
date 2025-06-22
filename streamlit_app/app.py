# streamlit_app/app.py

import streamlit as st
import requests
import io
import base64
import json
from datetime import datetime, timedelta
# Configuration for your Voice Agent URL
# Make sure this matches the port your voice_agent is running on (e.g., 8005)
VOICE_AGENT_URL = "http://127.0.0.1:8005" 
LLM_AGENT_URL = "http://127.0.0.1:8004"  
API_AGENT_URL = "http://127.0.0.1:8001"
st.set_page_config(
    page_title="Morning Market Brief",
    page_icon="🎙️",
    layout="centered"
)

st.title("🎙️ Morning Market Brief Generator")
st.markdown("Enter your query to get an audio market brief.")

# --- User Inputs ---
user_query = st.text_area(
    "Your Query:",
    "Tell me the latest market brief for tech stocks and general economy news.",
    height=100,
    help="e.g., 'Give me a brief on Amazon and the latest tech news.' or 'Summarize today's market for major indices.'"
)

col1, col2 = st.columns(2)

with col1:
    symbols = st.text_input(
        "Stock Symbols (comma-separated):",
        "AAPL,MSFT,NVDA,GOOGL,TSLA,AMZN",
        help="e.g., 'AAPL,MSFT,GOOGL'. Leave blank for general market data."
    )
with col2:
    news_topics = st.text_input(
        "News Topics (comma-separated):",
        "earnings,technology,markets,economy",
        help="e.g., 'AI,finance'. Leave blank for general news relevant to symbols."
    )

news_limit = st.slider(
    "Number of News Articles per Topic/Symbol:",
    min_value=1, max_value=20, value=10, step=1,
    help="Limits the number of news articles fetched for brevity."
)

# --- Generate Brief Button ---
if st.button("Generate Audio Brief", type="primary"):
    if not user_query:
        st.error("Please enter a query to generate the brief.")
    else:
        with st.spinner("Generating your market brief... This may take a moment."):
            try:
                # Prepare the data for the Voice Agent
                payload = {
                    "text": user_query,
                    "symbols": symbols,
                    "news_topics": news_topics,
                    "news_limit": news_limit
                }

                # Make the POST request to your Voice Agent
                response = requests.post(
                    f"{VOICE_AGENT_URL}/process_text_and_respond_with_speech",
                    json=payload,
                    timeout=120 # Increased timeout for potentially long brief generation
                )

                # Check if the request was successful
                if response.status_code == 200:
                    audio_bytes = response.content # Get the raw audio bytes
                    
                    if audio_bytes:
                        st.success("Brief generated successfully! Playing audio:")
                        st.audio(audio_bytes, format='audio/mpeg')
                        
                        # Optional: Provide a download link
                        st.download_button(
                            label="Download Audio Brief",
                            data=audio_bytes,
                            file_name="market_brief.mp3",
                            mime="audio/mpeg"
                        )
                    else:
                        st.warning("Received an empty audio response. The brief might be very short or there was an issue.")
                        st.info("Check your Voice Agent logs for more details.")

                elif response.status_code == 500:
                    st.error(f"Error from Voice Agent: {response.json().get('detail', 'Internal Server Error')}")
                    st.info("Please ensure all backend agents (API, Analytics, LLM, Voice) are running and check their logs for errors.")
                else:
                    st.error(f"Failed to generate brief. Status Code: {response.status_code}")
                    st.json(response.json()) # Display full JSON response for debugging

            except requests.exceptions.ConnectionError:
                st.error(f"Could not connect to the Voice Agent at {VOICE_AGENT_URL}.")
                st.info("Please ensure your Voice Agent is running and accessible.")
            except requests.exceptions.Timeout:
                st.error("The request to the Voice Agent timed out.")
                st.info("This can happen if the brief generation takes too long. Check agent logs.")
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")
                st.info("Please check your terminal where Streamlit is running for full traceback.")

st.markdown("---")
st.info("Ensure all backend agents (API, Analytics, LLM, Voice) are running before using this app.")
st.markdown("---")
st.header("🔍 Search for Specific News Articles")
with st.form("news_search_form"):
    st.markdown("**Enter criteria to search for news articles:**")
    search_tickers = st.text_input(
        "Company Tickers (comma-separated, optional):",
        key="search_tickers",
        help="e.g., MSFT,AMZN"
    )
    search_topics = st.text_input(
        "Keywords/Topics (comma-separated, optional):",
        key="search_topics",
        help="e.g., AI,earnings report,interest rates"
    )
    
    # Date range inputs
    today = datetime.now()
    default_start_date = today - timedelta(days=7) # Last 7 days by default
    
    col1, col2 = st.columns(2)
    with col1:
        time_from_date = st.date_input("Start Date", value=default_start_date)
    with col2:
        time_to_date = st.date_input("End Date", value=today)

    search_limit = st.slider(
        "Max articles to fetch:",
        min_value=5, max_value=50, value=20, step=5,
        key="search_limit_news_search" # Unique key for this slider
    )
    
    search_button = st.form_submit_button("Search News")

if search_button:
    if not search_tickers and not search_topics:
        st.warning("Please enter at least one company ticker or news topic to search.")
    else:
        with st.spinner("Searching for news articles..."):
            try:
                # Format dates to YYYYMMDDTHHMM
                time_from_str = time_from_date.strftime("%Y%m%dT0000") # Start of the day
                time_to_str = time_to_date.strftime("%Y%m%dT2359") # End of the day

                params = {
                    "tickers": search_tickers if search_tickers else None, # Pass None if empty
                    "topics": search_topics if search_topics else None,   # Pass None if empty
                    "time_from": time_from_str,
                    "time_to": time_to_str,
                    "limit": search_limit
                }
                # Filter out None values from params to avoid sending empty strings for optional fields
                params_cleaned = {k: v for k, v in params.items() if v is not None}

                # Directly call the API Agent's /news endpoint
                news_response = requests.get(
                    f"{API_AGENT_URL}/news",
                    params=params_cleaned,
                    timeout=30 # News fetching usually faster than LLM generation
                )
                news_response.raise_for_status()
                news_data = news_response.json()

                st.markdown("### News Search Results:")
                
                if news_data.get("articles") and len(news_data["articles"]) > 0:
                    st.write(f"Found {news_data.get('items_count', len(news_data['articles']))} relevant articles.")
                    
                    for i, article in enumerate(news_data["articles"]):
                        st.markdown(f"**{i+1}. {article.get('title', 'No Title')}**")
                        if article.get('url'):
                            st.markdown(f"[Read more]({article['url']})")
                        if article.get('summary'):
                            st.write(article['summary'])
                        st.markdown("---") # Separator between articles
                else:
                    st.info("No relevant news articles found for your search criteria.")
                    if news_data.get("message"):
                        st.caption(f"Reason: {news_data['message']}")
                            
                # For debugging, show raw data from API Agent
                with st.expander("Show Raw Data from API Agent"):
                    st.json(news_data)

            except requests.exceptions.RequestException as e:
                st.error(f"Could not connect to API Agent for news search: {e}")
                st.info(f"Please ensure the API Agent is running on {API_AGENT_URL}.")
            except json.JSONDecodeError:
                st.error("Failed to decode JSON response from API Agent during news search.")
                st.info(f"Raw response: {news_response.text[:500]}...")