from fastapi import HTTPException
"""
Save Endpoints
API routes for saving items to SQL Server
"""
from fastapi import APIRouter, Depends, Query
from app.schemas.requests import SaveItemsRequest, SaveItemsResponse, GetItemsResponse, SaveFlatItemInput, SaveCostEstimatesRequest, SaveCostEstimatesResponse, UpdateCostEstimateRequest, UpdateCostEstimateResponse

# New endpoint for saving flat items
from fastapi import Body

from app.services.sql_db_service import get_sql_service, SQLServerService
import logging


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/save-items", summary="Save flat items to SQL Server")
async def save_flat_items(
    request: SaveCostEstimatesRequest = Body(..., description="Cost estimates request with items array"),
    sql_service: SQLServerService = Depends(get_sql_service)
) -> SaveCostEstimatesResponse:
    """
    Persists one or more cost estimate records into SQL Server.
    
    This endpoint accepts a request body with an 'items' array containing cost estimates,
    saves them to SQL Server, and returns the saved items with operation status.
    
    Args:
        request: SaveCostEstimatesRequest containing list of items to save
        sql_service: Injected SQLServerService instance
        
    Returns:
        SaveCostEstimatesResponse with status, statusCode, message, and estimatedItems
    """
    items = request.items
    logger.info(f"Saving {len(items)} cost estimate items to SQL Server")
    
    result = await sql_service.save_flat_items([item.dict() for item in items])
    
    return SaveCostEstimatesResponse(
        status="success" if result["failed_count"] == 0 else "partial_success",
        saved_count=result["saved_count"]
    )


@router.get("/items", response_model=GetItemsResponse, summary="Get all items with pagination")
async def get_items(
    offset: int = Query(default=0, ge=0, description="Number of items to skip"),
    limit: int = Query(default=10, ge=1, le=100, description="Maximum number of items to return"),
    sql_service: SQLServerService = Depends(get_sql_service)
) -> GetItemsResponse:
    """
    Retrieve all items from SQL Server with pagination support
    
    This endpoint fetches items with offset and limit for pagination control.
    Items are ordered by creation timestamp (newest first).
    
    Args:
        offset: Number of items to skip (default: 0)
        limit: Maximum items to return (default: 10, max: 100)
        sql_service: Injected SQLServerService instance
        
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
    result = sql_service.get_all_items(offset=offset, limit=limit)
    
    # Log first item to debug
    if result['items']:
        logger.info(f"Sample item structure: {list(result['items'][0].keys())}")
        logger.info(f"Sample item ID field: id={result['items'][0].get('id')}, thread_id={result['items'][0].get('thread_id')}")
    
    # Enrich items with cluster name if clusterId is present
    for item in result['items']:
        cluster_id = item.get('clusterId')
        if cluster_id:
            try:
                cluster = sql_service.get_cluster(cluster_id)
                if cluster:
                    item['cluster_name'] = cluster.get('name', '')
                else:
                    item['cluster_name'] = ''
            except Exception as e:
                logger.warning(f"Failed to get cluster {cluster_id}: {e}")
                item['cluster_name'] = ''
    
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
    sql_service: SQLServerService = Depends(get_sql_service)
) -> GetItemsResponse:
    """
    Search items from SQL Server by message field with pagination support
    
    This endpoint performs a case-insensitive search on the message field
    and returns matching items with pagination.
    If items have a clusterId, the cluster's zipcodes are included in the response.
    
    Args:
        search_query: Search text to find in message field (required)
        offset: Number of items to skip (default: 0)
        limit: Maximum items to return (default: 10, max: 100)
        sql_service: Injected SQLServerService instance
        
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
    result = sql_service.search_items_by_message(
        search_query=search_query,
        offset=offset,
        limit=limit
    )
    
    # Enrich items with cluster name if clusterId is present
    for item in result['items']:
        cluster_id = item.get('clusterId')
        if cluster_id:
            try:
                cluster = sql_service.get_cluster(cluster_id)
                if cluster:
                    item['cluster_name'] = cluster.get('name', '')
                else:
                    item['cluster_name'] = ''
            except Exception as e:
                logger.warning(f"Failed to get cluster {cluster_id}: {e}")
                item['cluster_name'] = ''
    
    message = f"Found {result['returned_count']} items matching '{search_query}' out of {result['total_count']} total"
    
    return GetItemsResponse(
        data=result,
        status="success",
        status_code=200,
        message=message
    )

@router.put("/update-item/{item_id}", summary="Update an existing cost estimate item", response_model=UpdateCostEstimateResponse)
async def update_item(
    item_id: str,
    cluster_name: str = Query(None, description="Cluster name (primary partition key) for the item"),
    zipcode: str = Query(None, description="Zipcode (fallback partition key) for the item"),
    request: UpdateCostEstimateRequest = Body(..., description="Fields to update"),
    sql_service: SQLServerService = Depends(get_sql_service)
) -> UpdateCostEstimateResponse:
    """
    Update an existing cost estimate item in SQL Server.
    
    This endpoint updates specified fields of an existing item while preserving
    immutable fields (id, zipcode, thread_id, type, currency). It guarantees that
    the record exists before updating.
    
    Args:
        item_id: Unique identifier of the item to update
        cluster_name: Cluster name (primary partition key) for the item
        zipcode: Zipcode (fallback partition key) for the item
        request: UpdateCostEstimateRequest containing fields to update
        sql_service: Injected SQLServerService instance
        
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
    # Log incoming request
    logger.info(f"Update request - item_id: {item_id}, cluster_name: {cluster_name}, zipcode: {zipcode}, update_fields: {request.item.dict(exclude_unset=True)}")
    
    # Validate item_id
    if not item_id or item_id == "null" or item_id == "undefined":
        raise HTTPException(status_code=400, detail="Invalid item_id. Item ID is required and cannot be null.")
    
    # Determine partition key to use
    if not cluster_name and not zipcode:
        raise HTTPException(status_code=400, detail="Either cluster_name or zipcode must be provided")
    
    partition_key = cluster_name or zipcode
    fallback_key = zipcode if cluster_name else None
    
    logger.info(f"Updating item {item_id} with partition key: {partition_key}" + (f", fallback: {fallback_key}" if fallback_key else ""))
    
    try:
        # Fetch existing item to ensure it exists (tries cluster_name first, then zipcode)
        existing_item = sql_service.get_item(item_id, partition_key, fallback_key)
        
        if existing_item is None:
            logger.warning(f"Item {item_id} not found for update with partition keys tried")
            raise HTTPException(status_code=404, detail=f"Item with id '{item_id}' not found")
        
        logger.info(f"Found existing item: {existing_item.get('id')}")
        
        # Get update fields
        update_data = request.item.dict(exclude_unset=True)
        
        if not update_data:
            logger.warning("No fields provided for update")
            raise HTTPException(status_code=400, detail="No fields provided for update")
        
        logger.info(f"Updating fields: {list(update_data.keys())}")
        
        # Use the dedicated update method
        success = await sql_service.update_item(item_id, update_data)
        
        if not success:
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
