from typing import Dict, Any, Optional
from datetime import datetime
import json
import logging
import re

from azure.ai.agents.models import ListSortOrder
from app.core.azure_client import get_azure_ai_client
from app.core.config import settings
from app.core.exceptions import APIError, ErrorCodes
from app.services.cosmos_db_service import get_cosmos_service
from app.services.history_agent_service import get_cosmos_agent_service

logger = logging.getLogger(__name__)

# --------------------------------------------------
# In-memory thread state
# --------------------------------------------------
_active_threads: Dict[str, dict] = {}

US_ZIP_REGEX = re.compile(r"^\d{5}$")


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def is_valid_us_zip(zipcode: str) -> bool:
    return bool(US_ZIP_REGEX.match(zipcode))


def extract_numbers(text: str):
    return [float(n) for n in re.findall(r"\d+\.?\d*", text)]


def interpret_price_adjustment(text: str, cur_min: float, cur_max: float):
    t = text.lower()
    nums = extract_numbers(t)

    if not nums:
        return None, None, True

    if len(nums) >= 2:
        return nums[0], nums[1], False

    val = nums[0]

    if any(k in t for k in ["too low", "increase", "higher", "cheap"]):
        return None, max(val, cur_max), False

    if any(k in t for k in ["too high", "lower", "expensive"]):
        return min(val, cur_min), None, False

    if any(k in t for k in ["min", "minimum", "starting"]):
        return val, None, False

    if any(k in t for k in ["max", "maximum", "cap", "upto"]):
        return None, val, False

    return None, None, True


