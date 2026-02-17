import os
import logging
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
            "clusterId": str(db_row.get("ClusterId")) if db_row.get("ClusterId") else None,
            "cluster_name": cluster_name or "",
            "estimate_scope": "full",
        }

    def save_flat_items(self, items):
        saved_count = 0
        failed_count = 0
        
        conn = self._get_connection()
        cursor = conn.cursor()

        for item in items:
            try:
                # Get item ID
                item_id = item.get("id") or item.get("thread_id")
                
                status_id = CostEstStatus.from_string(item.get("status", "need_estimate"))
                
                # Get ClusterId
                cluster_id = item.get("clusterId")
                if not cluster_id:
                    zipcode = item.get("zipcode", "00000")
                    cluster_id = self._find_cluster_id_by_zipcode(cursor, zipcode)

                # Try to convert to numeric ID for BodyFindID lookup
                try:
                    numeric_id = int(item_id) if item_id else None
                except (ValueError, TypeError):
                    numeric_id = None

                # Check if record exists with this BodyFindID
                if numeric_id:
                    cursor.execute("""
                        SELECT BodyFindID FROM [dbo].[BodyFindings] 
                        WHERE BodyFindID = ?
                    """, (numeric_id,))
                    existing = cursor.fetchone()

                    if existing:
                        # Update existing record
                        logging.info(f"Updating existing item with id: {numeric_id}")
                        cursor.execute("""
                            UPDATE [dbo].[BodyFindings]
                            SET FindingText = ?,
                                Zipcode = ?,
                                CostEstL = ?,
                                CostEstH = ?,
                                ClusterId = ?,
                                CostEstStatusID = ?
                            WHERE BodyFindID = ?
                        """, (
                            item.get("message", ""),
                            item.get("zipcode", ""),
                            item.get("min_estimate", 0.0),
                            item.get("max_estimate", 0.0),
                            cluster_id,
                            status_id,
                            numeric_id
                        ))
                    else:
                        # Insert new record - get next available BodyFindID
                        logging.info(f"Inserting new item")
                        cursor.execute("SELECT ISNULL(MAX(BodyFindID), 0) + 1 FROM [dbo].[BodyFindings]")
                        new_body_find_id = cursor.fetchone()[0]
                        
                        cursor.execute("""
                            INSERT INTO [dbo].[BodyFindings] 
                            (BodyFindID, FindingText, Zipcode, CostEstL, CostEstH, ClusterId, CostEstStatusID, NeedtoEdit)
                            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                        """, (
                            new_body_find_id,
                            item.get("message", ""),
                            item.get("zipcode", ""),
                            item.get("min_estimate", 0.0),
                            item.get("max_estimate", 0.0),
                            cluster_id,
                            status_id
                        ))
                else:
                    # Insert new record without ID - get next available BodyFindID
                    logging.info(f"Inserting new item")
                    cursor.execute("SELECT ISNULL(MAX(BodyFindID), 0) + 1 FROM [dbo].[BodyFindings]")
                    new_body_find_id = cursor.fetchone()[0]
                    
                    cursor.execute("""
                        INSERT INTO [dbo].[BodyFindings] 
                        (BodyFindID, FindingText, Zipcode, CostEstL, CostEstH, ClusterId, CostEstStatusID, NeedtoEdit)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                    """, (
                        new_body_find_id,
                        item.get("message", ""),
                        item.get("zipcode", ""),
                        item.get("min_estimate", 0.0),
                        item.get("max_estimate", 0.0),
                        cluster_id,
                        status_id
                    ))
                
                saved_count += 1
            except Exception as e:
                logging.error(f"Failed to save item {item.get('id', 'unknown')}: {e}")
                failed_count += 1

        conn.commit()
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
                bf.ClusterId,
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
                bf.ClusterId,
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
                bf.ClusterId,
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
                bf.ClusterId,
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

    def update_item(self, item_id: str, updates: dict) -> bool:
        """Update an existing item in SQL Server"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Try to convert item_id to int for BodyFindID
            try:
                numeric_id = int(item_id)
            except (ValueError, TypeError):
                logging.warning(f"Invalid item_id format: {item_id}")
                return False

            # Convert status string to integer if present
            status_id = None
            if "status" in updates:
                status_id = CostEstStatus.from_string(updates.get("status", "need_estimate"))

            # Build UPDATE query dynamically based on provided fields
            update_fields = []
            params = []

            if "message" in updates:
                update_fields.append("FindingText = ?")
                params.append(updates["message"])
            
            if "zipcode" in updates:
                update_fields.append("Zipcode = ?")
                params.append(updates["zipcode"])
            
            if "min_estimate" in updates:
                update_fields.append("CostEstL = ?")
                params.append(updates["min_estimate"])
            
            if "max_estimate" in updates:
                update_fields.append("CostEstH = ?")
                params.append(updates["max_estimate"])
            
            if "cluster_id" in updates:
                update_fields.append("ClusterId = ?")
                params.append(updates["cluster_id"])
            
            if status_id is not None:
                update_fields.append("CostEstStatusID = ?")
                params.append(status_id)

            if not update_fields:
                logging.warning("No fields to update")
                return True  # Nothing to update is not an error

            # Build and execute UPDATE query
            update_sql = f"UPDATE [dbo].[BodyFindings] SET {', '.join(update_fields)} WHERE BodyFindID = ?"
            params.append(numeric_id)

            logging.info(f"Executing update for item {item_id}: {len(update_fields)} fields")
            cursor.execute(update_sql, params)
            
            rows_affected = cursor.rowcount
            conn.commit()
            cursor.close()
            conn.close()

            if rows_affected == 0:
                logging.warning(f"No rows updated for item {item_id}")
                return False

            logging.info(f"Successfully updated item {item_id}, {rows_affected} row(s) affected")
            return True

        except Exception as e:
            logging.error(f"Failed to update item {item_id}: {e}")
            return False
