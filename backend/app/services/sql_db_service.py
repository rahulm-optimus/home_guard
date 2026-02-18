"""
SQL Server Service
Business logic for SQL Server operations
"""

from typing import List, Dict, Any, Optional
import pyodbc
from app.core.config import settings
from app.core.exceptions import APIError, ErrorCodes
from app.schemas.requests import CostEstStatus
import logging
import threading
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class SQLServerService:
    """Service for managing SQL Server operations"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self.connection_string: Optional[str] = None
            self._initialize()
            self._initialized = True

    def _initialize(self):
        """Initialize SQL Server connection string"""
        if not settings.SQL_SERVER or not settings.SQL_USERNAME or not settings.SQL_PASSWORD:
            logger.warning("SQL Server credentials not configured. Service will run in mock mode.")
            return

        try:
            self.connection_string = (
                f"DRIVER={{{settings.SQL_DRIVER}}};"
                f"SERVER={settings.SQL_SERVER};"
                f"DATABASE={settings.SQL_DATABASE};"
                f"UID={settings.SQL_USERNAME};"
                f"PWD={settings.SQL_PASSWORD};"
                f"Encrypt={'yes' if settings.SQL_ENCRYPT else 'no'};"
                f"TrustServerCertificate={'yes' if settings.SQL_TRUST_SERVER_CERTIFICATE else 'no'};"
                f"Connection Timeout={settings.SQL_CONNECTION_TIMEOUT};"
            )
            logger.info(f"SQL Server connection string configured for database: {settings.SQL_DATABASE}")
        except Exception as e:
            logger.error(f"Failed to initialize SQL Server connection: {e}")
            raise APIError(
                status_code=500,
                error_code=ErrorCodes.DATABASE_ERROR,
                message="Failed to initialize database connection",
                details=str(e)
            )

    def _get_connection(self) -> pyodbc.Connection:
        """Get a new database connection with optimized settings"""
        if not self.connection_string:
            raise APIError(
                status_code=500,
                error_code=ErrorCodes.DATABASE_ERROR,
                message="Database not configured"
            )
        
        try:
            conn = pyodbc.connect(self.connection_string)
            # Let pyodbc handle encoding automatically based on SQL Server settings
            return conn
        except Exception as e:
            logger.error(f"Failed to connect to SQL Server: {e}")
            raise APIError(
                status_code=500,
                error_code=ErrorCodes.DATABASE_ERROR,
                message="Failed to connect to database",
                details=str(e)
            )

    def _row_to_dict(self, cursor: pyodbc.Cursor, row: pyodbc.Row) -> Dict[str, Any]:
        """Convert a database row to dictionary"""
        columns = [column[0] for column in cursor.description]
        return dict(zip(columns, row))

    def _map_db_to_api(self, db_row: Dict[str, Any]) -> Dict[str, Any]:
        """Map SQL Server row to API response format"""
        # Use BodyFindID as the primary identifier
        item_id = str(db_row.get("BodyFindID"))
        
        return {
            "id": item_id,
            "status": CostEstStatus.to_string(db_row.get("CostEstStatusID", 0)),
            "thread_id": "",
            "dateOfCreation": None,
            "type": "home_repair",  # Default value
            "message": db_row.get("FindingText", ""),
            "currency": "USD",  # Default value
            "min_estimate": db_row.get("CostEstL", 0.0),
            "max_estimate": db_row.get("CostEstH", 0.0),
            "zipcode": str(db_row.get("Zipcode", "")).zfill(5) if db_row.get("Zipcode") else "",
            "estimate_scope": "full",  # Default value
        }

    async def save_flat_items(self, items: List[Dict[str, Any]], cosmos_service=None) -> Dict[str, Any]:
        """Save flat items to SQL Server and optionally to Cosmos DB"""
        if not self.connection_string:
            return self._mock_save_items(items)

        saved_count = 0
        failed_count = 0
        saved_items_for_cosmos = []  # Track items for Cosmos sync
        sql_body_find_ids = []  # Track IDs for potential rollback

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            for item in items:
                try:
                    # Get item ID
                    item_id = item.get("id") or item.get("thread_id")
                    
                    # Convert status string to integer
                    status_id = CostEstStatus.from_string(item.get("status", "need_estimate"))

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
                            # Update existing record
                            logger.info(f"Updating existing item with id: {numeric_id}")
                            cursor.execute("""
                                UPDATE [dbo].[BodyFindings]
                                SET FindingText = ?,
                                    Zipcode = ?,
                                    CostEstL = ?,
                                    CostEstH = ?,
                                    CostEstStatusID = ?
                                WHERE BodyFindID = ?
                            """, (
                                item.get("message", ""),
                                item.get("zipcode", ""),
                                item.get("min_estimate", 0.0),
                                item.get("max_estimate", 0.0),
                                status_id,
                                numeric_id
                            ))
                            actual_body_find_id = numeric_id
                        else:
                            # Insert new record - get next available BodyFindID
                            logger.info(f"Inserting new item")
                            cursor.execute("SELECT ISNULL(MAX(BodyFindID), 0) + 1 FROM [dbo].[BodyFindings]")
                            new_body_find_id = cursor.fetchone()[0]
                            
                            cursor.execute("""
                                INSERT INTO [dbo].[BodyFindings] 
                                (BodyFindID, FindingText, Zipcode, CostEstL, CostEstH, CostEstStatusID, NeedtoEdit)
                                VALUES (?, ?, ?, ?, ?, ?, 0)
                            """, (
                                new_body_find_id,
                                item.get("message", ""),
                                item.get("zipcode", ""),
                                item.get("min_estimate", 0.0),
                                item.get("max_estimate", 0.0),
                                status_id
                            ))
                            actual_body_find_id = new_body_find_id
                    else:
                        # Insert new record without ID - get next available BodyFindID
                        logger.info(f"Inserting new item")
                        cursor.execute("SELECT ISNULL(MAX(BodyFindID), 0) + 1 FROM [dbo].[BodyFindings]")
                        new_body_find_id = cursor.fetchone()[0]
                        
                        cursor.execute("""
                            INSERT INTO [dbo].[BodyFindings] 
                            (BodyFindID, FindingText, Zipcode, CostEstL, CostEstH, CostEstStatusID, NeedtoEdit)
                            VALUES (?, ?, ?, ?, ?, ?, 0)
                        """, (
                            new_body_find_id,
                            item.get("message", ""),
                            item.get("zipcode", ""),
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
                            "status": status_id,
                            "thread_id": item.get("thread_id", ""),
                            "dateOfCreation": item.get("dateOfCreation", ""),
                            "type": item.get("type", "home_repair"),
                            "currency": item.get("currency", "USD"),
                        })
                    
                    saved_count += 1
                except Exception as e:
                    logger.error(f"Failed to save item {item.get('id', 'unknown')}: {e}")
                    failed_count += 1

            # Commit SQL transaction first
            conn.commit()
            logger.info(f"SQL Server save committed: {saved_count} items")
            
            # Sync to Cosmos DB if service provided
            if cosmos_service and saved_items_for_cosmos:
                try:
                    logger.info(f"Syncing {len(saved_items_for_cosmos)} items to Cosmos DB")
                    
                    # Convert items to Cosmos format with cluster_name resolution
                    cosmos_items = []
                    for sql_item in saved_items_for_cosmos:
                        cluster_name = ""
                        zipcode = sql_item.get("zipcode")
                        if zipcode:
                            try:
                                cluster = self._find_cluster_id_by_zipcode(cursor, zipcode)
                                if cluster:
                                    cluster_info = self.get_cluster(str(cluster))
                                    if cluster_info:
                                        cluster_name = cluster_info.get("name", "")
                            except Exception as cluster_err:
                                logger.warning(f"Failed to get cluster name for zipcode {zipcode}: {cluster_err}")
                        
                        cosmos_item = cosmos_service._convert_to_cosmos_format(sql_item, cluster_name)
                        cosmos_items.append(cosmos_item)
                    
                    # Save to Cosmos DB
                    cosmos_result = await cosmos_service.save_flat_items(cosmos_items)
                    
                    if cosmos_result.get("failed_count", 0) > 0:
                        # Cosmos save failed for some items - rollback SQL
                        logger.error(f"Cosmos DB save failed for {cosmos_result['failed_count']} items. Rolling back SQL.")
                        
                        # Rollback: delete the items we just saved
                        rollback_cursor = conn.cursor()
                        for body_find_id in sql_body_find_ids:
                            try:
                                rollback_cursor.execute("""
                                    DELETE FROM [dbo].[BodyFindings]
                                    WHERE BodyFindID = ?
                                """, (body_find_id,))
                            except Exception as rb_err:
                                logger.error(f"Rollback failed for BodyFindID {body_find_id}: {rb_err}")
                        
                        conn.commit()
                        rollback_cursor.close()
                        conn.close()
                        
                        raise APIError(
                            status_code=500,
                            error_code=ErrorCodes.DATABASE_ERROR,
                            message="Failed to sync items to Cosmos DB. SQL changes rolled back.",
                            details=str(cosmos_result.get("failed_items"))
                        )
                    
                    logger.info(f"Successfully synced {cosmos_result['saved_count']} items to Cosmos DB")
                    
                except Exception as cosmos_err:
                    # Cosmos sync failed completely - rollback SQL
                    logger.error(f"Cosmos DB sync failed: {cosmos_err}. Rolling back SQL.")
                    
                    # Rollback: delete the items we just saved
                    rollback_cursor = conn.cursor()
                    for body_find_id in sql_body_find_ids:
                        try:
                            rollback_cursor.execute("""
                                DELETE FROM [dbo].[BodyFindings]
                                WHERE BodyFindID = ?
                            """, (body_find_id,))
                        except Exception as rb_err:
                            logger.error(f"Rollback failed for BodyFindID {body_find_id}: {rb_err}")
                    
                    conn.commit()
                    rollback_cursor.close()
                    conn.close()
                    
                    raise APIError(
                        status_code=500,
                        error_code=ErrorCodes.DATABASE_ERROR,
                        message="Failed to sync items to Cosmos DB. SQL changes rolled back.",
                        details=str(cosmos_err)
                    )
            
            cursor.close()
            conn.close()

            return {"saved_count": saved_count, "failed_count": failed_count}

        except APIError:
            # Re-raise API errors (including Cosmos sync failures)
            raise
        except Exception as e:
            logger.error(f"Database operation failed: {e}")
            raise APIError(
                status_code=500,
                error_code=ErrorCodes.DATABASE_ERROR,
                message="Failed to save items",
                details=str(e)
            )

    def _find_cluster_id_by_zipcode(self, cursor: pyodbc.Cursor, zipcode: str) -> Optional[int]:
        """Find ClusterId by zipcode from ClusterZipCodes table"""
        try:
            cursor.execute("""
                SELECT TOP 1 ClusterID 
                FROM [dbo].[ClusterZipCodes]
                WHERE ZipCode = ?
            """, (int(zipcode),))
            
            row = cursor.fetchone()
            return row[0] if row else None
        except Exception as e:
            logger.warning(f"Failed to find cluster for zipcode {zipcode}: {e}")
            return None

    def get_all_items(self, offset: int = 0, limit: int = 10) -> Dict[str, Any]:
        """Get all items with pagination"""
        if not self.connection_string:
            return self._mock_get_all_items(offset, limit)

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Get total count
            cursor.execute("""
                SELECT COUNT(*) 
                FROM [dbo].[BodyFindings]
                WHERE CostEstStatusID = 20 OR CostEstStatusID = 40
            """)
            total_count = cursor.fetchone()[0]

            # Get paginated items
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

            items = []
            for row in cursor.fetchall():
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

        except Exception as e:
            logger.error(f"Failed to get items: {e}")
            raise APIError(
                status_code=500,
                error_code=ErrorCodes.DATABASE_ERROR,
                message="Failed to retrieve items",
                details=str(e)
            )

    def search_items_by_message(self, search_query: str, offset: int = 0, limit: int = 10) -> Dict[str, Any]:
        """Search items by message/finding text"""
        if not self.connection_string:
            return self._mock_search_items(search_query, offset, limit)

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            search_pattern = f"%{search_query}%"

            # Get total count
            cursor.execute("""
                SELECT COUNT(*) 
                FROM [dbo].[BodyFindings]
                WHERE FindingText LIKE ? AND (CostEstStatusID = 20 OR CostEstStatusID = 40)
            """, (search_pattern,))
            total_count = cursor.fetchone()[0]

            # Get paginated search results
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

            items = []
            for row in cursor.fetchall():
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

        except Exception as e:
            logger.error(f"Failed to search items: {e}")
            raise APIError(
                status_code=500,
                error_code=ErrorCodes.DATABASE_ERROR,
                message="Failed to search items",
                details=str(e)
            )

    def get_item(self, item_id: str, partition_key_value: str, fallback_partition_key: str = None) -> Optional[Dict[str, Any]]:
        """Get item by BodyFindID"""
        if not self.connection_string:
            return None

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Try to convert item_id to int for BodyFindID
            try:
                numeric_id = int(item_id)
            except (ValueError, TypeError):
                logger.warning(f"Invalid item_id format: {item_id}")
                return None

            # Get by BodyFindID
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
            
            logger.warning(f"Item with id {item_id} not found in database")
            return None

        except Exception as e:
            logger.error(f"Failed to get item: {e}")
            raise APIError(
                status_code=500,
                error_code=ErrorCodes.DATABASE_ERROR,
                message="Failed to retrieve item",
                details=str(e)
            )

    async def update_item(self, item_id: str, updates: Dict[str, Any], cosmos_service=None) -> bool:
        """
        Update an existing item in SQL Server and optionally in Cosmos DB.
        
        SQL Server updates: Only cost estimates (min_estimate, max_estimate), message, and status
        Cosmos DB updates: All fields including zipcode, cluster_name, thread_id, etc.
        
        Note: zipcode and clusterId are NOT updated in SQL Server but ARE updated in Cosmos DB
        """
        if not self.connection_string:
            return False

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Try to convert item_id to int for BodyFindID
            try:
                numeric_id = int(item_id)
            except (ValueError, TypeError):
                logger.warning(f"Invalid item_id format: {item_id}")
                return False

            # Get the current item state for potential rollback
            cursor.execute("""
                SELECT FindingText, CostEstL, CostEstH, CostEstStatusID, Zipcode
                FROM [dbo].[BodyFindings]
                WHERE BodyFindID = ?
            """, (numeric_id,))
            old_row = cursor.fetchone()
            
            if not old_row:
                logger.warning(f"Item {item_id} not found for update")
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
            # zipcode will NOT be updated in SQL Server
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
            
            if status_id is not None:
                update_fields.append("CostEstStatusID = ?")
                params.append(status_id)

            if not update_fields:
                logger.warning("No fields to update")
                cursor.close()
                conn.close()
                return True  # Nothing to update is not an error

            # Build and execute UPDATE query
            update_sql = f"UPDATE [dbo].[BodyFindings] SET {', '.join(update_fields)} WHERE BodyFindID = ?"
            params.append(numeric_id)

            logger.info(f"Executing update for item {item_id}: {len(update_fields)} fields")
            cursor.execute(update_sql, params)
            
            rows_affected = cursor.rowcount

            if rows_affected == 0:
                logger.warning(f"No rows updated for item {item_id}")
                cursor.close()
                conn.close()
                return False

            # Commit SQL transaction
            conn.commit()
            logger.info(f"SQL Server update committed for item {item_id}")

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
                    
                    # If zipcode was in the update request, apply it to Cosmos
                    # (it's not updated in SQL Server, but should be in Cosmos)
                    if "zipcode" in updates:
                        updated_item["zipcode"] = updates["zipcode"]
                        logger.info(f"Applying zipcode from updates to Cosmos: {updates['zipcode']}")
                    
                    # Resolve cluster name using zipcode
                    cluster_name = ""
                    zipcode_to_use = updated_item.get("zipcode")
                    
                    if zipcode_to_use:
                        try:
                            logger.info(f"Resolving cluster for zipcode: {zipcode_to_use}")
                            cluster_id = self._find_cluster_id_by_zipcode(cursor, zipcode_to_use)
                            if cluster_id:
                                cluster = self.get_cluster(str(cluster_id))
                                if cluster:
                                    cluster_name = cluster.get("name", "")
                                    logger.info(f"Resolved cluster name: '{cluster_name}' for zipcode {zipcode_to_use}")
                                else:
                                    logger.warning(f"No cluster found for cluster_id {cluster_id}")
                            else:
                                logger.warning(f"No cluster_id found for zipcode {zipcode_to_use}")
                        except Exception as cluster_err:
                            logger.warning(f"Failed to get cluster for zipcode {zipcode_to_use}: {cluster_err}")
                    else:
                        logger.info(f"No zipcode found for item {item_id}")
                    
                    # Convert to Cosmos format
                    cosmos_item = cosmos_service._convert_to_cosmos_format(updated_item, cluster_name)
                    
                    # Merge any additional fields from the original updates that should go to Cosmos
                    # (but not SQL Server) such as thread_id, type, dateOfCreation, etc.
                    cosmos_only_fields = ["thread_id", "type", "dateOfCreation", "currency"]
                    for field in cosmos_only_fields:
                        if field in updates:
                            cosmos_item[field] = updates[field]
                            logger.info(f"Applying {field} from updates to Cosmos: {updates[field]}")
                    
                    logger.info(f"Cosmos item format: id='{cosmos_item.get('id')}', cluster_name='{cosmos_item.get('cluster_name')}', zipcode='{cosmos_item.get('zipcode')}'")
                    
                    # Update in Cosmos DB using cluster_name as partition key
                    cosmos_success = await cosmos_service.update_item(
                        item_id=str(numeric_id),
                        cluster_name=cluster_name,
                        updates=cosmos_item
                    )
                    
                    if not cosmos_success:
                        # Cosmos update failed - rollback SQL (only fields we updated)
                        logger.error("Cosmos DB update failed. Rolling back SQL.")
                        
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
                        
                        raise APIError(
                            status_code=500,
                            error_code=ErrorCodes.DATABASE_ERROR,
                            message="Failed to sync update to Cosmos DB. SQL changes rolled back."
                        )
                    
                    logger.info(f"Successfully synced update for item {item_id} to Cosmos DB")
                    
                except Exception as cosmos_err:
                    # Cosmos sync failed - rollback SQL (only fields we updated)
                    logger.error(f"Cosmos DB sync failed: {cosmos_err}. Rolling back SQL.")
                    
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
                    
                    raise APIError(
                        status_code=500,
                        error_code=ErrorCodes.DATABASE_ERROR,
                        message="Failed to sync update to Cosmos DB. SQL changes rolled back.",
                        details=str(cosmos_err)
                    )
            
            cursor.close()
            conn.close()

            logger.info(f"Successfully updated item {item_id}")
            return True

        except APIError:
            # Re-raise API errors (including Cosmos sync failures)
            raise
        except Exception as e:
            logger.error(f"Failed to update item {item_id}: {e}")
            raise APIError(
                status_code=500,
                error_code=ErrorCodes.DATABASE_ERROR,
                message="Failed to update item",
                details=str(e)
            )

    def delete_item(self, item_id: str, zipcode: str) -> Dict[str, Any]:
        """Delete item by BodyFindID (hard delete since no IsDeleted field)"""
        if not self.connection_string:
            return {"status": "success", "message": "Mock mode: Item would be deleted"}

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Try to convert item_id to int for BodyFindID
            try:
                numeric_id = int(item_id)
            except (ValueError, TypeError):
                logger.warning(f"Invalid item_id format: {item_id}")
                raise APIError(
                    status_code=400,
                    error_code=ErrorCodes.VALIDATION_ERROR,
                    message=f"Invalid item_id: {item_id}"
                )

            cursor.execute("""
                DELETE FROM [dbo].[BodyFindings]
                WHERE BodyFindID = ?
            """, (numeric_id,))

            rows_affected = cursor.rowcount
            conn.commit()
            cursor.close()
            conn.close()

            if rows_affected > 0:
                return {"status": "success", "message": f"Item {item_id} deleted successfully"}
            else:
                raise APIError(
                    status_code=404,
                    error_code=ErrorCodes.NOT_FOUND,
                    message=f"Item {item_id} not found"
                )

        except APIError:
            raise
        except Exception as e:
            logger.error(f"Failed to delete item: {e}")
            raise APIError(
                status_code=500,
                error_code=ErrorCodes.DATABASE_ERROR,
                message="Failed to delete item",
                details=str(e)
            )

    def query_items(self, query: str) -> List[Dict[str, Any]]:
        """Execute custom SQL query (use with caution)"""
        if not self.connection_string:
            return []

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(query)
            items = []
            
            for row in cursor.fetchall():
                row_dict = self._row_to_dict(cursor, row)
                items.append(row_dict)

            cursor.close()
            conn.close()

            return items

        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise APIError(
                status_code=500,
                error_code=ErrorCodes.DATABASE_ERROR,
                message="Query execution failed",
                details=str(e)
            )

    # ============ Cluster Operations ============

    def get_cluster(self, cluster_id: str) -> Optional[Dict[str, Any]]:
        """Get cluster by ID with zipcodes"""
        if not self.connection_string:
            return None

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Get cluster info
            cursor.execute("""
                SELECT ClusterID, ClusterName, ClusterDescription, CreatedDate
                FROM [dbo].[Clusters]
                WHERE ClusterID = ?
            """, (int(cluster_id),))

            row = cursor.fetchone()
            if not row:
                cursor.close()
                conn.close()
                return None

            cluster = self._row_to_dict(cursor, row)

            # Get zipcodes for this cluster
            cursor.execute("""
                SELECT ZipCode
                FROM [dbo].[ClusterZipCodes]
                WHERE ClusterID = ?
                ORDER BY ZipCode
            """, (int(cluster_id),))

            zipcodes = [str(row[0]).zfill(5) for row in cursor.fetchall()]

            cursor.close()
            conn.close()

            return {
                "id": str(cluster["ClusterID"]),
                "name": cluster["ClusterName"],
                "description": cluster.get("ClusterDescription", ""),
                "zipcodes": zipcodes,
                "created_at": cluster["CreatedDate"].isoformat() if cluster.get("CreatedDate") else None,
                "updated_at": cluster["CreatedDate"].isoformat() if cluster.get("CreatedDate") else None
            }

        except Exception as e:
            logger.error(f"Failed to get cluster: {e}")
            raise APIError(
                status_code=500,
                error_code=ErrorCodes.DATABASE_ERROR,
                message="Failed to retrieve cluster",
                details=str(e)
            )

    def find_cluster_by_name(self, name: str, exclude_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Find cluster by name (case-insensitive, normalized)"""
        if not self.connection_string:
            return None

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            normalized_name = name.strip().lower()

            if exclude_id:
                cursor.execute("""
                    SELECT TOP 1 ClusterID, ClusterName, ClusterDescription, CreatedDate
                    FROM [dbo].[Clusters]
                    WHERE LOWER(LTRIM(RTRIM(ClusterName))) = ? AND ClusterID != ?
                """, (normalized_name, int(exclude_id)))
            else:
                cursor.execute("""
                    SELECT TOP 1 ClusterID, ClusterName, ClusterDescription, CreatedDate
                    FROM [dbo].[Clusters]
                    WHERE LOWER(LTRIM(RTRIM(ClusterName))) = ?
                """, (normalized_name,))

            row = cursor.fetchone()
            
            if row:
                cluster = self._row_to_dict(cursor, row)
                cursor.close()
                conn.close()
                return {
                    "id": str(cluster["ClusterID"]),
                    "name": cluster["ClusterName"],
                    "description": cluster.get("ClusterDescription", ""),
                    "created_at": cluster["CreatedDate"].isoformat() if cluster.get("CreatedDate") else None
                }
            
            cursor.close()
            conn.close()
            return None

        except Exception as e:
            logger.error(f"Failed to find cluster by name: {e}")
            raise APIError(
                status_code=500,
                error_code=ErrorCodes.DATABASE_ERROR,
                message="Failed to find cluster",
                details=str(e)
            )

    async def save_clusters(self, clusters: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Save or update clusters with zipcodes"""
        if not self.connection_string:
            return {"saved_count": len(clusters), "failed_count": 0}

        saved_count = 0
        failed_count = 0

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            for cluster in clusters:
                try:
                    cluster_id = cluster.get("id")
                    name = cluster.get("name", "")
                    description = cluster.get("description", "")
                    zipcodes = cluster.get("zipcodes", [])

                    logger.info(f"Processing cluster: id={cluster_id}, name={name}, zipcodes_count={len(zipcodes)}")

                    if cluster_id:
                        # Update existing cluster
                        logger.info(f"Updating cluster {cluster_id}")
                        cursor.execute("""
                            UPDATE [dbo].[Clusters]
                            SET ClusterName = ?, ClusterDescription = ?
                            WHERE ClusterID = ?
                        """, (name, description, int(cluster_id)))
                        
                        rows_updated = cursor.rowcount
                        logger.info(f"Cluster update affected {rows_updated} rows")
                        
                        if rows_updated == 0:
                            logger.warning(f"Cluster {cluster_id} not found for update")

                        # Delete old zipcode associations
                        logger.info(f"Deleting old zipcodes for cluster {cluster_id}")
                        cursor.execute("""
                            DELETE FROM [dbo].[ClusterZipCodes]
                            WHERE ClusterID = ?
                        """, (int(cluster_id),))
                        
                        deleted_count = cursor.rowcount
                        logger.info(f"Deleted {deleted_count} old zipcode associations")

                    else:
                        # Insert new cluster
                        logger.info(f"Inserting new cluster: {name}")
                        cursor.execute("""
                            INSERT INTO [dbo].[Clusters] (ClusterName, ClusterDescription)
                            OUTPUT INSERTED.ClusterID
                            VALUES (?, ?)
                        """, (name, description))
                        
                        cluster_id = cursor.fetchone()[0]
                        logger.info(f"New cluster created with ID: {cluster_id}")

                    # Insert zipcode associations using bulk insert for performance
                    if zipcodes:
                        logger.info(f"Bulk inserting {len(zipcodes)} zipcodes for cluster {cluster_id}")
                        try:
                            # Enable fast_executemany for maximum performance
                            cursor.fast_executemany = True
                            
                            # Prepare bulk insert data
                            zipcode_data = [(int(cluster_id), int(zipcode)) for zipcode in zipcodes]
                            
                            # Use executemany for bulk insert (much faster than loop)
                            cursor.executemany("""
                                INSERT INTO [dbo].[ClusterZipCodes] (ClusterID, ZipCode)
                                VALUES (?, ?)
                            """, zipcode_data)
                            
                            logger.info(f"Successfully bulk inserted {len(zipcodes)} zipcodes")
                        except Exception as zip_error:
                            logger.error(f"Failed to bulk insert zipcodes for cluster {cluster_id}: {zip_error}")
                            # Try individual inserts as fallback
                            cursor.fast_executemany = False
                            for zipcode in zipcodes:
                                try:
                                    cursor.execute("""
                                        INSERT INTO [dbo].[ClusterZipCodes] (ClusterID, ZipCode)
                                        VALUES (?, ?)
                                    """, (int(cluster_id), int(zipcode)))
                                except Exception as single_zip_error:
                                    logger.warning(f"Failed to add zipcode {zipcode}: {single_zip_error}")

                    saved_count += 1
                    logger.info(f"Successfully saved cluster {cluster_id}")

                except Exception as e:
                    logger.error(f"Failed to save cluster {cluster.get('name', 'unknown')}: {e}", exc_info=True)
                    failed_count += 1

            conn.commit()
            cursor.close()
            conn.close()

            return {"saved_count": saved_count, "failed_count": failed_count}

        except Exception as e:
            logger.error(f"Failed to save clusters: {e}")
            raise APIError(
                status_code=500,
                error_code=ErrorCodes.DATABASE_ERROR,
                message="Failed to save clusters",
                details=str(e)
            )

    async def update_cluster(self, cluster_id: str, name: Optional[str] = None, 
                           description: Optional[str] = None, zipcodes: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Optimized update method for a single cluster
        Only updates fields that are provided and returns the updated cluster
        """
        if not self.connection_string:
            return {"success": True}

        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cluster_id_int = int(cluster_id)

            # Update cluster metadata if provided
            if name is not None or description is not None:
                updates = []
                params = []
                
                if name is not None:
                    updates.append("ClusterName = ?")
                    params.append(name)
                
                if description is not None:
                    updates.append("ClusterDescription = ?")
                    params.append(description)
                
                params.append(cluster_id_int)
                
                update_query = f"""
                    UPDATE [dbo].[Clusters]
                    SET {', '.join(updates)}
                    WHERE ClusterID = ?
                """
                
                cursor.execute(update_query, params)
                logger.info(f"Updated cluster {cluster_id} metadata, rows affected: {cursor.rowcount}")

            # Update zipcodes if provided
            if zipcodes is not None:
                # Delete old zipcode associations
                cursor.execute("""
                    DELETE FROM [dbo].[ClusterZipCodes]
                    WHERE ClusterID = ?
                """, (cluster_id_int,))
                
                deleted_count = cursor.rowcount
                logger.info(f"Deleted {deleted_count} old zipcode associations for cluster {cluster_id}")

                # Bulk insert new zipcodes with fast_executemany for performance
                if zipcodes:
                    cursor.fast_executemany = True
                    zipcode_data = [(cluster_id_int, int(zipcode)) for zipcode in zipcodes]
                    cursor.executemany("""
                        INSERT INTO [dbo].[ClusterZipCodes] (ClusterID, ZipCode)
                        VALUES (?, ?)
                    """, zipcode_data)
                    logger.info(f"Bulk inserted {len(zipcodes)} new zipcodes for cluster {cluster_id}")

            conn.commit()
            cursor.close()
            conn.close()

            logger.info(f"Successfully updated cluster {cluster_id}")
            return {"success": True}

        except Exception as e:
            logger.error(f"Failed to update cluster {cluster_id}: {e}")
            raise APIError(
                status_code=500,
                error_code=ErrorCodes.DATABASE_ERROR,
                message="Failed to update cluster",
                details=str(e)
            )

    async def create_cluster(self, name: str, zipcodes: List[str], description: str = "") -> str:
        """
        Optimized create method for a new cluster
        Returns the newly created cluster ID
        """
        if not self.connection_string:
            return "mock-cluster-id"

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Insert new cluster
            logger.info(f"Creating new cluster: {name} with {len(zipcodes)} zipcodes")
            cursor.execute("""
                INSERT INTO [dbo].[Clusters] (ClusterName, ClusterDescription)
                OUTPUT INSERTED.ClusterID
                VALUES (?, ?)
            """, (name, description))
            
            cluster_id = cursor.fetchone()[0]
            logger.info(f"New cluster created with ID: {cluster_id}")

            # Bulk insert zipcodes with fast_executemany for max performance
            if zipcodes:
                cursor.fast_executemany = True
                zipcode_data = [(cluster_id, int(zipcode)) for zipcode in zipcodes]
                cursor.executemany("""
                    INSERT INTO [dbo].[ClusterZipCodes] (ClusterID, ZipCode)
                    VALUES (?, ?)
                """, zipcode_data)
                logger.info(f"Bulk inserted {len(zipcodes)} zipcodes for new cluster {cluster_id}")

            conn.commit()
            cursor.close()
            conn.close()

            logger.info(f"Successfully created cluster {cluster_id}")
            return str(cluster_id)

        except Exception as e:
            logger.error(f"Failed to create cluster: {e}")
            raise APIError(
                status_code=500,
                error_code=ErrorCodes.DATABASE_ERROR,
                message="Failed to create cluster",
                details=str(e)
            )

    def get_all_clusters(self, offset: int = 0, limit: int = 10, search: str = "") -> Dict[str, Any]:
        """Get all clusters with pagination and search (supports searching by name, description, or zipcodes)"""
        if not self.connection_string:
            return {"items": [], "total_count": 0, "offset": offset, "limit": limit, "returned_count": 0}

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Build WHERE clause for search
            where_clause = ""
            params = []
            
            if search:
                # Check if search contains zipcodes (comma-separated or single)
                zipcodes = [z.strip() for z in search.split(',') if z.strip().isdigit()]
                
                if zipcodes:
                    # Search by zipcodes
                    zipcode_placeholders = ','.join(['?' for _ in zipcodes])
                    where_clause = f"""
                        WHERE ClusterID IN (
                            SELECT DISTINCT ClusterID 
                            FROM [dbo].[ClusterZipCodes] 
                            WHERE ZipCode IN ({zipcode_placeholders})
                        )
                    """
                    params = [int(z) for z in zipcodes]
                else:
                    # Search by name or description
                    search_pattern = f"%{search}%"
                    where_clause = "WHERE ClusterName LIKE ? OR ClusterDescription LIKE ?"
                    params = [search_pattern, search_pattern]

            # Get total count
            count_query = f"SELECT COUNT(DISTINCT ClusterID) FROM [dbo].[Clusters] {where_clause}"
            cursor.execute(count_query, params)
            total_count = cursor.fetchone()[0]

            # Get paginated clusters
            query = f"""
                SELECT DISTINCT ClusterID, ClusterName, ClusterDescription, CreatedDate
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

                # Get zipcodes for this cluster
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
            logger.error(f"Failed to get clusters: {e}")
            raise APIError(
                status_code=500,
                error_code=ErrorCodes.DATABASE_ERROR,
                message="Failed to retrieve clusters",
                details=str(e)
            )

    def find_cluster_by_zipcode(self, zipcode: str) -> Optional[Dict[str, Any]]:
        """Find cluster by zipcode with full cluster details"""
        if not self.connection_string:
            return None

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # First find the cluster ID for this zipcode
            cursor.execute("""
                SELECT TOP 1 ClusterID
                FROM [dbo].[ClusterZipCodes]
                WHERE ZipCode = ?
            """, (int(zipcode),))

            row = cursor.fetchone()
            
            if not row:
                cursor.close()
                conn.close()
                return None
            
            cluster_id = row[0]
            
            # Now get full cluster details
            cursor.execute("""
                SELECT ClusterID, ClusterName, ClusterDescription, CreatedDate
                FROM [dbo].[Clusters]
                WHERE ClusterID = ?
            """, (cluster_id,))

            cluster_row = cursor.fetchone()
            if not cluster_row:
                cursor.close()
                conn.close()
                return None

            cluster = self._row_to_dict(cursor, cluster_row)

            # Get all zipcodes for this cluster
            cursor.execute("""
                SELECT ZipCode
                FROM [dbo].[ClusterZipCodes]
                WHERE ClusterID = ?
                ORDER BY ZipCode
            """, (cluster_id,))

            zipcodes = [str(row[0]).zfill(5) for row in cursor.fetchall()]

            cursor.close()
            conn.close()

            return {
                "ClusterId": str(cluster["ClusterID"]),
                "Name": cluster["ClusterName"],
                "Description": cluster.get("ClusterDescription", ""),
                "zipcodes": zipcodes,
                "CreatedDate": cluster["CreatedDate"].isoformat() if cluster.get("CreatedDate") else None
            }

        except Exception as e:
            logger.error(f"Failed to find cluster by zipcode: {e}")
            return None

    # ============ Mock Methods (for development without DB) ============

    def _mock_save_items(self, items: list) -> Dict[str, Any]:
        """Mock save for development"""
        logger.info(f"[MOCK] Would save {len(items)} items")
        return {"saved_count": len(items), "failed_count": 0}

    def _mock_get_all_items(self, offset: int, limit: int) -> Dict[str, Any]:
        """Mock get all items"""
        logger.info(f"[MOCK] Would retrieve items with offset={offset}, limit={limit}")
        return {
            "items": [],
            "total_count": 0,
            "offset": offset,
            "limit": limit,
            "returned_count": 0
        }

    def _mock_search_items(self, search_query: str, offset: int, limit: int) -> Dict[str, Any]:
        """Mock search items"""
        logger.info(f"[MOCK] Would search items with query='{search_query}', offset={offset}, limit={limit}")
        return {
            "items": [],
            "total_count": 0,
            "offset": offset,
            "limit": limit,
            "returned_count": 0
        }


# Singleton instance
_sql_service_instance: Optional[SQLServerService] = None
_sql_service_lock = threading.Lock()


def get_sql_service() -> SQLServerService:
    """
    Get or create singleton SQL Server service instance
    Thread-safe lazy initialization
    """
    global _sql_service_instance

    if _sql_service_instance is None:
        with _sql_service_lock:
            if _sql_service_instance is None:
                _sql_service_instance = SQLServerService()

    return _sql_service_instance
