import os
import logging
import json
import pyodbc
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import IntEnum

# SQL Server Configuration from environment
SQL_SERVER = os.environ.get("SQL_SERVER")
SQL_DATABASE = os.environ.get("SQL_DATABASE", "homeguard")
SQL_USERNAME = os.environ.get("SQL_USERNAME")
SQL_PASSWORD = os.environ.get("SQL_PASSWORD")
SQL_DRIVER = os.environ.get("SQL_DRIVER", "ODBC Driver 17 for SQL Server")


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


class SQLServerService:
    def __init__(self):
        self.connection_string = (
            f"DRIVER={{{SQL_DRIVER}}};"
            f"SERVER={SQL_SERVER};"
            f"DATABASE={SQL_DATABASE};"
            f"UID={SQL_USERNAME};"
            f"PWD={SQL_PASSWORD};"
            f"Encrypt=yes;"
            f"TrustServerCertificate=yes;"
            f"Connection Timeout=30;"
        )

    def _get_connection(self):
        """Get a new database connection"""
        return pyodbc.connect(self.connection_string)

    def _row_to_dict(self, cursor, row):
        """Convert a database row to dictionary"""
        columns = [column[0] for column in cursor.description]
        return dict(zip(columns, row))

    def _map_db_to_api(self, db_row: Dict[str, Any], cluster_name: Optional[str] = None) -> Dict[str, Any]:
        """Map SQL Server row to API response format"""
        # Use BodyFindID as the primary identifier
        item_id = str(db_row.get("BodyFindID"))
        
        return {
            "id": item_id,
            "status": CostEstStatus.to_string(db_row.get("CostEstStatusID", 0)),
            "thread_id": "",
            "dateOfCreation": None,
            "type": "home_repair",
            "message": db_row.get("FindingText", ""),
            "currency": "USD",
            "min_estimate": db_row.get("CostEstL", 0.0),
            "max_estimate": db_row.get("CostEstH", 0.0),
            "zipcode": str(db_row.get("Zipcode", "")).zfill(5) if db_row.get("Zipcode") else "",
            "cluster_name": cluster_name or "",
            "estimate_scope": "full",
        }

    def get_cluster(self, cluster_id: str) -> Optional[Dict[str, Any]]:
        """Get cluster by ID with cluster name"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Get cluster info
            cursor.execute("""
                SELECT ClusterID, ClusterName, ClusterDescription
                FROM [dbo].[Clusters]
                WHERE ClusterID = ?
            """, (int(cluster_id),))

            row = cursor.fetchone()
            if not row:
                cursor.close()
                conn.close()
                return None

            cluster = self._row_to_dict(cursor, row)
            cursor.close()
            conn.close()

            return {
                "id": str(cluster["ClusterID"]),
                "name": cluster["ClusterName"],
                "description": cluster.get("ClusterDescription", ""),
            }

        except Exception as e:
            logging.error(f"Failed to get cluster: {e}")
            return None

    def save_flat_items(self, items, cosmos_service=None):
        saved_count = 0
        failed_count = 0
        saved_items_for_cosmos = []  # Track items for Cosmos sync
        sql_body_find_ids = []  # Track IDs for potential rollback
        
        conn = self._get_connection()
        cursor = conn.cursor()

        for item in items:
            try:
                # Get item ID
                item_id = item.get("id") or item.get("thread_id")
                
                status_id = CostEstStatus.from_string(item.get("status", "need_estimate"))
                
                # Get cluster_id for Cosmos sync (NOT saved to SQL Server)
                cluster_id = None
                zipcode = item.get("zipcode", "00000")
                if zipcode:
                    cluster_id = self._find_cluster_id_by_zipcode(cursor, zipcode)

                # Try to convert to numeric ID for BodyFindID lookup
                try:
                    numeric_id = int(item_id) if item_id else None
                except (ValueError, TypeError):
                    numeric_id = None

                actual_body_find_id = None

                # Check if record exists with this BodyFindID
                if numeric_id:
                    cursor.execute("""
                        SELECT BodyFindID FROM [dbo].[BodyFindings] 
                        WHERE BodyFindID = ?
                    """, (numeric_id,))
                    existing = cursor.fetchone()

                    if existing:
                        # Update existing record (only cost fields, not zipcode or clusterId)
                        logging.info(f"Updating existing item with id: {numeric_id}")
                        cursor.execute("""
                            UPDATE [dbo].[BodyFindings]
                            SET FindingText = ?,
                                CostEstL = ?,
                                CostEstH = ?,
                                CostEstStatusID = ?
                            WHERE BodyFindID = ?
                        """, (
                            item.get("message", ""),
                            item.get("min_estimate", 0.0),
                            item.get("max_estimate", 0.0),
                            status_id,
                            numeric_id
                        ))
                        actual_body_find_id = numeric_id
                    else:
                        # Insert new record - get next available BodyFindID
                        logging.info(f"Inserting new item")
                        cursor.execute("SELECT ISNULL(MAX(BodyFindID), 0) + 1 FROM [dbo].[BodyFindings]")
                        new_body_find_id = cursor.fetchone()[0]
                        
                        cursor.execute("""
                            INSERT INTO [dbo].[BodyFindings] 
                            (BodyFindID, FindingText, CostEstL, CostEstH, CostEstStatusID, NeedtoEdit)
                            VALUES (?, ?, ?, ?, ?, 0)
                        """, (
                            new_body_find_id,
                            item.get("message", ""),
                            item.get("min_estimate", 0.0),
                            item.get("max_estimate", 0.0),
                            status_id
                        ))
                        actual_body_find_id = new_body_find_id
                else:
                    # Insert new record without ID - get next available BodyFindID
                    logging.info(f"Inserting new item")
                    cursor.execute("SELECT ISNULL(MAX(BodyFindID), 0) + 1 FROM [dbo].[BodyFindings]")
                    new_body_find_id = cursor.fetchone()[0]
                    
                    cursor.execute("""
                        INSERT INTO [dbo].[BodyFindings] 
                        (BodyFindID, FindingText, CostEstL, CostEstH, CostEstStatusID, NeedtoEdit)
                        VALUES (?, ?, ?, ?, ?, 0)
                    """, (
                        new_body_find_id,
                        item.get("message", ""),
                        item.get("min_estimate", 0.0),
                        item.get("max_estimate", 0.0),
                        status_id
                    ))
                    actual_body_find_id = new_body_find_id
                
                # Track for Cosmos sync
                if actual_body_find_id:
                    sql_body_find_ids.append(actual_body_find_id)
                    saved_items_for_cosmos.append({
                        "id": str(actual_body_find_id),
                        "message": item.get("message", ""),
                        "zipcode": item.get("zipcode", ""),
                        "min_estimate": item.get("min_estimate", 0.0),
                        "max_estimate": item.get("max_estimate", 0.0),
                        "clusterId": cluster_id,
                        "status": status_id,
                        "thread_id": item.get("thread_id", ""),
                        "dateOfCreation": item.get("dateOfCreation", ""),
                        "type": item.get("type", "home_repair"),
                        "currency": item.get("currency", "USD"),
                    })
                
                saved_count += 1
            except Exception as e:
                logging.error(f"Failed to save item {item.get('id', 'unknown')}: {e}")
                failed_count += 1

        # Commit SQL transaction first
        conn.commit()
        logging.info(f"SQL Server save committed: {saved_count} items")
        
        # Sync to Cosmos DB if service provided
        if cosmos_service and saved_items_for_cosmos:
            try:
                logging.info(f"Syncing {len(saved_items_for_cosmos)} items to Cosmos DB")
                
                # Convert items to Cosmos format with cluster_name resolution
                cosmos_items = []
                for sql_item in saved_items_for_cosmos:
                    cluster_name = ""
                    if sql_item.get("clusterId"):
                        try:
                            cluster = self.get_cluster(str(sql_item["clusterId"]))
                            if cluster:
                                cluster_name = cluster.get("name", "")
                        except Exception as cluster_err:
                            logging.warning(f"Failed to get cluster name for ID {sql_item['clusterId']}: {cluster_err}")
                    
                    cosmos_item = cosmos_service._convert_to_cosmos_format(sql_item, cluster_name)
                    cosmos_items.append(cosmos_item)
                
                # Save to Cosmos DB
                cosmos_result = cosmos_service.save_flat_items(cosmos_items)
                
                if cosmos_result.get("failed_count", 0) > 0:
                    # Cosmos save failed for some items - rollback SQL
                    logging.error(f"Cosmos DB save failed for {cosmos_result['failed_count']} items. Rolling back SQL.")
                    
                    # Rollback: delete the items we just saved
                    rollback_cursor = conn.cursor()
                    for body_find_id in sql_body_find_ids:
                        try:
                            rollback_cursor.execute("""
                                DELETE FROM [dbo].[BodyFindings]
                                WHERE BodyFindID = ?
                            """, (body_find_id,))
                        except Exception as rb_err:
                            logging.error(f"Rollback failed for BodyFindID {body_find_id}: {rb_err}")
                    
                    conn.commit()
                    rollback_cursor.close()
                    conn.close()
                    
                    raise Exception(f"Failed to sync items to Cosmos DB. SQL changes rolled back. Details: {cosmos_result.get('failed_items')}")
                
                logging.info(f"Successfully synced {cosmos_result['saved_count']} items to Cosmos DB")
                
            except Exception as cosmos_err:
                # Cosmos sync failed completely - rollback SQL
                logging.error(f"Cosmos DB sync failed: {cosmos_err}. Rolling back SQL.")
                
                # Rollback: delete the items we just saved
                rollback_cursor = conn.cursor()
                for body_find_id in sql_body_find_ids:
                    try:
                        rollback_cursor.execute("""
                            DELETE FROM [dbo].[BodyFindings]
                            WHERE BodyFindID = ?
                        """, (body_find_id,))
                    except Exception as rb_err:
                        logging.error(f"Rollback failed for BodyFindID {body_find_id}: {rb_err}")
                
                conn.commit()
                rollback_cursor.close()
                conn.close()
                
                raise Exception(f"Failed to sync items to Cosmos DB. SQL changes rolled back. Details: {cosmos_err}")
        
        cursor.close()
        conn.close()

        return {"saved_count": saved_count, "failed_count": failed_count}

    def _find_cluster_id_by_zipcode(self, cursor, zipcode: str) -> Optional[int]:
        """Find ClusterId by zipcode"""
        try:
            cursor.execute("""
                SELECT TOP 1 ClusterID 
                FROM [dbo].[ClusterZipCodes]
                WHERE ZipCode = ?
            """, (int(zipcode),))
            
            row = cursor.fetchone()
            return row[0] if row else None
        except:
            return None

    def get_all_items(self, offset=0, limit=10):
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) 
            FROM [dbo].[BodyFindings]
            WHERE CostEstStatusID = 20 OR CostEstStatusID = 40
        """)
        total_count = cursor.fetchone()[0]

        cursor.execute("""
            SELECT 
                bf.BodyFindID,
                bf.FindingText,
                bf.Zipcode,
                bf.CostEstL,
                bf.CostEstH,
                bf.CostEstStatusID
            FROM [dbo].[BodyFindings] bf
            WHERE bf.CostEstStatusID = 20 OR bf.CostEstStatusID = 40
            ORDER BY bf.BodyFindID DESC
            OFFSET ? ROWS
            FETCH NEXT ? ROWS ONLY
        """, (offset, limit))

        rows = cursor.fetchall()
        items = []
        for row in rows:
            row_dict = self._row_to_dict(cursor, row)
            items.append(self._map_db_to_api(row_dict))

        cursor.close()
        conn.close()

        return {
            "items": items,
            "total_count": total_count,
            "offset": offset,
            "limit": limit,
            "returned_count": len(items)
        }

    def search_items_by_message(self, search_query, offset=0, limit=10):
        conn = self._get_connection()
        cursor = conn.cursor()

        search_pattern = f"%{search_query}%"

        cursor.execute("""
            SELECT COUNT(*) 
            FROM [dbo].[BodyFindings]
            WHERE FindingText LIKE ? AND (CostEstStatusID = 20 OR CostEstStatusID = 40)
        """, (search_pattern,))
        total_count = cursor.fetchone()[0]

        cursor.execute("""
            SELECT 
                bf.BodyFindID,
                bf.FindingText,
                bf.Zipcode,
                bf.CostEstL,
                bf.CostEstH,
                bf.CostEstStatusID
            FROM [dbo].[BodyFindings] bf
            WHERE bf.FindingText LIKE ? AND (bf.CostEstStatusID = 20 OR bf.CostEstStatusID = 40)
            ORDER BY bf.BodyFindID DESC
            OFFSET ? ROWS
            FETCH NEXT ? ROWS ONLY
        """, (search_pattern, offset, limit))

        rows = cursor.fetchall()
        items = []
        for row in rows:
            row_dict = self._row_to_dict(cursor, row)
            items.append(self._map_db_to_api(row_dict))

        cursor.close()
        conn.close()

        return {
            "items": items,
            "total_count": total_count,
            "offset": offset,
            "limit": limit,
            "returned_count": len(items)
        }

    def get_item(self, item_id, zipcode=None):
        """Get item by id (BodyFindID)"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Try to convert item_id to int for BodyFindID
        try:
            numeric_id = int(item_id)
        except (ValueError, TypeError):
            logging.warning(f"Invalid item_id format: {item_id}")
            return None

        cursor.execute("""
            SELECT 
                bf.BodyFindID,
                bf.FindingText,
                bf.Zipcode,
                bf.CostEstL,
                bf.CostEstH,
                bf.CostEstStatusID
            FROM [dbo].[BodyFindings] bf
            WHERE bf.BodyFindID = ?
        """, (numeric_id,))

        row = cursor.fetchone()
        
        if row:
            row_dict = self._row_to_dict(cursor, row)
            cursor.close()
            conn.close()
            return self._map_db_to_api(row_dict)
        
        cursor.close()
        conn.close()
        return None

    def get_item_by_cluster(self, item_id: str, cluster_name: str) -> Optional[Dict[str, Any]]:
        """Get item by id (BodyFindID)"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Try to convert item_id to int for BodyFindID
        try:
            numeric_id = int(item_id)
        except (ValueError, TypeError):
            logging.warning(f"Invalid item_id format: {item_id}")
            return None

        cursor.execute("""
            SELECT 
                bf.BodyFindID,
                bf.FindingText,
                bf.Zipcode,
                bf.CostEstL,
                bf.CostEstH,
                bf.CostEstStatusID
            FROM [dbo].[BodyFindings] bf
            WHERE bf.BodyFindID = ?
        """, (numeric_id,))

        row = cursor.fetchone()
        
        if row:
            row_dict = self._row_to_dict(cursor, row)
            cursor.close()
            conn.close()
            return self._map_db_to_api(row_dict)
        
        cursor.close()
        conn.close()
        return None

    def get_all_clusters(self, offset=0, limit=10, search=""):
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            where_clause = ""
            params = []
            if search:
                search_pattern = f"%{search}%"
                where_clause = "WHERE ClusterName LIKE ? OR ClusterDescription LIKE ?"
                params = [search_pattern, search_pattern]

            count_query = f"SELECT COUNT(*) FROM [dbo].[Clusters] {where_clause}"
            cursor.execute(count_query, params)
            total_count = cursor.fetchone()[0]

            query = f"""
                SELECT ClusterID, ClusterName, ClusterDescription, CreatedDate
                FROM [dbo].[Clusters]
                {where_clause}
                ORDER BY CreatedDate DESC
                OFFSET ? ROWS
                FETCH NEXT ? ROWS ONLY
            """
            cursor.execute(query, params + [offset, limit])

            # Convert all cluster rows to dictionaries first (before any nested queries)
            cluster_rows = cursor.fetchall()
            clusters = [self._row_to_dict(cursor, row) for row in cluster_rows]
            
            items = []
            for cluster in clusters:
                cluster_id = cluster["ClusterID"]

                cursor.execute("""
                    SELECT ZipCode
                    FROM [dbo].[ClusterZipCodes]
                    WHERE ClusterID = ?
                    ORDER BY ZipCode
                """, (cluster_id,))

                zipcodes = [str(zip_row[0]).zfill(5) for zip_row in cursor.fetchall()]

                items.append({
                    "id": str(cluster_id),
                    "name": cluster["ClusterName"],
                    "description": cluster.get("ClusterDescription", ""),
                    "zipcodes": zipcodes,
                    "created_at": cluster["CreatedDate"].isoformat() if cluster.get("CreatedDate") else None,
                    "updated_at": cluster["CreatedDate"].isoformat() if cluster.get("CreatedDate") else None
                })

            cursor.close()
            conn.close()

            return {
                "items": items,
                "total_count": total_count,
                "offset": offset,
                "limit": limit,
                "returned_count": len(items)
            }
        except Exception as e:
            logging.error(f"Failed to get clusters: {e}")
            # Return empty result instead of raising error
            return {
                "items": [],
                "total_count": 0,
                "offset": offset,
                "limit": limit,
                "returned_count": 0
            }

    def find_cluster_by_zipcode(self, zipcode):
        """Find cluster by zipcode"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT TOP 1 c.ClusterID, c.ClusterName
                FROM [dbo].[Clusters] c
                INNER JOIN [dbo].[ClusterZipCodes] cz ON c.ClusterID = cz.ClusterID
                WHERE cz.ZipCode = ?
            """, (int(zipcode),))

            row = cursor.fetchone()
            cursor.close()
            conn.close()

            if row:
                return {
                    "cluster_id": str(row[0]),
                    "cluster_name": row[1]
                }
            
            return None
        except Exception as e:
            logging.error(f"Failed to find cluster by zipcode: {e}")
            return None

    def update_item(self, item_id: str, updates: dict, cosmos_service=None) -> bool:
        """
        Update an existing item in SQL Server and optionally in Cosmos DB.
        
        SQL Server updates: Only cost estimates (min_estimate, max_estimate), message, and status
        Cosmos DB updates: All fields including zipcode, cluster_name, thread_id, etc.
        
        Note: zipcode and clusterId are NOT updated in SQL Server but ARE updated in Cosmos DB
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Try to convert item_id to int for BodyFindID
            try:
                numeric_id = int(item_id)
            except (ValueError, TypeError):
                logging.warning(f"Invalid item_id format: {item_id}")
                return False

            # Get the current item state for potential rollback
            cursor.execute("""
                SELECT FindingText, CostEstL, CostEstH, CostEstStatusID, Zipcode
                FROM [dbo].[BodyFindings]
                WHERE BodyFindID = ?
            """, (numeric_id,))
            old_row = cursor.fetchone()
            
            if not old_row:
                logging.warning(f"Item {item_id} not found for update")
                cursor.close()
                conn.close()
                return False
            
            # Store old values for rollback (only fields we're updating in SQL)
            old_values = {
                "FindingText": old_row[0],
                "CostEstL": old_row[1],
                "CostEstH": old_row[2],
                "CostEstStatusID": old_row[3]
            }
            # Store current zipcode for Cosmos sync
            current_zipcode = str(old_row[4]) if old_row[4] else ""

            # Convert status string to integer if present
            status_id = None
            if "status" in updates:
                status_id = CostEstStatus.from_string(updates.get("status", "need_estimate"))

            # Build UPDATE query dynamically based on provided fields
            # NOTE: For now, only update cost estimates in SQL Server
            # zipcode and clusterId will NOT be updated in SQL Server
            update_fields = []
            params = []

            if "message" in updates:
                update_fields.append("FindingText = ?")
                params.append(updates["message"])
            
            # NOTE: zipcode update commented out - not updating in SQL Server
            # if "zipcode" in updates:
            #     update_fields.append("Zipcode = ?")
            #     params.append(updates["zipcode"])
            
            if "min_estimate" in updates:
                update_fields.append("CostEstL = ?")
                params.append(updates["min_estimate"])
            
            if "max_estimate" in updates:
                update_fields.append("CostEstH = ?")
                params.append(updates["max_estimate"])
            
            # NOTE: clusterId update commented out - not updating in SQL Server
            # if "cluster_id" in updates:
            #     update_fields.append("ClusterID = ?")
            #     params.append(updates["cluster_id"])
            
            if status_id is not None:
                update_fields.append("CostEstStatusID = ?")
                params.append(status_id)

            if not update_fields:
                logging.warning("No fields to update")
                cursor.close()
                conn.close()
                return True  # Nothing to update is not an error

            # Build and execute UPDATE query
            update_sql = f"UPDATE [dbo].[BodyFindings] SET {', '.join(update_fields)} WHERE BodyFindID = ?"
            params.append(numeric_id)

            logging.info(f"Executing update for item {item_id}: {len(update_fields)} fields")
            cursor.execute(update_sql, params)
            
            rows_affected = cursor.rowcount

            if rows_affected == 0:
                logging.warning(f"No rows updated for item {item_id}")
                cursor.close()
                conn.close()
                return False

            # Commit SQL transaction
            conn.commit()
            logging.info(f"SQL Server update committed for item {item_id}")

            # Sync to Cosmos DB if service provided
            if cosmos_service:
                try:
                    # Read back the updated item from SQL Server
                    cursor.execute("""
                        SELECT 
                            bf.BodyFindID,
                            bf.FindingText,
                            bf.Zipcode,
                            bf.CostEstL,
                            bf.CostEstH,
                            bf.CostEstStatusID
                        FROM [dbo].[BodyFindings] bf
                        WHERE bf.BodyFindID = ?
                    """, (numeric_id,))
                    
                    updated_row = cursor.fetchone()
                    updated_dict = self._row_to_dict(cursor, updated_row)
                    updated_item = self._map_db_to_api(updated_dict)
                    
                    # If zipcode or cluster_name were in the update request, apply them to Cosmos
                    # (they're not updated in SQL Server, but should be in Cosmos)
                    if "zipcode" in updates:
                        updated_item["zipcode"] = updates["zipcode"]
                        logging.info(f"Applying zipcode from updates to Cosmos: {updates['zipcode']}")
                    
                    # Determine which zipcode to use for cluster lookup
                    zipcode_to_use = updated_item.get("zipcode") or current_zipcode
                    
                    # Resolve cluster name by looking up zipcode
                    cluster_name = ""
                    if zipcode_to_use:
                        try:
                            logging.info(f"Resolving cluster name for zipcode: {zipcode_to_use}")
                            cluster_info = self.find_cluster_by_zipcode(zipcode_to_use)
                            if cluster_info:
                                cluster_name = cluster_info.get("cluster_name", "")
                                logging.info(f"Resolved cluster name: '{cluster_name}' for zipcode {zipcode_to_use}")
                            else:
                                logging.warning(f"No cluster found for zipcode {zipcode_to_use}")
                        except Exception as cluster_err:
                            logging.error(f"Failed to get cluster name for zipcode {zipcode_to_use}: {cluster_err}")
                    else:
                        logging.info(f"No zipcode found for item {item_id}")
                    
                    # Convert to Cosmos format
                    cosmos_item = cosmos_service._convert_to_cosmos_format(updated_item, cluster_name)
                    
                    # Merge any additional fields from the original updates that should go to Cosmos
                    # (but not SQL Server) such as thread_id, type, dateOfCreation, etc.
                    cosmos_only_fields = ["thread_id", "type", "dateOfCreation", "currency"]
                    for field in cosmos_only_fields:
                        if field in updates:
                            cosmos_item[field] = updates[field]
                            logging.info(f"Applying {field} from updates to Cosmos: {updates[field]}")
                    
                    logging.info(f"Cosmos item format: {json.dumps(cosmos_item)}")
                    
                    # Update in Cosmos DB using cluster_name as partition key
                    cosmos_success = cosmos_service.update_item(
                        item_id=str(numeric_id),
                        cluster_name=cluster_name,
                        updates=cosmos_item
                    )
                    
                    if not cosmos_success:
                        # Cosmos update failed - rollback SQL (only fields we updated)
                        logging.error("Cosmos DB update failed. Rolling back SQL.")
                        
                        rollback_cursor = conn.cursor()
                        rollback_cursor.execute("""
                            UPDATE [dbo].[BodyFindings]
                            SET FindingText = ?, CostEstL = ?, CostEstH = ?, CostEstStatusID = ?
                            WHERE BodyFindID = ?
                        """, (
                            old_values["FindingText"],
                            old_values["CostEstL"],
                            old_values["CostEstH"],
                            old_values["CostEstStatusID"],
                            numeric_id
                        ))
                        conn.commit()
                        rollback_cursor.close()
                        conn.close()
                        
                        raise Exception("Failed to sync update to Cosmos DB. SQL changes rolled back.")
                    
                    logging.info(f"Successfully synced update for item {item_id} to Cosmos DB")
                    
                except Exception as cosmos_err:
                    # Cosmos sync failed - rollback SQL (only fields we updated)
                    logging.error(f"Cosmos DB sync failed: {cosmos_err}. Rolling back SQL.")
                    
                    rollback_cursor = conn.cursor()
                    rollback_cursor.execute("""
                        UPDATE [dbo].[BodyFindings]
                        SET FindingText = ?, CostEstL = ?, CostEstH = ?, CostEstStatusID = ?
                        WHERE BodyFindID = ?
                    """, (
                        old_values["FindingText"],
                        old_values["CostEstL"],
                        old_values["CostEstH"],
                        old_values["CostEstStatusID"],
                        numeric_id
                    ))
                    conn.commit()
                    rollback_cursor.close()
                    conn.close()
                    
                    raise Exception(f"Failed to sync update to Cosmos DB. SQL changes rolled back. Details: {cosmos_err}")
            
            cursor.close()
            conn.close()

            logging.info(f"Successfully updated item {item_id}")
            return True

        except Exception as e:
            logging.error(f"Failed to update item {item_id}: {e}")
            raise e
