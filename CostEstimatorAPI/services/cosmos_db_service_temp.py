import os
import logging
import uuid
from typing import Optional, Dict, Any, List
from azure.cosmos import CosmosClient, exceptions
from datetime import datetime
from enum import IntEnum

COSMOS_DB_ENDPOINT = os.environ.get("COSMOS_DB_ENDPOINT")
COSMOS_DB_KEY = os.environ.get("COSMOS_DB_KEY")
COSMOS_DB_DATABASE_NAME = os.environ.get("COSMOS_DB_DATABASE_NAME", "homeguard")

COSMOS_DB_CONTAINER_NAME = os.environ.get("COSMOS_DB_CONTAINER_NAME", "NewEstimates")
# COSMOS_DB_CLUSTER_CONTAINER_NAME = os.environ.get("COSMOS_DB_CLUSTER_CONTAINER_NAME", "zipcodeClusters")

# Import CostEstStatus from sql_db_service
class CostEstStatus(IntEnum):
    """Cost Estimate Status mapping for SQL Server CostEstStatusID field"""
    LEAVE_ALONE = 0
    NEED_ESTIMATE = 10
    ESTIMATE_COMPLETE = 20
    EDIT_INPUT = 30
    AI_ANALYZED = 40
    
    @classmethod
    def from_string(cls, status_str: str) -> int:
        """Convert string status to integer ID"""
        mapping = {
            "leave_alone": cls.LEAVE_ALONE,
            "need_estimate": cls.NEED_ESTIMATE,
            "estimate_complete": cls.ESTIMATE_COMPLETE,
            "edit_input": cls.EDIT_INPUT,
            "ai_analyzed": cls.AI_ANALYZED,
            "approved": cls.ESTIMATE_COMPLETE,
            "pending": cls.NEED_ESTIMATE,
            "completed": cls.ESTIMATE_COMPLETE,
        }
        return mapping.get(status_str.lower(), cls.LEAVE_ALONE)
    
    @classmethod
    def to_string(cls, status_id: int) -> str:
        """Convert integer ID to string status"""
        mapping = {
            cls.LEAVE_ALONE: "leave_alone",
            cls.NEED_ESTIMATE: "need_estimate",
            cls.ESTIMATE_COMPLETE: "estimate_complete",
            cls.EDIT_INPUT: "edit_input",
            cls.AI_ANALYZED: "ai_analyzed",
        }
        return mapping.get(status_id, "leave_alone")

