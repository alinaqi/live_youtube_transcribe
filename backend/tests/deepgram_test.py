from deepgram import DeepgramClient, DeepgramClientOptions, LiveTranscriptionEvents, LiveOptions
import httpx
import threading
import json
import os
import asyncio
import queue
import websockets
from websockets.sync.client import connect
import pyaudio
import yt_dlp
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Configuration - get API key from .env file
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
if not DEEPGRAM_API_KEY:
    print("Error: DEEPGRAM_API_KEY not found in .env file")
    sys.exit(1)

# Audio settings for playback
TIMEOUT = 0.050
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 48000
CHUNK = 8000

# Voice mapping for Deepgram TTS
VOICE_MAP = {
    "en": "aura-orion-en",  # English
    "es": "aura-stella-es",  # Spanish
    "de": "aura-wilhelm-de",  # German
    "fr": "aura-josephine-fr",  # French
    "hi": "aura-pratik-hi",  # Hindi
    "it": "aura-giorgia-it",  # Italian
    "ja": "aura-yuki-ja",  # Japanese
    "ko": "aura-jin-ko",  # Korean
    "pt": "aura-mateus-pt",  # Portuguese
    "zh": "aura-zhiyu-zh",  # Chinese
}

# Default to English if language not supported
def get_voice_for_language(language_code):
    return VOICE_MAP.get(language_code, "aura-orion-en")

# TTS API endpoint - will be set dynamically per language
# TTS_URL = f"wss://api.deepgram.com/v1/speak?encoding=linear16&sample_rate={RATE}&voice=aura-orion-en"

def get_youtube_audio_url(youtube_url: str) -> str:
    """Extract audio URL from a YouTube video link"""
    ydl_opts = {'format': 'bestaudio/best', 'quiet': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=False)
        # Get the best audio URL
        return info['url']

class Speaker:
    """Class to handle audio playback"""
    _audio: pyaudio.PyAudio
    _chunk: int
    _rate: int
    _format: int
    _channels: int
    _output_device_index: int

    _stream: pyaudio.Stream
    _thread: threading.Thread
    _queue: queue.Queue
    _exit: threading.Event

    def __init__(
        self,
        rate: int = RATE,
        chunk: int = CHUNK,
        channels: int = CHANNELS,
        output_device_index: int = None,
    ):
        self._exit = threading.Event()
        self._queue = queue.Queue()

        self._audio = pyaudio.PyAudio()
        self._chunk = chunk
        self._rate = rate
        self._format = FORMAT
        self._channels = channels
        self._output_device_index = output_device_index

    def start(self) -> bool:
        """Start the audio playback stream"""
        self._stream = self._audio.open(
            format=self._format,
            channels=self._channels,
            rate=self._rate,
            input=False,
            output=True,
            frames_per_buffer=self._chunk,
            output_device_index=self._output_device_index,
        )

        self._exit.clear()

        self._thread = threading.Thread(
            target=_play, args=(self._queue, self._stream, self._exit), daemon=True
        )
        self._thread.start()

        self._stream.start_stream()
        return True

    def stop(self):
        """Stop the audio playback stream"""
        self._exit.set()

        if self._stream is not None:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None

        self._thread.join()
        self._thread = None
        self._queue = None

    def play(self, data):
        """Add audio data to playback queue"""
        print(f"Received audio data of length: {len(data)} bytes")  # Debug log
        self._queue.put(data)

def _play(audio_out: queue.Queue, stream, stop):
    """Audio playback worker function"""
    while not stop.is_set():
        try:
            data = audio_out.get(True, TIMEOUT)
            print(f"Playing audio chunk of length: {len(data)} bytes")  # Debug log
            stream.write(data)
        except queue.Empty:
            # Silent timeout, keep looping
            pass
        except Exception as e:
            print(f"_play error: {e}")

