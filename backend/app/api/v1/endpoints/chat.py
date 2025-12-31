"""Chat endpoint for conversational cost estimates"""
from fastapi import APIRouter, HTTPException, Depends
from app.services.chat_conversation_service import get_chat_conversation_service
from app.schemas.chat import ChatRequest, ChatResponse
from app.core.exceptions import APIError
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat_with_agent(
    request: ChatRequest,
    chat_service = Depends(get_chat_conversation_service)
):
    """
    Conversational chat endpoint for cost estimates.
    
    The agent will:
    - Ask for zipcode and description if not provided
    - Call the cost-estimate endpoint internally
    - Present results conversationally with full details
    """
    try:
        result = chat_service.chat(
            message=request.message,
            thread_id=request.thread_id
        )
        
        return ChatResponse(
            message=result["message"],
            thread_id=result["thread_id"],
            status="success",
            estimate=result.get("estimate", {"min": "", "max": ""})
        )
    
    except APIError as e:
        logger.error(f"Chat API error: {e.message}")
        raise HTTPException(
            status_code=e.status_code,
            detail={
                "error": e.error_code,
                "message": e.message,
                "details": e.details
            }
        )
    except Exception as e:
        logger.error(f"Unexpected chat error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "CHAT_ERROR",
                "message": str(e),
                "details": {}
            }
        )