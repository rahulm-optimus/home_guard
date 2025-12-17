"""
Search Endpoints
API routes for testing Azure AI Foundry Agent
"""

from fastapi import APIRouter
from pydantic import BaseModel
from app.services.general_service import AgentSearchService
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

router = APIRouter()

# ----------- Request / Response Models -----------

class SearchRequest(BaseModel):
    query: str


class SearchResponse(BaseModel):
    status: str
    data: Dict[str, Any]
    bing_used: bool


# ----------- Endpoint -----------

@router.post(
    "/test-agent",
    response_model=SearchResponse,
    summary="Test Azure AI Agent Search"
)
async def agent_search_endpoint(input: SearchRequest) -> SearchResponse:
    logger.info(f"Agent search request received: {input.query}")

    agent_service = AgentSearchService()
    result = agent_service.search(input.query)

    return result

