"""
Azure AI Agent Service - Complete Solution
Handles ALL estimation logic in one place - no separate services needed
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import time
from azure.ai.projects import AIProjectClient
from azure.identity import AzureCliCredential
from azure.ai.agents.models import ListSortOrder
from app.core.config import settings
from app.core.exceptions import APIError, ErrorCodes
from app.schemas.requests import EstimateItemResponse, EstimateModel, ItemDetail
import logging
import json
import re
import os

logger = logging.getLogger(__name__)

# Category mappings
CATEGORIES = {
    "Home inspection": ["Structure", "Roofing", "Exterior", "Electrical", "Heating System", 
                        "Cooling/Heat Pump System", "Insulation/Ventilation", "Plumbing", "Interior", "Pool/Spa"]
}


class AzureAgentService:
    """All-in-one service - handles estimation from request to response"""
    
    def __init__(self):
        self.agent_id = settings.AZURE_AI_AGENT_ID
        self.client = None
        self._initialize()
    
    def _initialize(self):
        """Initialize Azure AI client"""
        try:
            if settings.AZURE_TENANT_ID:
                os.environ['AZURE_TENANT_ID'] = settings.AZURE_TENANT_ID
            
            credential = AzureCliCredential(tenant_id=settings.AZURE_TENANT_ID or None)
            self.client = AIProjectClient(credential=credential, endpoint=settings.AZURE_AI_PROJECT_ENDPOINT)
            logger.info(f"Azure AI Agent ready: {self.agent_id}")
        except Exception as e:
            logger.error(f"Init failed: {e}")
            raise APIError(f"Failed to initialize: {e}", 500, ErrorCodes.AGENT_ERROR)
    
    def process_estimate_request(
        self,
        items: List[str],
        category: str,
        zipcode: str,
        # address: str,  # COMMENTED OUT - Testing removal
        username: str
        # use_bing: Optional[bool] = None  # COMMENTED OUT - Testing removal
    ) -> Dict[str, Any]:
        """
        Main entry point - process entire estimate request
        Single agent call for all items
        """
        start_time = time.time()
        logger.info(f"Processing {len(items)} items for {category} in {zipcode}")
        
        # Extract base category and specific subcategory if provided
        # Handle formats like "Home inspection - Structure"
        if " - " in category:
            base_category, specific_subcat = category.split(" - ", 1)
            base_category = base_category.strip()
            specific_subcat = specific_subcat.strip()
        else:
            base_category = category.strip()
            specific_subcat = None
        
        # Get subcategories for the base category
        subcategories = CATEGORIES.get(base_category, ["General"])
        
        # If a specific subcategory was provided, use it as default
        default_subcat = specific_subcat if specific_subcat else subcategories[0]
        
        # enable_bing = use_bing if use_bing is not None else settings.AZURE_AGENT_USE_BING  # COMMENTED OUT - Testing removal
        
        # Build prompt with all items
        items_text = "\n".join([f"{i+1}. {item}" for i, item in enumerate(items)])
        
        prompt = f"""You are a home repair cost estimator. Estimate costs for these {len(items)} repair items.

Location: {zipcode}
Category: {category}
Subcategories available: {', '.join(subcategories)}

Repair Items:
{items_text}

Use your knowledge to estimate repair costs.

Respond with ONLY a JSON array containing exactly {len(items)} objects. Each object must have:
- description: the repair item description
- subcategory: one from the list above
- min: minimum cost estimate (number)
- max: maximum cost estimate (number)
- note: brief explanation (under 50 chars)

Example:
[
  {{"description": "Foundation cracks", "subcategory": "Structure", "min": 2000, "max": 5000, "note": "Structural foundation repair"}},
  {{"description": "Settlement issues", "subcategory": "Structure", "min": 1500, "max": 4000, "note": "Foundation stabilization"}}
]

