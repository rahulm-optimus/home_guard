
from pydantic import BaseModel
from typing import Optional, Any, List

class SaveCostEstimateItem(BaseModel):
    status: str
    thread_id: str
    dateOfCreation: str
    type: str
    message: str
    currency: str
    min_estimate: float
    max_estimate: float
    cluster_name: str  # Changed: removed zipcodes array, kept only cluster_name

class SaveCostEstimatesRequest(BaseModel):
    items: List[SaveCostEstimateItem]

class SaveCostEstimatesResponse(BaseModel):
    status: str
    saved_count: int

class UpdateCostEstimateItem(BaseModel):
    id: Optional[str] = None
    status: Optional[str] = None
    thread_id: Optional[str] = None
    dateOfCreation: Optional[str] = None
    type: Optional[str] = None
    message: Optional[str] = None
    currency: Optional[str] = None
    min_estimate: Optional[float] = None
    max_estimate: Optional[float] = None
    estimate_scope: Optional[str] = None

class UpdateCostEstimateRequest(BaseModel):
    item: UpdateCostEstimateItem

class UpdateCostEstimateResponse(BaseModel):
    status: str
    message: str
    item_id: str

class GetItemsResponse(BaseModel):
    data: Any
    status: str
    status_code: int
    message: str
