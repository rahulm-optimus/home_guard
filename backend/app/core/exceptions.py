"""
Custom Exception Classes
Centralized exception definitions for the application
"""
from typing import Optional


class APIError(Exception):
    """Base API Error with structured response"""
    
    def __init__(
        self, 
        message: str, 
        status_code: int = 500,
        error_code: str = "INTERNAL_ERROR",
        details: Optional[dict] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(APIError):
    """Validation error (400)"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            status_code=400,
            error_code=ErrorCodes.VALIDATION_ERROR,
            details=details
        )


class NotFoundError(APIError):
    """Resource not found error (404)"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            status_code=404,
            error_code=ErrorCodes.NOT_FOUND,
            details=details
        )


class UnauthorizedError(APIError):
    """Unauthorized error (401)"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            status_code=401,
            error_code=ErrorCodes.UNAUTHORIZED,
            details=details
        )


class ServiceError(APIError):
    """External service error (503)"""
    def __init__(self, message: str, error_code: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            status_code=503,
            error_code=error_code,
            details=details
        )


class ErrorCodes:
    """Standard error code constants"""
    
    # Generic errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    BAD_REQUEST = "BAD_REQUEST"
    
    # Service specific errors
    OPENAI_ERROR = "OPENAI_ERROR"
    BING_SEARCH_ERROR = "BING_SEARCH_ERROR"
    AGENT_ERROR = "AGENT_ERROR"
    QUERY_PROCESSING_ERROR = "QUERY_PROCESSING_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    COSMOS_DB_ERROR = "COSMOS_DB_ERROR"
