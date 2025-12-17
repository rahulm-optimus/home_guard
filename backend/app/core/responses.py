"""
Standardized Response Builders
Creates consistent API response structures
"""
from typing import Optional


def create_error_response(
    message: str,
    status_code: int = 500,
    error_code: str = "INTERNAL_ERROR",
    details: Optional[dict] = None
) -> dict:
    """
    Create standardized error response
    
    Args:
        message: Error message
        status_code: HTTP status code
        error_code: Application error code
        details: Additional error details
        
    Returns:
        Standardized error response dictionary
    """
    return {
        "status": "error",
        "status_code": status_code,
        "error": {
            "code": error_code,
            "message": message,
            "details": details or {}
        },
        "data": {}
    }


def create_success_response(
    data: dict,
    message: str = "Success",
    status_code: int = 200
) -> dict:
    """
    Create standardized success response
    
    Args:
        data: Response data payload
        message: Success message
        status_code: HTTP status code
        
    Returns:
        Standardized success response dictionary
    """
    return {
        "status": "success",
        "status_code": status_code,
        "message": message,
        "data": data
    }
