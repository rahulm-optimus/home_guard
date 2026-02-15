"""
Request/Response Schemas (DTOs)
Pydantic models for API request and response validation
"""
from pydantic import BaseModel, Field
from typing import Optional, Any
from enum import IntEnum
# ============ Request Schemas ============


# class SaveFlatItemInput(BaseModel):
#     """Input model for saving a flat item (new Cosmos structure)"""
#     status: str
#     thread_id: str
#     dateOfCreation: str
#     type: str
#     message: str
#     currency: str
#     min_estimate: float
#     max_estimate: float
#     zipcode: str
#     clusterId: Optional[str] = Field(None, description="Optional cluster ID reference")


# class SaveCostEstimatesRequest(BaseModel):
#     """Request wrapper for saving cost estimates"""
#     items: list[SaveFlatItemInput] = Field(..., min_items=1, description="List of cost estimate records to save")


# class SaveCostEstimatesResponse(BaseModel):
#     """Response from save cost estimates endpoint"""
#     status: str = Field(..., description="Operation status", example="success")
#     saved_count: int = Field(..., description="Number of items saved successfully", example=2)


class UpdateCostEstimateItem(BaseModel):
    """Input model for updating an existing cost estimate item (only updatable fields)"""
    status: Optional[str] = Field(None, description="Updated status")
    dateOfCreation: Optional[str] = Field(None, description="Updated creation date")
    message: Optional[str] = Field(None, description="Updated message")
    min_estimate: Optional[float] = Field(None, description="Updated minimum estimate")
    max_estimate: Optional[float] = Field(None, description="Updated maximum estimate")
    estimate_scope: Optional[str] = Field(None, description="Updated estimate scope (e.g., labor_only)")


class UpdateCostEstimateRequest(BaseModel):
    """Request wrapper for updating a cost estimate item"""
    item: UpdateCostEstimateItem = Field(..., description="Fields to update")


class UpdateCostEstimateResponse(BaseModel):
    """Response from update cost estimate endpoint"""
    status: str = Field(..., description="Operation status", example="success")
    message: str = Field(..., description="Operation message", example="Item updated successfully")
    item_id: str = Field(..., description="ID of the updated item")


# ============ Cluster Schemas ============

class CreateClusterRequest(BaseModel):
    """Request for creating a new zipcode cluster"""
    name: str = Field(..., min_length=1, description="Display name of the cluster")
    zipcodes: list[str] = Field(..., min_items=1, description="List of zipcodes in this cluster")
    description: Optional[str] = Field(None, description="Optional description of the cluster")


class UpdateClusterRequest(BaseModel):
    """Request for updating an existing zipcode cluster"""
    name: Optional[str] = Field(None, min_length=1, description="Updated display name")
    zipcodes: Optional[list[str]] = Field(None, min_items=1, description="Updated list of zipcodes")
    description: Optional[str] = Field(None, description="Updated description")


class ClusterResponse(BaseModel):
    """Response containing cluster data"""
    status: str = Field(..., description="Operation status", example="success")
    message: str = Field(..., description="Operation message")
    data: Optional[dict] = Field(None, description="Cluster data")


class GetClustersResponse(BaseModel):
    """Response from get clusters endpoint"""
    status: str = Field(..., description="Operation status")
    status_code: int = Field(..., description="HTTP status code")
    message: str = Field(..., description="Response message")
    data: dict = Field(..., description="Paginated clusters with metadata")


# # ============ Request Schemas ============

# class QueryInput(BaseModel):
#     """Input model for query requests"""
#     query: str = Field(..., min_length=1, description="User query string")


# class EstimateQueryInput(BaseModel):
#     """Input model for estimate requests"""
#     query: list[str] = Field(..., min_items=1, description="List of items to estimate")
#     category: str = Field(..., description="Category for all items")
#     zipcode: str = Field(..., min_length=5, max_length=10, description="Zipcode for location-based estimates")
#     # address: str = Field(..., description="Full address for location-based estimates")  # COMMENTED OUT - Testing removal
#     username: str = Field(..., description="Username/owner of the inspection")


# # ============ Response Schemas ============

