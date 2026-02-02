# import os
# import logging
# import uuid
# from typing import Optional, Dict, Any
# from azure.cosmos import CosmosClient

# COSMOS_DB_ENDPOINT = os.environ.get("COSMOS_DB_ENDPOINT")
# COSMOS_DB_KEY = os.environ.get("COSMOS_DB_KEY")
# COSMOS_DB_DATABASE_NAME = os.environ.get("COSMOS_DB_DATABASE_NAME", "homeguard")

# COSMOS_DB_CONTAINER_NAME = os.environ.get("COSMOS_DB_CONTAINER_NAME", "items")
# COSMOS_DB_CLUSTER_CONTAINER_NAME = os.environ.get("COSMOS_DB_CLUSTER_CONTAINER_NAME", "zipcodeClusters")

# class CosmosDBService:
#     def __init__(self):
#         self.client = CosmosClient(COSMOS_DB_ENDPOINT, credential=COSMOS_DB_KEY)
#         self.database = self.client.get_database_client(COSMOS_DB_DATABASE_NAME)
#         self.container = self.database.get_container_client(COSMOS_DB_CONTAINER_NAME)
#         self.cluster_container = self.database.get_container_client(COSMOS_DB_CLUSTER_CONTAINER_NAME)

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
