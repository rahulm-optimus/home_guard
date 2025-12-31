"""  
API v1 Router
Aggregates all v1 endpoints
"""
from fastapi import APIRouter
from app.api.v1.endpoints import health, chat
from app.api.v1.endpoints import data_base

api_router = APIRouter()

# Include endpoint routers
api_router.include_router(health.router, tags=["Health Check"])
api_router.include_router(data_base.router, tags=["Database"])
api_router.include_router(chat.router, tags=["Chat Conversation"])