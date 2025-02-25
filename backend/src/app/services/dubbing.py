"""
Dubbing service for YouTube videos.
Handles extraction of audio from YouTube, transcription, translation, and text-to-speech.
"""
import os
import asyncio
import logging
import uuid
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import httpx
import yt_dlp
from pydub import AudioSegment
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions
from fastapi import HTTPException
from openai import OpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

# Global dict to track active dubbing jobs
active_jobs: Dict[str, Dict[str, Any]] = {}

class DubbingService:
    """Service for managing YouTube video dubbing."""
    
    def __init__(self):
        """Initialize the dubbing service."""
        self.deepgram_api_key = settings.DEEPGRAM_API_KEY
        self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.output_dir = Path(settings.MEDIA_DIR) / "dubbed"
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    async def start_dubbing_job(self, youtube_url: str, source_language: str = "de-DE", target_language: str = "en") -> str:
        """
        Start a new dubbing job for a YouTube video.
        
        Args:
            youtube_url: URL of the YouTube video
            source_language: Language code of the source video
            target_language: Language code to translate to
            
        Returns:
            job_id: Unique identifier for the dubbing job
        """
        # Generate a unique job ID
        job_id = str(uuid.uuid4())
        
        # Create job directory
        job_dir = self.output_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        
        # Store job details
        active_jobs[job_id] = {
            "id": job_id,
            "youtube_url": youtube_url,
            "source_language": source_language,
            "target_language": target_language,
            "status": "initializing",
            "created_at": time.time(),
            "progress": 0,
            "output_file": None,
            "error": None,
            "segments": []
        }
        
        # Start processing in the background
        asyncio.create_task(self._process_dubbing_job(job_id, youtube_url, source_language, target_language, job_dir))
        
        return job_id
    
    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get the status of a dubbing job.
        
        Args:
            job_id: The job ID to check
            
        Returns:
            Job status information
        """
        if job_id not in active_jobs:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        return active_jobs[job_id]
    
    async def _process_dubbing_job(self, job_id: str, youtube_url: str, source_language: str, target_language: str, job_dir: Path):
        """
        Process a dubbing job in the background.
        
        Args:
            job_id: The job ID
            youtube_url: URL of the YouTube video
            source_language: Language code of the source video
            target_language: Language code to translate to
            job_dir: Directory to store job files
        """
        try:
            # Update job status
            active_jobs[job_id]["status"] = "extracting_audio"
            
            # Extract audio URL
            audio_url = self._get_youtube_audio_url(youtube_url)
            
            # Initialize Deepgram client
            deepgram = DeepgramClient(self.deepgram_api_key)
            
            # Set up buffer and queues for processing
            buffer_content = ""
            transcript_segments = []
            translated_segments = []
            audio_segments = []
            
            # Create connection options
            options = LiveOptions(
                smart_format=True,
                model="nova-2",
                language=source_language
            )
            
            # Update job status
            active_jobs[job_id]["status"] = "transcribing"
            
            # Create a Deepgram connection
            dg_connection = deepgram.listen.live.v("1")
            
            # Define event handlers
            async def on_message(result):
                transcript = result.channel.alternatives[0].transcript
                if not transcript.strip():
                    return
                
                logger.info(f"Received transcript: {transcript}")
                transcript_segments.append(transcript)
                
                # Update buffer
                nonlocal buffer_content
                if buffer_content:
                    buffer_content += " " + transcript
                else:
                    buffer_content = transcript
                
                # Process buffer if it's large enough or enough time has passed
                if len(buffer_content) > 150:
                    content_to_process = buffer_content
                    buffer_content = ""
                    await self._translate_and_synthesize(
                        content_to_process,
                        job_id,
                        job_dir,
                        translated_segments,
                        audio_segments
                    )
            
            # Register event handlers
            dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
            
            # Start connection
            await dg_connection.start(options)
            
            # Stream audio to Deepgram
            async with httpx.AsyncClient() as client:
                async with client.stream("GET", audio_url) as response:
                    async for chunk in response.aiter_bytes():
                        await dg_connection.send(chunk)
                        await asyncio.sleep(0.01)  # Slight delay to prevent flooding
                        
                        # Check for job cancellation
                        if active_jobs[job_id].get("status") == "cancelled":
                            break
            
            # Finish the connection
            await dg_connection.finish()
            
            # Process any remaining buffer content
            if buffer_content.strip():
                await self._translate_and_synthesize(
                    buffer_content,
                    job_id,
                    job_dir,
                    translated_segments,
                    audio_segments
                )
            
            # Combine all audio segments
            output_file = job_dir / "dubbed_audio.mp3"
            if audio_segments:
                combined_audio = AudioSegment.empty()
                for segment_file in audio_segments:
                    audio = AudioSegment.from_file(segment_file, format="mp3")
                    combined_audio += audio
                
                combined_audio.export(output_file, format="mp3")
                
                # Update job status
                active_jobs[job_id]["status"] = "completed"
                active_jobs[job_id]["output_file"] = str(output_file)
                active_jobs[job_id]["progress"] = 100
            else:
                # No audio segments were created
                active_jobs[job_id]["status"] = "completed_no_audio"
                active_jobs[job_id]["error"] = "No audio segments were created"
                
        except Exception as e:
            logger.error(f"Error processing dubbing job {job_id}: {str(e)}")
            active_jobs[job_id]["status"] = "failed"
            active_jobs[job_id]["error"] = str(e)
    
    async def _translate_and_synthesize(
        self,
        text: str,
        job_id: str,
        job_dir: Path,
        translated_segments: List[str],
        audio_segments: List[Path]
    ):
        """
        Translate text and create synthesized speech.
        
        Args:
            text: Text to translate
            job_id: The job ID
            job_dir: Directory to store files
            translated_segments: List to store translated segments
            audio_segments: List to store audio segment files
        """
        try:
            # Translate the text
            translation_response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "developer", "content": "You are a language translator. Translate the following text to English:"},
                    {"role": "user", "content": text}
                ]
            )
            translated_text = translation_response.choices[0].message.content.strip()
            logger.info(f"Translated text: {translated_text}")
            
            # Add to segments
            translated_segments.append(translated_text)
            active_jobs[job_id]["segments"].append({
                "original": text,
                "translated": translated_text
            })
            
            # Generate speech
            segment_id = len(audio_segments) + 1
            speech_file_path = job_dir / f"segment_{segment_id}.mp3"
            
            tts_response = self.openai_client.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=translated_text,
            )
            
            with open(speech_file_path, "wb") as f:
                for chunk in tts_response.iter_bytes():
                    f.write(chunk)
            
            audio_segments.append(speech_file_path)
            
            # Update progress
            active_jobs[job_id]["progress"] = min(90, len(audio_segments) * 5)
            
        except Exception as e:
            logger.error(f"Error in translation/synthesis: {str(e)}")
            raise
    
    def _get_youtube_audio_url(self, youtube_url: str) -> str:
        """
        Extract a direct audio URL from a YouTube link.
        
        Args:
            youtube_url: URL of the YouTube video
            
        Returns:
            Direct URL to the audio stream
        """
        try:
            ydl_opts = {'format': 'bestaudio/best', 'quiet': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=False)
                return info['url']
        except Exception as e:
            logger.error(f"Error extracting YouTube audio URL: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Could not extract audio from YouTube URL: {str(e)}")

# Create a singleton instance
dubbing_service = DubbingService() 