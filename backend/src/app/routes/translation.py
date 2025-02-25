"""
API routes for translation functionality.
"""
import logging
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.models import (
    TranslationRequest,
    TranslationResponse,
    ErrorResponse,
    LanguageCode,
)
from app.services.translation import translation_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/",
    response_model=TranslationResponse,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def translate_text(request: TranslationRequest):
    """
    Translate text from source language to target language.
    
    Args:
        request: TranslationRequest object with text and language parameters
        
    Returns:
        TranslationResponse with original and translated text
        
    Raises:
        HTTPException: If the translation fails
    """
    try:
        translation = await translation_service.translate_text(
            text=request.text,
            source_language=request.source_language,
            target_language=request.target_language,
        )
        
        return translation
    
    except ValueError as e:
        logger.error(f"Invalid translation request: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Translation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Translation failed: {str(e)}")


@router.websocket("/ws")
async def translation_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time translation.
    
    Establishes a WebSocket connection and streams translation results
    as transcription segments are received.
    """
    await websocket.accept()
    
    try:
        # Get initial parameters from client
        data = await websocket.receive_json()
        target_language = data.get("target_language")
        
        if not target_language:
            await websocket.send_json({
                "status": "error",
                "message": "Missing target language"
            })
            await websocket.close()
            return
        
        # Process incoming transcription segments
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") != "transcription":
                continue
                
            text = data.get("data", {}).get("text", "")
            source_language = data.get("data", {}).get("language", LanguageCode.ENGLISH)
            
            if not text:
                continue
                
            # Translate the segment
            translation = await translation_service.translate_text(
                text=text,
                source_language=source_language,
                target_language=target_language,
            )
            
            # Send back the translation
            await websocket.send_json({
                "status": "success",
                "type": "translation",
                "data": translation.dict()
            })
            
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except ValueError as e:
        logger.error(f"Invalid WebSocket request: {str(e)}")
        await websocket.send_json({
            "status": "error",
            "message": str(e)
        })
    except Exception as e:
        logger.exception(f"WebSocket error: {str(e)}")
        await websocket.send_json({
            "status": "error",
            "message": f"Translation error: {str(e)}"
        })
        await websocket.close() 