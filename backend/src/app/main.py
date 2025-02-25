"""
Main application module for the YouTube Video Translation API.
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routes import transcription, translation, dubbing

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.VERSION,
    openapi_url=f"{settings.API_PREFIX}/openapi.json",
    docs_url=f"{settings.API_PREFIX}/docs",
    redoc_url=f"{settings.API_PREFIX}/redoc",
)

# Set up CORS
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include routers
app.include_router(
    transcription.router,
    prefix=f"{settings.API_PREFIX}/transcription",
    tags=["transcription"],
)
app.include_router(
    translation.router,
    prefix=f"{settings.API_PREFIX}/translation",
    tags=["translation"],
)
app.include_router(
    dubbing.router,
    prefix=f"{settings.API_PREFIX}/dubbing",
    tags=["dubbing"],
)

@app.get(f"{settings.API_PREFIX}/health")
async def health_check():
    """
    Health check endpoint to verify API is running.
    """
    return {"status": "ok"} 