# class ErrorDetail(BaseModel):
#     """Error detail structure"""
#     code: str
#     message: str
#     details: dict = {}


# class BaseResponse(BaseModel):
#     """Base response structure for all API responses"""
#     status: str
#     status_code: int
#     message: str


# class ErrorResponse(BaseResponse):
#     """Error response structure"""
#     error: ErrorDetail
#     data: dict = {}


# class AgentResponse(BaseResponse):
#     """Response from the agent endpoint"""
#     data: dict = Field(..., description="Agent response data including query results")


# class SearchResponse(BaseResponse):
#     """Response from the search endpoint"""
#     data: dict = Field(..., description="Search results")


# # ============ Estimate Models ============

# class AddressInfo(BaseModel):
#     """Address information"""
#     address: str = Field(..., description="Full address")


# class EstimateModel(BaseModel):
#     """Estimate range model"""
#     min: float = Field(..., description="Minimum estimate")
#     max: float = Field(..., description="Maximum estimate")


# class ItemDetail(BaseModel):
#     """Individual item details"""
#     description: str = Field(..., description="Item description")
#     subcategory: str = Field(..., description="Subcategory")
#     estimate: EstimateModel = Field(..., description="Estimate range")
#     note: str = Field(..., description="Additional notes")


# class EstimateItemResponse(BaseModel):
#     """Estimate response with items array"""
#     category: str = Field(..., description="Category")
#     items: list[ItemDetail] = Field(..., description="List of item details")
#     dateofcreation: str = Field(..., description="Date of creation (YYYY-MM-DD)")
#     zipcode: str = Field(..., description="Zipcode")
#     # address: str = Field(..., description="Full address")  # COMMENTED OUT - Testing removal
#     username: str = Field(..., description="Username/owner")


# class EstimateResponse(BaseResponse):
#     """Response from the estimate agent endpoint"""
#     data: EstimateItemResponse = Field(..., description="Estimate data with items")
#     message: list[str] = Field(..., description="Messages for each item")
#     error: list[str] = Field(default_factory=list, description="Errors if any")


# # ============ Data Transfer Objects ============

# class AgentExecutionResult(BaseModel):
#     """Internal DTO for agent execution results"""
#     original_query: str
#     trimmed_query: str
#     used_search: bool
#     search_results: Optional[str] = None
#     response: str


# class SearchResult(BaseModel):
#     """Single search result item"""
#     name: str
#     url: str
#     snippet: str


# class BingSearchResults(BaseModel):
#     """Bing search results collection"""
#     query: str
#     total_results: int
#     search_results: list[SearchResult]


# # ============ Save Item Schemas ============

# class SaveItemInput(BaseModel):
#     """Input model for saving an item"""
#     id: str = Field(..., description="Unique item identifier")
#     category: str = Field(..., description="Category")
#     items: list[ItemDetail] = Field(..., description="List of item details")
#     dateofcreation: str = Field(..., description="Date of creation (YYYY-MM-DD)")
#     zipcode: str = Field(..., description="Zipcode (partition key)")
#     # address: str = Field(..., description="Full address")  # COMMENTED OUT - Testing removal
#     username: str = Field(..., description="Username/owner")
#     status: str = Field(default="pending", description="Item status")
#     clusterId: Optional[str] = Field(None, description="Optional cluster ID reference")
    
#     model_config = {
#         "json_schema_extra": {
#             "examples": [
#                 {
#                     "id": "inspection-001",
#                     "category": "Termite inspection",
#                     "items": [
#                         {
#                             "description": "Fungus damage was noted to the rafter tail as indicated",
#                             "subcategory": "Fungus damage",
#                             "estimate": {
#                                 "min": 800.0,
#                                 "max": 5000.0
#                             },
#                             "note": "Fungus/rot damage repair costs $800-$5,000."
#                         },
#                         {
#                             "description": "Fungus damage was noted to the roof sheathing as indicated",
#                             "subcategory": "Fungus damage",
#                             "estimate": {
#                                 "min": 800.0,
#                                 "max": 5000.0
#                             },
#                             "note": "Fungus/rot damage repair costs $800-$5,000."
#                         }
#                     ],
#                     "dateofcreation": "2025-12-12",
#                     "zipcode": "94551",
#                     "address": "2623 Anywhere Street, Hometown, CA 94551",
#                     "username": "John doe",
#                     "status": "pending"
#                 }
#             ]
#         }
#     }


