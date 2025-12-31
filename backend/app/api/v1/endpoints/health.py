"""
Health Check Endpoint
Tests OpenAI/Azure configuration and connectivity
"""
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from fastapi import APIRouter, HTTPException
from app.core.config import settings, get_settings
from datetime import datetime
from typing import Dict, Any
import logging
import time

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health/chat-agent", tags=["Health Check"])
async def chat_agent_health_check() -> Dict[str, Any]:
    """
    Health check for Azure Chat Agent: runs a simple FAQ query to verify agent and settings.
    Initializes client with credentials, uses AZURE_CHAT_AGENT_ID, creates and deletes thread.
    """
    try:
        endpoint = settings.AZURE_AI_PROJECT_ENDPOINT
        agent_id = settings.AZURE_CHAT_AGENT_ID
        credential = DefaultAzureCredential()
        client = AIProjectClient(credential=credential, endpoint=endpoint)
        # Create a thread
        thread = client.agents.threads.create()
        thread_id = thread.id
        faq_message = "What is Home Guard?"
        client.agents.messages.create(
            thread_id=thread_id,
            role="user",
            content=faq_message
        )
        run = client.agents.runs.create(
            thread_id=thread_id,
            agent_id=agent_id
        )
        # Poll for completion with timeout
        timeout = 10  # seconds
        poll_interval = 1
        waited = 0
        while run.status not in ("completed", "failed") and waited < timeout:
            time.sleep(poll_interval)
            waited += poll_interval
            run = client.agents.runs.get(
                thread_id=thread_id,
                run_id=run.id
            )
        if run.status != "completed":
            # Clean up thread before raising error
            try:
                client.agents.threads.delete(thread_id=thread_id)
            except Exception:
                pass
            raise Exception(f"Agent run did not complete in {timeout} seconds (status: {run.status})")
        # Get the assistant's reply (remove order_by, just use limit)
        response = next(
            m for m in client.agents.messages.list(
                thread_id=thread_id,
                limit=5
            ) if m.role == "assistant" and m.text_messages
        )
        answer = response.text_messages[-1].text.value
        # Clean up thread after success
        try:
            client.agents.threads.delete(thread_id=thread_id)
        except Exception:
            pass
        return {
            "status": "ok",
            "agent_id": agent_id,
            "faq_question": faq_message,
            "faq_answer": answer,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        logger.error(f"Chat agent health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Chat agent health check failed: {e}")

