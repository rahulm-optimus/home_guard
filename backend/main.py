"""
Main Application Entry Point
FastAPI application factory and configuration
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from app.core.config import settings
from app.core.middleware import error_handling_middleware
from app.api.v1.router import api_router
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_application() -> FastAPI:
    """
    Application factory pattern
    Creates and configures the FastAPI application
    
    Returns:
        Configured FastAPI application instance
    """
    app = FastAPI(
        title=settings.APP_NAME,
        description=settings.APP_DESCRIPTION,
        version=settings.APP_VERSION,
        debug=settings.DEBUG
    )
    
    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Error Handling Middleware
    app.middleware("http")(error_handling_middleware)
    

    # Include API routers
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    
    logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION} initialized")
    
    return app


# Create the app instance
app = create_application()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",  # Must be string for reload mode
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
