from fastapi import HTTPException
"""
Save Endpoints
API routes for saving items to Cosmos DB
"""
from fastapi import APIRouter, Depends, Query
from app.schemas.requests import SaveItemsRequest, SaveItemsResponse, GetItemsResponse, SaveFlatItemInput, SaveCostEstimatesRequest, SaveCostEstimatesResponse, UpdateCostEstimateItem, UpdateCostEstimateRequest, UpdateCostEstimateResponse

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


@router.get("/search-items", response_model=GetItemsResponse, summary="Search items by message")
async def search_items(
    search_query: str = Query(..., description="Search query to filter items by message field"),
    offset: int = Query(default=0, ge=0, description="Number of items to skip"),
    limit: int = Query(default=10, ge=1, le=100, description="Maximum number of items to return"),
    cosmos_service: CosmosDBService = Depends(get_cosmos_service)
) -> GetItemsResponse:
    """
    Search items from Cosmos DB by message field with pagination support
    
    This endpoint performs a case-insensitive search on the message field
    and returns matching items with pagination.
    
    Args:
        search_query: Search text to find in message field (required)
        offset: Number of items to skip (default: 0)
        limit: Maximum items to return (default: 10, max: 100)
        cosmos_service: Injected CosmosDBService instance
        
    Returns:
        GetItemsResponse with paginated search results and metadata
        
    Example Response:
    ```json
    {
        "status": "success",
        "status_code": 200,
        "message": "Found 5 items matching 'plumbing'",
        "data": {
            "items": [...],
            "total_count": 5,
            "offset": 0,
            "limit": 10,
            "returned_count": 5
        }
    }
    ```
    """
    logger.info(f"Searching items with query='{search_query}', offset={offset}, limit={limit}")
    
    # Search items by message
    result = cosmos_service.search_items_by_message(
        search_query=search_query,
        offset=offset,
        limit=limit
    )
    
    message = f"Found {result['returned_count']} items matching '{search_query}' out of {result['total_count']} total"
    
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


@router.put("/update-item/{item_id}", summary="Update an existing cost estimate item", response_model=UpdateCostEstimateResponse)
async def update_item(
    item_id: str,
    zipcode: str = Query(..., description="Zipcode (partition key) for the item"),
    request: UpdateCostEstimateRequest = Body(..., description="Fields to update"),
    cosmos_service: CosmosDBService = Depends(get_cosmos_service)
) -> UpdateCostEstimateResponse:
    """
    Update an existing cost estimate item in Cosmos DB.
    
    This endpoint updates specified fields of an existing item while preserving
    immutable fields (id, zipcode, thread_id, type, currency). It guarantees that
    the record exists before updating.
    
    Args:
        item_id: Unique identifier of the item to update
        zipcode: Zipcode (partition key) for the item
        request: UpdateCostEstimateRequest containing fields to update
        cosmos_service: Injected CosmosDBService instance
        
    Returns:
        UpdateCostEstimateResponse with status and item_id
        
    Raises:
        HTTPException: 404 if item not found, 500 for other errors
        
    Example Request:
    ```json
    {
        "item": {
            "status": "approved",
            "min_estimate": 120.0,
            "max_estimate": 250.0,
            "message": "Updated cost estimate"
        }
    }
    ```
    """
    logger.info(f"Updating item {item_id} with zipcode {zipcode}")
    
    try:
        # Fetch existing item to ensure it exists
        existing_item = cosmos_service.get_item(item_id, zipcode)
        
        if existing_item is None:
            logger.warning(f"Item {item_id} not found for update")
            raise HTTPException(status_code=404, detail=f"Item with id '{item_id}' not found")
        
        # Remove Cosmos DB system fields (read-only fields that start with _)
        system_fields = ['_rid', '_self', '_etag', '_attachments', '_ts']
        item_data = {k: v for k, v in existing_item.items() if k not in system_fields}
        
        # Merge update fields into existing item
        update_data = request.item.dict(exclude_unset=True)
        
        # Update only the provided fields
        for key, value in update_data.items():
            if value is not None:
                item_data[key] = value
        
        logger.info(f"Merged update fields: {list(update_data.keys())}")
        
        # Upsert the updated item
        result = await cosmos_service.save_flat_items([item_data])
        
        if result["failed_count"] > 0:
            logger.error(f"Failed to update item {item_id}")
            raise HTTPException(status_code=500, detail="Failed to update item")
        
        logger.info(f"Successfully updated item {item_id}")
        return UpdateCostEstimateResponse(
            status="success",
            message="Item updated successfully",
            item_id=item_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error updating item {item_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
