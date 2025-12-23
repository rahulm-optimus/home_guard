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
async def comprehensive_health_check() -> Dict[str, Any]:
    """
    Comprehensive health check endpoint
    
    Tests all system components:
    - Basic API status
    - OpenAI/Azure AI configuration and connectivity
    - Azure AI Foundry Agent connectivity
    
    Returns:
        Comprehensive health status for all components
    """
    timestamp = datetime.now().isoformat()
    health_results = {
        "status": "healthy",
        "timestamp": timestamp,
        "service": "HomeGuard API",
        "components": {}
    }
    
    # Basic health
    health_results["components"]["api"] = {
        "status": "healthy",
        "message": "API is running"
    }
    
    # OpenAI Health Check
    try:
        # Force reload settings from .env file
        get_settings.cache_clear()
        fresh_settings = get_settings()
        
        # Reset LLM instance to use fresh settings
        reset_llm()
        
        # Configuration Check
        config_info = {
            "endpoint": fresh_settings.AZURE_OPENAI_ENDPOINT,
            "api_version": fresh_settings.AZURE_OPENAI_API_VERSION,
            "deployment_name": fresh_settings.AZURE_OPENAI_DEPLOYMENT_NAME,
            "temperature": fresh_settings.AZURE_OPENAI_TEMPERATURE,
            "api_key_configured": bool(fresh_settings.AZURE_OPENAI_API_KEY),
        }
        
        logger.info(f"OpenAI health check started - Endpoint: {config_info['endpoint']} (settings reloaded)")
        
        # LLM Instance Creation
        try:
            llm = get_llm()
            llm_info = {
                "llm_type": type(llm).__name__,
                "created": True
            }
        except Exception as e:
            logger.error(f"Failed to create LLM instance: {str(e)}")
            health_results["components"]["openai"] = {
                "status": "unhealthy",
                "configuration": config_info,
                "llm_instance": {"created": False, "error": str(e)},
                "test_query": {"executed": False, "reason": "LLM instance creation failed"}
            }
            health_results["status"] = "degraded"
        
        # Test Query
        if "openai" not in health_results["components"]:
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
                
                openai_status = "healthy" if test_result["success"] else "degraded"
                health_results["components"]["openai"] = {
                    "status": openai_status,
                    "configuration": config_info,
                    "llm_instance": llm_info,
                    "test_query": test_result
                }
                
                if openai_status == "degraded":
                    health_results["status"] = "degraded"
                    
            except Exception as e:
                logger.error(f"OpenAI test query failed: {str(e)}")
                health_results["components"]["openai"] = {
                    "status": "unhealthy",
                    "configuration": config_info,
                    "llm_instance": llm_info,
                    "test_query": {
                        "executed": False,
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                }
                health_results["status"] = "degraded"
    
    except Exception as e:
        logger.error(f"OpenAI health check failed with exception: {str(e)}")
        health_results["components"]["openai"] = {
            "status": "unhealthy",
            "error": str(e),
            "error_type": type(e).__name__
        }
        health_results["status"] = "degraded"
    
    # Agent Health Check
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
            
            agent_status = "healthy" if test_result["success"] else "degraded"
            health_results["components"]["agent"] = {
                "status": agent_status,
                "configuration": config_info,
                "test_query": test_result
            }
            
            if agent_status == "degraded":
                health_results["status"] = "degraded"
                
        except Exception as e:
            logger.error(f"Agent test failed: {str(e)}")
            health_results["components"]["agent"] = {
                "status": "unhealthy",
                "configuration": config_info,
                "test_query": {
                    "executed": False,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            }
            health_results["status"] = "degraded"
    
    except Exception as e:
        logger.error(f"Agent health check failed: {str(e)}")
        health_results["components"]["agent"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_results["status"] = "degraded"
    
    return health_results


# Legacy endpoints - kept for backward compatibility but deprecated
@router.get("/health/openai", tags=["Health Check"], deprecated=True)
async def openai_health_check() -> Dict[str, Any]:
    """
    DEPRECATED: Use /health endpoint instead
    
    Test OpenAI/Azure AI configuration and connectivity
    """
    result = await comprehensive_health_check()
    return result["components"].get("openai", {"status": "unknown"})


@router.get("/health/agent", tags=["Health Check"], deprecated=True)
async def agent_health_check() -> Dict[str, Any]:
    """
    DEPRECATED: Use /health endpoint instead
    
    Test Azure AI Foundry Agent connectivity and health
    """
    result = await comprehensive_health_check()
    return result["components"].get("agent", {"status": "unknown"})
