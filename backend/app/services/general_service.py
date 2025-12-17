"""
Agent Search Service
Simple Azure AI Foundry Agent usage (clean & safe)
"""

import json
from typing import Dict, Any
from azure.ai.projects import AIProjectClient
from azure.identity import AzureCliCredential
from azure.ai.agents.models import ListSortOrder
from app.core.config import settings
from app.core.exceptions import APIError, ErrorCodes
import logging

logger = logging.getLogger(__name__)


class AgentSearchService:
    def __init__(self):
        try:
            self.agent_id = settings.AZURE_AI_AGENT_ID

            self.client = AIProjectClient(
                credential=AzureCliCredential(
                    tenant_id=settings.AZURE_TENANT_ID or None
                ),
                endpoint=settings.AZURE_AI_PROJECT_ENDPOINT
            )

            logger.info("AgentSearchService initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize AgentSearchService: {e}")
            raise APIError(
                message="Failed to initialize Azure AI Agent client",
                status_code=500,
                error_code=ErrorCodes.AGENT_ERROR
            )

    def search(self, query: str) -> Dict[str, Any]:
        thread_id = None

        try:
            logger.info(f"Agent query: {query}")

            agent = self.client.agents.get_agent(self.agent_id)

            # 1️ Create thread
            thread = self.client.agents.threads.create()
            thread_id = thread.id

            # 2️ Send message
            self.client.agents.messages.create(
                thread_id=thread_id,
                role="user",
                content=query
            )

            # 3️ Run agent
            run = self.client.agents.runs.create_and_process(
                thread_id=thread_id,
                agent_id=agent.id
            )

            if run.status == "failed":
                error_msg = str(run.last_error) if run.last_error else "Unknown error"
                logger.error(f"Agent run failed: {error_msg}")

                return {
                    "status": "failed",
                    "error": error_msg,
                    "bing_used": False
                }

            # 4️ Read response
            messages = self.client.agents.messages.list(
                thread_id=thread_id,
                order=ListSortOrder.ASCENDING
            )

            response_text = None
            for msg in messages:
                if msg.role == "assistant" and msg.text_messages:
                    response_text = msg.text_messages[-1].text.value
                    break

            if not response_text:
                raise APIError(
                    message="Agent returned no response",
                    status_code=500,
                    error_code=ErrorCodes.AGENT_ERROR
                )

            # 5️ Parse JSON safely
            try:
                parsed_response = json.loads(response_text)
            except json.JSONDecodeError:
                raise APIError(
                    message="Agent response is not valid JSON",
                    status_code=500,
                    error_code=ErrorCodes.AGENT_ERROR
                )

            # 6️ Minimal structure validation
            if "status" not in parsed_response or "data" not in parsed_response:
                raise APIError(
                    message="Agent response JSON structure is invalid",
                    status_code=500,
                    error_code=ErrorCodes.AGENT_ERROR
                )

            logger.info("Agent query completed successfully")

            return {
                "status": "completed",
                "data": parsed_response,
                "bing_used": True  # Agent-configured grounding
            }

        except APIError:
            raise  # rethrow known errors

        except Exception as e:
            logger.error(f"Agent search failed: {e}")
            raise APIError(
                message=f"Agent search failed: {str(e)}",
                status_code=500,
                error_code=ErrorCodes.AGENT_ERROR
            )

        finally:
            # 7️ Cleanup thread
            if thread_id:
                try:
                    self.client.agents.threads.delete(thread_id)
                    logger.info(f"Deleted agent thread: {thread_id}")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to delete thread {thread_id}: {cleanup_error}")
