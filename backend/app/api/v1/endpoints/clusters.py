"""
Cluster Endpoints
API routes for managing zipcode clusters in Cosmos DB
"""
from fastapi import APIRouter, Depends, Query, HTTPException, Body
from app.schemas.requests import (
    CreateClusterRequest,
    UpdateClusterRequest,
    ClusterResponse,
    GetClustersResponse
)
from app.services.cosmos_db_service import get_cosmos_service, CosmosDBService
import logging
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)
router = APIRouter()


def normalize_cluster_name(name: str) -> str:
    """Normalize cluster name by trimming and collapsing multiple spaces to single space."""
    return ' '.join(name.strip().split())


@router.post("/clusters", summary="Create a new zipcode cluster", response_model=ClusterResponse)
async def create_cluster(
    request: CreateClusterRequest = Body(..., description="Cluster creation request"),
    cosmos_service: CosmosDBService = Depends(get_cosmos_service)
) -> ClusterResponse:
    """
    Create a new zipcode cluster in Cosmos DB.
    If a cluster with the same name already exists (case-insensitive, trimmed),
    it will update the existing cluster instead.
    
    Args:
        request: CreateClusterRequest with cluster details
        cosmos_service: Injected CosmosDBService instance
        
    Returns:
        ClusterResponse with status and created/updated cluster data
        
    Example Request:
    ```json
    {
        "name": "Bay Area East",
        "zipcodes": ["94551", "94552", "94553"],
        "description": "East Bay Area cluster"
    }
    ```
    """
    # Normalize the cluster name
    normalized_name = normalize_cluster_name(request.name)
    logger.info(f"Creating/updating cluster: {normalized_name}")
    
    try:
        # Check if cluster with same name exists
        existing_cluster = cosmos_service.find_cluster_by_name(normalized_name)
        
        if existing_cluster:
            # Update existing cluster
            logger.info(f"Cluster '{normalized_name}' already exists (id={existing_cluster['id']}), updating...")
            existing_cluster["name"] = normalized_name
            existing_cluster["zipcodes"] = request.zipcodes
            existing_cluster["description"] = request.description or ""
            existing_cluster["updated_at"] = datetime.utcnow().isoformat() + "Z"
            
            result = await cosmos_service.save_clusters([existing_cluster])
            
            if result["failed_count"] > 0:
                logger.error(f"Failed to update cluster {existing_cluster['id']}")
                raise HTTPException(status_code=500, detail="Failed to update cluster")
            
            saved_cluster = result["saved_items"][0]["data"]
            logger.info(f"Successfully updated cluster {existing_cluster['id']}")
            return ClusterResponse(
                status="success",
                message="Cluster updated successfully",
                data=saved_cluster
            )
        else:
            # Create new cluster
            cluster_id = str(uuid.uuid4())
            cluster_data = {
                "id": cluster_id,
                "name": normalized_name,
                "zipcodes": request.zipcodes,
                "description": request.description or "",
                "created_at": datetime.utcnow().isoformat() + "Z",
                "updated_at": datetime.utcnow().isoformat() + "Z"
            }
            
            result = await cosmos_service.save_clusters([cluster_data])
            
            if result["failed_count"] > 0:
                logger.error(f"Failed to create cluster {cluster_id}")
                raise HTTPException(status_code=500, detail="Failed to create cluster")
            
            saved_cluster = result["saved_items"][0]["data"]
            logger.info(f"Successfully created cluster {cluster_id}")
            return ClusterResponse(
                status="success",
                message="Cluster created successfully",
                data=saved_cluster
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating cluster: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.put("/clusters/{cluster_id}", summary="Update an existing zipcode cluster", response_model=ClusterResponse)
async def update_cluster(
    cluster_id: str,
    request: UpdateClusterRequest = Body(..., description="Cluster update request"),
    cosmos_service: CosmosDBService = Depends(get_cosmos_service)
) -> ClusterResponse:
    """
    Update an existing zipcode cluster in Cosmos DB.
    
    Args:
        cluster_id: Unique identifier of the cluster to update
        request: UpdateClusterRequest with fields to update
        cosmos_service: Injected CosmosDBService instance
        
    Returns:
        ClusterResponse with status and updated cluster data
        
    Example Request:
    ```json
    {
        "name": "Bay Area East Updated",
        "zipcodes": ["94551", "94552", "94553", "94560"],
        "description": "Updated description"
    }
    ```
    """
    logger.info(f"Updating cluster {cluster_id}")
    
    try:
        # Fetch existing cluster from cluster container
        existing_cluster = cosmos_service.get_cluster(cluster_id)
        
        if existing_cluster is None:
            logger.warning(f"Cluster {cluster_id} not found for update")
            raise HTTPException(status_code=404, detail=f"Cluster with id '{cluster_id}' not found")
        
        # Merge update fields
        update_data = request.dict(exclude_unset=True)
        
        for key, value in update_data.items():
            if value is not None:
                # Normalize cluster name if being updated
                if key == "name":
                    value = normalize_cluster_name(value)
                    # Check if another cluster has this name
                    duplicate = cosmos_service.find_cluster_by_name(value, exclude_id=cluster_id)
                    if duplicate:
                        logger.error(f"Duplicate cluster name: {value}")
                        raise HTTPException(status_code=409, detail="Cluster name already exists")
                existing_cluster[key] = value
        
        # Update timestamp
        existing_cluster["updated_at"] = datetime.utcnow().isoformat() + "Z"
        
        logger.info(f"Merged update fields: {list(update_data.keys())}")
        
        # Upsert the updated cluster
        result = await cosmos_service.save_clusters([existing_cluster])
        
        if result["failed_count"] > 0:
            logger.error(f"Failed to update cluster {cluster_id}")
            raise HTTPException(status_code=500, detail="Failed to update cluster")
        
        # Get the saved cluster data
        saved_cluster = result["saved_items"][0]["data"]
        
        logger.info(f"Successfully updated cluster {cluster_id}")
        return ClusterResponse(
            status="success",
            message="Cluster updated successfully",
            data=saved_cluster
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error updating cluster {cluster_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get("/clusters/check-name", summary="Check if a cluster name already exists")
async def check_cluster_name(
    name: str = Query(..., description="Cluster name to check"),
    cosmos_service: CosmosDBService = Depends(get_cosmos_service)
) -> dict:
    """
    Check if a cluster with the given name already exists (case-insensitive, trimmed).
    
    Args:
        name: The cluster name to check
        cosmos_service: Injected CosmosDBService instance
        
    Returns:
        dict with exists flag and cluster details if found
    """
    try:
        normalized_name = normalize_cluster_name(name)
        existing_cluster = cosmos_service.find_cluster_by_name(normalized_name)
        
        if existing_cluster:
            return {
                "exists": True,
                "cluster_id": existing_cluster.get("id"),
                "name": existing_cluster.get("name"),
                "zipcodes": existing_cluster.get("zipcodes", []),
                "zipcode_count": len(existing_cluster.get("zipcodes", []))
            }
        else:
            return {"exists": False}
    
    except Exception as e:
        logger.error(f"Error checking cluster name: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to check cluster name: {str(e)}")


@router.get("/clusters", response_model=GetClustersResponse, summary="Get all clusters with pagination")
async def get_clusters(
    offset: int = Query(default=0, ge=0, description="Number of items to skip"),
    limit: int = Query(default=10, ge=1, le=100, description="Maximum number of items to return"),
    search: str = Query(default="", description="Search query for cluster name or description"),
    cosmos_service: CosmosDBService = Depends(get_cosmos_service)
) -> GetClustersResponse:
    """
    Retrieve all clusters from Cosmos DB with pagination and search support.
    
    Args:
        offset: Number of items to skip (default: 0)
        limit: Maximum items to return (default: 10, max: 100)
        search: Optional search query for filtering clusters
        cosmos_service: Injected CosmosDBService instance
        
    Returns:
        GetClustersResponse with paginated clusters and metadata
    """
    logger.info(f"Fetching clusters with offset={offset}, limit={limit}, search='{search}'")
    
    try:
        # Get clusters from Cosmos DB
        result = cosmos_service.get_all_clusters(offset=offset, limit=limit, search=search)
        
        message = f"Retrieved {result['returned_count']} clusters out of {result['total_count']} total"
        
        return GetClustersResponse(
            data=result,
            status="success",
            status_code=200,
            message=message
        )
        
    except Exception as e:
        logger.error(f"Error fetching clusters: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch clusters: {str(e)}")
