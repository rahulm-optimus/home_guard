# Test endpoint for simplified agent

from fastapi import APIRouter, HTTPException, Depends, Query
from app.services.test_agent import get_azure_agent_service
from app.core.exceptions import APIError, ValidationError
from app.schemas.requests import EstimateQueryInput, EstimateResponse
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/test-estimate", response_model=EstimateResponse)
async def estimate_items_test(
    input: EstimateQueryInput,
    use_bing: bool = Query(default=None),
    agent_service = Depends(get_azure_agent_service)
):
    """Process estimate request using test agent"""
    try:
        # Validate
        valid_items = [item.strip() for item in input.query if item and item.strip()]
        if not valid_items:
            raise ValidationError("At least one valid item required")
        
        # Direct call - no separate service
        result = agent_service.process_estimate_request(
            items=valid_items,
            category=input.category.strip(),
            zipcode=input.zipcode.strip(),
            address=input.address.strip(),
            username=input.username.strip(),
            use_bing=use_bing
        )
        
        # Check for complete failure
        if len(result["errors"]) > 0 and len(result["data"].items) == 0:
            raise APIError(
                message="Failed to process all items",
                status_code=500,
                error_code="PROCESSING_ERROR",
                details={"errors": result["errors"]}
            )
        
        return EstimateResponse(
            data=result["data"],
            message=result["messages"],
            error=result["errors"],
            status="success" if not result["errors"] else "partial_success",
            status_code=200
        )
    except ValidationError as e:
        logger.error(f"Validation error: {e.message}")
        raise HTTPException(
            status_code=e.status_code,
            detail={"error": e.error_code, "message": e.message, "details": e.details}
        )
    except APIError as e:
        logger.error(f"API error: {e.message}")
        raise HTTPException(
            status_code=e.status_code,
            detail={"error": e.error_code, "message": e.message, "details": e.details}
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"error": "INTERNAL_ERROR", "message": str(e), "details": {}}
        )