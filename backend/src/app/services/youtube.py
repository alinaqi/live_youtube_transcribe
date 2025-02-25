"""
Service for downloading and processing YouTube videos.
"""
import io
import re
import logging
import subprocess
import tempfile
from typing import BinaryIO, Optional, Tuple
import httpx

logger = logging.getLogger(__name__)

# Regular expression for extracting YouTube video IDs
YOUTUBE_ID_REGEX = r'(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'


async def extract_youtube_id(url: str) -> str:
    """
    Extract the YouTube video ID from a URL.
    
    Args:
        url: YouTube URL
        
    Returns:
        YouTube video ID
        
    Raises:
        ValueError: If the URL is invalid or doesn't contain a valid YouTube ID
    """
    match = re.search(YOUTUBE_ID_REGEX, url)
    
    if not match:
        raise ValueError(f"Invalid YouTube URL: {url}")
        
    return match.group(1)


async def extract_youtube_audio(url: str) -> io.BytesIO:
    """
    Extract audio from a YouTube video URL using ffmpeg.
    
    Args:
        url: YouTube URL
        
    Returns:
        BytesIO object containing the audio data
        
    Raises:
        ValueError: If the URL is invalid or audio extraction fails
    """
    try:
        # Extract the YouTube video ID
        video_id = await extract_youtube_id(url)
        logger.info(f"Extracted YouTube ID: {video_id}")
        
        # For this example, we'll use a temporary file approach with ffmpeg
        # In a production environment, you might want to use a more efficient method
        with tempfile.NamedTemporaryFile(suffix='.mp3') as temp_file:
            # Construct the YouTube URL
            yt_url = f"https://www.youtube.com/watch?v={video_id}"
            
            # Use ffmpeg to download and extract audio
            # Note: In a production environment, consider using yt-dlp or pytube
            # But for simplicity, we'll use ffmpeg directly
            command = [
                'ffmpeg',
                '-i', yt_url,  # Input URL
                '-vn',         # Disable video
                '-acodec', 'libmp3lame',  # Use MP3 codec
                '-ar', '44100',           # Audio sample rate
                '-ab', '192k',            # Audio bitrate
                '-y',                     # Overwrite output file
                temp_file.name            # Output file
            ]
            
            # Run the ffmpeg command
            process = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            
            if process.returncode != 0:
                logger.error(f"ffmpeg error: {process.stderr}")
                raise ValueError(f"Failed to extract audio from YouTube video: {process.stderr}")
                
            # Read the audio data
            temp_file.seek(0)
            audio_data = io.BytesIO(temp_file.read())
            
            return audio_data
            
    except subprocess.SubprocessError as e:
        logger.exception(f"ffmpeg subprocess error: {str(e)}")
        raise ValueError(f"Failed to process YouTube video: {str(e)}")
    except Exception as e:
        logger.exception(f"YouTube audio extraction error: {str(e)}")
        raise ValueError(f"Failed to extract audio from YouTube video: {str(e)}") 