"""
Save Endpoints
API routes for saving items to Cosmos DB
"""
from fastapi import APIRouter, Depends, Query
from app.schemas.requests import SaveItemsRequest, SaveItemsResponse, GetItemsResponse
from app.services.cosmos_service import get_cosmos_service, CosmosDBService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/save-items", response_model=SaveItemsResponse, summary="Save items to Cosmos DB")
async def save_items(
    request: SaveItemsRequest,
    cosmos_service: CosmosDBService = Depends(get_cosmos_service)
) -> SaveItemsResponse:
    """
    Save multiple items to Azure Cosmos DB
    
    Args:
        request: SaveItemsRequest containing list of items
        cosmos_service: Injected CosmosDBService instance
        
    Returns:
        SaveItemsResponse with save operation results
        
    Example Request:
    ```json
    {
        "items": [
            {
                "id": "item-1",
                "category": "Home inspection",
                "items": [
                    {
                        "description": "Fix leaking kitchen faucet",
                        "subcategory": "Plumbing",
                        "estimate": {
                            "min": 150.0,
                            "max": 1500.0
                        },
                        "note": "Plumbing repair estimate"
                    },
                    {
                        "description": "Repair broken window",
                        "subcategory": "Interior",
                        "estimate": {
                            "min": 300.0,
                            "max": 800.0
                        },
                        "note": "Interior window repair"
                    }
                ],
                "dateofcreation": "2025-12-12",
                "zipcode": "94551",
                "address": "2623 Anywhere Street, Hometown, CA 94551",
                "username": "john_doe",
                "status": "pending"
            }
        ]
    }
    ```
    
    Example Response:
    ```json
    {
        "status": "success",
        "status_code": 200,
        "message": "Successfully saved all 1 items",
        "data": {
            "total_items": 1,
            "saved_count": 1,
            "failed_count": 0,
            "saved_items": [
                {
                    "id": "item-1",
                    "status": "saved"
                }
            ]
        }
    }
    ```
    """
    logger.info(f"Saving {len(request.items)} items to Cosmos DB")
    
    result = cosmos_service.save_items(request.items)
    
    if result["failed_count"] == 0:
        message = f"Successfully saved all {result['saved_count']} items"
    else:
        message = f"Saved {result['saved_count']} items, {result['failed_count']} failed"
    
    return SaveItemsResponse(
        data=result,
        status="success" if result["failed_count"] == 0 else "partial_success",
        status_code=200,
        message=message
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
