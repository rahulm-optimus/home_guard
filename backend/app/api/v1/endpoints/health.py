"""
Health Check Endpoint
Tests OpenAI/Azure configuration and connectivity
"""
from fastapi import APIRouter, HTTPException
from app.core.config import settings, get_settings
from app.utils.llm import get_llm, reset_llm
from langchain_core.messages import SystemMessage, HumanMessage
from datetime import datetime
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", tags=["Health Check"])
async def health_check() -> Dict[str, Any]:
    """
    Basic health check endpoint
    
    Returns:
        Status of the API
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "HomeGuard API"
    }


@router.get("/health/openai", tags=["Health Check"])
async def openai_health_check() -> Dict[str, Any]:
    """
    Test OpenAI/Azure AI configuration and connectivity
    
    This endpoint verifies:
    - Configuration is loaded correctly (reloads from .env)
    - API credentials are valid
    - LLM endpoint is accessible
    - Model can generate responses
    
    Returns:
        Detailed health check results including configuration and test query results
    """
    try:
        # Force reload settings from .env file
        get_settings.cache_clear()
        fresh_settings = get_settings()
        
        # Reset LLM instance to use fresh settings
        reset_llm()
        
        # Step 1: Configuration Check
        config_info = {
            "endpoint": fresh_settings.AZURE_OPENAI_ENDPOINT,
            "api_version": fresh_settings.AZURE_OPENAI_API_VERSION,
            "deployment_name": fresh_settings.AZURE_OPENAI_DEPLOYMENT_NAME,
            "temperature": fresh_settings.AZURE_OPENAI_TEMPERATURE,
            "api_key_configured": bool(fresh_settings.AZURE_OPENAI_API_KEY),
            "api_key_preview": f"{fresh_settings.AZURE_OPENAI_API_KEY[:10]}...{fresh_settings.AZURE_OPENAI_API_KEY[-5:]}" if fresh_settings.AZURE_OPENAI_API_KEY else None,
        }
        
        logger.info(f"OpenAI health check started - Endpoint: {config_info['endpoint']} (settings reloaded)")
        
        # Step 2: LLM Instance Creation
        try:
            llm = get_llm()
            llm_info = {
                "llm_type": type(llm).__name__,
                "created": True
            }
        except Exception as e:
            logger.error(f"Failed to create LLM instance: {str(e)}")
            return {
                "status": "unhealthy",
                "timestamp": datetime.now().isoformat(),
                "configuration": config_info,
                "llm_instance": {
                    "created": False,
                    "error": str(e)
                },
                "test_query": {
                    "executed": False,
                    "reason": "LLM instance creation failed"
                }
            }
        
        # Step 3: Test Query
        try:
            test_start = datetime.now()
            
            messages = [
                SystemMessage(content="You are a helpful assistant. Respond concisely."),
                HumanMessage(content="Return the text: 'OpenAI connection successful'")
            ]
            
            response = llm.invoke(messages)
            
            test_duration = (datetime.now() - test_start).total_seconds()
            
            test_result = {
                "executed": True,
                "duration_seconds": round(test_duration, 3),
                "response_preview": response.content[:100],
                "response_length": len(response.content),
                "success": "successful" in response.content.lower()
            }
            
            # Check for metadata indicating grounding/citations
            grounding_detected = False
            if hasattr(response, 'response_metadata'):
                metadata = response.response_metadata
                grounding_indicators = ['citations', 'grounding', 'sources', 'retrieved_documents']
                grounding_detected = any(ind in str(metadata).lower() for ind in grounding_indicators)
                
                test_result["metadata"] = {
                    "finish_reason": metadata.get("finish_reason", "unknown"),
                    "model": metadata.get("model", "unknown"),
                    "grounding_detected": grounding_detected
                }
            
            logger.info(f"OpenAI test query successful - Duration: {test_duration}s")
            
        except Exception as e:
            logger.error(f"Test query failed: {str(e)}")
            test_result = {
                "executed": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
        
        # Step 4: Compile Results
        overall_status = "healthy" if test_result.get("executed") and test_result.get("success") else "degraded"
        
        result = {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "configuration": config_info,
            "llm_instance": llm_info,
            "test_query": test_result,
            "recommendations": []
        }
        
        # Add recommendations based on results
        if not test_result.get("executed"):
            result["recommendations"].append("Check API credentials and network connectivity")
        if not test_result.get("success"):
            result["recommendations"].append("Model responded but unexpected content - verify deployment")
        if test_result.get("duration_seconds", 0) > 5:
            result["recommendations"].append("Response time is slow - check network or consider timeout adjustments")
        
        return result
        
    except Exception as e:
        logger.error(f"Health check failed with exception: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "status": "unhealthy",
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "error_type": type(e).__name__
            }
        )


@router.get("/health/agent", tags=["Health Check"])
async def agent_health_check() -> Dict[str, Any]:
    """
    Test Azure AI Foundry Agent connectivity and health
    
    Returns:
        Azure AI Agent health status
    """
    try:
        from app.services.azure_agent_service import get_azure_agent_service
        
        config_info = {
            "agent_id": settings.AZURE_AI_AGENT_ID,
            "endpoint": settings.AZURE_AI_PROJECT_ENDPOINT,
            "bing_enabled": settings.AZURE_AGENT_USE_BING
        }
        
        # Try a simple test query
        try:
            agent_service = get_azure_agent_service()
            test_start = datetime.now()
            
            result = agent_service.get_cost_estimate(
                description="Test roof repair",
                subcategory="Roofing",
                zipcode="94551",
                use_bing=False  # Quick test without Bing
            )
            
            test_duration = (datetime.now() - test_start).total_seconds()
            
            test_result = {
                "executed": True,
                "duration_seconds": round(test_duration, 3),
                "has_estimate": bool(result.get("min") and result.get("max")),
                "success": bool(result.get("min", 0) > 0)
            }
            
            overall_status = "healthy" if test_result["success"] else "degraded"
            
        except Exception as e:
            logger.error(f"Agent test failed: {str(e)}")
            test_result = {
                "executed": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
            overall_status = "unhealthy"
        
        return {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "configuration": config_info,
            "test_query": test_result
        }
        
    except Exception as e:
        logger.error(f"Agent health check failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "status": "unhealthy",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
        )
