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
import uuid

logger = logging.getLogger(__name__)


class CosmosDBService:
    """Service for managing Azure Cosmos DB operations"""

    def __init__(self):
        self.client: Optional[CosmosClient] = None
        self.database = None
        self.container = None
        self._initialize()

    def _initialize(self):
        """Initialize Cosmos DB client and container"""
        if not settings.COSMOS_DB_ENDPOINT or not settings.COSMOS_DB_KEY:
            logger.warning("Cosmos DB credentials not configured. Service will run in mock mode.")
            return

        try:
            self.client = CosmosClient(
                url=settings.COSMOS_DB_ENDPOINT,
                credential=settings.COSMOS_DB_KEY
            )

            self.database = self.client.create_database_if_not_exists(
                id=settings.COSMOS_DB_DATABASE_NAME
            )

            self.container = self.database.create_container_if_not_exists(
                id=settings.COSMOS_DB_CONTAINER_NAME,
                partition_key=PartitionKey(path="/zipcode"),
                offer_throughput=400
            )

            logger.info(
                f"Cosmos DB initialized: "
                f"{settings.COSMOS_DB_DATABASE_NAME}/"
                f"{settings.COSMOS_DB_CONTAINER_NAME}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize Cosmos DB: {str(e)}")
            raise APIError(
                message=f"Failed to connect to Cosmos DB: {str(e)}",
                status_code=500,
                error_code=ErrorCodes.COSMOS_DB_ERROR
            )

    # ------------------------------------------------------------------
    # CRUD OPERATIONS
    # ------------------------------------------------------------------

    def delete_item(self, item_id: str, zipcode: str) -> Dict[str, Any]:
        """Delete an item by id and partition key"""
        if not self.container:
            logger.warning("Cosmos DB not configured. Cannot delete item.")
            return {"status": "error", "message": "Cosmos DB not configured."}

        try:
            self.container.delete_item(
                item=str(item_id),
                partition_key=str(zipcode)
            )
            logger.info(f"Deleted item {item_id} (zipcode={zipcode})")
            return {"status": "success", "message": f"Item {item_id} deleted."}

        except exceptions.CosmosResourceNotFoundError:
            logger.warning(f"Item {item_id} not found for deletion.")
            return {"status": "not_found", "message": f"Item {item_id} not found."}

        except Exception as e:
            logger.error(f"Failed to delete item {item_id}: {str(e)}")
            return {"status": "error", "message": str(e)}

    def get_item(self, item_id: str, zipcode: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single item"""
        if not self.container:
            logger.warning("Cosmos DB not configured. Cannot retrieve item.")
            return None

        try:
            return self.container.read_item(
                item=item_id,
                partition_key=str(zipcode)
            )

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

    # ------------------------------------------------------------------
    # SAVE OPERATIONS
    # ------------------------------------------------------------------

    async def save_flat_items(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Save flat dict-based items (non-Pydantic)
        Ensures `id` and `zipcode` exist
        """
        if not self.container:
            logger.warning("Cosmos DB not configured. Running in mock mode.")
            return self._mock_save_items(items)

        saved_items = []
        failed_items = []

        for item in items:
            try:
                if not isinstance(item, dict):
                    item = dict(item)

                if not item.get("id"):
                    item["id"] = item.get("thread_id") or str(uuid.uuid4())

                if not item.get("zipcode"):
                    raise ValueError("Missing 'zipcode' field")

                result = self.container.upsert_item(body=item)

                saved_items.append({
                    "id": result.get("id"),
                    "status": "saved"
                })

                logger.info(f"Saved flat item: {result.get('id')}")

            except Exception as e:
                logger.error(f"Failed to save flat item: {str(e)}")
                failed_items.append({
                    "id": item.get("id"),
                    "error": str(e)
                })

        return {
            "total_items": len(items),
            "saved_count": len(saved_items),
            "failed_count": len(failed_items),
            "saved_items": saved_items,
            "failed_items": failed_items or None
        }

    # ------------------------------------------------------------------
    # QUERY OPERATIONS
    # ------------------------------------------------------------------

    def query_items(self, query: str) -> List[Dict[str, Any]]:
        """Run a SQL query against Cosmos DB"""
        if not self.container:
            logger.warning("Cosmos DB not configured. Cannot query items.")
            return []

        try:
            return list(self.container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))

        except Exception as e:
            logger.error(f"Failed to query items: {str(e)}")
            raise APIError(
                message=f"Failed to query items from Cosmos DB: {str(e)}",
                status_code=500,
                error_code=ErrorCodes.COSMOS_DB_ERROR
            )

    def get_all_items(self, offset: int = 0, limit: int = 10) -> Dict[str, Any]:
        """Retrieve all items with pagination"""
        if not self.container:
            logger.warning("Cosmos DB not configured. Running in mock mode.")
            return self._mock_get_all_items(offset, limit)

        try:
            items = list(self.container.query_items(
                query=(
                    "SELECT * FROM c "
                    "ORDER BY c._ts DESC "
                    f"OFFSET {offset} LIMIT {limit}"
                ),
                enable_cross_partition_query=True
            ))

            count = list(self.container.query_items(
                query="SELECT VALUE COUNT(1) FROM c",
                enable_cross_partition_query=True
            ))[0]

            return {
                "items": items,
                "total_count": count,
                "offset": offset,
                "limit": limit,
                "returned_count": len(items)
            }

        except Exception as e:
            logger.error(f"Failed to retrieve items: {str(e)}")
            raise APIError(
                message=f"Failed to retrieve items from Cosmos DB: {str(e)}",
                status_code=500,
                error_code=ErrorCodes.COSMOS_DB_ERROR
            )

    def search_items_by_message(self, search_query: str, offset: int = 0, limit: int = 10) -> Dict[str, Any]:
        """Search items by message field with pagination"""
        if not self.container:
            logger.warning("Cosmos DB not configured. Running in mock mode.")
            return self._mock_search_items(search_query, offset, limit)

        try:
            # Using CONTAINS for case-insensitive search
            search_query_escaped = search_query.replace("'", "''")
            
            items = list(self.container.query_items(
                query=(
                    "SELECT * FROM c "
                    f"WHERE CONTAINS(LOWER(c.message), LOWER('{search_query_escaped}')) "
                    "ORDER BY c._ts DESC "
                    f"OFFSET {offset} LIMIT {limit}"
                ),
                enable_cross_partition_query=True
            ))

            count_result = list(self.container.query_items(
                query=(
                    "SELECT VALUE COUNT(1) FROM c "
                    f"WHERE CONTAINS(LOWER(c.message), LOWER('{search_query_escaped}'))"
                ),
                enable_cross_partition_query=True
            ))
            count = count_result[0] if count_result else 0

            return {
                "items": items,
                "total_count": count,
                "offset": offset,
                "limit": limit,
                "returned_count": len(items)
            }

        except Exception as e:
            logger.error(f"Failed to search items: {str(e)}")
            raise APIError(
                message=f"Failed to search items from Cosmos DB: {str(e)}",
                status_code=500,
                error_code=ErrorCodes.COSMOS_DB_ERROR
            )

    # ------------------------------------------------------------------
    # MOCK METHODS
    # ------------------------------------------------------------------

    def _mock_save_items(self, items: list) -> Dict[str, Any]:
        saved_items = []

        for item in items:
            item_id = item.get("id") if isinstance(item, dict) else getattr(item, "id", None)
            saved_items.append({
                "id": item_id,
                "status": "saved (mock)"
            })

        return {
            "total_items": len(items),
            "saved_count": len(items),
            "failed_count": 0,
            "saved_items": saved_items,
            "failed_items": None,
            "note": "Mock mode enabled"
        }

    def _mock_get_all_items(self, offset: int, limit: int) -> Dict[str, Any]:
        mock_items = [
            {
                "id": f"mock-{i}",
                "zipcode": "12345",
                "category": "plumbing",
                "description": f"Mock item {i}",
                "status": "active"
            }
            for i in range(offset, offset + min(limit, 3))
        ]

        return {
            "items": mock_items,
            "total_count": 3,
            "offset": offset,
            "limit": limit,
            "returned_count": len(mock_items),
            "note": "Mock mode enabled"
        }

    def _mock_search_items(self, search_query: str, offset: int, limit: int) -> Dict[str, Any]:
        mock_items = [
            {
                "id": f"mock-{i}",
                "zipcode": "12345",
                "message": f"Mock item with {search_query}",
                "description": f"Mock search result {i}",
                "status": "active"
            }
            for i in range(offset, offset + min(limit, 2))
        ]

        return {
            "items": mock_items,
            "total_count": 2,
            "offset": offset,
            "limit": limit,
            "returned_count": len(mock_items),
            "note": "Mock mode enabled"
        }


# ----------------------------------------------------------------------
# THREAD-SAFE SINGLETON
# ----------------------------------------------------------------------

_cosmos_service_instance: Optional[CosmosDBService] = None
_cosmos_lock = threading.Lock()


def get_cosmos_service() -> CosmosDBService:
    """Thread-safe singleton getter"""
    global _cosmos_service_instance

    if _cosmos_service_instance is None:
        with _cosmos_lock:
            if _cosmos_service_instance is None:
                _cosmos_service_instance = CosmosDBService()
                logger.info("CosmosDBService singleton initialized")

    return _cosmos_service_instance
