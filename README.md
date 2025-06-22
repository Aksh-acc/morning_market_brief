Okay, here's a comprehensive `README.md` file for your "Morning Market Brief Dashboard" project. It covers the project's purpose, architecture, setup, running instructions, and usage.

-----

# 📈 Morning Market Brief Dashboard

## Project Overview

The Morning Market Brief Dashboard is an AI-powered application designed to provide users with quick, concise, and up-to-date summaries of market performance and financial news. It leverages a multi-agent architecture to collect data, analyze it, generate human-like briefs using a Large Language Model (LLM), and even convert the brief to speech. Additionally, it offers a dedicated news search feature to find specific articles by company or topic.

## Features

  * **Automated Market Brief Generation:** Generate a comprehensive market brief covering stock performance and general news.
  * **Customizable Briefs:** Specify stock symbols and news topics to tailor the brief content.
  * **Dedicated News Search:** Search for specific financial news articles by company tickers, keywords/topics, and date ranges.
  * **Text-to-Speech (TTS):** Listen to the generated market brief using a built-in voice agent.
  * **Modular Agent Architecture:** A scalable design comprising specialized FastAPI agents for distinct functionalities.
  * **Streamlit User Interface:** An intuitive web interface for easy interaction and display of information.

## Architecture

The project employs a modular, microservices-like architecture consisting of several independent FastAPI agents and a Streamlit frontend:

1.  **API Agent (Port 8001):**
      * **Role:** The primary gateway for external data.
      * **Functionality:** Fetches real-time stock quotes and financial news from Alpha Vantage API.
2.  **Analytics Agent (Port 8003):**
      * **Role:** Processes raw data into a more digestible format.
      * **Functionality:** Summarizes news articles, performs deduplication, and potentially calculates sentiment (though the current implementation focuses on summarization).
3.  **LLM Agent (Port 8000):**
      * **Role:** The "brain" of the operation, orchestrating data and generating the final brief.
      * **Functionality:** Calls the API Agent and Analytics Agent to gather and process data, then uses a Hugging Face pre-trained LLM (e.g., Flan-T5) to synthesize a coherent market brief.
4.  **Voice Agent (Port 8005):**
      * **Role:** Provides audio output of the generated brief.
      * **Functionality:** Converts text-to-speech using `gTTS` (Google Text-to-Speech).
5.  **Streamlit App (Port 8501 - default):**
      * **Role:** The user interface.
      * **Functionality:** Allows users to input parameters, trigger brief generation, search for news, and listen to the audio brief. It interacts with the LLM Agent and API Agent to fetch data.

### Interaction Flow:

  * **Brief Generation:** Streamlit App -\> LLM Agent -\> (API Agent, Analytics Agent) -\> LLM Agent -\> Streamlit App
  * **News Search:** Streamlit App -\> API Agent
  * **Text-to-Speech:** Streamlit App -\> Voice Agent

## Prerequisites

Before you begin, ensure you have the following installed:

  * **Python 3.9+** (recommended)
  * **pip** (Python package installer)

## Setup Instructions

Follow these steps to get the project up and running on your local machine:

### 1\. Clone the Repository (or set up project structure)

If you have a Git repository, clone it:

```bash
git clone <your-repository-url>
cd morning_market_brief
```

If you are setting up manually, ensure your project structure matches:

```
morning_market_brief/
├── agents/
│   ├── api_agent/
│   │   └── main.py
│   ├── analytics_agent/
│   │   └── main.py
│   ├── llm_agent/
│   │   └── main.py
│   └── voice_agent/
│       └── main.py
├── streamlit_app/
│   └── app.py
├── .env.example  # Create this file
├── requirements.txt # Create this file based on step 2
└── README.md
```

### 2\. Create a Virtual Environment & Install Dependencies

It's highly recommended to use a virtual environment to manage project dependencies.

```bash
# Navigate to the project root directory
cd morning_market_brief

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows:
.\venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Create a requirements.txt file with necessary dependencies:
# Save this content into requirements.txt in your project root
cat <<EOF > requirements.txt
fastapi~=0.111.0
uvicorn[standard]~=0.30.0
requests~=2.32.0
python-dotenv~=1.0.0
streamlit~=1.36.0
langchain~=0.2.0
langchain-community~=0.2.0
langchain-huggingface~=0.0.3
transformers~=4.42.0
torch # Or torch-cpu, torch-cuda depending on your hardware
gTTS~=2.5.1
scikit-learn~=1.5.0 # For Analytics Agent
sentence-transformers~=2.7.0 # For Analytics Agent
EOF

# Install the dependencies
pip install -r requirements.txt
```

