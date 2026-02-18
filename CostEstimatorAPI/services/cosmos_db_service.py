# import os
# import logging
# import uuid
# from typing import Optional, Dict, Any, List
# from azure.cosmos import CosmosClient, exceptions
# from datetime import datetime
# from enum import IntEnum

# COSMOS_DB_ENDPOINT = os.environ.get("COSMOS_DB_ENDPOINT")
# COSMOS_DB_KEY = os.environ.get("COSMOS_DB_KEY")
# COSMOS_DB_DATABASE_NAME = os.environ.get("COSMOS_DB_DATABASE_NAME", "homeguard")

# COSMOS_DB_CONTAINER_NAME = os.environ.get("COSMOS_DB_CONTAINER_NAME", "items")
# COSMOS_DB_CLUSTER_CONTAINER_NAME = os.environ.get("COSMOS_DB_CLUSTER_CONTAINER_NAME", "zipcodeClusters")

# # Import CostEstStatus from sql_db_service
# class CostEstStatus(IntEnum):
#     """Cost Estimate Status mapping for SQL Server CostEstStatusID field"""
#     LEAVE_ALONE = 0
#     NEED_ESTIMATE = 10
#     ESTIMATE_COMPLETE = 20
#     EDIT_INPUT = 30
#     AI_ANALYZED = 40
    
#     @classmethod
#     def from_string(cls, status_str: str) -> int:
#         """Convert string status to integer ID"""
#         mapping = {
#             "leave_alone": cls.LEAVE_ALONE,
#             "need_estimate": cls.NEED_ESTIMATE,
#             "estimate_complete": cls.ESTIMATE_COMPLETE,
#             "edit_input": cls.EDIT_INPUT,
#             "ai_analyzed": cls.AI_ANALYZED,
#             "approved": cls.ESTIMATE_COMPLETE,
#             "pending": cls.NEED_ESTIMATE,
#             "completed": cls.ESTIMATE_COMPLETE,
#         }
#         return mapping.get(status_str.lower(), cls.LEAVE_ALONE)
    
#     @classmethod
#     def to_string(cls, status_id: int) -> str:
#         """Convert integer ID to string status"""
#         mapping = {
#             cls.LEAVE_ALONE: "leave_alone",
#             cls.NEED_ESTIMATE: "need_estimate",
#             cls.ESTIMATE_COMPLETE: "estimate_complete",
#             cls.EDIT_INPUT: "edit_input",
#             cls.AI_ANALYZED: "ai_analyzed",
#         }
#         return mapping.get(status_id, "leave_alone")

# class CosmosDBService:
#     def __init__(self):
#         self.client = CosmosClient(COSMOS_DB_ENDPOINT, credential=COSMOS_DB_KEY)
#         self.database = self.client.get_database_client(COSMOS_DB_DATABASE_NAME)
#         self.container = self.database.get_container_client(COSMOS_DB_CONTAINER_NAME)
#         self.cluster_container = self.database.get_container_client(COSMOS_DB_CLUSTER_CONTAINER_NAME)

#     def _convert_status_to_string(self, status_id: int) -> str:
#         """Convert SQL Server status integer to Cosmos DB status string"""
#         return CostEstStatus.to_string(status_id)
    
#     def _convert_to_cosmos_format(self, item: Dict[str, Any], cluster_name: str = "") -> Dict[str, Any]:
#         """
#         Convert SQL Server item format to Cosmos DB format.
        
#         Maps SQL fields to Cosmos DB schema:
#         - status: integer -> string
#         - id: ensure string format
#         - cluster_name: add from resolution
#         - dateOfCreation: add if missing
#         - currency: add if missing
#         - type: add if missing
#         """
#         cosmos_item = {
#             "id": str(item.get("id", "")),
#             "status": item.get("status", "need_estimate") if isinstance(item.get("status"), str) else self._convert_status_to_string(item.get("status", 10)),
#             "dateOfCreation": item.get("dateOfCreation", datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")),
#             "message": item.get("message", ""),
#             "currency": item.get("currency", "USD"),
#             "min_estimate": float(item.get("min_estimate", 0.0)),
#             "max_estimate": float(item.get("max_estimate", 0.0)),
#             "cluster_name": cluster_name or item.get("cluster_name", ""),
#             "zipcode": str(item.get("zipcode", "")),
#         }
        
