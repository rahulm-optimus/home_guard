"""Chat Conversation Service with Azure AI Agent"""
from typing import Dict, Any, Optional
from azure.ai.projects import AIProjectClient
from azure.identity import AzureCliCredential
from azure.ai.agents.models import ListSortOrder, FunctionTool
from app.core.config import settings
from app.core.exceptions import APIError, ErrorCodes
import logging
import json
import threading
import requests

logger = logging.getLogger(__name__)

# Global client instances for thread safety
_chat_client_lock = threading.Lock()
_chat_shared_credential = None
_chat_shared_client = None
_active_threads: Dict[str, str] = {}  # Store thread_id mapping


class ChatConversationService:
    """Service to handle chat conversations with Azure AI Agent"""
    
    def __init__(self):
        self.agent_id = settings.AZURE_CHAT_AGENT_ID
        self._initialize_client()
        self._register_functions()
    
    def _initialize_client(self):
        """Initialize Azure AI client with thread-safe singleton pattern"""
        global _chat_shared_credential, _chat_shared_client
        
        try:
            with _chat_client_lock:
                if _chat_shared_credential is None:
                    import os
                    if settings.AZURE_TENANT_ID:
                        os.environ['AZURE_TENANT_ID'] = settings.AZURE_TENANT_ID
                    _chat_shared_credential = AzureCliCredential(tenant_id=settings.AZURE_TENANT_ID or None)
                    logger.info("Azure CLI credential initialized for chat")
                
                if _chat_shared_client is None:
                    _chat_shared_client = AIProjectClient(
                        credential=_chat_shared_credential, 
                        endpoint=settings.AZURE_AI_PROJECT_ENDPOINT
                    )
                    logger.info(f"Azure AI Chat Agent ready: {self.agent_id}")
                
                self.ai_client = _chat_shared_client
        except Exception as e:
            logger.error(f"Chat agent init failed: {e}")
            raise APIError(f"Failed to initialize chat agent: {e}", 500, ErrorCodes.AGENT_ERROR)
    
    def _register_functions(self):
        """Register cost estimation function for the agent to call"""
        self.functions = {
            "get_cost_estimate": {
                "type": "function",
                "function": {
                    "name": "get_cost_estimate",
                    "description": "Get cost estimates for home inspection items. Call this when user provides repair/inspection descriptions and a zipcode.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of repair/inspection item descriptions"
                            },
                            "category": {
                                "type": "string",
                                "description": "Category for the items (e.g., 'General Repairs')"
                            },
                            "zipcode": {
                                "type": "string",
                                "description": "5-digit postal/ZIP code for location-based pricing"
                            },
                            "username": {
                                "type": "string",
                                "description": "Username for tracking (default: 'chatbot_user')"
                            }
                        },
                        "required": ["query", "zipcode"]
                    }
                }
            }
        }
    
    def _call_cost_estimate_api(self, query: list, category: str, zipcode: str, username: str = "chatbot_user") -> Dict[str, Any]:
        """Call the internal cost-estimate endpoint"""
        try:
            url = f"http://localhost:{settings.PORT or 5000}/api/v1/cost-estimate"
            payload = {
                "query": query,
                "category": category or "General Repairs",
                "zipcode": zipcode,
                "username": username
            }
            
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to call cost-estimate API: {e}")
            return {"error": str(e), "status": "failed"}
    
    def _handle_function_call(self, function_name: str, arguments: str) -> str:
        """Handle function calls from the agent"""
        try:
            args = json.loads(arguments)
            
            if function_name == "get_cost_estimate":
                result = self._call_cost_estimate_api(
                    query=args.get("query", []),
                    category=args.get("category", "General Repairs"),
                    zipcode=args.get("zipcode"),
                    username=args.get("username", "chatbot_user")
                )
                return json.dumps(result)
            
            return json.dumps({"error": f"Unknown function: {function_name}"})
        except Exception as e:
            logger.error(f"Function call error: {e}")
            return json.dumps({"error": str(e)})
    
    def chat(self, message: str, thread_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a chat message and return response
        
        Args:
            message: User's message
            thread_id: Optional existing thread ID for conversation continuity
        
        Returns:
            Dict with 'message' (bot response) and 'thread_id'
        """
        try:
            # Create or retrieve thread
            if thread_id and thread_id in _active_threads:
                thread = self.ai_client.agents.threads.get(thread_id)
                logger.info(f"Using existing thread: {thread_id}")
            else:
                thread = self.ai_client.agents.threads.create()
                thread_id = thread.id
                _active_threads[thread_id] = thread_id
                logger.info(f"Created new thread: {thread_id}")
            
            # Add system instructions about cost estimation
            system_message = """You are a home inspection assistant. When users ask about cost estimates:
1. Ask for zipcode if not provided
2. Ask for description of the repair/inspection item if not clear
3. Once you have both, call the get_cost_estimate function
4. Present the results conversationally, including:
   - Category
   - Each item's description, subcategory, min/max estimate, and reasoning (from 'note')
5. NEVER make up prices - only use data from get_cost_estimate function
6. Be helpful and conversational"""
            
            # Add user message
            self.ai_client.agents.messages.create(
                thread_id=thread_id,
                role="user",
                content=message
            )
            
            # Create and configure the agent with function calling
            agent = self.ai_client.agents.get_agent(self.agent_id)
            
            # Run the agent with function tools
            run = self.ai_client.agents.runs.create_and_process(
                thread_id=thread_id,
                agent_id=agent.id
            )
            
            # Handle function calls if any
            while run.status == "requires_action":
                tool_calls = run.required_action.submit_tool_outputs.tool_calls
                tool_outputs = []
                
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    arguments = tool_call.function.arguments
                    
                    logger.info(f"Agent calling function: {function_name} with args: {arguments}")
                    output = self._handle_function_call(function_name, arguments)
                    
                    tool_outputs.append({
                        "tool_call_id": tool_call.id,
                        "output": output
                    })
                
                # Submit tool outputs and continue
                run = self.ai_client.agents.runs.submit_tool_outputs_and_process(
                    thread_id=thread_id,
                    run_id=run.id,
                    tool_outputs=tool_outputs
                )
            
            if run.status == "failed":
                raise APIError(f"Agent run failed: {run.last_error}", 500, ErrorCodes.AGENT_ERROR)
            
            # Get the response
            messages = self.ai_client.agents.messages.list(
                thread_id=thread_id,
                order=ListSortOrder.DESCENDING,
                limit=1
            )
            
            response_text = None
            for msg in messages:
                if msg.role == "assistant" and msg.text_messages:
                    response_text = msg.text_messages[-1].text.value
                    break
            
            if not response_text:
                raise APIError("No response from agent", 500, ErrorCodes.AGENT_ERROR)
            
            return {
                "message": response_text,
                "thread_id": thread_id,
                "status": "success"
            }
            
        except APIError:
            raise
        except Exception as e:
            logger.error(f"Chat error: {e}")
            raise APIError(f"Chat failed: {e}", 500, ErrorCodes.AGENT_ERROR)


_chat_service = None
_chat_service_lock = threading.Lock()


def get_chat_conversation_service() -> ChatConversationService:
    """Thread-safe singleton getter for Chat Conversation Service"""
    global _chat_service
    if _chat_service is None:
        with _chat_service_lock:
            if _chat_service is None:
                _chat_service = ChatConversationService()
    return _chat_service