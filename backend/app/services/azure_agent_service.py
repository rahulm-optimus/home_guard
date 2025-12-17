"""Azure AI Agent Service - Simplified and Optimized"""
from typing import Dict, Any, Optional
from azure.ai.projects import AIProjectClient
from azure.identity import AzureCliCredential
from azure.ai.agents.models import ListSortOrder
from app.core.config import settings
from app.core.exceptions import APIError, ErrorCodes
import logging
import json
import re
import threading

logger = logging.getLogger(__name__)

# Fallback cost ranges for quick responses
FALLBACK_COSTS = {
    "Fungus damage": (800, 5000), "Insect related findings": (500, 3000),
    "Wood destroying organisms": (1000, 6000), "Roofing": (1500, 10000),
    "Plumbing": (300, 2500), "Electrical": (400, 3000),
    "Structure": (2000, 15000), "Exterior": (500, 5000), "Interior": (300, 3000)
}

# Global client instances for thread safety
_client_lock = threading.Lock()
_shared_credential = None
_shared_client = None


class AzureAgentService:
    
    def __init__(self):
        self.agent_id = settings.AZURE_AI_AGENT_ID
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Azure AI client with thread-safe singleton pattern"""
        global _shared_credential, _shared_client
        
        try:
            with _client_lock:
                if _shared_credential is None:
                    # One-time credential initialization
                    import os
                    if settings.AZURE_TENANT_ID:
                        os.environ['AZURE_TENANT_ID'] = settings.AZURE_TENANT_ID
                    _shared_credential = AzureCliCredential(tenant_id=settings.AZURE_TENANT_ID or None)
                    logger.info("Azure CLI credential initialized")
                
                if _shared_client is None:
                    _shared_client = AIProjectClient(
                        credential=_shared_credential, 
                        endpoint=settings.AZURE_AI_PROJECT_ENDPOINT
                    )
                    logger.info(f"Azure AI Agent ready: {self.agent_id}")
                
                self.ai_client = _shared_client
        except Exception as e:
            logger.error(f"Agent init failed: {e}")
            raise APIError(f"Failed to initialize agent: {e}", 500, ErrorCodes.AGENT_ERROR)
    
    def get_cost_estimate(self, description: str, subcategory: str, zipcode: str, use_bing: Optional[bool] = None) -> Dict[str, Any]:
        """Get cost estimate - simplified and optimized"""
        if not description.strip() or not zipcode.strip():
            raise APIError("Description and zipcode required", 400, ErrorCodes.VALIDATION_ERROR)
        
        enable_bing = use_bing if use_bing is not None else settings.AZURE_AGENT_USE_BING
        
        # Optimized prompt - short and direct
        prompt = f"""Cost estimate for: {description}
Subcategory: {subcategory} | Zip: {zipcode}

{"Search web for prices." if enable_bing else "Use your knowledge."}
Return JSON: {{"min": <number>, "max": <number>, "note": "<50 chars>"}}"""
        
        try:
            agent = self.ai_client.agents.get_agent(self.agent_id)
            thread = self.ai_client.agents.threads.create()
            self.ai_client.agents.messages.create(thread_id=thread.id, role="user", content=prompt)
            
            # Run with optimizations - handle tools parameter correctly
            if enable_bing:
                # Use agent's default tools (includes Bing)
                run = self.ai_client.agents.runs.create_and_process(
                    thread_id=thread.id,
                    agent_id=agent.id
                )
            else:
                # Disable tools by setting empty list
                run = self.ai_client.agents.runs.create_and_process(
                    thread_id=thread.id,
                    agent_id=agent.id,
                    tools=[]
                )
            
            if run.status == "failed":
                if "bing" in str(run.last_error).lower():
                    logger.warning(f"Bing failed for {subcategory}, using fallback")
                    return self._fallback(subcategory, zipcode)
                raise APIError(f"Agent failed: {run.last_error}", 500, ErrorCodes.AGENT_ERROR)
            
            # Get response
            messages = self.ai_client.agents.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)
            response = next((m.text_messages[-1].text.value for m in messages if m.role == "assistant" and m.text_messages), None)
            
            if not response:
                raise APIError("No agent response", 500, ErrorCodes.AGENT_ERROR)
            
            return self._parse_response(response, subcategory, zipcode, enable_bing)
        except APIError:
            raise
        except Exception as e:
            if "bing" in str(e).lower() or "unauthorized" in str(e).lower():
                logger.warning(f"Bing error, using fallback: {e}")
                return self._fallback(subcategory, zipcode)
            raise APIError(f"Estimate failed: {e}", 500, ErrorCodes.AGENT_ERROR)
    
    def _fallback(self, subcategory: str, zipcode: str) -> Dict[str, Any]:
        """Quick fallback estimate"""
        min_cost, max_cost = FALLBACK_COSTS.get(subcategory, (500, 2500))
        return {"min": float(min_cost), "max": float(max_cost), "note": f"Standard {subcategory} estimate for {zipcode}"}
    
    def _parse_response(self, text: str, subcategory: str, zipcode: str, bing: bool) -> Dict[str, Any]:
        """Parse agent response - handles JSON or text"""
        try:
            # Extract JSON
            text = text.strip()
            if "```" in text:
                text = text.split("```")[1].replace("json", "").strip()
            
            start, end = text.find("{"), text.rfind("}") + 1
            if start != -1 and end > start:
                data = json.loads(text[start:end])
                min_cost, max_cost = float(data.get("min", 500)), float(data.get("max", 2000))
                note = data.get("note", "AI estimate")[:100]  # Limit note length
                
                if min_cost >= max_cost:
                    min_cost, max_cost = max_cost, min_cost
                
                return {"min": min_cost, "max": max_cost, "note": f"[{'Bing' if bing else 'AI'}] {note}"}
        except:
            pass
        
        # Fallback: extract $ amounts
        amounts = [float(m.replace('$', '').replace(',', '')) for m in re.findall(r'\$[\d,]+', text)]
        if len(amounts) >= 2:
            return {"min": min(amounts[:2]), "max": max(amounts[:2]), "note": f"[{'Bing' if bing else 'AI'}] {text[:80]}"}
        
        return self._fallback(subcategory, zipcode)


_azure_agent_service = None
_service_lock = threading.Lock()


def get_azure_agent_service() -> AzureAgentService:
    """Thread-safe singleton getter for Azure Agent Service"""
    global _azure_agent_service
    if _azure_agent_service is None:
        with _service_lock:
            if _azure_agent_service is None:  # Double-check pattern
                _azure_agent_service = AzureAgentService()
    return _azure_agent_service