#         # Add optional fields if present
#         if "thread_id" in item:
#             cosmos_item["thread_id"] = item["thread_id"]
#         if "type" in item:
#             cosmos_item["type"] = item["type"]
#         else:
#             cosmos_item["type"] = "home_repair"
            
#         return cosmos_item

#     def save_flat_items(self, items):
#         saved_count = 0
#         failed_count = 0
#         for item in items:
#             try:
#                 # Generate unique id if not present
#                 if 'id' not in item:
#                     item['id'] = str(uuid.uuid4())
#                 self.container.upsert_item(item)
#                 saved_count += 1
#             except Exception as e:
#                 logging.error(f"Failed to save item: {e}")
#                 failed_count += 1
#         return {"saved_count": saved_count, "failed_count": failed_count}

#     def update_item(self, item_id: str, cluster_name: str, updates: Dict[str, Any]) -> bool:
#         """
#         Update an existing item in Cosmos DB.
        
#         Args:
#             item_id: The item ID (BodyFindID as string)
#             cluster_name: Partition key for the item (cluster_name)
#             updates: Dictionary with updated fields (already in Cosmos format)
            
#         Returns:
#             True if update successful, False otherwise
#         """
#         try:
#             logging.info(f"[COSMOS] Attempting to read item {item_id} with partition key cluster_name='{cluster_name}'")
#             # Read existing item first
#             try:
#                 existing_item = self.container.read_item(
#                     item=str(item_id),
#                     partition_key=str(cluster_name)
#                 )
#                 logging.info(f"[COSMOS] Found existing item {item_id} in Cosmos DB")
#             except exceptions.CosmosResourceNotFoundError:
#                 logging.warning(f"[COSMOS] Item {item_id} not found in Cosmos DB with cluster_name='{cluster_name}' - will upsert")
#                 # Item doesn't exist, so upsert the complete item
#                 if "id" not in updates:
#                     updates["id"] = str(item_id)
#                 if "cluster_name" not in updates:
#                     updates["cluster_name"] = str(cluster_name)
                
#                 self.container.upsert_item(body=updates)
#                 logging.info(f"Upserted item {item_id} to Cosmos DB")
#                 return True
            
#             # Merge updates into existing item
#             for key, value in updates.items():
#                 existing_item[key] = value
            
#             # Upsert the merged item
#             self.container.upsert_item(body=existing_item)
#             logging.info(f"Updated item {item_id} in Cosmos DB")
#             return True

#         except Exception as e:
#             logging.error(f"Failed to update item {item_id} in Cosmos DB: {str(e)}")
#             raise Exception(f"Failed to update item in Cosmos DB: {str(e)}")

#     def get_all_items(self, offset=0, limit=10):
#         query = "SELECT * FROM c ORDER BY c.dateOfCreation DESC OFFSET @offset LIMIT @limit"
#         items = list(self.container.query_items(
#             query=query,
#             parameters=[{"name": "@offset", "value": offset}, {"name": "@limit", "value": limit}],
#             enable_cross_partition_query=True
#         ))
#         total_count = list(self.container.query_items(
#             query="SELECT VALUE COUNT(1) FROM c",
#             enable_cross_partition_query=True
#         ))
#         total_count = total_count[0] if total_count else 0
#         returned_count = len(items)
#         return {
#             "items": items,
#             "total_count": total_count,
#             "offset": offset,
#             "limit": limit,
#             "returned_count": returned_count
#         }

