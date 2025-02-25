import os
import threading
import httpx
import yt_dlp
from queue import Queue, Empty
from pathlib import Path
from time import sleep
import time

from pydub import AudioSegment
from pydub.playback import play

from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions

# Set your API keys
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY") 
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # Ensure this is set in your environment

# Configure OpenAI client using the provided example code
from openai import OpenAI
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Function to extract a direct audio URL from a YouTube link
def get_youtube_audio_url(youtube_url: str) -> str:
    ydl_opts = {'format': 'bestaudio/best', 'quiet': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=False)
        return info['url']

# Example YouTube link; update as desired.
youtube_link = "https://www.youtube.com/watch?v=Z39OR2zj_x8"
URL = get_youtube_audio_url(youtube_link)

# Create a thread-safe queues for different stages of processing
transcript_buffer = Queue()  # For collecting transcript segments
translation_queue = Queue()  # For translated segments to be synthesized
audio_queue = Queue()        # For audio segments ready to be played

# Buffer control variables
BUFFER_TIME = 3.0  # seconds to buffer transcript segments
buffer_lock = threading.Lock()
buffer_content = ""
last_segment_time = 0

def buffer_processor():
    """
    Worker that processes the transcript buffer and sends complete thoughts for translation
    """
    global buffer_content, last_segment_time
    
    while True:
        try:
            # Get new transcript segment
            transcript, timestamp = transcript_buffer.get(timeout=0.5)
            
            # Add to buffer
            with buffer_lock:
                if buffer_content:
                    buffer_content += " " + transcript
                else:
                    buffer_content = transcript
                last_segment_time = timestamp
            
            # Check if we should process the buffer (if enough time has passed or buffer is getting large)
            current_time = time.time()
            with buffer_lock:
                buffer_age = current_time - last_segment_time
                should_process = buffer_age >= BUFFER_TIME or len(buffer_content) > 150
                
                if should_process and buffer_content.strip():
                    content_to_process = buffer_content
                    buffer_content = ""
                    translation_queue.put(content_to_process)
            
            transcript_buffer.task_done()
            
        except Empty:
            # If no new segments, check if buffer needs processing due to time
            current_time = time.time()
            with buffer_lock:
                buffer_age = current_time - last_segment_time
                if buffer_age >= BUFFER_TIME and buffer_content.strip():
                    content_to_process = buffer_content
                    buffer_content = ""
                    translation_queue.put(content_to_process)
            
            # Short sleep to prevent CPU spinning
            sleep(0.1)

def translation_worker():
    """
    Worker thread function that processes buffered transcript texts:
    translates them and queues for speech synthesis.
    """
    while True:
        try:
            # Wait for a transcript text
            transcript = translation_queue.get(timeout=1)
        except Empty:
            continue

        try:
            # --- Translation using OpenAI GPT-3.5-turbo ---
            translation_response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "developer", "content": "You are a language translator. Translate the following text to English:"},
                    {"role": "user", "content": transcript}
                ]
            )
            translated_text = translation_response.choices[0].message.content.strip()
            print(f"Translated text: {translated_text}")
            
            # --- Text-to-Speech using OpenAI TTS endpoint ---
            speech_file_path = Path(f"speech_{int(time.time()*1000)}.mp3")
            tts_response = openai_client.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=translated_text,
            )
            tts_response.stream_to_file(speech_file_path)
            
            # Load audio and add to playback queue
            audio = AudioSegment.from_file(speech_file_path, format="mp3")
            audio_queue.put(audio)
            
            # Clean up temp file
            try:
                os.remove(speech_file_path)
            except:
                pass
                
        except Exception as e:
            print(f"Processing error: {e}")

        # Mark this item as processed
        translation_queue.task_done()

def audio_playback_worker():
    """
    Worker thread that handles continuous audio playback from the queue.
    """
    while True:
        try:
            # Get audio segment to play
            audio = audio_queue.get(timeout=1)
            # Play the audio
            play(audio)
            audio_queue.task_done()
        except Empty:
            # No audio to play, continue checking
            sleep(0.1)
        except Exception as e:
            print(f"Playback error: {e}")
            audio_queue.task_done()

# Start the worker threads
buffer_thread = threading.Thread(target=buffer_processor, daemon=True)
buffer_thread.start()

translation_thread = threading.Thread(target=translation_worker, daemon=True)
translation_thread.start()

playback_thread = threading.Thread(target=audio_playback_worker, daemon=True)
playback_thread.start()

def on_message(self, result, **kwargs):
    # Extract the transcript text from Deepgram's result
    transcript = result.channel.alternatives[0].transcript
    if not transcript.strip():
        return
    
    print(f"Received transcript: {transcript}")
    # Put the transcript text on the buffer queue with current timestamp
    transcript_buffer.put((transcript, time.time()))

def main():
    try:
        # Initialize Deepgram client (legacy interface)
        deepgram = DeepgramClient(DEEPGRAM_API_KEY)
        dg_connection = deepgram.listen.live.v('1')

        # Register the on_message callback
        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)

        # Create connection options (example: using German as source language)
        options = LiveOptions(smart_format=True, model="nova-2", language="de-DE")
        dg_connection.start(options)

        # Use a lock and flag to manage graceful exit of the streaming thread
        lock_exit = threading.Lock()
        exit_flag = False

        def stream_thread():
            # Stream audio data from the YouTube audio URL to Deepgram
            with httpx.stream('GET', URL) as r:
                for data in r.iter_bytes():
                    lock_exit.acquire()
                    if exit_flag:
                        lock_exit.release()
                        break
                    lock_exit.release()
                    dg_connection.send(data)
                    sleep(0.01)  # Slight delay to avoid overwhelming the connection

        streamer = threading.Thread(target=stream_thread)
        streamer.start()

        input('Press Enter to stop transcription...\n')
        lock_exit.acquire()
        exit_flag = True
        lock_exit.release()
        streamer.join()

        dg_connection.finish()
        print('Finished streaming and transcription.')

        # Wait for all queues to be fully processed before exiting
        transcript_buffer.join()
        translation_queue.join()
        audio_queue.join()

    except Exception as e:
        print(f"Could not open socket: {e}")
        return

if __name__ == '__main__':
    main()
