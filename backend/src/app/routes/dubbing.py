"""
API routes for YouTube video dubbing.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Path, Query, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, Any
import os
from pathlib import Path as FilePath

from app.services.dubbing import dubbing_service

router = APIRouter()

class DubbingRequest(BaseModel):
    """
    Request model for starting a dubbing job.
    """
    youtube_url: HttpUrl
    source_language: Optional[str] = "de-DE"  # Default to German
    target_language: Optional[str] = "en"     # Default to English

class DubbingResponse(BaseModel):
    """
    Response model for dubbing job info.
    """
    job_id: str
    status: str
    progress: int
    youtube_url: HttpUrl
    source_language: str
    target_language: str
    output_file: Optional[str] = None
    error: Optional[str] = None
    segments: List[Dict[str, str]] = []
    created_at: float

@router.post("/", response_model=DubbingResponse)
async def start_dubbing(request: DubbingRequest):
    """
    Start a new dubbing job for a YouTube video.
    
    Args:
        request: Dubbing request with YouTube URL and language options
        
    Returns:
        Job information including ID for status tracking
    """
    try:
        job_id = await dubbing_service.start_dubbing_job(
            str(request.youtube_url),
            request.source_language,
            request.target_language
        )
        
        # Get initial job status
        job_status = await dubbing_service.get_job_status(job_id)
        return job_status
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting dubbing job: {str(e)}")

@router.get("/{job_id}", response_model=DubbingResponse)
async def get_dubbing_status(job_id: str = Path(..., description="The ID of the dubbing job")):
    """
    Get status of a dubbing job.
    
    Args:
        job_id: ID of the dubbing job to check
        
    Returns:
        Current status of the dubbing job
    """
    try:
        return await dubbing_service.get_job_status(job_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting job status: {str(e)}")

@router.get("/{job_id}/audio")
async def get_dubbed_audio(job_id: str = Path(..., description="The ID of the dubbing job")):
    """
    Get the dubbed audio file for a completed job.
    
    Args:
        job_id: ID of the dubbing job
        
    Returns:
        Audio file as a streaming response
    """
    try:
        job_status = await dubbing_service.get_job_status(job_id)
        
        if job_status["status"] != "completed":
            raise HTTPException(
                status_code=400, 
                detail=f"Job is not complete. Current status: {job_status['status']}"
            )
            
        if not job_status["output_file"]:
            raise HTTPException(status_code=404, detail="No output file available")
            
        output_file = job_status["output_file"]
        if not os.path.exists(output_file):
            raise HTTPException(status_code=404, detail="Output file not found")
            
        return FileResponse(
            path=output_file,
            media_type="audio/mpeg",
            filename="dubbed_audio.mp3"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving audio file: {str(e)}")

@router.delete("/{job_id}")
async def cancel_dubbing_job(job_id: str = Path(..., description="The ID of the dubbing job")):
    """
    Cancel an in-progress dubbing job.
    
    Args:
        job_id: ID of the dubbing job to cancel
        
    Returns:
        Confirmation of cancellation
    """
    try:
        # Get current status
        job_status = await dubbing_service.get_job_status(job_id)
        
        # Only cancel if not already completed or failed
        if job_status["status"] not in ["completed", "failed"]:
            job_status["status"] = "cancelled"
            return {"message": f"Job {job_id} cancelled successfully"}
            
        return {"message": f"Job {job_id} is already in final state: {job_status['status']}"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cancelling job: {str(e)}") 