# class SaveItemsRequest(BaseModel):
#     """Request to save multiple items"""
#     items: list[SaveItemInput] = Field(..., min_items=1, description="List of items to save")


# class SaveItemsResponse(BaseResponse):
#     """Response from save items endpoint"""
#     data: dict = Field(..., description="Save operation results")


# class GetItemsResponse(BaseResponse):
#     """Response from get items endpoint"""
#     data: dict = Field(..., description="Paginated items with metadata")



"""
Request/Response Schemas (DTOs)
Pydantic models for API request and response validation
"""
from pydantic import BaseModel, Field
from typing import Optional, Any
from enum import IntEnum

# ============ Enums ============


class CostEstStatus(IntEnum):
    """Cost Estimate Status mapping for SQL Server CostEstStatusID field"""
    LEAVE_ALONE = 0
    NEED_ESTIMATE = 10
    ESTIMATE_COMPLETE = 20
    EDIT_INPUT = 30
    AI_ANALYZED = 40
    
    @classmethod
    def from_string(cls, status_str: str) -> int:
        """Convert string status to integer ID"""
        mapping = {
            "leave_alone": cls.LEAVE_ALONE,
            "need_estimate": cls.NEED_ESTIMATE,
            "estimate_complete": cls.ESTIMATE_COMPLETE,
            "edit_input": cls.EDIT_INPUT,
            "ai_analyzed": cls.AI_ANALYZED,
            # Common aliases
            "approved": cls.ESTIMATE_COMPLETE,
            "pending": cls.NEED_ESTIMATE,
            "completed": cls.ESTIMATE_COMPLETE,
        }
        return mapping.get(status_str.lower(), cls.LEAVE_ALONE)
    
    @classmethod
    def to_string(cls, status_id: int) -> str:
        """Convert integer ID to string status"""
        mapping = {
            cls.LEAVE_ALONE: "leave_alone",
            cls.NEED_ESTIMATE: "need_estimate",
            cls.ESTIMATE_COMPLETE: "estimate_complete",
            cls.EDIT_INPUT: "edit_input",
            cls.AI_ANALYZED: "ai_analyzed",
        }
        return mapping.get(status_id, "leave_alone")


# ============ Request Schemas ============


class SaveFlatItemInput(BaseModel):
    """Input model for saving a flat item (new Cosmos structure)"""
    status: str
    thread_id: str
    dateOfCreation: str
    type: str
    message: str
    currency: str
    min_estimate: float
    max_estimate: float
    zipcode: str


class SaveCostEstimatesRequest(BaseModel):
    """Request wrapper for saving cost estimates"""
    items: list[SaveFlatItemInput] = Field(..., min_items=1, description="List of cost estimate records to save")


class SaveCostEstimatesResponse(BaseModel):
    """Response from save cost estimates endpoint"""
    status: str = Field(..., description="Operation status", example="success")
    saved_count: int = Field(..., description="Number of items saved successfully", example=2)


# ============ Request Schemas ============

class QueryInput(BaseModel):
    """Input model for query requests"""
    query: str = Field(..., min_length=1, description="User query string")


class EstimateQueryInput(BaseModel):
    """Input model for estimate requests"""
    query: list[str] = Field(..., min_items=1, description="List of items to estimate")
    category: str = Field(..., description="Category for all items")
    zipcode: str = Field(..., min_length=5, max_length=10, description="Zipcode for location-based estimates")
    # address: str = Field(..., description="Full address for location-based estimates")  # COMMENTED OUT - Testing removal
    username: str = Field(..., description="Username/owner of the inspection")


# ============ Response Schemas ============

class ErrorDetail(BaseModel):
    """Error detail structure"""
    code: str
    message: str
    details: dict = {}


class BaseResponse(BaseModel):
    """Base response structure for all API responses"""
    status: str
    status_code: int
    message: str


