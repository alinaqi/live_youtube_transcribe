"""
Server startup script for the YouTube Translation API.
"""
import logging
import uvicorn

from app.core.config import settings

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO if settings.DEBUG else logging.WARNING,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        workers=1,
    ) 