class CosmosDBService:
    def __init__(self):
        self.client = CosmosClient(COSMOS_DB_ENDPOINT, credential=COSMOS_DB_KEY)
        self.database = self.client.get_database_client(COSMOS_DB_DATABASE_NAME)
        self.container = self.database.get_container_client(COSMOS_DB_CONTAINER_NAME)
        self.cluster_container = self.database.get_container_client(COSMOS_DB_CLUSTER_CONTAINER_NAME)

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

    def save_flat_items(self, items):
        """
        Save flat dict-based items to Cosmos DB.
        Ensures `id` and `zipcode` exist before saving.
        """
        saved_count = 0
        failed_count = 0
        saved_items = []
        failed_items = []
        
        for item in items:
            try:
                # Ensure item is a dict
                if not isinstance(item, dict):
                    item = dict(item)
                
                # Validate required fields
                if not item.get("id"):
                    # Only generate ID if not present
                    item["id"] = item.get("thread_id") or str(uuid.uuid4())
                    logging.warning(f"Generated new ID for item: {item['id']}")
                
                if not item.get("cluster_name"):
                    logging.error(f"Missing cluster_name for item {item.get('id', 'unknown')}")
                    failed_count += 1
                    failed_items.append({
                        "id": item.get("id"),
                        "error": "Missing required field: cluster_name"
                    })
                    continue
                
                # Ensure id and cluster_name are strings
                item["id"] = str(item["id"])
                item["cluster_name"] = str(item["cluster_name"])
                
                # Upsert to Cosmos DB
                result = self.container.upsert_item(item)
                saved_count += 1
                saved_items.append({
                    "id": result.get("id"),
                    "status": "saved"
                })
                logging.info(f"Saved item: {result.get('id')} with cluster_name: {result.get('cluster_name')}")
                
            except Exception as e:
                logging.error(f"Failed to save item {item.get('id', 'unknown')}: {e}")
                failed_count += 1
                failed_items.append({
                    "id": item.get("id"),
                    "error": str(e)
                })
        
        return {
            "saved_count": saved_count,
            "failed_count": failed_count,
            "saved_items": saved_items,
            "failed_items": failed_items if failed_items else None
        }

    def update_item(self, item_id: str, cluster_name: str, updates: Dict[str, Any]) -> bool:
        """
        Update an existing item in Cosmos DB with etag-based concurrency control.
        
        Args:
            item_id: The item ID (BodyFindID as string)
            cluster_name: Partition key for the item (cluster name) - if empty, will query to find it
            updates: Dictionary with updated fields (already in Cosmos format)
            
        Returns:
            True if update successful, False otherwise
        """
        try:
            # Ensure id is set correctly
            item_id_str = str(item_id)
            cluster_name_str = str(cluster_name) if cluster_name else ""
            
            logging.info(f"[COSMOS UPDATE] Starting update for item_id='{item_id_str}', cluster_name='{cluster_name_str}'")
            logging.info(f"[COSMOS UPDATE] Updates to apply: {updates}")
            
            # If cluster_name is empty, query to find the existing item
            existing_item = None
            if not cluster_name_str:
                logging.info(f"[COSMOS UPDATE] cluster_name is empty, querying across all partitions to find item {item_id_str}")
                try:
                    query = "SELECT * FROM c WHERE c.id = @id"
                    parameters = [{"name": "@id", "value": item_id_str}]
                    logging.info(f"[COSMOS UPDATE] Executing query: {query} with parameters: {parameters}")
                    
                    results = list(self.container.query_items(
                        query=query,
                        parameters=parameters,
                        enable_cross_partition_query=True,
                        max_item_count=1
                    ))
                    
                    logging.info(f"[COSMOS UPDATE] Query returned {len(results)} results")
                    
                    if results:
                        existing_item = results[0]
                        cluster_name_str = existing_item.get("cluster_name", "")
                        logging.info(f"[COSMOS UPDATE] Found existing item {item_id_str}")
                        logging.info(f"[COSMOS UPDATE] Existing item cluster_name='{cluster_name_str}'")
                        logging.info(f"[COSMOS UPDATE] Existing item data: {existing_item}")
                    else:
                        logging.warning(f"[COSMOS UPDATE] Item {item_id_str} not found in query results - will create new item")
                except Exception as query_err:
                    logging.error(f"[COSMOS UPDATE] Query failed for item {item_id_str}: {query_err}")
                    import traceback
                    logging.error(f"Full exception: {traceback.format_exc()}")
                    # If query fails, try to create new item with the cluster_name from updates
                    cluster_name_str = updates.get("cluster_name", "")
                    logging.info(f"[COSMOS UPDATE] Using cluster_name from updates: '{cluster_name_str}'")
            
            # Read existing item first with etag (if we haven't already queried it)
            if existing_item is None:
                logging.info(f"[COSMOS UPDATE] Attempting to read item {item_id_str} with partition_key='{cluster_name_str}'")
                try:
                    existing_item = self.container.read_item(
                        item=item_id_str,
                        partition_key=cluster_name_str
                    )
                    logging.info(f"[COSMOS UPDATE] Successfully read item {item_id_str} with cluster_name='{cluster_name_str}'")
                    logging.info(f"[COSMOS UPDATE] Read item data: {existing_item}")
                except exceptions.CosmosResourceNotFoundError:
                    logging.warning(f"[COSMOS UPDATE] Item {item_id_str} not found with read_item (cluster_name='{cluster_name_str}') - will create new")
                    existing_item = None
                except Exception as read_err:
                    logging.error(f"[COSMOS UPDATE] read_item failed: {read_err}")
                    import traceback
                    logging.error(f"Full exception: {traceback.format_exc()}")
                    existing_item = None
            else:
                logging.info(f"[COSMOS UPDATE] Using existing item from query (skipping read_item)")
                
            # If we found an existing item, update it
            if existing_item:
                logging.info(f"[COSMOS UPDATE] Proceeding with UPDATE operation for item {item_id_str}")
                # Get the etag for concurrency control
                etag = existing_item.get('_etag')
                logging.info(f"[COSMOS UPDATE] Item etag: {etag}")
                
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
                        logging.info(f"[COSMOS UPDATE] Preserving existing value for '{key}': '{existing_item.get(key)}' (update value was empty)")
                
                # Ensure id and cluster_name are always correct
                existing_item["id"] = item_id_str
                if not existing_item.get("cluster_name"):
                    existing_item["cluster_name"] = cluster_name_str or updates.get("cluster_name", "")
                
                logging.info(f"[COSMOS UPDATE] Merged item to upsert: {existing_item}")
                
                # Upsert with etag for optimistic concurrency control
                try:
                    result = self.container.upsert_item(
                        body=existing_item,
                        if_match=etag  # Only update if etag matches (no concurrent modifications)
                    )
                    logging.info(f"[COSMOS UPDATE] Successfully updated item {item_id_str} with etag concurrency control")
                    logging.info(f"[COSMOS UPDATE] Updated item result: {result}")
                    return True
                except exceptions.CosmosHttpResponseError as ce:
                    if ce.status_code == 412:  # Precondition failed (etag mismatch)
                        logging.warning(f"[COSMOS UPDATE] Concurrent modification detected (412), retrying without etag...")
                        # Retry once without etag (force update)
                        result = self.container.upsert_item(body=existing_item)
                        logging.info(f"[COSMOS UPDATE] Updated item {item_id_str} on retry")
                        logging.info(f"[COSMOS UPDATE] Retry result: {result}")
                        return True
                    else:
                        logging.error(f"[COSMOS UPDATE] Upsert failed with status {ce.status_code}: {ce}")
                        raise
            else:
                # Item doesn't exist, so create it with all required fields
                logging.info(f"[COSMOS UPDATE] Proceeding with CREATE operation for item {item_id_str}")
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
                
                logging.info(f"[COSMOS UPDATE] New item to create: {new_item}")
                
                result = self.container.upsert_item(body=new_item)
                logging.info(f"[COSMOS UPDATE] Created new item {item_id_str}")
                logging.info(f"[COSMOS UPDATE] Create result: {result}")
                return True

        except Exception as e:
            logging.error(f"Failed to update item {item_id} in Cosmos DB: {str(e)}")
            raise Exception(f"Failed to update item in Cosmos DB: {str(e)}")

    def get_all_items(self, offset=0, limit=10):
        query = "SELECT * FROM c ORDER BY c.dateOfCreation DESC OFFSET @offset LIMIT @limit"
        items = list(self.container.query_items(
            query=query,
            parameters=[{"name": "@offset", "value": offset}, {"name": "@limit", "value": limit}],
            enable_cross_partition_query=True
        ))
        total_count = list(self.container.query_items(
            query="SELECT VALUE COUNT(1) FROM c",
            enable_cross_partition_query=True
        ))
        total_count = total_count[0] if total_count else 0
        returned_count = len(items)
        return {
            "items": items,
            "total_count": total_count,
            "offset": offset,
            "limit": limit,
            "returned_count": returned_count
        }

    def search_items_by_message(self, search_query, offset=0, limit=10):
        query = "SELECT * FROM c WHERE CONTAINS(LOWER(c.message), LOWER(@search_query)) ORDER BY c.dateOfCreation DESC OFFSET @offset LIMIT @limit"
        items = list(self.container.query_items(
            query=query,
            parameters=[{"name": "@search_query", "value": search_query}, {"name": "@offset", "value": offset}, {"name": "@limit", "value": limit}],
            enable_cross_partition_query=True
        ))
        total_count = list(self.container.query_items(
            query="SELECT VALUE COUNT(1) FROM c WHERE CONTAINS(LOWER(c.message), LOWER(@search_query))",
            parameters=[{"name": "@search_query", "value": search_query}],
            enable_cross_partition_query=True
        ))
        total_count = total_count[0] if total_count else 0
        returned_count = len(items)
        return {
            "items": items,
            "total_count": total_count,
            "offset": offset,
            "limit": limit,
            "returned_count": returned_count
        }

    def get_item(self, item_id, zipcode):
        """Legacy method - get item by id and zipcode"""
        items = list(self.container.query_items(
            query="SELECT * FROM c WHERE c.id=@item_id AND c.zipcode=@zipcode",
            parameters=[{"name": "@item_id", "value": item_id}, {"name": "@zipcode", "value": zipcode}],
            enable_cross_partition_query=True
        ))
        return items[0] if items else None

    def get_item_by_cluster(self, item_id: str, cluster_name: str) -> Optional[Dict[str, Any]]:
        """Get item by id and cluster_name (new partition key structure)"""
        items = list(self.container.query_items(
            query="SELECT * FROM c WHERE c.id=@item_id AND c.cluster_name=@cluster_name",
            parameters=[
                {"name": "@item_id", "value": item_id},
                {"name": "@cluster_name", "value": cluster_name}
            ],
            enable_cross_partition_query=True
        ))
        return items[0] if items else None

    def get_all_clusters(self, offset=0, limit=10, search=""):
        query = "SELECT * FROM c"
        if search:
            search_escaped = search.replace("'", "''")
            query += f" WHERE CONTAINS(LOWER(c.name), LOWER('{search_escaped}')) OR CONTAINS(LOWER(c.description), LOWER('{search_escaped}'))"
        query += " ORDER BY c.created_at DESC OFFSET @offset LIMIT @limit"
        items = list(self.cluster_container.query_items(
            query=query,
            parameters=[{"name": "@offset", "value": offset}, {"name": "@limit", "value": limit}],
            enable_cross_partition_query=True
        ))
        count_query = "SELECT VALUE COUNT(1) FROM c"
        if search:
            count_query += f" WHERE CONTAINS(LOWER(c.name), LOWER('{search_escaped}')) OR CONTAINS(LOWER(c.description), LOWER('{search_escaped}'))"
        total_count = list(self.cluster_container.query_items(
            query=count_query,
            enable_cross_partition_query=True
        ))
        total_count = total_count[0] if total_count else 0
        returned_count = len(items)
        return {
            "items": items,
            "total_count": total_count,
            "offset": offset,
            "limit": limit,
            "returned_count": returned_count
        }

    def find_cluster_by_zipcode(self, zipcode: str) -> Optional[Dict[str, Any]]:
        """
        Find a cluster that contains the given zipcode.
        
        Args:
            zipcode: The zipcode to search for
            
        Returns:
            The cluster document if found, None otherwise
        """
        try:
            # Query to find cluster containing this zipcode
            query = "SELECT * FROM c WHERE ARRAY_CONTAINS(c.zipcodes, @zipcode)"
            parameters = [{"name": "@zipcode", "value": zipcode}]
            
            results = list(self.cluster_container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True,
                max_item_count=1
            ))
            
            if results:
                # Remove Cosmos DB system fields
                cluster = results[0]
                system_fields = ['_rid', '_self', '_etag', '_attachments', '_ts']
                return {k: v for k, v in cluster.items() if k not in system_fields}
            return None
            
        except Exception as e:
            logging.error(f"Failed to search for cluster by zipcode: {str(e)}")
            return None
