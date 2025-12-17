"""
Middleware Components
Error handling and request/response interceptors
"""
from fastapi import Request, status
from fastapi.responses import JSONResponse
from .exceptions import APIError
from .responses import create_error_response
import traceback
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def error_handling_middleware(request: Request, call_next):
    """
    Global error handling middleware
    Catches all exceptions and returns structured error responses
    """
    try:
        response = await call_next(request)
        return response
    
    except APIError as e:
        # Custom API errors
        logger.error(f"API Error: {e.error_code} - {e.message}")
        return JSONResponse(
            status_code=e.status_code,
            content=create_error_response(
                message=e.message,
                status_code=e.status_code,
                error_code=e.error_code,
                details=e.details
            )
        )
    
    except Exception as e:
        # Unexpected errors
        error_msg = str(e)
        trace = traceback.format_exc()
        
        logger.error(f"Unexpected Error: {error_msg}\n{trace}")
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=create_error_response(
                message=f"Internal server error: {error_msg}",
                status_code=500,
                error_code="INTERNAL_ERROR",
                details={"traceback": trace if logger.level == logging.DEBUG else None}
            )
        )