# --------------------------------------------------
# Chat Conversation Service
# --------------------------------------------------
class ChatConversationService:

    def __init__(self):
        self.client = get_azure_ai_client()
        self.agent_id = settings.AZURE_CHAT_AGENT_ID

    # --------------------------------------------------
    # Intent classifier
    # --------------------------------------------------
    def _classify(self, thread_id: str, message: str) -> dict:
        prompt = f"""
You are an intent classifier for a home repair cost assistant.

Return ONLY valid JSON:

{{
  "intent": "estimate_request | approval_yes | approval_no | clarification | negotiation | out_of_scope",
  "item": "<string or null>",
  "zipcode": "<5-digit ZIP or null>"
}}

Message:
{message}
"""
        self.client.agents.messages.create(thread_id=thread_id, role="user", content=prompt)
        self.client.agents.runs.create_and_process(thread_id=thread_id, agent_id=self.agent_id)

        msg = next(
            m for m in self.client.agents.messages.list(
                thread_id=thread_id,
                order=ListSortOrder.DESCENDING,
                limit=5
            ) if m.role == "assistant"
        )

        return json.loads(msg.text_messages[-1].text.value)

    # --------------------------------------------------
    # ZIP → Location resolver (agent-powered)
    # --------------------------------------------------
    def _resolve_location(self, thread_id: str, zipcode: str) -> str:
        prompt = f"""
Using Bing search, identify the US city and state for ZIP code {zipcode}.

Return ONLY JSON:
{{ "city": "<city>", "state": "<state>" }}
"""
        self.client.agents.messages.create(thread_id=thread_id, role="user", content=prompt)
        self.client.agents.runs.create_and_process(thread_id=thread_id, agent_id=self.agent_id)

        msg = next(
            m for m in self.client.agents.messages.list(
                thread_id=thread_id,
                order=ListSortOrder.DESCENDING
            ) if m.role == "assistant"
        )

        data = json.loads(msg.text_messages[-1].text.value)
        return f"{data['city']}, {data['state']}"

    # --------------------------------------------------
    # Main chat
    # --------------------------------------------------
    def chat(self, message: str, thread_id: Optional[str] = None) -> Dict[str, Any]:
        try:
            if not thread_id:
                thread_id = self.client.agents.threads.create().id

            state = _active_threads.get(thread_id, {
                "status": "collecting",
                "item": None,
                "zipcode": None,
                "location": None,
                "estimate": None,
                "created": None
            })

            intent_data = self._classify(thread_id, message)
            intent = intent_data["intent"]

            # ---------------- OUT OF SCOPE ----------------
            if intent == "out_of_scope":
                return {
                    "message": "I can help with home repair and inspection cost estimates.",
                    "thread_id": thread_id
                }

            # ---------------- NEGOTIATION ----------------
            if state.get("estimate") and intent in ["negotiation", "clarification"]:
                new_min, new_max, unclear = interpret_price_adjustment(
                    message,
                    state["estimate"]["min"],
                    state["estimate"]["max"]
                )

                if unclear:
                    return {
                        "message": (
                            "Got it. What price range do you feel is more realistic?\n"
                            "You can share a minimum, maximum, or full range."
                        ),
                        "thread_id": thread_id
                    }

                if new_min is not None:
                    state["estimate"]["min"] = new_min
                if new_max is not None:
                    state["estimate"]["max"] = new_max

                state["estimate"]["avg"] = round(
                    (state["estimate"]["min"] + state["estimate"]["max"]) / 2, 2
                )

                _active_threads[thread_id] = state

                return {
                    "message": (
                        f"Updated estimate for **{state['item']}** in **{state['location']}  {state['zipcode']}**:\n\n"
                        f"• Min: ${state['estimate']['min']}\n"
                        f"• Max: ${state['estimate']['max']}\n\n"
                        "Would you like to save this estimate? (yes/no)"
                    ),
                    "thread_id": thread_id
                }

            # ---------------- APPROVAL ----------------
            if state["status"] == "pending_approval":
                if intent == "approval_yes":
                    return self._save(thread_id)
                if intent == "approval_no":
                    _active_threads.pop(thread_id, None)
                    return {
                        "message": "Okay, I didn’t save it. You can ask for another estimate.",
                        "thread_id": thread_id
                    }

            # ---------------- COLLECT INPUTS ----------------
            if intent_data.get("item"):
                state["item"] = intent_data["item"]

            if intent_data.get("zipcode"):
                state["zipcode"] = intent_data["zipcode"]

            if not state["item"]:
                _active_threads[thread_id] = state
                return {"message": "What home repair or inspection item do you need?", "thread_id": thread_id}

            if not state["zipcode"]:
                _active_threads[thread_id] = state
                return {"message": "Please provide a valid 5-digit US ZIP code.", "thread_id": thread_id}

            if not is_valid_us_zip(state["zipcode"]):
                state["zipcode"] = None
                _active_threads[thread_id] = state
                return {
                    "message": "That ZIP code is not valid. Please enter a valid US ZIP.",
                    "thread_id": thread_id
                }

            # ---------------- LOCATION ----------------
            if not state["location"]:
                state["location"] = self._resolve_location(thread_id, state["zipcode"])

            # ---------------- HISTORICAL ----------------
            hist = get_cosmos_agent_service().search(
                f"{state['item']} {state['zipcode']}"
            ) or {}

            hist_data = hist.get("extracted_json") or {}
            approved_min = hist_data.get("last_approved_min")
            approved_max = hist_data.get("last_approved_max")

            # ---------------- MARKET (BING) ----------------
            estimate_prompt = f"""
Use Bing search ONLY.

Find multiple market price ranges for:
Item: "{state['item']}"
Location: "{state['location']}"

Return ONLY JSON:
{{ "min": number, "max": number }}
"""
            self.client.agents.messages.create(thread_id=thread_id, role="user", content=estimate_prompt)
            self.client.agents.runs.create_and_process(thread_id=thread_id, agent_id=self.agent_id)

            msg = next(
                m for m in self.client.agents.messages.list(thread_id=thread_id, order=ListSortOrder.DESCENDING)
                if m.role == "assistant"
            )

            data = json.loads(msg.text_messages[-1].text.value)

            state["estimate"] = {
                "min": data["min"],
                "max": data["max"],
                "avg": round((data["min"] + data["max"]) / 2, 2)
            }

            state["status"] = "pending_approval"
            state["created"] = datetime.utcnow().isoformat()
            _active_threads[thread_id] = state

            prev = ""
            if approved_min and approved_max:
                prev = f"Previous approved range:\n\n **${approved_min} – ${approved_max}**\n\n"

            return {
                "message": (
                    f"Estimate for **{state['item']}** in **{state['location']} {state['zipcode']}**:\n\n"
                    f"{prev}"
                    f"Market estimate:\n\n"
                    f"**${state['estimate']['min']} - ${state['estimate']['max']}**\n\n"
                    f"This range is based on recent market pricing from multiple contractors, "
                    f"local labor rates in {state['location']}, material costs, and typical job complexity.\n\n"
                    f"Would you like to save this estimate? (yes/no)"
                ),
                "thread_id": thread_id
            }

        except Exception as e:
            logger.exception("Chat error")
            raise APIError(str(e), 500, ErrorCodes.AGENT_ERROR)

    # --------------------------------------------------
    # Save
    # --------------------------------------------------
    def _save(self, thread_id: str):
        state = _active_threads.pop(thread_id)

        save_obj = {
            "id": thread_id,
            "thread_id": thread_id,
            "status": "approved",
            "type": "home_inspection",
            "message": state["item"],
            "zipcode": state["zipcode"],
            "currency": "USD",
            "min_estimate": state["estimate"]["min"],
            "max_estimate": state["estimate"]["max"],
            "avg_estimate": state["estimate"]["avg"],
            "dateOfCreation": datetime.utcnow().isoformat()
        }

        get_cosmos_service().save_flat_items([save_obj])

        return {
            "message": "Estimate saved successfully.",
            "thread_id": thread_id,
            "estimate": save_obj
        }


# --------------------------------------------------
# Singleton
# --------------------------------------------------
_chat_service = None

def get_chat_conversation_service() -> ChatConversationService:
    global _chat_service
    if not _chat_service:
        _chat_service = ChatConversationService()
    return _chat_service