#     def search_items_by_message(self, search_query, offset=0, limit=10):
#         query = "SELECT * FROM c WHERE CONTAINS(LOWER(c.message), LOWER(@search_query)) ORDER BY c.dateOfCreation DESC OFFSET @offset LIMIT @limit"
#         items = list(self.container.query_items(
#             query=query,
#             parameters=[{"name": "@search_query", "value": search_query}, {"name": "@offset", "value": offset}, {"name": "@limit", "value": limit}],
#             enable_cross_partition_query=True
#         ))
#         total_count = list(self.container.query_items(
#             query="SELECT VALUE COUNT(1) FROM c WHERE CONTAINS(LOWER(c.message), LOWER(@search_query))",
#             parameters=[{"name": "@search_query", "value": search_query}],
#             enable_cross_partition_query=True
#         ))
#         total_count = total_count[0] if total_count else 0
#         returned_count = len(items)
#         return {
#             "items": items,
#             "total_count": total_count,
#             "offset": offset,
#             "limit": limit,
#             "returned_count": returned_count
#         }

#     def get_item(self, item_id, zipcode):
#         """Legacy method - get item by id and zipcode"""
#         items = list(self.container.query_items(
#             query="SELECT * FROM c WHERE c.id=@item_id AND c.zipcode=@zipcode",
#             parameters=[{"name": "@item_id", "value": item_id}, {"name": "@zipcode", "value": zipcode}],
#             enable_cross_partition_query=True
#         ))
#         return items[0] if items else None

#     def get_item_by_cluster(self, item_id: str, cluster_name: str) -> Optional[Dict[str, Any]]:
#         """Get item by id and cluster_name (new partition key structure)"""
#         items = list(self.container.query_items(
#             query="SELECT * FROM c WHERE c.id=@item_id AND c.cluster_name=@cluster_name",
#             parameters=[
#                 {"name": "@item_id", "value": item_id},
#                 {"name": "@cluster_name", "value": cluster_name}
#             ],
#             enable_cross_partition_query=True
#         ))
#         return items[0] if items else None

#     def get_all_clusters(self, offset=0, limit=10, search=""):
#         query = "SELECT * FROM c"
#         if search:
#             search_escaped = search.replace("'", "''")
#             query += f" WHERE CONTAINS(LOWER(c.name), LOWER('{search_escaped}')) OR CONTAINS(LOWER(c.description), LOWER('{search_escaped}'))"
#         query += " ORDER BY c.created_at DESC OFFSET @offset LIMIT @limit"
#         items = list(self.cluster_container.query_items(
#             query=query,
#             parameters=[{"name": "@offset", "value": offset}, {"name": "@limit", "value": limit}],
#             enable_cross_partition_query=True
#         ))
#         count_query = "SELECT VALUE COUNT(1) FROM c"
#         if search:
#             count_query += f" WHERE CONTAINS(LOWER(c.name), LOWER('{search_escaped}')) OR CONTAINS(LOWER(c.description), LOWER('{search_escaped}'))"
#         total_count = list(self.cluster_container.query_items(
#             query=count_query,
#             enable_cross_partition_query=True
#         ))
#         total_count = total_count[0] if total_count else 0
#         returned_count = len(items)
#         return {
#             "items": items,
#             "total_count": total_count,
#             "offset": offset,
#             "limit": limit,
#             "returned_count": returned_count
#         }

#     def find_cluster_by_zipcode(self, zipcode: str) -> Optional[Dict[str, Any]]:
#         """
#         Find a cluster that contains the given zipcode.
        
#         Args:
#             zipcode: The zipcode to search for
            
#         Returns:
#             The cluster document if found, None otherwise
#         """
#         try:
#             # Query to find cluster containing this zipcode
#             query = "SELECT * FROM c WHERE ARRAY_CONTAINS(c.zipcodes, @zipcode)"
#             parameters = [{"name": "@zipcode", "value": zipcode}]
            
#             results = list(self.cluster_container.query_items(
#                 query=query,
#                 parameters=parameters,
#                 enable_cross_partition_query=True,
#                 max_item_count=1
#             ))
            
#             if results:
#                 # Remove Cosmos DB system fields
#                 cluster = results[0]
#                 system_fields = ['_rid', '_self', '_etag', '_attachments', '_ts']
#                 return {k: v for k, v in cluster.items() if k not in system_fields}
#             return None
            
#         except Exception as e:
#             logging.error(f"Failed to search for cluster by zipcode: {str(e)}")
#             return None
