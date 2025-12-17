"""
New Estimate Service - Simplified with Parallel Processing
No database cache - agent is fast enough with parallel execution
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.services.azure_agent_service import get_azure_agent_service, AzureAgentService
from app.utils.llm import get_llm
from langchain_core.messages import SystemMessage, HumanMessage
from app.schemas.requests import EstimateItemResponse, EstimateModel, ItemDetail
import logging
import threading

logger = logging.getLogger(__name__)

CATEGORIES = {
    "Home inspection": ["Structure", "Roofing", "Exterior", "Electrical", "Heating System", 
                        "Cooling/Heat Pump System", "Insulation/Ventilation", "Plumbing", "Interior", "Pool/Spa"],
    "Termite inspection": ["Insect related findings", "Fungus damage", "Wood destroying organisms"],
    "Roof inspection": ["Roof related findings"],
    "Sewer inspection": ["Sewer related findings"],
    "NHD Inspection": ["NHD related findings"]
}


class NewEstimateService:
    
    def __init__(self, azure_agent_service: AzureAgentService):
        self.agent = azure_agent_service
        self.llm = get_llm()
    
    def _classify(self, category: str, description: str) -> str:
        """Quick subcategory classification"""
        subcats = CATEGORIES.get(category, ["Structure"])
        if len(subcats) == 1:
            return subcats[0]
        
        try:
            prompt = f"Category: {category}\nDescription: {description}\nChoose one: {', '.join(subcats)}\nReturn ONLY the name."
            response = self.llm.invoke([SystemMessage(content=prompt), HumanMessage(content=description)])
            result = response.content.strip()
            return result if result in subcats else subcats[0]
        except Exception as e:
            logger.warning(f"Classification failed: {e}")
            return subcats[0]
    
    def _process_single_item(self, idx: int, item: str, category: str, zipcode: str, use_bing: Optional[bool]) -> Dict[str, Any]:
        """Process single item in parallel thread - returns result dict"""
        try:
            if not item or not item.strip():
                return {"error": f"Item {idx}: Empty description", "success": False}
            
            item = item.strip()
            logger.debug(f"[Worker-{idx}] Processing: {item[:50]}...")
            
            # Classify subcategory
            subcategory = self._classify(category, item)
            
            # Get estimate from agent (no cache - agent is fast enough)
            result = self.agent.get_cost_estimate(item, subcategory, zipcode, use_bing)
            
            return {
                "success": True,
                "item": ItemDetail(
                    description=item,
                    subcategory=subcategory,
                    estimate=EstimateModel(min=result['min'], max=result['max']),
                    note=result['note']
                ),
                "message": f"Item {idx}: {subcategory}"
            }
        except Exception as e:
            logger.error(f"Item {idx} failed: {e}")
            return {"error": f"Item {idx}: {str(e)}", "success": False}
    
    def process_estimate_request(self, items: List[str], category: str, zipcode: str, 
                                address: str, username: str, use_bing: Optional[bool] = None) -> Dict[str, Any]:
        """Process items in parallel for faster response"""
        logger.info(f"Processing {len(items)} items for {category} in {zipcode} (parallel)")
        
        results = []
        errors_list = []
        
        # Process items in parallel using ThreadPoolExecutor
        max_workers = min(len(items), 4)  # Max 4 concurrent requests to avoid overwhelming Azure
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="EstimateWorker") as executor:
            futures = {executor.submit(self._process_single_item, idx, item, category, zipcode, use_bing): idx 
                      for idx, item in enumerate(items, 1)}
            
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as e:
                    logger.error(f"Future failed: {e}")
                    results.append({"error": str(e), "success": False})
        
        # Sort by original order
        results.sort(key=lambda x: int(x.get("message", "Item 0:").split(":")[0].replace("Item ", "")) 
                    if x.get("success") else 0)
        
        # Separate successes and errors
        item_details = [r["item"] for r in results if r.get("success")]
        messages = [r["message"] for r in results if r.get("success")]
        errors = [r["error"] for r in results if not r.get("success")]
        
        logger.info(f"Completed: {len(item_details)} success, {len(errors)} errors")
        
        return {
            "data": EstimateItemResponse(category=category, items=item_details, 
                                        dateofcreation=datetime.now().strftime("%Y-%m-%d"),
                                        zipcode=zipcode, address=address, username=username),
            "messages": messages,
            "errors": errors
        }


_new_estimate_service = None
_service_lock = threading.Lock()


def get_new_estimate_service() -> NewEstimateService:
    """Thread-safe singleton getter for NewEstimateService"""
    global _new_estimate_service
    
    if _new_estimate_service is None:
        with _service_lock:
            if _new_estimate_service is None:  # Double-check pattern
                azure_agent_service = get_azure_agent_service()
                _new_estimate_service = NewEstimateService(azure_agent_service)
                logger.info("NewEstimateService singleton initialized")
    
    return _new_estimate_service
