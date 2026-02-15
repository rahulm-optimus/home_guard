"""
Cluster Endpoints
API routes for managing zipcode clusters in SQL Server
"""
from fastapi import APIRouter, Depends, Query, HTTPException, Body
from app.schemas.requests import (
    CreateClusterRequest,
    UpdateClusterRequest,
    ClusterResponse,
    GetClustersResponse
)
from app.services.sql_db_service import get_sql_service, SQLServerService
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
    sql_service: SQLServerService = Depends(get_sql_service)
) -> ClusterResponse:
    """
    Create a new zipcode cluster in SQL Server.
    If a cluster with the same name already exists (case-insensitive, trimmed),
    it will update the existing cluster instead.
    
    Args:
        request: CreateClusterRequest with cluster details
        sql_service: Injected SQLServerService instance
        
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
    logger.info(f"Creating/updating cluster: {normalized_name} with {len(request.zipcodes)} zipcodes")
    
    try:
        # Check if cluster with same name exists
        existing_cluster = sql_service.find_cluster_by_name(normalized_name)
        
        if existing_cluster:
            # Update existing cluster using optimized method
            logger.info(f"Cluster '{normalized_name}' already exists (id={existing_cluster['id']}), updating...")
            
            await sql_service.update_cluster(
                cluster_id=existing_cluster['id'],
                name=normalized_name,
                description=request.description or "",
                zipcodes=request.zipcodes
            )
            
            # Fetch the updated cluster
            saved_cluster = sql_service.get_cluster(existing_cluster['id'])
            logger.info(f"Successfully updated cluster {existing_cluster['id']}")
            
            return ClusterResponse(
                status="success",
                message="Cluster updated successfully",
                data=saved_cluster
            )
        else:
            # Create new cluster using optimized method
            logger.info(f"Creating new cluster: {normalized_name}")
            
            cluster_id = await sql_service.create_cluster(
                name=normalized_name,
                zipcodes=request.zipcodes,
                description=request.description or ""
            )
            
            # Fetch the newly created cluster
            saved_cluster = sql_service.get_cluster(cluster_id)
            
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
    sql_service: SQLServerService = Depends(get_sql_service)
) -> ClusterResponse:
    """
    Update an existing zipcode cluster in SQL Server.
    
    Args:
        cluster_id: Unique identifier of the cluster to update
        request: UpdateClusterRequest with fields to update
        sql_service: Injected SQLServerService instance
        
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
        # Verify cluster exists
        existing_cluster = sql_service.get_cluster(cluster_id)
        
        if existing_cluster is None:
            logger.warning(f"Cluster {cluster_id} not found for update")
            raise HTTPException(status_code=404, detail=f"Cluster with id '{cluster_id}' not found")
        
        # Get update fields
        update_data = request.dict(exclude_unset=True)
        
        # Normalize cluster name if being updated
        new_name = update_data.get("name")
        if new_name:
            new_name = normalize_cluster_name(new_name)
            # Check if another cluster has this name
            duplicate = sql_service.find_cluster_by_name(new_name, exclude_id=cluster_id)
            if duplicate:
                logger.error(f"Duplicate cluster name: {new_name}")
                raise HTTPException(status_code=409, detail="Cluster name already exists")
            update_data["name"] = new_name
        
        logger.info(f"Updating fields: {list(update_data.keys())}")
        
        # Use optimized update method
        await sql_service.update_cluster(
            cluster_id=cluster_id,
            name=update_data.get("name"),
            description=update_data.get("description"),
            zipcodes=update_data.get("zipcodes")
        )
        
        # Fetch the updated cluster
        updated_cluster = sql_service.get_cluster(cluster_id)
        
        logger.info(f"Successfully updated cluster {cluster_id}")
        return ClusterResponse(
            status="success",
            message="Cluster updated successfully",
            data=updated_cluster
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error updating cluster {cluster_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get("/clusters/check-name", summary="Check if a cluster name already exists")
async def check_cluster_name(
    name: str = Query(..., description="Cluster name to check"),
    sql_service: SQLServerService = Depends(get_sql_service)
) -> dict:
    """
    Check if a cluster with the given name already exists (case-insensitive, trimmed).
    
    Args:
        name: The cluster name to check
        sql_service: Injected SQLServerService instance
        
    Returns:
        dict with exists flag and cluster details if found
    """
    try:
        normalized_name = normalize_cluster_name(name)
        existing_cluster = sql_service.find_cluster_by_name(normalized_name)
        
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
    sql_service: SQLServerService = Depends(get_sql_service)
) -> GetClustersResponse:
    """
    Retrieve all clusters from SQL Server with pagination and search support.
    
    Args:
        offset: Number of items to skip (default: 0)
        limit: Maximum items to return (default: 10, max: 100)
        search: Optional search query for filtering clusters
        sql_service: Injected SQLServerService instance
        
    Returns:
        GetClustersResponse with paginated clusters and metadata
    """
    logger.info(f"Fetching clusters with offset={offset}, limit={limit}, search='{search}'")
    
    try:
        # Get clusters from SQL Server
        result = sql_service.get_all_clusters(offset=offset, limit=limit, search=search)
        
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


@router.get("/cluster-by-zipcode", summary="Find which cluster a zipcode belongs to")
async def get_cluster_by_zipcode(
    zipcode: str = Query(..., description="5-digit zipcode to search for"),
    sql_service: SQLServerService = Depends(get_sql_service)
):
    """
    Find which cluster a specific zipcode belongs to.
    Returns cluster information if found, or null if zipcode doesn't belong to any cluster.
    
    Args:
        zipcode: 5-digit zipcode to search for
        sql_service: Injected SQLServerService instance
        
    Returns:
        JSON with cluster information if found, or message if not found
        
    Example Response (found):
    ```json
    {
        "found": true,
        "cluster_id": "123",
        "cluster_name": "Bay Area",
        "zipcodes": ["94102", "94103", "94104"],
        "description": "San Francisco Bay Area"
    }
    ```
    
    Example Response (not found):
    ```json
    {
        "found": false,
        "cluster_id": null,
        "cluster_name": "",
        "zipcodes": ["94999"],
        "message": "Zipcode 94999 does not belong to any cluster"
    }
    ```
    """
    # Normalize zipcode (remove spaces, ensure 5 digits)
    zipcode = zipcode.strip()
    
    if not zipcode.isdigit() or len(zipcode) != 5:
        raise HTTPException(status_code=400, detail="Invalid zipcode format. Must be 5 digits.")
    
    logger.info(f"Searching for cluster containing zipcode: {zipcode}")
    
    try:
        # Search for cluster containing this zipcode
        cluster = sql_service.find_cluster_by_zipcode(zipcode)
        
        if cluster:
            # Cluster found
            response = {
                "found": True,
                "cluster_id": str(cluster.get("ClusterId")),
                "cluster_name": cluster.get("Name", ""),
                "zipcodes": cluster.get("zipcodes", []),
                "description": cluster.get("Description", "")
            }
            logger.info(f"Found cluster '{cluster.get('Name')}' for zipcode {zipcode}")
        else:
            # No cluster found for this zipcode
            response = {
                "found": False,
                "cluster_id": None,
                "cluster_name": "",
                "zipcodes": [zipcode],
                "message": f"Zipcode {zipcode} does not belong to any cluster"
            }
            logger.info(f"No cluster found for zipcode {zipcode}")
        
        return response
        
    except Exception as e:
        logger.error(f"Error searching for cluster by zipcode {zipcode}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to search for cluster: {str(e)}")
