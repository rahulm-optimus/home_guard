from typing import Dict, Any
from app.core.config import settings
import threading
import logging
import re
import json

from app.core.azure_client import get_azure_ai_client

logger = logging.getLogger(__name__)

class CosmosAgentService:
    def __init__(self):
        self.agent_id = settings.AZURE_AI_COSMOS_AGENT_ID
        self.ai_client = get_azure_ai_client()

    def search(self, query: str) -> Dict[str, Any]:
        """
        Returns the latest assistant text_messages.
        If no assistant message exists, returns "Could not find the result".
        """
        try:
            thread = self.ai_client.agents.threads.create()
            thread_id = thread.id
            assistant_instruction = (
            f"{query}\n\n"
            "After using the AI search tool, check if the result matches the query above. "
            "If the result is relevant and matches the query, return the data in JSON format "
            "with keys: last_approved_min, last_approved_max, currency, thread_id or id. "
            "If the result does not match the query, return null."
            )

            self.ai_client.agents.messages.create(
                thread_id=thread_id,
                role="user",
                content=assistant_instruction
            )

            run = self.ai_client.agents.runs.create_and_process(
                thread_id=thread_id,
                agent_id=self.agent_id
            )

            if run.status == "failed":
                return {"error": "Agent execution failed"}

            messages = list(self.ai_client.agents.messages.list(thread_id=thread_id))

            # Only look at assistant messages with text_messages
            assistant_messages = [m for m in messages if m.role == "assistant" and getattr(m, "text_messages", None)]

            if not assistant_messages:
                return {"result": "Could not find the result"}

            latest_text = assistant_messages[-1].text_messages[-1].text.value

            # Try to extract JSON object from the text
            json_match = re.search(r"\{.*\}", latest_text, re.DOTALL)
            extracted_json = None
            if json_match:
                try:
                    extracted_json = json.loads(json_match.group())
                except Exception as e:
                    logger.warning(f"Failed to parse JSON from assistant message: {e}")

            return {
                "result": latest_text,
                "extracted_json": extracted_json
            }

        except Exception as e:
            logger.error(f"CosmosAgentService search error: {e}")
            return {"error": str(e)}
        # finally:
        #     # Clean up the thread after execution
        #     try:
        #         if 'thread_id' in locals():
        #             self.ai_client.agents.threads.delete(thread_id=thread_id)
        #     except Exception as cleanup_err:
        #         logger.warning(f"Failed to delete thread {thread_id}: {cleanup_err}")

_cosmos_agent_service = None
_service_lock = threading.Lock()

def get_cosmos_agent_service() -> CosmosAgentService:
    global _cosmos_agent_service
    if _cosmos_agent_service is None:
        with _service_lock:
            if _cosmos_agent_service is None:
                _cosmos_agent_service = CosmosAgentService()
    return _cosmos_agent_service
