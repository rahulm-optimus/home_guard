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
import uuid
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
        # Use BodyFindingID if ThreadID is None/NULL
        thread_id = db_row.get("ThreadID")
        item_id = thread_id if thread_id else str(db_row.get("BodyFindingID"))
        
        return {
            "id": item_id,
            "status": CostEstStatus.to_string(db_row.get("CostEstStatusID", 0)),
            "thread_id": thread_id or "",
            "dateOfCreation": db_row.get("CreatedDate").isoformat() if db_row.get("CreatedDate") else None,
            "type": "home_repair",  # Default value
            "message": db_row.get("FindingText", ""),
            "currency": "USD",  # Default value
            "min_estimate": db_row.get("CostEstL", 0.0),
            "max_estimate": db_row.get("CostEstH", 0.0),
            "zipcode": db_row.get("ZipCode", ""),
            "clusterId": str(db_row.get("ClusterId")) if db_row.get("ClusterId") else None,
            "estimate_scope": "full",  # Default value
        }

    async def save_flat_items(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Save flat items to SQL Server"""
        if not self.connection_string:
            return self._mock_save_items(items)

        saved_count = 0
        failed_count = 0

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            for item in items:
                try:
                    # Generate ThreadID if not present (use id from API)
                    thread_id = item.get("id") or item.get("thread_id")
                    
                    # If no thread_id, generate one
                    if not thread_id:
                        thread_id = str(uuid.uuid4())
                    
                    # Convert status string to integer
                    status_id = CostEstStatus.from_string(item.get("status", "need_estimate"))
                    
                    # Get ClusterId from clusterId field or resolve from zipcode
                    cluster_id = item.get("clusterId")
                    if not cluster_id:
                        zipcode = item.get("zipcode", "00000")
                        cluster_result = self._find_cluster_id_by_zipcode(cursor, zipcode)
                        cluster_id = cluster_result if cluster_result else None

                    # Try to convert to numeric ID for BodyFindingID comparison
                    try:
                        numeric_id = int(thread_id)
                    except (ValueError, TypeError):
                        numeric_id = None

                    # Check if this is an update (record exists with this ThreadID or BodyFindingID)
                    if numeric_id:
                        cursor.execute("""
                            SELECT BodyFindingID FROM [dbo].[PlsBodyBodyData_BodyFindings] 
                            WHERE (ThreadID = ? OR BodyFindingID = ?) AND IsDeleted = 0
                        """, (thread_id, numeric_id))
                    else:
                        cursor.execute("""
                            SELECT BodyFindingID FROM [dbo].[PlsBodyBodyData_BodyFindings] 
                            WHERE ThreadID = ? AND IsDeleted = 0
                        """, (thread_id,))
                    existing = cursor.fetchone()

                    if existing:
                        # Update existing record
                        logger.info(f"Updating existing item with id: {thread_id}")
                        if numeric_id:
                            cursor.execute("""
                                UPDATE [dbo].[PlsBodyBodyData_BodyFindings]
                                SET FindingText = ?,
                                    ZipCode = ?,
                                    CostEstL = ?,
                                    CostEstH = ?,
                                    ClusterId = ?,
                                    CostEstStatusID = ?,
                                    LastUpdated = SYSDATETIME(),
                                    ThreadID = ?
                                WHERE (ThreadID = ? OR BodyFindingID = ?) AND IsDeleted = 0
                            """, (
                                item.get("message", ""),
                                item.get("zipcode", "00000"),
                                item.get("min_estimate", 0.0),
                                item.get("max_estimate", 0.0),
                                cluster_id,
                                status_id,
                                thread_id,
                                thread_id,
                                numeric_id
                            ))
                        else:
                            cursor.execute("""
                                UPDATE [dbo].[PlsBodyBodyData_BodyFindings]
                                SET FindingText = ?,
                                    ZipCode = ?,
                                    CostEstL = ?,
                                    CostEstH = ?,
                                    ClusterId = ?,
                                    CostEstStatusID = ?,
                                    LastUpdated = SYSDATETIME(),
                                    ThreadID = ?
                                WHERE ThreadID = ? AND IsDeleted = 0
                            """, (
                                item.get("message", ""),
                                item.get("zipcode", "00000"),
                                item.get("min_estimate", 0.0),
                                item.get("max_estimate", 0.0),
                                cluster_id,
                                status_id,
                                thread_id,
                                thread_id
                            ))
                    else:
                        # Insert new record
                        logger.info(f"Inserting new item with id: {thread_id}")
                        cursor.execute("""
                            INSERT INTO [dbo].[PlsBodyBodyData_BodyFindings] 
                            (ThreadID, FindingText, ZipCode, CostEstL, CostEstH, ClusterId, CostEstStatusID, CreatedDate, LastUpdated, IsDeleted)
                            VALUES (?, ?, ?, ?, ?, ?, ?, SYSDATETIME(), SYSDATETIME(), 0)
                        """, (
                            thread_id,
                            item.get("message", ""),
                            item.get("zipcode", "00000"),
                            item.get("min_estimate", 0.0),
                            item.get("max_estimate", 0.0),
                            cluster_id,
                            status_id
                        ))
                    
                    saved_count += 1
                except Exception as e:
                    logger.error(f"Failed to save item {item.get('id', 'unknown')}: {e}")
                    failed_count += 1

            conn.commit()
            cursor.close()
            conn.close()

            return {"saved_count": saved_count, "failed_count": failed_count}

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
                FROM [dbo].[PlsBodyBodyData_BodyFindings]
                WHERE IsDeleted = 0 AND (CostEstStatusID = 20 OR CostEstStatusID = 40)
            """)
            total_count = cursor.fetchone()[0]

            # Get paginated items
            cursor.execute("""
                SELECT 
                    bf.BodyFindingID,
                    bf.ThreadID,
                    bf.FindingText,
                    bf.ZipCode,
                    bf.CostEstL,
                    bf.CostEstH,
                    bf.ClusterId,
                    bf.CostEstStatusID,
                    bf.CreatedDate
                FROM [dbo].[PlsBodyBodyData_BodyFindings] bf
                WHERE bf.IsDeleted = 0 AND (bf.CostEstStatusID = 20 OR bf.CostEstStatusID = 40)
                ORDER BY bf.CreatedDate DESC
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
                FROM [dbo].[PlsBodyBodyData_BodyFindings]
                WHERE IsDeleted = 0 AND FindingText LIKE ? AND (CostEstStatusID = 20 OR CostEstStatusID = 40)
            """, (search_pattern,))
            total_count = cursor.fetchone()[0]

            # Get paginated search results
            cursor.execute("""
                SELECT 
                    bf.BodyFindingID,
                    bf.ThreadID,
                    bf.FindingText,
                    bf.ZipCode,
                    bf.CostEstL,
                    bf.CostEstH,
                    bf.ClusterId,
                    bf.CostEstStatusID,
                    bf.CreatedDate
                FROM [dbo].[PlsBodyBodyData_BodyFindings] bf
                WHERE bf.IsDeleted = 0 AND bf.FindingText LIKE ? AND (bf.CostEstStatusID = 20 OR bf.CostEstStatusID = 40)
                ORDER BY bf.CreatedDate DESC
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
        """Get item by ThreadID or BodyFindingID with optional zipcode fallback"""
        if not self.connection_string:
            return None

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Try to convert item_id to int for BodyFindingID comparison
            try:
                numeric_id = int(item_id)
            except (ValueError, TypeError):
                numeric_id = None

            # Try to get by ThreadID first, or by BodyFindingID if ThreadID is NULL
            if numeric_id:
                cursor.execute("""
                    SELECT 
                        bf.BodyFindingID,
                        bf.ThreadID,
                        bf.FindingText,
                        bf.ZipCode,
                        bf.CostEstL,
                        bf.CostEstH,
                        bf.ClusterId,
                        bf.CostEstStatusID,
                        bf.CreatedDate
                    FROM [dbo].[PlsBodyBodyData_BodyFindings] bf
                    WHERE (bf.ThreadID = ? OR bf.BodyFindingID = ?) 
                        AND bf.IsDeleted = 0
                """, (item_id, numeric_id))
            else:
                cursor.execute("""
                    SELECT 
                        bf.BodyFindingID,
                        bf.ThreadID,
                        bf.FindingText,
                        bf.ZipCode,
                        bf.CostEstL,
                        bf.CostEstH,
                        bf.ClusterId,
                        bf.CostEstStatusID,
                        bf.CreatedDate
                    FROM [dbo].[PlsBodyBodyData_BodyFindings] bf
                    WHERE bf.ThreadID = ? AND bf.IsDeleted = 0
                """, (item_id,))

            row = cursor.fetchone()
            
            # If not found and fallback zipcode provided, try with zipcode
            if not row and fallback_partition_key:
                if numeric_id:
                    cursor.execute("""
                        SELECT 
                            bf.BodyFindingID,
                            bf.ThreadID,
                            bf.FindingText,
                            bf.ZipCode,
                            bf.CostEstL,
                            bf.CostEstH,
                            bf.ClusterId,
                            bf.CostEstStatusID,
                            bf.CreatedDate
                        FROM [dbo].[PlsBodyBodyData_BodyFindings] bf
                        WHERE (bf.ThreadID = ? OR bf.BodyFindingID = ?)
                            AND bf.ZipCode = ? AND bf.IsDeleted = 0
                    """, (item_id, numeric_id, fallback_partition_key))
                else:
                    cursor.execute("""
                        SELECT 
                            bf.BodyFindingID,
                            bf.ThreadID,
                            bf.FindingText,
                            bf.ZipCode,
                            bf.CostEstL,
                            bf.CostEstH,
                            bf.ClusterId,
                            bf.CostEstStatusID,
                            bf.CreatedDate
                        FROM [dbo].[PlsBodyBodyData_BodyFindings] bf
                        WHERE bf.ThreadID = ? AND bf.ZipCode = ? AND bf.IsDeleted = 0
                    """, (item_id, fallback_partition_key))
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

    async def update_item(self, item_id: str, updates: Dict[str, Any]) -> bool:
        """Update an existing item in SQL Server"""
        if not self.connection_string:
            return False

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Try to convert item_id to int for BodyFindingID comparison
            try:
                numeric_id = int(item_id)
            except (ValueError, TypeError):
                numeric_id = None

            # Convert status string to integer if present
            status_id = None
            if "status" in updates:
                status_id = CostEstStatus.from_string(updates.get("status", "need_estimate"))

            # Get ClusterId from updates or resolve from zipcode
            cluster_id = updates.get("clusterId")
            if not cluster_id and "zipcode" in updates:
                cluster_result = self._find_cluster_id_by_zipcode(cursor, updates.get("zipcode", "00000"))
                cluster_id = cluster_result if cluster_result else None

            # Build UPDATE query dynamically based on provided fields
            update_fields = []
            params = []

            if "message" in updates:
                update_fields.append("FindingText = ?")
                params.append(updates["message"])
            
            if "zipcode" in updates:
                update_fields.append("ZipCode = ?")
                params.append(updates["zipcode"])
            
            if "min_estimate" in updates:
                update_fields.append("CostEstL = ?")
                params.append(updates["min_estimate"])
            
            if "max_estimate" in updates:
                update_fields.append("CostEstH = ?")
                params.append(updates["max_estimate"])
            
            if cluster_id is not None:
                update_fields.append("ClusterId = ?")
                params.append(cluster_id)
            
            if status_id is not None:
                update_fields.append("CostEstStatusID = ?")
                params.append(status_id)

            # Always update LastUpdated
            update_fields.append("LastUpdated = SYSDATETIME()")

            if not update_fields:
                logger.warning("No fields to update")
                return True  # Nothing to update is not an error

            # Build and execute UPDATE query
            update_sql = f"UPDATE [dbo].[PlsBodyBodyData_BodyFindings] SET {', '.join(update_fields)}"
            
            if numeric_id:
                update_sql += " WHERE (ThreadID = ? OR BodyFindingID = ?) AND IsDeleted = 0"
                params.extend([item_id, numeric_id])
            else:
                update_sql += " WHERE ThreadID = ? AND IsDeleted = 0"
                params.append(item_id)

            logger.info(f"Executing update for item {item_id}: {len(update_fields)} fields")
            cursor.execute(update_sql, params)
            
            rows_affected = cursor.rowcount
            conn.commit()
            cursor.close()
            conn.close()

            if rows_affected == 0:
                logger.warning(f"No rows updated for item {item_id}")
                return False

            logger.info(f"Successfully updated item {item_id}, {rows_affected} row(s) affected")
            return True

        except Exception as e:
            logger.error(f"Failed to update item {item_id}: {e}")
            raise APIError(
                status_code=500,
                error_code=ErrorCodes.DATABASE_ERROR,
                message="Failed to update item",
                details=str(e)
            )

    def delete_item(self, item_id: str, zipcode: str) -> Dict[str, Any]:
        """Soft delete item by ThreadID"""
        if not self.connection_string:
            return {"status": "success", "message": "Mock mode: Item would be deleted"}

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE [dbo].[PlsBodyBodyData_BodyFindings]
                SET IsDeleted = 1, LastUpdated = SYSDATETIME()
                WHERE ThreadID = ? AND IsDeleted = 0
            """, (item_id,))

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
