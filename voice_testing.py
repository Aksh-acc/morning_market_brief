# test_audio.py

from gtts import gTTS
import io
import os
import sys
import platform

print("--- gTTS Audio Test Script ---")

test_text_short = "Hello, this is a test audio from gTTS. Can you hear me now?"
test_text_long = """
The quick brown fox jumps over the lazy dog.
This is a slightly longer piece of text to test if longer outputs also work.
The market brief for today includes updates on Amazon, which is currently trading at 213.57.
It opened at 212.40, with a daily high of 213.87 and a low of 210.50.
The stock is showing positive movement, up by 5.66, which is a 0.00% change today.
"""

output_filename_short = "test_audio_short.mp3"
output_filename_long = "test_audio_long.mp3"

def generate_and_save_audio(text, filename):
    print(f"\nAttempting to generate audio for text (first 50 chars): '{text[:50]}...'")
    print(f"Saving to: {filename}")
    
    try:
        tts = gTTS(text=text, lang='en', slow=False)
        
        # Method 1: Save directly to a file (more common for gTTS basic use)
        tts.save(filename)
        print(f"Successfully saved audio to {filename}")
        
        # Method 2: Save to an in-memory buffer (what your FastAPI app does)
        audio_buffer = io.BytesIO()
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)
        
        # Verify buffer content (size)
        buffer_content = audio_buffer.getvalue()
        print(f"In-memory buffer size: {len(buffer_content)} bytes")
        
        # Optional: Save buffer to another file to compare
        buffer_output_filename = f"buffer_{filename}"
        with open(buffer_output_filename, "wb") as f:
            f.write(buffer_content)
        print(f"Successfully saved in-memory buffer to {buffer_output_filename} for verification.")

        # Try to play the saved file using default system player
        if os.path.exists(filename):
            print(f"Attempting to play {filename}...")
            if platform.system() == "Windows":
                os.startfile(filename) # Opens with default associated program
            elif platform.system() == "Darwin": # macOS
                os.system(f"afplay '{filename}'")
            elif platform.system() == "Linux":
                # Requires 'xdg-open' (often available) or specific player like 'aplay' or 'mpg123'
                os.system(f"xdg-open '{filename}'")
            else:
                print("Cannot automatically play audio on this OS. Please open the file manually.")
        else:
            print(f"Error: {filename} was not found after saving.")

    except Exception as e:
        print(f"Error generating or saving audio: {e}")
        print("Please ensure you have an active internet connection for gTTS.")
        print("Also, check if your system has all necessary codecs for MP3 playback.")

if __name__ == "__main__":
    # Test with a short text
    generate_and_save_audio(test_text_short, output_filename_short)

    print("\n--- Testing with a longer text ---")
    # Test with a longer text (similar to your brief)
    generate_and_save_audio(test_text_long, output_filename_long)

    print("\n--- Audio Test Script Finished ---")
    print(f"Please check your current directory for '{output_filename_short}' and '{output_filename_long}'")
    print("and try playing them manually to confirm if gTTS produced valid audio.")