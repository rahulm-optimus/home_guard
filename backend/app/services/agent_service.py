"""
Agent Service
Simple service for Azure AI agent interactions
"""

import logging
from typing import Dict, Any, Optional

from azure.ai.agents.models import ListSortOrder
from app.core.azure_client import get_azure_ai_client
from app.core.config import settings
from app.core.exceptions import APIError, ErrorCodes

logger = logging.getLogger(__name__)


class AgentService:
    """Service for handling agent conversations"""

    def __init__(self):
        self.client = get_azure_ai_client()
        self.agent_id = settings.AZURE_AGENT_ID
        logger.info(f"AgentService initialized with agent: {self.agent_id}")

    def chat(self, message: str, thread_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Send user message to agent and get response.

        Args:
            message: User's input message
            thread_id: Optional thread ID for conversation continuity

        Returns:
            Dictionary with message, thread_id, and status
        """
        try:
            # Create new thread if none provided
            if not thread_id:
                thread = self.client.agents.threads.create()
                thread_id = thread.id
                logger.info(f"Created new thread: {thread_id}")

            logger.info(f"Processing message in thread {thread_id}")

            # Send user message to agent
            self.client.agents.messages.create(
                thread_id=thread_id, role="user", content=message
            )

            # Run the agent
            run = self.client.agents.runs.create_and_process(
                thread_id=thread_id, agent_id=self.agent_id
            )

            # Check run status
            if run.status == "failed":
                error_msg = str(run.last_error) if run.last_error else "Unknown error"
                logger.error(f"Agent run failed: {error_msg}")
                raise APIError(
                    message=f"Agent execution failed: {error_msg}",
                    status_code=500,
                    error_code=ErrorCodes.AGENT_ERROR,
                )

            # Get the latest assistant response
            messages = list(
                self.client.agents.messages.list(
                    thread_id=thread_id, order=ListSortOrder.DESCENDING, limit=10
                )
            )

            # Find the latest assistant message
            assistant_message = None
            for msg in messages:
                if (
                    msg.role == "assistant"
                    and hasattr(msg, "text_messages")
                    and msg.text_messages
                ):
                    assistant_message = msg.text_messages[-1].text.value
                    break

            if not assistant_message:
                raise APIError(
                    message="Agent returned no response",
                    status_code=500,
                    error_code=ErrorCodes.AGENT_ERROR,
                )

            logger.info(f"Agent response received")

            return {
                "message": assistant_message,
                "thread_id": thread_id,
                "status": "success",
            }

        except APIError:
            raise
        except Exception as e:
            logger.exception(f"Unexpected error in chat: {e}")
            raise APIError(
                message=f"Chat processing failed: {str(e)}",
                status_code=500,
                error_code=ErrorCodes.AGENT_ERROR,
            )


# Singleton instance
_agent_service = None


def get_agent_service() -> AgentService:
    """Get singleton instance of AgentService"""
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service
