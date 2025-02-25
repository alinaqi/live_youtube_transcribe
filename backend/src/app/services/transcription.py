"""
Service for audio transcription using Deepgram.
"""
import io
import logging
import asyncio
from typing import AsyncGenerator, BinaryIO, List, Optional, Union, Dict, Any
from deepgram import Deepgram

from app.core.config import settings
from app.models import (
    LanguageCode,
    TranscriptionSegment,
    TranscriptionResponse,
)

logger = logging.getLogger(__name__)

class TranscriptionService:
    """
    Service for audio transcription using Deepgram API.
    """
    
    def __init__(self):
        """Initialize the Deepgram client with API key."""
        self.client = Deepgram(settings.DEEPGRAM_API_KEY)
        logger.info("Initialized Deepgram transcription service")
        
    async def transcribe_audio(
        self, 
        audio_stream: Union[BinaryIO, bytes, io.BytesIO],
        language: Optional[LanguageCode] = LanguageCode.ENGLISH,
    ) -> TranscriptionResponse:
        """
        Transcribe audio using Deepgram.
        
        Args:
            audio_stream: Binary audio data
            language: Language code for transcription
            
        Returns:
            TranscriptionResponse with segments and full text
        """
        try:
            # Configure Deepgram options
            options = {
                "smart_format": True,
                "diarize": True,
                "language": language,
                "model": "nova-2",
                "punctuate": True,
                "utterances": True,
            }
            
            # Process with Deepgram
            if isinstance(audio_stream, io.BytesIO):
                audio_data = audio_stream.getvalue()
            elif isinstance(audio_stream, bytes):
                audio_data = audio_stream
            else:
                audio_data = audio_stream.read()
                
            # Use the appropriate method for the Deepgram SDK v2.12.0
            response = await self.client.transcription.prerecorded(
                audio_data, options
            )
            
            # Extract transcription data
            segments = []
            full_text = ""
            
            if response and 'results' in response:
                # Adapting to the v2.12.0 response format
                if 'utterances' in response['results']:
                    for utterance in response['results']['utterances']:
                        segments.append(
                            TranscriptionSegment(
                                start=utterance['start'],
                                end=utterance['end'],
                                text=utterance['transcript'],
                            )
                        )
                
                full_text = " ".join([s.text for s in segments])
                
            return TranscriptionResponse(
                segments=segments,
                full_text=full_text or "",
                language=language,
            )
            
        except Exception as e:
            logger.exception(f"Deepgram transcription error: {str(e)}")
            raise
            
    async def stream_transcription(
        self,
        audio_stream: Union[BinaryIO, bytes, io.BytesIO],
        language: Optional[LanguageCode] = LanguageCode.ENGLISH,
    ) -> AsyncGenerator[TranscriptionResponse, None]:
        """
        Stream audio transcription for real-time processing.
        
        Args:
            audio_stream: Binary audio data
            language: Language code for transcription
            
        Yields:
            TranscriptionResponse objects as they become available
        """
        try:
            # For real streaming, we would use Deepgram's WebSocket connection.
            # For this example, we'll simulate streaming by chunking the audio
            # and processing it in segments.
            
            # Read the entire audio stream
            if isinstance(audio_stream, io.BytesIO):
                audio_data = audio_stream.getvalue()
            elif isinstance(audio_stream, bytes):
                audio_data = audio_stream
            else:
                audio_data = audio_stream.read()
            
            # Simulate streaming by processing the audio in chunks
            # In a real implementation, this would be a WebSocket connection
            chunk_size = len(audio_data) // 10  # Divide into 10 chunks
            
            for i in range(10):
                start_idx = i * chunk_size
                end_idx = start_idx + chunk_size if i < 9 else len(audio_data)
                chunk = audio_data[start_idx:end_idx]
                
                # Process the chunk with v2.12.0 API
                options = {
                    "smart_format": True,
                    "language": language,
                    "model": "nova-2",
                    "punctuate": True,
                }
                
                response = await self.client.transcription.prerecorded(
                    chunk, options
                )
                
                # Extract and yield results adapted for v2.12.0
                if response and 'results' in response:
                    # Check if channels data is available
                    if 'channels' in response['results'] and len(response['results']['channels']) > 0:
                        # Get alternatives from the first channel
                        alternatives = response['results']['channels'][0]['alternatives']
                        if alternatives and len(alternatives) > 0:
                            # Check if paragraphs are available
                            if 'paragraphs' in alternatives[0] and 'paragraphs' in alternatives[0]['paragraphs']:
                                for para in alternatives[0]['paragraphs']['paragraphs']:
                                    segments = []
                                    
                                    # Process sentences within paragraphs
                                    if 'sentences' in para:
                                        for sentence in para['sentences']:
                                            segments.append(
                                                TranscriptionSegment(
                                                    start=sentence['start'],
                                                    end=sentence['end'],
                                                    text=sentence['text'],
                                                )
                                            )
                                        
                                    if segments:
                                        full_text = " ".join([s.text for s in segments])
                                        yield TranscriptionResponse(
                                            segments=segments,
                                            full_text=full_text,
                                            language=language,
                                        )
                
                # Sleep to simulate real-time processing
                await asyncio.sleep(0.2)
                
        except Exception as e:
            logger.exception(f"Deepgram streaming error: {str(e)}")
            raise

# Singleton instance
transcription_service = TranscriptionService() 