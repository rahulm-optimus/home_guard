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
        self.cluster_container = None
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

            self.cluster_container = self.database.create_container_if_not_exists(
                id=settings.COSMOS_DB_CLUSTER_CONTAINER_NAME,
                partition_key=PartitionKey(path="/id"),
                offer_throughput=400
            )

            logger.info(
                f"Cosmos DB initialized: "
                f"{settings.COSMOS_DB_DATABASE_NAME}/"
                f"{settings.COSMOS_DB_CONTAINER_NAME}, "
                f"{settings.COSMOS_DB_CLUSTER_CONTAINER_NAME}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize Cosmos DB: {str(e)}")
            raise APIError(
                message=f"Failed to connect to Cosmos DB: {str(e)}",
                status_code=500,
                error_code=ErrorCodes.COSMOS_DB_ERROR
            )

    # ------------------------------------------------------------------
    # HELPER METHODS
    # ------------------------------------------------------------------

    def _remove_system_fields(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Remove Cosmos DB system fields from a document"""
        system_fields = ['_rid', '_self', '_etag', '_attachments', '_ts']
        return {k: v for k, v in item.items() if k not in system_fields}

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

    def get_item(self, item_id: str, partition_key_value: str, fallback_partition_key: str = None) -> Optional[Dict[str, Any]]:
        """Retrieve a single item with support for multiple partition keys
        
        Args:
            item_id: The item ID
            partition_key_value: Primary partition key value (e.g., cluster_name)
            fallback_partition_key: Fallback partition key value (e.g., zipcode) to try if first fails
        """
        if not self.container:
            logger.warning("Cosmos DB not configured. Cannot retrieve item.")
            return None

        # Try with primary partition key
        try:
            item = self.container.read_item(
                item=item_id,
                partition_key=str(partition_key_value)
            )
            logger.info(f"Item {item_id} found with partition key: {partition_key_value}")
            return item

        except exceptions.CosmosResourceNotFoundError:
            # If fallback partition key is provided, try with it
            if fallback_partition_key:
                logger.info(f"Item {item_id} not found with partition key {partition_key_value}, trying fallback {fallback_partition_key}")
                try:
                    item = self.container.read_item(
                        item=item_id,
                        partition_key=str(fallback_partition_key)
                    )
                    logger.info(f"Item {item_id} found with fallback partition key: {fallback_partition_key}")
                    return item
                except exceptions.CosmosResourceNotFoundError:
                    logger.info(f"Item {item_id} not found with either partition key")
                    return None
            else:
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
    # CLUSTER OPERATIONS
    # ------------------------------------------------------------------

    def get_cluster(self, cluster_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single cluster by ID"""
        if not self.cluster_container:
            logger.warning("Cluster container not configured. Cannot retrieve cluster.")
            return None

        try:
            cluster = self.cluster_container.read_item(
                item=cluster_id,
                partition_key=cluster_id
            )
            return self._remove_system_fields(cluster)

        except exceptions.CosmosResourceNotFoundError:
            logger.info(f"Cluster not found: {cluster_id}")
            return None

        except Exception as e:
            logger.error(f"Failed to retrieve cluster: {str(e)}")
            raise APIError(
                message=f"Failed to retrieve cluster from Cosmos DB: {str(e)}",
                status_code=500,
                error_code=ErrorCodes.COSMOS_DB_ERROR
            )

    def find_cluster_by_name(self, name: str, exclude_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Find a cluster by name (case-insensitive, trimmed).
        
        Args:
            name: The cluster name to search for
            exclude_id: Optional cluster ID to exclude from results (useful for updates)
            
        Returns:
            The cluster document if found, None otherwise
        """
        if not self.cluster_container:
            logger.warning("Cluster container not configured. Cannot search for cluster.")
            return None

        try:
            # Normalize the search name: trim and collapse spaces
            normalized_name = ' '.join(name.strip().split()).lower()
            
            # Build query to find cluster by normalized name
            query = "SELECT * FROM c WHERE LOWER(TRIM(REPLACE(REPLACE(c.name, '  ', ' '), '  ', ' '))) = @name"
            parameters = [{"name": "@name", "value": normalized_name}]
            
            # Add exclusion if updating existing cluster
            if exclude_id:
                query += " AND c.id != @exclude_id"
                parameters.append({"name": "@exclude_id", "value": exclude_id})
            
            results = list(self.cluster_container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True,
                max_item_count=1
            ))
            
            if results:
                return self._remove_system_fields(results[0])
            return None

        except Exception as e:
            logger.error(f"Failed to search for cluster by name: {str(e)}")
            raise APIError(
                message=f"Failed to search for cluster: {str(e)}",
                status_code=500,
                error_code=ErrorCodes.COSMOS_DB_ERROR
            )

    async def save_clusters(self, clusters: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Save/upsert clusters to the cluster container"""
        if not self.cluster_container:
            logger.warning("Cluster container not configured. Running in mock mode.")
            return self._mock_save_items(clusters)

        saved_clusters = []
        failed_clusters = []

        for cluster in clusters:
            try:
                if not isinstance(cluster, dict):
                    cluster = dict(cluster)

                if not cluster.get("id"):
                    cluster["id"] = str(uuid.uuid4())

                result = self.cluster_container.upsert_item(body=cluster)
                cleaned_result = self._remove_system_fields(result)

                saved_clusters.append({
                    "id": cleaned_result.get("id"),
                    "status": "saved",
                    "data": cleaned_result
                })

                logger.info(f"Saved cluster: {cleaned_result.get('id')}")

            except exceptions.CosmosHttpResponseError as e:
                error_msg = str(e)
                # Check for unique key constraint violation
                if "Conflict" in error_msg or "unique" in error_msg.lower():
                    logger.error(f"Duplicate cluster name: {cluster.get('name')}")
                    failed_clusters.append({
                        "id": cluster.get("id"),
                        "error": "Cluster name already exists",
                        "error_type": "duplicate_name"
                    })
                else:
                    logger.error(f"Failed to save cluster: {error_msg}")
                    failed_clusters.append({
                        "id": cluster.get("id"),
                        "error": error_msg
                    })

            except Exception as e:
                logger.error(f"Failed to save cluster: {str(e)}")
                failed_clusters.append({
                    "id": cluster.get("id"),
                    "error": str(e)
                })

        return {
            "total_items": len(clusters),
            "saved_count": len(saved_clusters),
            "failed_count": len(failed_clusters),
            "saved_items": saved_clusters,
            "failed_items": failed_clusters or None
        }

    def get_all_clusters(self, offset: int = 0, limit: int = 10, search: str = "") -> Dict[str, Any]:
        """Retrieve all clusters with pagination and search support"""
        if not self.cluster_container:
            logger.warning("Cluster container not configured. Running in mock mode.")
            return {
                "items": [],
                "total_count": 0,
                "offset": offset,
                "limit": limit,
                "returned_count": 0,
                "note": "Cluster container not configured"
            }

        try:
            # Build query with search if provided
            if search:
                search_escaped = search.replace("'", "''")
                
                # Handle comma-separated zipcodes
                zipcodes = [z.strip() for z in search_escaped.split(',') if z.strip()]
                
                # Build zipcode search conditions
                if len(zipcodes) > 1:
                    # Multiple zipcodes: create OR conditions for each
                    # Escape single quotes for each zipcode first
                    escaped_zipcodes = [zc.replace("'", "''") for zc in zipcodes]
                    zipcode_conditions = " OR ".join([f"CONTAINS(z, '{zc}') " for zc in escaped_zipcodes])
                    zipcode_search = f"EXISTS(SELECT VALUE z FROM z IN c.zipcodes WHERE {zipcode_conditions})"
                else:
                    # Single search term (could be name, description, or single zipcode)
                    zipcode_search = f"EXISTS(SELECT VALUE z FROM z IN c.zipcodes WHERE CONTAINS(z, '{search_escaped}'))"
                
                query = (
                    "SELECT * FROM c "
                    f"WHERE CONTAINS(LOWER(c.name), LOWER('{search_escaped}')) "
                    f"OR CONTAINS(LOWER(c.description), LOWER('{search_escaped}')) "
                    f"OR {zipcode_search} "
                    "ORDER BY c.created_at DESC "
                    f"OFFSET {offset} LIMIT {limit}"
                )
                count_query = (
                    "SELECT VALUE COUNT(1) FROM c "
                    f"WHERE CONTAINS(LOWER(c.name), LOWER('{search_escaped}')) "
                    f"OR CONTAINS(LOWER(c.description), LOWER('{search_escaped}')) "
                    f"OR {zipcode_search}"
                )
            else:
                query = (
                    "SELECT * FROM c "
                    "ORDER BY c.created_at DESC "
                    f"OFFSET {offset} LIMIT {limit}"
                )
                count_query = "SELECT VALUE COUNT(1) FROM c"

            # Execute query
            items = list(self.cluster_container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))

            # Remove system fields from all items
            cleaned_items = [self._remove_system_fields(item) for item in items]

            # Get total count
            count_result = list(self.cluster_container.query_items(
                query=count_query,
                enable_cross_partition_query=True
            ))
            count = count_result[0] if count_result else 0

            return {
                "items": cleaned_items,
                "total_count": count,
                "offset": offset,
                "limit": limit,
                "returned_count": len(cleaned_items)
            }

        except Exception as e:
            logger.error(f"Failed to retrieve clusters: {str(e)}")
            raise APIError(
                message=f"Failed to retrieve clusters from Cosmos DB: {str(e)}",
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
