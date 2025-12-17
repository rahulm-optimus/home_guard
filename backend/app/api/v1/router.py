"""  
API v1 Router
Aggregates all v1 endpoints
"""
from fastapi import APIRouter
from app.api.v1.endpoints import search, save, health
from app.api.v1.endpoints import agend ,test


api_router = APIRouter()

# Include endpoint routers
api_router.include_router(health.router, tags=["Health Check"])
api_router.include_router(agend.router, tags=["Agent"])
api_router.include_router(search.router, tags=["Test Search"])
api_router.include_router(save.router, tags=["Database"])
api_router.include_router(test.router, tags=["Test Agent"])