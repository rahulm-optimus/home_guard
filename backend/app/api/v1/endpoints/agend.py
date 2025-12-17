"""
New Agent Endpoint
API endpoint for Azure AI Foundry agent with Bing search capability
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from app.schemas.requests import EstimateQueryInput, EstimateResponse
from app.services.new_estimate_service import get_new_estimate_service, NewEstimateService
from app.core.exceptions import APIError, ValidationError
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/estimate", response_model=EstimateResponse, summary="Get estimates using Azure AI Foundry Agent (with optional Bing)")
async def estimate_items_new(
    input: EstimateQueryInput,
    use_bing: bool = Query(default=None, description="Enable/disable Bing search for this request (overrides config default)"),
    estimate_service: NewEstimateService = Depends(get_new_estimate_service)
) -> EstimateResponse:
    """
    Process estimate request using Azure AI Foundry agent with parallel execution
    
    Flow:
    1. Classifies subcategories for each item in parallel
    2. Calls Azure AI Foundry Agent (up to 4 concurrent requests)
    3. Agent automatically uses Bing search when needed
    4. Returns cost estimates with detailed notes
    
    Request Body:
    ```json
    {
        "query": [
            "Fungus damage was noted to the rafter tail.",
            "Replace kitchen cabinets"
        ],
        "category": "Termite inspection",
        "zipcode": "94551",
        "address": "2623 Anywhere Street, Hometown, CA 94551",
        "username": "John Doe"
    }
    ```
    
    Response Body:
    ```json
    {
        "status": "success",
        "status_code": 200,
        "message": [
            "Item 1: Azure AI Agent estimate for Fungus damage (with Bing search)",
            "Item 2: Azure AI Agent estimate for Structure (with Bing search)"
        ],
        "error": [],
        "data": {
            "category": "Termite inspection",
            "items": [
                {
                    "description": "Fungus damage was noted to the rafter tail.",
                    "subcategory": "Fungus damage",
                    "estimate": {
                        "min": 800.0,
                        "max": 5000.0
                    },
                    "note": "[Azure AI Agent - Zipcode: 94551] Repair costs include..."
                }
            ],
            "dateofcreation": "2025-12-15",
            "zipcode": "94551",
            "address": "2623 Anywhere Street, Hometown, CA 94551",
            "username": "John Doe"
        }
    }
    ```
    """
    try:
        # Validate input data
        if not input.query or len(input.query) == 0:
            raise ValidationError("At least one item is required", details={"field": "query"})
        
        # Filter out empty items
        valid_items = [item.strip() for item in input.query if item and item.strip()]
        if not valid_items:
            raise ValidationError("All items are empty. Please provide valid item descriptions.", details={"field": "query"})
        
        if not input.zipcode or len(input.zipcode.strip()) < 5:
            raise ValidationError("Valid zipcode is required (minimum 5 characters)", details={"field": "zipcode"})
        
        if not input.address or not input.address.strip():
            raise ValidationError("Address is required", details={"field": "address"})
        
        if not input.username or not input.username.strip():
            raise ValidationError("Username is required", details={"field": "username"})
        
        if not input.category or not input.category.strip():
            raise ValidationError("Category is required", details={"field": "category"})
        
        logger.info(f"Processing new estimate request for {len(valid_items)} items in zipcode {input.zipcode}")
        
        result = estimate_service.process_estimate_request(
            items=valid_items,
            category=input.category.strip(),
            zipcode=input.zipcode.strip(),
            address=input.address.strip(),
            username=input.username.strip(),
            use_bing=use_bing
        )
        
        # Check if all items failed
        if len(result["errors"]) > 0 and len(result["data"].items) == 0:
            logger.error(f"All items failed to process: {result['errors']}")
            raise APIError(
                message="Failed to process all items. Please check your input and try again.",
                status_code=500,
                error_code="PROCESSING_ERROR",
                details={"errors": result["errors"]}
            )
        
        return EstimateResponse(
            data=result["data"],
            message=result["messages"],
            error=result["errors"],
            status="success" if len(result["errors"]) == 0 else "partial_success",
            status_code=200
        )
        
    except ValidationError as e:
        logger.error(f"Validation error: {e.message}")
        raise HTTPException(status_code=e.status_code, detail={
            "status": "error",
            "status_code": e.status_code,
            "message": e.message,
            "error_code": e.error_code,
            "details": e.details
        })
    except APIError as e:
        logger.error(f"API error: {e.message}")
        raise HTTPException(status_code=e.status_code, detail={
            "status": "error",
            "status_code": e.status_code,
            "message": e.message,
            "error_code": e.error_code,
            "details": e.details
        })
    except Exception as e:
        logger.error(f"Unexpected error processing estimate: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail={
            "status": "error",
            "status_code": 500,
            "message": f"An unexpected error occurred while processing your request: {str(e)}",
            "error_code": "INTERNAL_ERROR"
        })