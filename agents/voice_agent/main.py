from fastapi import FastAPI, HTTPException, status, Response
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging
import requests
from gtts import gTTS # Text-to-Speech library
import io # To handle audio in memory
import os # Import os for file operations
import asyncio # Import asyncio for running async functions manually

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI(
    title="Voice Agent",
    description="Handles speech-to-text, interacts with LLM, and performs text-to-speech.",
    version="1.0.0"
)

# --- Configuration for other Agents (adjust ports if necessary) ---
LLM_AGENT_URL = "http://127.0.0.1:8004" # Your LLM Agent URL 

# --- Pydantic Models ---
class TextInput(BaseModel):
    text: str
    symbols: Optional[str] = "SPY,QQQ,^IXIC,^DJI,AAPL,MSFT,NVDA,GOOGL,TSLA,AMZN"
    news_topics: Optional[str] = "earnings,technology,markets,economy"
    news_limit: int = 10

# --- Helper to call other internal FastAPI agents ---
async def _call_agent(agent_url: str, endpoint: str, method: str = "GET", params: Optional[Dict] = None, json_data: Optional[Dict] = None) -> Optional[Any]:
    url = f"{agent_url}/{endpoint}"
    logging.info(f"Calling {method} {url} with params: {params}, data: {json_data}")
    try:
        if method == "GET":
            response = requests.get(url, params=params, timeout=60)
        elif method == "POST":
            response = requests.post(url, params=params, json=json_data, timeout=60)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to call agent {agent_url} at {url}: {e}", exc_info=True)
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred while calling agent {agent_url}: {e}", exc_info=True)
        return None

# --- Routes ---
@app.get("/")
async def root():
    print("🔥 API has restarted successfully 🔥")
    return {"message": "LLM Market Brief Agent is running. Use /docs for API documentation."}


@app.post("/process_text_and_respond_with_speech", response_class=Response)
async def process_text_and_respond_with_speech(input_data: TextInput):
    """
    Receives text, sends it to the LLM agent to generate a brief,
    and converts the brief into speech.
    """
    logging.info(f"Received text input: '{input_data.text[:200]}...'")

    llm_response = await _call_agent(
        LLM_AGENT_URL,
        "generate_brief",
        method="POST",
        params={
            "symbols": input_data.symbols,
            "news_topics": input_data.news_topics,
            "news_limit": input_data.news_limit
        }
    )

    if llm_response and llm_response.get("status") == "success":
        brief_text = llm_response.get("brief", "I could not generate a brief.")
        logging.info("Successfully received brief from LLM agent.")
    else:
        brief_text = "I'm sorry, I encountered an issue generating the market brief. Please try again later."
        logging.error(f"LLM Agent failed to generate brief: {llm_response}")
        # Optionally, raise an HTTPException here if you want to explicitly signal an error
        # raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=brief_text)

    # --- ADDED LOGGING AND FILE SAVING FOR TESTING ---
    logging.info(f"Brief text length for TTS: {len(brief_text)}")
    logging.info(f"Brief text for TTS (first 200 chars): '{brief_text[:200]}'")

    # Define a temporary filename for testing
    test_output_filename = "generated_brief_from_voice_agent.mp3"
    
    # Clean up previous test file if it exists
    if os.path.exists(test_output_filename):
        os.remove(test_output_filename)
        logging.info(f"Removed previous test file: {test_output_filename}")
    # --- END ADDED LOGGING AND FILE SAVING FOR TESTING ---

    # Convert text to speech
    try:
        tts = gTTS(text=brief_text, lang='en', slow=False)
        audio_buffer = io.BytesIO()
        
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0) # Rewind the buffer to the beginning

        logging.info("Text converted to speech successfully.")

        # --- SAVE TO FILE FOR MANUAL VERIFICATION ---
        # This part will save the audio buffer to a file every time the endpoint is called.
        # You can comment this out or remove it once you're confident it's working.
        try:
            with open(test_output_filename, "wb") as f:
                f.write(audio_buffer.getvalue())
            logging.info(f"Saved generated audio to '{test_output_filename}' for manual verification.")
            # Important: Rewind the buffer AGAIN after writing to file,
            # so it's ready to be sent in the HTTP response.
            audio_buffer.seek(0) 
        except Exception as file_save_error:
            logging.error(f"Failed to save test audio file: {file_save_error}", exc_info=True)
        # --- END SAVE TO FILE FOR MANUAL VERIFICATION ---
        
        # Return audio as a direct file response
        return Response(content=audio_buffer.getvalue(), media_type="audio/mpeg")

    except Exception as e:
        logging.error(f"Failed to convert text to speech: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate speech: {e}"
        )
    
# --- Manual Test Block (for local execution without uvicorn) ---
if __name__ == "__main__":
    logging.info("Running manual test for process_text_and_respond_with_speech...")

    # Create an instance of TextInput (the expected input for the function)
    test_input = TextInput(
        text="Tell me the latest market brief for Amazon and technology news.",
        symbols="AMZN",
        news_topics="technology",
        news_limit=5
    )

    # Use asyncio.run() to execute the async function
    # Note: When running manually like this, the _call_agent will still attempt to reach
    # the LLM_AGENT_URL (http://127.0.0.1:8000). So, your LLM Agent still needs to be running.
    asyncio.run(process_text_and_respond_with_speech(test_input))
    logging.info("Manual test finished. Check 'generated_brief_from_voice_agent.mp3' in this directory.")

# --- (Optional) Speech-to-Text Endpoint Placeholder ---
# This would require an STT library like SpeechRecognition or directly integrating with
# an STT API (e.g., OpenAI Whisper API).
# @app.post("/transcribe_audio")
# async def transcribe_audio(audio_file: UploadFile = File(...)):
#     """
#     Receives an audio file and transcribes it to text.
#     (Requires STT integration)
#     """
#     try:
#         # Example using a hypothetical STT model:
#         # audio_bytes = await audio_file.read()
#         # transcribed_text = my_stt_model.transcribe(audio_bytes)
#         # return {"transcribed_text": transcribed_text}
#         raise NotImplementedError("Speech-to-Text functionality is not implemented in this template.")
#     except Exception as e:
#         logging.error(f"Error during audio transcription: {e}", exc_info=True)
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error during audio transcription: {e}")