class TranscribeSpeakPipeline:
    """Main class to handle transcription and text-to-speech pipeline"""
    def __init__(self, youtube_url, target_language="en"):
        self.youtube_url = youtube_url
        self.target_language = target_language
        self.audio_url = None
        self.dg_connection = None
        self.tts_socket = None
        self.speaker = None
        self.transcription_queue = queue.Queue()
        self.exit = threading.Event()
        self.lock_exit = threading.Lock()
        
        # Set appropriate voice for language
        self.voice = get_voice_for_language(target_language)
        self.tts_url = f"wss://api.deepgram.com/v1/speak?encoding=linear16&sample_rate={RATE}&voice={self.voice}"
    
    def setup(self):
        """Set up connections and resources"""
        # Extract audio URL from YouTube
        print(f"Extracting audio from YouTube: {self.youtube_url}")
        self.audio_url = get_youtube_audio_url(self.youtube_url)
        
        # Initialize Deepgram client for transcription
        deepgram = DeepgramClient(DEEPGRAM_API_KEY)
        self.dg_connection = deepgram.listen.live.v('1')
        
        # Initialize TTS connection
        print(f"Connecting to Deepgram TTS service with voice: {self.voice}")
        self.tts_socket = connect(
            self.tts_url, additional_headers={"Authorization": f"Token {DEEPGRAM_API_KEY}"}
        )
        
        # Initialize speaker for audio playback
        self.speaker = Speaker()
        self.speaker.start()
        
        # Set up transcription callback with proper closure
        pipeline = self  # Capture self in closure
        def on_transcription(dg_self, result, **kwargs):
            sentence = result.channel.alternatives[0].transcript
            if len(sentence) == 0:
                return
                
            print(f"Transcription: {sentence}")
            # Add transcription to queue for TTS
            pipeline.transcription_queue.put(sentence)
            
        self.dg_connection.on(LiveTranscriptionEvents.Transcript, on_transcription)
    
    async def tts_receiver(self):
        """Handle incoming TTS audio data"""
        try:
            while not self.exit.is_set():
                if self.tts_socket is None:
                    break

                message = self.tts_socket.recv()
                if message is None:
                    continue

                if isinstance(message, str):
                    print(f"TTS message: {message}")
                elif isinstance(message, bytes):
                    print(f"Received TTS audio data of length: {len(message)} bytes")  # Debug log
                    self.speaker.play(message)
        except Exception as e:
            print(f"TTS receiver error: {e}")
    
    def tts_sender(self):
        """Send transcribed text to TTS service"""
        try:
            while not self.exit.is_set():
                try:
                    text = self.transcription_queue.get(timeout=1.0)
                    if text:
                        print(f"Sending to TTS: {text}")
                        self.tts_socket.send(json.dumps({"type": "Speak", "text": text}))
                except queue.Empty:
                    # Timeout, continue loop
                    continue
                except Exception as e:
                    print(f"TTS sender error: {e}")
        except Exception as e:
            print(f"TTS sender thread error: {e}")
        finally:
            print("TTS sender thread exiting")
    
    def transcription_streamer(self):
        """Stream audio from YouTube to Deepgram for transcription"""
        try:
            options = LiveOptions(
                smart_format=True, 
                model="nova-2", 
                language=self.target_language,
                punctuate=True,
                interim_results=False
            )
            self.dg_connection.start(options)
            
            with httpx.stream('GET', self.audio_url) as r:
                for data in r.iter_bytes():
                    self.lock_exit.acquire()
                    if self.exit.is_set():
                        self.lock_exit.release()
                        break
                    self.lock_exit.release()

                    self.dg_connection.send(data)
                    
        except Exception as e:
            print(f"Transcription streamer error: {e}")
        finally:
            print("Transcription streamer exiting")
    
    def start(self):
        """Start the full pipeline"""
        self.setup()
        
        # Start TTS receiver thread
        self.tts_receiver_thread = threading.Thread(
            target=asyncio.run, 
            args=(self.tts_receiver(),)
        )
        self.tts_receiver_thread.start()
        
        # Start TTS sender thread
        self.tts_sender_thread = threading.Thread(
            target=self.tts_sender
        )
        self.tts_sender_thread.start()
        
        # Start transcription streamer thread
        self.transcription_thread = threading.Thread(
            target=self.transcription_streamer
        )
        self.transcription_thread.start()
        
        # Wait for user to stop
        print("\nListening and speaking... Press Enter to stop\n")
        input()
        
        # Clean up
        self.stop()
    
    def stop(self):
        """Stop all threads and clean up resources"""
        print("Shutting down...")
        self.exit.set()
        
        # Close transcription connection
        if self.dg_connection:
            self.dg_connection.finish()
            
        # Close TTS connection
        if self.tts_socket:
            try:
                self.tts_socket.send(json.dumps({"type": "Flush"}))
                self.tts_socket.send(json.dumps({"type": "Close"}))
                self.tts_socket.close()
            except:
                pass
                
        # Stop audio playback
        if self.speaker:
            self.speaker.stop()
            
        # Wait for transcription thread to complete
        if hasattr(self, 'transcription_thread'):
            self.transcription_thread.join()
            
        # TTS sender thread can be joined directly
        if hasattr(self, 'tts_sender_thread'):
            self.tts_sender_thread.join()

        # The TTS receiver thread is using asyncio.run so it might not be directly joinable
        # Force exit instead
        print("Pipeline stopped")

def main():
    # Show usage if help is requested
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help']:
        print("Usage: python deepgram_test.py [YOUTUBE_URL] [TARGET_LANGUAGE]")
        print("\nOptions:")
        print("  YOUTUBE_URL     : URL of the YouTube video to transcribe")
        print("  TARGET_LANGUAGE : Language code (en, es, fr, de, etc.)")
        print("\nSupported languages:")
        for lang, voice in VOICE_MAP.items():
            print(f"  {lang} - {voice}")
        sys.exit(0)
        
    # YouTube video to transcribe and speak
    default_youtube_link = "https://www.youtube.com/watch?v=Osl4NgAXvRk"
    default_language = "en"
    
    # Process command line arguments
    youtube_link = sys.argv[1] if len(sys.argv) > 1 else default_youtube_link
    target_language = sys.argv[2] if len(sys.argv) > 2 else default_language
    
    print(f"Using YouTube video: {youtube_link}")
    print(f"Target language: {target_language}")
    
    # Create and start the pipeline
    pipeline = TranscribeSpeakPipeline(youtube_link, target_language=target_language)
    pipeline.start()

if __name__ == '__main__':
    main()