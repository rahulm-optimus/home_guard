"""  
API v1 Router
Aggregates all v1 endpoints
"""
from fastapi import APIRouter
from app.api.v1.endpoints import search, save, health, chat
from app.api.v1.endpoints import cost_estimate


api_router = APIRouter()

# Include endpoint routers
api_router.include_router(health.router, tags=["Health Check"])
api_router.include_router(search.router, tags=["General Search Agent"])
api_router.include_router(save.router, tags=["Database"])
api_router.include_router(cost_estimate.router, tags=["Cost Estimation Agent"])
api_router.include_router(chat.router, tags=["Chat Conversation"])