from fastapi import HTTPException
"""
Save Endpoints
API routes for saving items to Cosmos DB
"""
from fastapi import APIRouter, Depends, Query
from app.schemas.requests import SaveItemsRequest, SaveItemsResponse, GetItemsResponse, SaveFlatItemInput, SaveCostEstimatesRequest, SaveCostEstimatesResponse

# New endpoint for saving flat items
from fastapi import Body

from app.services.cosmos_db_service import get_cosmos_service, CosmosDBService
import logging


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/save-items", summary="Save cost estimate items", response_model=SaveCostEstimatesResponse)
async def save_flat_items(
    request: SaveCostEstimatesRequest = Body(..., description="Cost estimates request with items array"),
    cosmos_service: CosmosDBService = Depends(get_cosmos_service)
) -> SaveCostEstimatesResponse:
    """
    Persists one or more cost estimate records into Cosmos DB.
    
    This endpoint accepts a request body with an 'items' array containing cost estimates,
    saves them to Azure Cosmos DB, and returns the saved items with operation status.
    
    Args:
        request: SaveCostEstimatesRequest containing list of items to save
        cosmos_service: Injected CosmosDBService instance
        
    Returns:
        SaveCostEstimatesResponse with status, statusCode, message, and estimatedItems
    """
    items = request.items
    logger.info(f"Saving {len(items)} cost estimate items to Cosmos DB")
    
    result = await cosmos_service.save_flat_items([item.dict() for item in items])
    
    return SaveCostEstimatesResponse(
        status="success" if result["failed_count"] == 0 else "partial_success",
        saved_count=result["saved_count"]
    )


@router.get("/items", response_model=GetItemsResponse, summary="Get all items with pagination")
async def get_items(
    offset: int = Query(default=0, ge=0, description="Number of items to skip"),
    limit: int = Query(default=10, ge=1, le=100, description="Maximum number of items to return"),
    cosmos_service: CosmosDBService = Depends(get_cosmos_service)
) -> GetItemsResponse:
    """
    Retrieve all items from Cosmos DB with pagination support
    
    This endpoint fetches items with offset and limit for pagination control.
    Items are ordered by creation timestamp (newest first).
    
    Args:
        offset: Number of items to skip (default: 0)
        limit: Maximum items to return (default: 10, max: 100)
        cosmos_service: Injected CosmosDBService instance
        
    Returns:
        GetItemsResponse with paginated items and metadata
        
    Example Response:
    ```json
    {
        "status": "success",
        "status_code": 200,
        "message": "Retrieved 10 items",
        "data": {
            "items": [...],
            "total_count": 45,
            "offset": 0,
            "limit": 10,
            "returned_count": 10
        }
    }
    ```
    """
    logger.info(f"Fetching items with offset={offset}, limit={limit}")
    
    # Get paginated items
    result = cosmos_service.get_all_items(offset=offset, limit=limit)
    
    message = f"Retrieved {result['returned_count']} items out of {result['total_count']} total"
    
    return GetItemsResponse(
        data=result,
        status="success",
        status_code=200,
        message=message
    )


@router.delete("/items/{item_id}", summary="Delete an item from Cosmos DB")
async def delete_item(
    item_id: str,
    zipcode: str = Query(..., description="Zipcode (partition key) for the item"),
    cosmos_service: CosmosDBService = Depends(get_cosmos_service)
) -> dict:
    """
    Delete a single item from Cosmos DB by id and zipcode (partition key)
    """
    result = cosmos_service.delete_item(item_id, zipcode)
    if result["status"] == "success":
        return {"status": "success", "message": result["message"]}
    elif result["status"] == "not_found":
        raise HTTPException(status_code=404, detail=result["message"])
    else:
        raise HTTPException(status_code=500, detail=result["message"])
