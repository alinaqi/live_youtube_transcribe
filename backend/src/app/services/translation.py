"""
Service for text translation using OpenAI or other translation services.
"""
import logging
from typing import Optional
import openai

from app.core.config import settings
from app.models import (
    LanguageCode,
    TranslationResponse,
)

logger = logging.getLogger(__name__)

class TranslationService:
    """
    Service for translating text using OpenAI's API.
    """
    
    def __init__(self):
        """Initialize the translation service with API key."""
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        logger.info("Initialized translation service")
        
    async def translate_text(
        self,
        text: str,
        source_language: Optional[LanguageCode] = None,
        target_language: LanguageCode = LanguageCode.ENGLISH,
    ) -> TranslationResponse:
        """
        Translate text from source language to target language.
        
        Args:
            text: Text to translate
            source_language: Source language code (optional, auto-detect if None)
            target_language: Target language code
            
        Returns:
            TranslationResponse with original and translated text
        """
        if not text:
            return TranslationResponse(
                original_text="",
                translated_text="",
                source_language=source_language or LanguageCode.ENGLISH,
                target_language=target_language,
            )
            
        try:
            # Construct the prompt for translation
            prompt = f"Translate the following text"
            
            if source_language:
                source_name = source_language.name.capitalize()
                prompt += f" from {source_name}"
                
            target_name = target_language.name.capitalize()
            prompt += f" to {target_name}:\n\n{text}\n\nTranslation:"
            
            # Use OpenAI for translation
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a professional translator."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1024,
            )
            
            translated_text = response.choices[0].message.content.strip()
            
            return TranslationResponse(
                original_text=text,
                translated_text=translated_text,
                source_language=source_language or LanguageCode.ENGLISH,
                target_language=target_language,
            )
            
        except Exception as e:
            logger.exception(f"Translation error: {str(e)}")
            raise

# Singleton instance
translation_service = TranslationService() 