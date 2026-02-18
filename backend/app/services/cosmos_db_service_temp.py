"""
Cosmos DB Service
Business logic for Azure Cosmos DB operations
"""

from typing import List, Dict, Any, Optional
from azure.cosmos import CosmosClient, PartitionKey, exceptions
from app.core.config import settings
from app.core.exceptions import APIError, ErrorCodes
from app.schemas.requests import SaveItemInput, CostEstStatus
import logging
import threading
import uuid
from datetime import datetime

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
                partition_key=PartitionKey(path="/cluster_name"),
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

    def _convert_status_to_string(self, status_id: int) -> str:
        """Convert SQL Server status integer to Cosmos DB status string"""
        return CostEstStatus.to_string(status_id)
    
    def _convert_to_cosmos_format(self, item: Dict[str, Any], cluster_name: str = "") -> Dict[str, Any]:
        """
        Convert SQL Server item format to Cosmos DB format.
        
        Maps SQL fields to Cosmos DB schema:
        - status: integer -> string
        - id: ensure string format
        - cluster_name: add from resolution
        - dateOfCreation: add if missing
        - currency: add if missing
        - type: add if missing
        
        Note: Only includes fields that have non-empty values to avoid overwriting existing Cosmos data
        """
        cosmos_item = {
            "id": str(item.get("id", "")),
            "status": item.get("status", "need_estimate") if isinstance(item.get("status"), str) else self._convert_status_to_string(item.get("status", 10)),
            "message": item.get("message", ""),
            "currency": item.get("currency", "USD"),
            "min_estimate": float(item.get("min_estimate", 0.0)),
            "max_estimate": float(item.get("max_estimate", 0.0)),
            "cluster_name": cluster_name or item.get("cluster_name", ""),
        }
        
        # Only add optional fields if they have non-empty values
        # This prevents overwriting existing Cosmos data with empty strings
        if item.get("zipcode"):
            cosmos_item["zipcode"] = str(item.get("zipcode"))
        
        if item.get("thread_id"):
            cosmos_item["thread_id"] = item["thread_id"]
        
        if item.get("dateOfCreation"):
            cosmos_item["dateOfCreation"] = item["dateOfCreation"]
        elif "dateOfCreation" not in cosmos_item:
            cosmos_item["dateOfCreation"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        
        if item.get("type"):
            cosmos_item["type"] = item["type"]
        else:
            cosmos_item["type"] = "home_repair"
            
        return cosmos_item

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

                if not item.get("cluster_name"):
                    raise ValueError("Missing 'cluster_name' field")

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

    async def update_item(self, item_id: str, cluster_name: str, updates: Dict[str, Any]) -> bool:
        """
        Update an existing item in Cosmos DB with etag-based concurrency control.
        
        Args:
            item_id: The item ID (BodyFindID as string)
            cluster_name: Partition key for the item (cluster name) - if empty, will query to find it
            updates: Dictionary with updated fields (already in Cosmos format)
            
        Returns:
            True if update successful, False otherwise
            
        Raises:
            APIError: If update fails
        """
        if not self.container:
            logger.warning("Cosmos DB not configured. Cannot update item.")
            return False

        try:
            # Ensure id is set correctly
            item_id_str = str(item_id)
            cluster_name_str = str(cluster_name) if cluster_name else ""
            
            logger.info(f"[COSMOS UPDATE] Starting update for item_id='{item_id_str}', cluster_name='{cluster_name_str}'")
            logger.info(f"[COSMOS UPDATE] Updates to apply: {updates}")
            
            # If cluster_name is empty, query to find the existing item
            existing_item = None
            if not cluster_name_str:
                logger.info(f"[COSMOS UPDATE] cluster_name is empty, querying across all partitions to find item {item_id_str}")
                try:
                    query = "SELECT * FROM c WHERE c.id = @id"
                    parameters = [{"name": "@id", "value": item_id_str}]
                    logger.info(f"[COSMOS UPDATE] Executing query: {query} with parameters: {parameters}")
                    
                    results = list(self.container.query_items(
                        query=query,
                        parameters=parameters,
                        enable_cross_partition_query=True,
                        max_item_count=1
                    ))
                    
                    logger.info(f"[COSMOS UPDATE] Query returned {len(results)} results")
                    
                    if results:
                        existing_item = results[0]
                        cluster_name_str = existing_item.get("cluster_name", "")
                        logger.info(f"[COSMOS UPDATE] Found existing item {item_id_str}")
                        logger.info(f"[COSMOS UPDATE] Existing item cluster_name='{cluster_name_str}'")
                        logger.info(f"[COSMOS UPDATE] Existing item data: {existing_item}")
                    else:
                        logger.warning(f"[COSMOS UPDATE] Item {item_id_str} not found in query results - will create new item")
                except Exception as query_err:
                    logger.error(f"[COSMOS UPDATE] Query failed for item {item_id_str}: {query_err}")
                    logger.exception("Full exception details:")
                    # If query fails, try to create new item with the cluster_name from updates
                    cluster_name_str = updates.get("cluster_name", "")
                    logger.info(f"[COSMOS UPDATE] Using cluster_name from updates: '{cluster_name_str}'")
            
            # Read existing item first with etag (if we haven't already queried it)
            if existing_item is None:
                logger.info(f"[COSMOS UPDATE] Attempting to read item {item_id_str} with partition_key='{cluster_name_str}'")
                try:
                    existing_item = self.container.read_item(
                        item=item_id_str,
                        partition_key=cluster_name_str
                    )
                    logger.info(f"[COSMOS UPDATE] Successfully read item {item_id_str} with cluster_name='{cluster_name_str}'")
                    logger.info(f"[COSMOS UPDATE] Read item data: {existing_item}")
                except exceptions.CosmosResourceNotFoundError:
                    logger.warning(f"[COSMOS UPDATE] Item {item_id_str} not found with read_item (cluster_name='{cluster_name_str}') - will create new")
                    existing_item = None
                except Exception as read_err:
                    logger.error(f"[COSMOS UPDATE] read_item failed: {read_err}")
                    logger.exception("Full exception details:")
                    existing_item = None
            else:
                logger.info(f"[COSMOS UPDATE] Using existing item from query (skipping read_item)")
                
            # If we found an existing item, update it
            if existing_item:
                logger.info(f"[COSMOS UPDATE] Proceeding with UPDATE operation for item {item_id_str}")
                # Get the etag for concurrency control
                etag = existing_item.get('_etag')
                logger.info(f"[COSMOS UPDATE] Item etag: {etag}")
                
                # Merge updates into existing item (preserving system fields and non-empty values)
                for key, value in updates.items():
                    # Skip system fields
                    if key in ['_rid', '_self', '_etag', '_attachments', '_ts']:
                        continue
                    
                    # Always update id with the correct value
                    if key == "id":
                        existing_item[key] = item_id_str
                    # For cluster_name, use the resolved value
                    elif key == "cluster_name":
                        existing_item[key] = cluster_name_str or value
                    # For other fields, only update if value is not empty/None
                    # This preserves existing zipcode, thread_id, etc. if update doesn't have them
                    elif value is not None and value != "":
                        existing_item[key] = value
                    # If update value is empty but field doesn't exist in item, set it
                    elif key not in existing_item:
                        existing_item[key] = value
                    # Otherwise preserve existing value
                    else:
                        logger.info(f"[COSMOS UPDATE] Preserving existing value for '{key}': '{existing_item.get(key)}' (update value was empty)")
                
                # Ensure id and cluster_name are always correct
                existing_item["id"] = item_id_str
                if not existing_item.get("cluster_name"):
                    existing_item["cluster_name"] = cluster_name_str or updates.get("cluster_name", "")
                
                logger.info(f"[COSMOS UPDATE] Merged item to upsert: {existing_item}")
                
                # Upsert with etag for optimistic concurrency control
                try:
                    result = self.container.upsert_item(
                        body=existing_item,
                        if_match=etag  # Only update if etag matches (no concurrent modifications)
                    )
                    logger.info(f"[COSMOS UPDATE] Successfully updated item {item_id_str} with etag concurrency control")
                    logger.info(f"[COSMOS UPDATE] Updated item result: {result}")
                    return True
                except exceptions.CosmosHttpResponseError as ce:
                    if ce.status_code == 412:  # Precondition failed (etag mismatch)
                        logger.warning(f"[COSMOS UPDATE] Concurrent modification detected (412), retrying without etag...")
                        # Retry once without etag (force update)
                        result = self.container.upsert_item(body=existing_item)
                        logger.info(f"[COSMOS UPDATE] Updated item {item_id_str} on retry")
                        logger.info(f"[COSMOS UPDATE] Retry result: {result}")
                        return True
                    else:
                        logger.error(f"[COSMOS UPDATE] Upsert failed with status {ce.status_code}: {ce}")
                        raise
            else:
                # Item doesn't exist, so create it with all required fields
                logger.info(f"[COSMOS UPDATE] Proceeding with CREATE operation for item {item_id_str}")
                new_item = updates.copy()
                new_item["id"] = item_id_str
                new_item["cluster_name"] = cluster_name_str or updates.get("cluster_name", "")
                
                # Ensure all required fields have defaults
                if "status" not in new_item:
                    new_item["status"] = "need_estimate"
                if "dateOfCreation" not in new_item:
                    new_item["dateOfCreation"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                if "currency" not in new_item:
                    new_item["currency"] = "USD"
                if "type" not in new_item:
                    new_item["type"] = "home_repair"
                if "message" not in new_item:
                    new_item["message"] = ""
                if "min_estimate" not in new_item:
                    new_item["min_estimate"] = 0.0
                if "max_estimate" not in new_item:
                    new_item["max_estimate"] = 0.0
                if "zipcode" not in new_item:
                    new_item["zipcode"] = ""
                
                logger.info(f"[COSMOS UPDATE] New item to create: {new_item}")
                
                result = self.container.upsert_item(body=new_item)
                logger.info(f"[COSMOS UPDATE] Created new item {item_id_str}")
                logger.info(f"[COSMOS UPDATE] Create result: {result}")
                return True
                
                result = self.container.upsert_item(body=new_item)
                logger.info(f"[COSMOS] Created new item {item_id_str} in Cosmos DB")
                return True

        except APIError:
            raise
        except Exception as e:
            logger.error(f"Failed to update item {item_id} in Cosmos DB: {str(e)}")
            raise APIError(
                message=f"Failed to update item in Cosmos DB: {str(e)}",
                status_code=500,
                error_code=ErrorCodes.COSMOS_DB_ERROR
            )

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