class ErrorResponse(BaseResponse):
    """Error response structure"""
    error: ErrorDetail
    data: dict = {}


class AgentResponse(BaseResponse):
    """Response from the agent endpoint"""
    data: dict = Field(..., description="Agent response data including query results")


class SearchResponse(BaseResponse):
    """Response from the search endpoint"""
    data: dict = Field(..., description="Search results")


# ============ Estimate Models ============

class AddressInfo(BaseModel):
    """Address information"""
    address: str = Field(..., description="Full address")


class EstimateModel(BaseModel):
    """Estimate range model"""
    min: float = Field(..., description="Minimum estimate")
    max: float = Field(..., description="Maximum estimate")


class ItemDetail(BaseModel):
    """Individual item details"""
    description: str = Field(..., description="Item description")
    subcategory: str = Field(..., description="Subcategory")
    estimate: EstimateModel = Field(..., description="Estimate range")
    note: str = Field(..., description="Additional notes")


class EstimateItemResponse(BaseModel):
    """Estimate response with items array"""
    category: str = Field(..., description="Category")
    items: list[ItemDetail] = Field(..., description="List of item details")
    dateofcreation: str = Field(..., description="Date of creation (YYYY-MM-DD)")
    zipcode: str = Field(..., description="Zipcode")
    # address: str = Field(..., description="Full address")  # COMMENTED OUT - Testing removal
    username: str = Field(..., description="Username/owner")


class EstimateResponse(BaseResponse):
    """Response from the estimate agent endpoint"""
    data: EstimateItemResponse = Field(..., description="Estimate data with items")
    message: list[str] = Field(..., description="Messages for each item")
    error: list[str] = Field(default_factory=list, description="Errors if any")


# ============ Data Transfer Objects ============

class AgentExecutionResult(BaseModel):
    """Internal DTO for agent execution results"""
    original_query: str
    trimmed_query: str
    used_search: bool
    search_results: Optional[str] = None
    response: str


class SearchResult(BaseModel):
    """Single search result item"""
    name: str
    url: str
    snippet: str


class BingSearchResults(BaseModel):
    """Bing search results collection"""
    query: str
    total_results: int
    search_results: list[SearchResult]


# ============ Save Item Schemas ============

class SaveItemInput(BaseModel):
    """Input model for saving an item"""
    id: str = Field(..., description="Unique item identifier")
    category: str = Field(..., description="Category")
    items: list[ItemDetail] = Field(..., description="List of item details")
    dateofcreation: str = Field(..., description="Date of creation (YYYY-MM-DD)")
    zipcode: str = Field(..., description="Zipcode (partition key)")
    # address: str = Field(..., description="Full address")  # COMMENTED OUT - Testing removal
    username: str = Field(..., description="Username/owner")
    status: str = Field(default="pending", description="Item status")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "inspection-001",
                    "category": "Termite inspection",
                    "items": [
                        {
                            "description": "Fungus damage was noted to the rafter tail as indicated",
                            "subcategory": "Fungus damage",
                            "estimate": {
                                "min": 800.0,
                                "max": 5000.0
                            },
                            "note": "Fungus/rot damage repair costs $800-$5,000."
                        },
                        {
                            "description": "Fungus damage was noted to the roof sheathing as indicated",
                            "subcategory": "Fungus damage",
                            "estimate": {
                                "min": 800.0,
                                "max": 5000.0
                            },
                            "note": "Fungus/rot damage repair costs $800-$5,000."
                        }
                    ],
                    "dateofcreation": "2025-12-12",
                    "zipcode": "94551",
                    "address": "2623 Anywhere Street, Hometown, CA 94551",
                    "username": "John doe",
                    "status": "pending"
                }
            ]
        }
    }


class SaveItemsRequest(BaseModel):
    """Request to save multiple items"""
    items: list[SaveItemInput] = Field(..., min_items=1, description="List of items to save")


class SaveItemsResponse(BaseResponse):
    """Response from save items endpoint"""
    data: dict = Field(..., description="Save operation results")


class GetItemsResponse(BaseResponse):
    """Response from get items endpoint"""
    data: dict = Field(..., description="Paginated items with metadata")
