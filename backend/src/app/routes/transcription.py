"""
API routes for transcription functionality.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from app.models import (
    TranscriptionRequest,
    TranscriptionResponse,
    ErrorResponse,
    LanguageCode,
)
from app.services.transcription import transcription_service
from app.services.youtube import extract_youtube_audio

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/",
    response_model=TranscriptionResponse,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def transcribe_youtube_video(request: TranscriptionRequest):
    """
    Transcribe audio from a YouTube video URL.
    
    Args:
        request: TranscriptionRequest object containing YouTube URL and optional parameters
        
    Returns:
        TranscriptionResponse with timestamped segments and full text
        
    Raises:
        HTTPException: If the video cannot be processed or transcription fails
    """
    try:
        # Extract YouTube video ID from URL
        audio_stream = await extract_youtube_audio(request.youtube_url)
        
        # Process with Deepgram
        transcription = await transcription_service.transcribe_audio(
            audio_stream, 
            language=request.language
        )
        
        return transcription
    
    except ValueError as e:
        logger.error(f"Invalid request: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Transcription error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


@router.websocket("/ws")
async def transcription_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time transcription.
    
    Establishes a WebSocket connection and streams transcription results
    as the YouTube video plays.
    """
    await websocket.accept()
    
    try:
        # Get initial parameters from client
        data = await websocket.receive_json()
        youtube_url = data.get("youtube_url")
        language = data.get("language", LanguageCode.ENGLISH)
        
        if not youtube_url:
            await websocket.send_json({
                "status": "error",
                "message": "Missing YouTube URL"
            })
            await websocket.close()
            return
        
        # Start streaming transcription
        audio_stream = await extract_youtube_audio(youtube_url)
        
        async for result in transcription_service.stream_transcription(
            audio_stream, language=language
        ):
            await websocket.send_json({
                "status": "success",
                "type": "transcription",
                "data": result.dict()
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
            "message": f"Transcription error: {str(e)}"
        })
        await websocket.close() 