Return ONLY the JSON array."""
        
        try:
            # Single agent call
            agent = self.client.agents.get_agent(self.agent_id)
            thread = self.client.agents.threads.create()
            logger.info(f"Sending prompt to agent: {prompt}")
            self.client.agents.messages.create(thread_id=thread.id, role="user", content=prompt)
            
            # Run agent
            # if enable_bing:  # COMMENTED OUT - Testing removal
            #     run = self.client.agents.runs.create_and_process(thread_id=thread.id, agent_id=agent.id)
            # else:
            #     run = self.client.agents.runs.create_and_process(thread_id=thread.id, agent_id=agent.id, tools=[])
            run = self.client.agents.runs.create_and_process(thread_id=thread.id, agent_id=agent.id)  # Using default agent tools
            
            if run.status == "failed":
                elapsed_time = time.time() - start_time
                logger.error(f"Agent failed: {run.last_error} (Time: {elapsed_time:.2f}s)")
                raise APIError(
                    message=f"Agent execution failed: {run.last_error}",
                    status_code=500,
                    error_code=ErrorCodes.AGENT_ERROR,
                    details={"elapsed_time": f"{elapsed_time:.2f}s"}
                )
            
            # Get response
            messages = self.client.agents.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)
            response = next((m.text_messages[-1].text.value for m in messages 
                           if m.role == "assistant" and m.text_messages), None)
            
            if not response:
                elapsed_time = time.time() - start_time
                logger.error(f"No agent response (Time: {elapsed_time:.2f}s)")
                raise APIError(
                    message="No response received from agent",
                    status_code=500,
                    error_code=ErrorCodes.AGENT_ERROR,
                    details={"elapsed_time": f"{elapsed_time:.2f}s"}
                )
            
            # Parse and format response
            return self._format_response(response, items, category, default_subcat, 
                                        zipcode, username, start_time)
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"Processing failed: {e} (Time: {elapsed_time:.2f}s)")
            raise APIError(
                message=f"Request processing failed: {str(e)}",
                status_code=500,
                error_code=ErrorCodes.AGENT_ERROR,
                details={"elapsed_time": f"{elapsed_time:.2f}s", "error": str(e)}
            )
    
    def _format_response(self, agent_response: str, items: List[str], category: str, 
                        default_subcat: str, zipcode: str, username: str, start_time: float) -> Dict[str, Any]:
        """Parse agent response and format for API"""
        try:
            # Extract JSON array with improved parsing
            text = agent_response.strip()
            logger.info(f"Raw agent response length: {len(text)} chars")
            logger.info(f"Raw agent response: {text}")
            
            # Handle markdown code blocks
            if "```json" in text:
                # Extract content between ```json and ```
                parts = text.split("```json")
                if len(parts) > 1:
                    text = parts[1].split("```")[0].strip()
                    logger.info(f"Extracted from ```json block: {text}")
            elif "```" in text:
                # Generic code block
                parts = text.split("```")
                if len(parts) >= 2:
                    text = parts[1].replace("json", "").strip()
                    logger.info(f"Extracted from ``` block: {text}")
            
            # Find JSON array boundaries - be very precise
            start_idx = text.find("[")
            if start_idx == -1:
                logger.error(f"No opening bracket found. Full text: {text}")
                raise ValueError("No JSON array found in agent response")
            
            # Find the matching closing bracket by counting brackets
            bracket_count = 0
            end_idx = -1
            for i in range(start_idx, len(text)):
                if text[i] == '[':
                    bracket_count += 1
                elif text[i] == ']':
                    bracket_count -= 1
                    if bracket_count == 0:
                        end_idx = i + 1
                        break
            
            if end_idx == -1:
                logger.error(f"No matching closing bracket found. Text from start: {text[start_idx:start_idx+200]}")
                raise ValueError("Malformed JSON array - no closing bracket")
            
            # Extract ONLY the JSON array, ignore everything before and after
            json_text = text[start_idx:end_idx].strip()
            logger.info(f"Extracted JSON (length {len(json_text)} chars)")
            logger.info(f"JSON content: {json_text}")
            
            # Parse the JSON
            data = json.loads(json_text)
            
            # Validate structure
            if not isinstance(data, list):
                logger.error(f"Expected array but got {type(data).__name__}: {data}")
                raise ValueError(f"Agent returned {type(data).__name__} instead of array")
            
            if len(data) == 0:
                logger.error("Agent returned empty array")
                logger.error(f"Original JSON text was: {json_text}")
                logger.error(f"Full agent response was: {agent_response}")
                raise ValueError("Agent returned empty array - check agent prompt and configuration")
            
            # Check first item structure
            if not isinstance(data[0], dict):
                logger.error(f"Array items should be objects but got {type(data[0]).__name__}: {data[0]}")
                logger.error(f"Full data: {data}")
                raise ValueError(
                    f"Agent returned array of {type(data[0]).__name__} instead of objects. "
                    f"Sample: {str(data[0])[:100]}. Full response: {str(data)[:500]}"
                )
            
            # Build response items
            item_details = []
            messages = []
            
            for i, item_data in enumerate(data):
                if not isinstance(item_data, dict):
                    logger.warning(f"Skipping item {i+1}: expected object, got {type(item_data).__name__}")
                    continue
                
                min_cost = float(item_data.get("min", 500))
                max_cost = float(item_data.get("max", 2000))
                
                if min_cost >= max_cost:
                    min_cost, max_cost = max_cost, min_cost
                
                subcategory = item_data.get("subcategory", default_subcat)
                description = items[i] if i < len(items) else item_data.get("description", "")
                # Compose a 2-line note with zipcode, area, and reason
                agent_note = item_data.get("note", "").strip()
                location_info = f"Zipcode: {zipcode}"
                if not agent_note:
                    agent_note = "Estimated for this area based on local rates."
                # Compose the note: agent's note + location, max 2 lines
                # note = f"[{'Bing' if bing else 'AI'}] {agent_note} ({location_info})"  # COMMENTED OUT - bing param removed
                note = f"{agent_note} ({location_info})"
                # Ensure max 2 lines and not too long
                note_lines = note.splitlines()
                note = "\n".join(note_lines[:2])[:180]
                
                
                logger.info(f"Item {i+1} - Agent returned subcategory: '{item_data.get('subcategory')}', using: '{subcategory}'")
                
                item_details.append(ItemDetail(
                    description=description,
                    subcategory=subcategory,
                    estimate=EstimateModel(min=min_cost, max=max_cost),
                    note=note
                ))
                
                messages.append(f"Item {i+1}: {subcategory}")
            
            elapsed_time = time.time() - start_time
            logger.info(f"Success: {len(item_details)} items (Time: {elapsed_time:.2f}s)")
            
            messages.append(f"Execution time: {elapsed_time:.2f}s")
            
            return {
                "data": EstimateItemResponse(
                    category=category,
                    items=item_details,
                    dateofcreation=datetime.now().strftime("%Y-%m-%d"),
                    zipcode=zipcode,
                    # address="",  # Empty string for backward compatibility  # COMMENTED OUT - Testing removal
                    username=username
                ),
                "messages": messages,
                "errors": [],
                "execution_time": f"{elapsed_time:.2f}s"
            }
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"Parse failed: {e} (Time: {elapsed_time:.2f}s)")
            logger.error(f"Full agent response that failed to parse: {agent_response}")
            raise APIError(
                message=f"Failed to parse agent response: {str(e)}",
                status_code=500,
                error_code=ErrorCodes.AGENT_ERROR,
                details={
                    "elapsed_time": f"{elapsed_time:.2f}s", 
                    "parse_error": str(e),
                    "response_preview": agent_response[:500] if len(agent_response) > 500 else agent_response
                }
            )


# Simple singleton
_service = None

def get_azure_agent_service() -> AzureAgentService:
    """Get service instance"""
    global _service
    if _service is None:
        _service = AzureAgentService()
    return _service