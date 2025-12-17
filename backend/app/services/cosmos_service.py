"""
Cosmos DB Service
Business logic for Azure Cosmos DB operations
"""
from typing import List, Dict, Any, Optional
from azure.cosmos import CosmosClient, PartitionKey, exceptions
from app.core.config import settings
from app.core.exceptions import APIError, ErrorCodes
from app.schemas.requests import SaveItemInput
import logging
import threading

logger = logging.getLogger(__name__)


class CosmosDBService:
    """Service for managing Azure Cosmos DB operations"""
    
    def __init__(self):
        self.client: Optional[CosmosClient] = None
        self.database = None
        self.container = None
        self._initialize()
    
    def _initialize(self):
        """Initialize Cosmos DB client and get database/container references"""
        if not settings.COSMOS_DB_ENDPOINT or not settings.COSMOS_DB_KEY:
            logger.warning("Cosmos DB credentials not configured. Service will run in mock mode.")
            return
        
        try:
            self.client = CosmosClient(
                url=settings.COSMOS_DB_ENDPOINT,
                credential=settings.COSMOS_DB_KEY
            )
            
            # Get or create database
            self.database = self.client.create_database_if_not_exists(
                id=settings.COSMOS_DB_DATABASE_NAME
            )
            
            # Get or create container
            self.container = self.database.create_container_if_not_exists(
                id=settings.COSMOS_DB_CONTAINER_NAME,
                partition_key=PartitionKey(path="/zipcode"),
                offer_throughput=400
            )
            
            logger.info(f"Cosmos DB initialized: {settings.COSMOS_DB_DATABASE_NAME}/{settings.COSMOS_DB_CONTAINER_NAME}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Cosmos DB: {str(e)}")
            raise APIError(
                message=f"Failed to connect to Cosmos DB: {str(e)}",
                status_code=500,
                error_code=ErrorCodes.COSMOS_DB_ERROR
            )
    
    def save_items(self, items: List[SaveItemInput]) -> Dict[str, Any]:
        """
        Save multiple items to Cosmos DB
        
        Args:
            items: List of items to save
            
        Returns:
            Dictionary with save operation results
            
        Raises:
            APIError: If save operation fails
        """
        if not self.container:
            # Mock mode - return success without actually saving
            logger.warning("Cosmos DB not configured. Running in mock mode.")
            return self._mock_save_items(items)
        
        try:
            saved_items = []
            failed_items = []
            
            for item in items:
                try:
                    # Convert Pydantic model to dict
                    item_dict = item.dict()
                    
                    # Upsert item (insert or update if exists)
                    result = self.container.upsert_item(body=item_dict)
                    saved_items.append({
                        "id": result["id"],
                        "status": "saved"
                    })
                    
                    logger.info(f"Saved item: {item.id}")
                    
                except exceptions.CosmosHttpResponseError as e:
                    logger.error(f"Failed to save item {item.id}: {str(e)}")
                    failed_items.append({
                        "id": item.id,
                        "error": str(e)
                    })
                except Exception as e:
                    logger.error(f"Unexpected error saving item {item.id}: {str(e)}")
                    failed_items.append({
                        "id": item.id,
                        "error": str(e)
                    })
            
            # Prepare response
            total_items = len(items)
            saved_count = len(saved_items)
            failed_count = len(failed_items)
            
            return {
                "total_items": total_items,
                "saved_count": saved_count,
                "failed_count": failed_count,
                "saved_items": saved_items,
                "failed_items": failed_items if failed_items else None
            }
            
        except Exception as e:
            logger.error(f"Cosmos DB save operation failed: {str(e)}")
            raise APIError(
                message=f"Failed to save items to Cosmos DB: {str(e)}",
                status_code=500,
                error_code=ErrorCodes.COSMOS_DB_ERROR,
                details={"error": str(e)}
            )
    
    def _mock_save_items(self, items: List[SaveItemInput]) -> Dict[str, Any]:
        """
        Mock save operation when Cosmos DB is not configured
        
        Args:
            items: List of items to save
            
        Returns:
            Mock success response
        """
        saved_items = [
            {"id": item.id, "status": "saved (mock)"}
            for item in items
        ]
        
        return {
            "total_items": len(items),
            "saved_count": len(items),
            "failed_count": 0,
            "saved_items": saved_items,
            "failed_items": None,
            "note": "Running in mock mode. Configure COSMOS_DB_ENDPOINT and COSMOS_DB_KEY to save to actual database."
        }
    
    def get_item(self, item_id: str, zipcode: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve a single item from Cosmos DB
        
        Args:
            item_id: Item identifier
            zipcode: Partition key value
            
        Returns:
            Item data or None if not found
        """
        if not self.container:
            logger.warning("Cosmos DB not configured. Cannot retrieve items.")
            return None
        
        try:
            item = self.container.read_item(
                item=item_id,
                partition_key=zipcode
            )
            return item
        except exceptions.CosmosResourceNotFoundError:
            logger.info(f"Item not found: {item_id}")
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve item: {str(e)}")
            raise APIError(
                message=f"Failed to retrieve item from Cosmos DB: {str(e)}",
                status_code=500,
                error_code=ErrorCodes.COSMOS_DB_ERROR
            )
    
    def query_items(self, query: str) -> List[Dict[str, Any]]:
        """
        Query items from Cosmos DB
        
        Args:
            query: SQL query string
            
        Returns:
            List of items matching the query
        """
        if not self.container:
            logger.warning("Cosmos DB not configured. Cannot query items.")
            return []
        
        try:
            items = list(self.container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))
            return items
        except Exception as e:
            logger.error(f"Failed to query items: {str(e)}")
            raise APIError(
                message=f"Failed to query items from Cosmos DB: {str(e)}",
                status_code=500,
                error_code=ErrorCodes.COSMOS_DB_ERROR
            )
    
    def get_all_items(self, offset: int = 0, limit: int = 10) -> Dict[str, Any]:
        """
        Retrieve all items with pagination support
        
        Args:
            offset: Number of items to skip
            limit: Maximum number of items to return
            
        Returns:
            Dictionary with paginated items and metadata
        """
        if not self.container:
            logger.warning("Cosmos DB not configured. Running in mock mode.")
            return self._mock_get_all_items(offset, limit)
        
        try:
            # Query to get all items with pagination
            query = f"SELECT * FROM c ORDER BY c._ts DESC OFFSET {offset} LIMIT {limit}"
            
            items = list(self.container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))
            
            # Get total count (separate query without pagination)
            count_query = "SELECT VALUE COUNT(1) FROM c"
            count_result = list(self.container.query_items(
                query=count_query,
                enable_cross_partition_query=True
            ))
            total_count = count_result[0] if count_result else 0
            
            logger.info(f"Retrieved {len(items)} items (offset: {offset}, limit: {limit})")
            
            return {
                "items": items,
                "total_count": total_count,
                "offset": offset,
                "limit": limit,
                "returned_count": len(items)
            }
            
        except Exception as e:
            logger.error(f"Failed to retrieve items: {str(e)}")
            raise APIError(
                message=f"Failed to retrieve items from Cosmos DB: {str(e)}",
                status_code=500,
                error_code=ErrorCodes.COSMOS_DB_ERROR,
                details={"error": str(e)}
            )
    
    def _mock_get_all_items(self, offset: int, limit: int) -> Dict[str, Any]:
        """
        Mock get all items operation when Cosmos DB is not configured
        
        Args:
            offset: Number of items to skip
            limit: Maximum number of items to return
            
        Returns:
            Mock response with sample data
        """
        mock_items = [
            {
                "id": f"mock-{i}",
                "zipcode": "12345",
                "category": "plumbing",
                "subcategory": "leak",
                "description": f"Mock item {i}",
                "dateofcreation": "2024-01-15",
                "estimate": {"min": 100.0, "max": 200.0},
                "note": "Mock data",
                "status": "active"
            }
            for i in range(offset, min(offset + limit, offset + 3))
        ]
        
        return {
            "items": mock_items,
            "total_count": 3,
            "offset": offset,
            "limit": limit,
            "returned_count": len(mock_items),
            "note": "Running in mock mode. Configure COSMOS_DB_ENDPOINT and COSMOS_DB_KEY to fetch from actual database."
        }


# Singleton instance
_cosmos_service_instance = None
_cosmos_lock = threading.Lock()


def get_cosmos_service() -> CosmosDBService:
    """Thread-safe singleton getter for CosmosDBService"""
    global _cosmos_service_instance
    
    if _cosmos_service_instance is None:
        with _cosmos_lock:
            if _cosmos_service_instance is None:  # Double-check pattern
                _cosmos_service_instance = CosmosDBService()
                logger.info("CosmosDBService singleton initialized")
    
    return _cosmos_service_instance