**Note on `torch`:** If you have a GPU, consider installing a CUDA-enabled version of `torch` for faster LLM inference (e.g., `pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121`). Otherwise, `pip install torch` will install the CPU version.

### 3\. Set Up Alpha Vantage API Key

The `API Agent` requires an Alpha Vantage API key to fetch financial data.

1.  Go to the [Alpha Vantage website](https://www.google.com/search?q=https://www.alphavantage.co/support/%23api-key) and get a free API key.
2.  In the root directory of your project (`morning_market_brief/`), create a file named `.env` (if it doesn't exist).
3.  Add your API key to this file:
    ```
    ALPHA_VANTAGE_API_KEY=YOUR_ALPHA_VANTAGE_API_KEY_HERE
    ```
    **Replace `YOUR_ALPHA_VANTAGE_API_KEY_HERE` with your actual key.**

### 4\. Ensure Correct Agent Configurations

Verify that the URLs for inter-agent communication are correctly set in each `main.py` file:

  * **`agents/llm_agent/main.py`**:
    ```python
    API_AGENT_URL = "http://127.0.0.1:8001"
    ANALYTICS_AGENT_URL = "http://127.0.0.1:8003"
    ```
  * **`agents/voice_agent/main.py`**:
    ```python
    LLM_AGENT_URL = "http://127.0.0.1:8000" # Not directly used by Streamlit, but for voice agent internal calls
    ```
  * **`streamlit_app/app.py`**:
    ```python
    LLM_AGENT_URL = "http://127.0.0.1:8000"
    VOICE_AGENT_URL = "http://127.0.0.1:8005"
    API_AGENT_URL = "http://127.0.0.1:8001"
    ```

## Running the Application

To run the full application, you need to start each agent and then the Streamlit app. It's recommended to use separate terminal windows for each agent so you can monitor their logs.

**Make sure your virtual environment is activated in each terminal window.**

### 1\. Start the API Agent

```bash
cd agents/api_agent
uvicorn main:app --reload --port 8001
```

### 2\. Start the Analytics Agent

```bash
cd agents/analytics_agent
uvicorn main:app --reload --port 8003
```

### 3\. Start the LLM Agent

This agent will download the LLM model (`google/flan-t5-base` by default) the first time it runs, which might take a few minutes depending on your internet speed.

```bash
cd agents/llm_agent
uvicorn main:app --reload --port 8000
```

### 4\. Start the Voice Agent

```bash
cd agents/voice_agent
uvicorn main:app --reload --port 8005
```

### 5\. Start the Streamlit Application

```bash
cd streamlit_app
streamlit run app.py
```

After running `streamlit run app.py`, your web browser should automatically open to the Streamlit dashboard (usually `http://localhost:8501`).

## Usage

### Generate Market Brief

1.  In the Streamlit app, navigate to the "Generate Today's Market Brief" section.
2.  Enter comma-separated stock symbols (e.g., `AAPL,MSFT,NVDA`) and/or news topics (e.g., `earnings,AI`).
3.  Adjust the "Max news articles per ticker/topic for brief" slider.
4.  Check "Generate a more comprehensive brief?" if you want a detailed summary.
5.  Click "Generate Brief".
6.  The brief will appear on the dashboard. If the Voice Agent is running, a "Listen to the Brief" audio player will also appear.

### Search for Specific News Articles

1.  Scroll down to the "Search for Specific News Articles" section.
2.  Enter company tickers (optional) and/or keywords/topics (optional).
3.  Select a "Start Date" and "End Date" for the news search.
4.  Adjust the "Max articles to fetch" slider.
5.  Click "Search News".
6.  A list of individual news articles with titles, summaries, and links will be displayed.

## Troubleshooting

  * **Agent not running:** Check the terminal window for the respective agent. Look for error messages. Ensure all dependencies are installed.
  * **"Could not connect to LLM Agent/API Agent":** Verify that the corresponding agent's terminal shows it's running on the correct port and that there are no network blockers.
  * **"Failed to decode JSON response":** This often means an agent returned a non-JSON response (e.g., an HTML error page or an empty response). Check the agent's terminal for errors.
  * **"ALPHA\_VANTAGE\_API\_KEY environment variable not set\!":** Ensure you have created the `.env` file in the project root and added your API key correctly, then restart the `API Agent`.
  * **Repetitive LLM Output:** If your generated brief is highly repetitive, consider upgrading the LLM model in `agents/llm_agent/main.py` from `google/flan-t5-small` to `google/flan-t5-base` or `google/flan-t5-large`. Remember to restart the LLM Agent after changing the model.

-----
