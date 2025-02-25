"""
Schema definitions for API input and output models.
"""
from enum import Enum
from typing import Dict, List, Optional, Union
from pydantic import BaseModel, Field, HttpUrl


class LanguageCode(str, Enum):
    """
    Supported language codes for translation.
    """
    ENGLISH = "en"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"
    ITALIAN = "it"
    PORTUGUESE = "pt"
    RUSSIAN = "ru"
    JAPANESE = "ja"
    CHINESE = "zh"
    KOREAN = "ko"
    ARABIC = "ar"
    HINDI = "hi"


class TranscriptionRequest(BaseModel):
    """
    Request model for transcription.
    """
    youtube_url: str = Field(..., description="YouTube video URL to transcribe")
    language: Optional[LanguageCode] = Field(
        default=LanguageCode.ENGLISH,
        description="Source language of the video"
    )


class TranslationRequest(BaseModel):
    """
    Request model for translation.
    """
    text: str = Field(..., description="Text to translate")
    source_language: Optional[LanguageCode] = Field(
        default=LanguageCode.ENGLISH,
        description="Source language of the text"
    )
    target_language: LanguageCode = Field(
        ..., 
        description="Target language for translation"
    )


class TranscriptionSegment(BaseModel):
    """
    Model for a segment of transcribed text.
    """
    start: float = Field(..., description="Start time in seconds")
    end: float = Field(..., description="End time in seconds")
    text: str = Field(..., description="Transcribed text")


class TranscriptionResponse(BaseModel):
    """
    Response model for transcription results.
    """
    segments: List[TranscriptionSegment] = Field(
        default_factory=list,
        description="List of transcribed segments with timestamps"
    )
    full_text: str = Field(..., description="Complete transcribed text")
    language: LanguageCode = Field(..., description="Detected language")


class TranslationResponse(BaseModel):
    """
    Response model for translation results.
    """
    original_text: str = Field(..., description="Original text")
    translated_text: str = Field(..., description="Translated text")
    source_language: LanguageCode = Field(..., description="Source language")
    target_language: LanguageCode = Field(..., description="Target language")


class WebSocketMessage(BaseModel):
    """
    Model for WebSocket messages, used for real-time communication.
    """
    type: str = Field(..., description="Message type (e.g., 'transcription', 'translation')")
    data: Dict = Field(..., description="Message data")


class ErrorResponse(BaseModel):
    """
    Standardized error response model.
    """
    status: str = Field(default="error", description="Response status")
    message: str = Field(..., description="Error message")
    details: Optional[Dict] = Field(default=None, description="Additional error details") 