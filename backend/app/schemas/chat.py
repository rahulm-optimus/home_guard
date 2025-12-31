"""Chat schemas for request/response validation"""
from pydantic import BaseModel, Field
from typing import Optional

class ChatRequest(BaseModel):
    """Request model for chat messages"""
    message: str = Field(..., min_length=1, description="User message")
    thread_id: Optional[str] = Field(None, description="Thread ID for conversation continuity")
    
class ChatResponse(BaseModel):
    """Response model for chat messages"""
    message: str = Field(..., description="Bot response message")
    thread_id: str = Field(..., description="Thread ID for conversation continuity")
    status: str = Field(default="success", description="Response status")
    estimate: dict = Field(default_factory=lambda: {"min": "", "max": ""}, description="Average min/max estimate or empty if not available")