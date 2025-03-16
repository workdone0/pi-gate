import aiosqlite
import logging
import pandas as pd
import asyncio
from typing import List, Dict, Any, Optional

LOG_FILE = "/tmp/pi_gate.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

DATABASE_FILE = "dns_logs.db"

async def init_db() -> None:
    """Initialize the database and create tables if they don't exist."""
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS dns_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_ip TEXT,
                    domain TEXT,
                    blocked INTEGER,
                    success INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()
    except aiosqlite.Error as e:
        logging.error(f"Error initializing database: {e}")
        raise

async def log_query(client_ip: str, domain: str, blocked: int, success: int) -> None:
    """Log a DNS query to the database.
    
    Args:
        client_ip: The IP address of the client making the request
        domain: The domain being queried
        blocked: 1 if the request was blocked, 0 if allowed
        success: 1 if resolved successfully, 0 if failed
    """
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            await db.execute(
                "INSERT INTO dns_requests (client_ip, domain, blocked, success) VALUES (?, ?, ?, ?)",
                (client_ip, domain, blocked, success)
            )
            await db.commit()
    except aiosqlite.Error as e:
        logging.error(f"Error logging query: {e}")
        raise

async def fetch_logs(limit: Optional[int] = None, 
                    offset: int = 0,
                    filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Fetch DNS logs from the database with optional filtering and pagination.
    
    Args:
        limit: Maximum number of records to return (None for all)
        offset: Number of records to skip
        filters: Dictionary of column names and values to filter by
        
    Returns:
        List of dictionaries containing the log records
    """
    try:
        query = "SELECT * FROM dns_requests"
        params = []
        
        # Apply filters if provided
        if filters:
            conditions = []
            for column, value in filters.items():
                if column in ["client_ip", "domain", "blocked"]:
                    conditions.append(f"{column} = ?")
                    params.append(value)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
        
        # Apply ordering
        query += " ORDER BY timestamp DESC"
        
        # Apply pagination
        if limit is not None:
            query += f" LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        
        async with aiosqlite.connect(DATABASE_FILE) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            
            # Convert to list of dictionaries
            result = [dict(row) for row in rows]
            return result
            
    except aiosqlite.Error as e:
        logging.error(f"Error fetching logs: {e}")
        return []

# Helper function for pandas DataFrame conversion (runs in a separate thread)
async def get_logs_dataframe() -> pd.DataFrame:
    """Fetch all logs and return as a pandas DataFrame."""
    try:
        logs = await fetch_logs()
        # Run DataFrame conversion in a thread pool to avoid blocking
        return await asyncio.to_thread(pd.DataFrame, logs)
    except Exception as e:
        logging.error(f"Error converting logs to DataFrame: {e}")
        return pd.DataFrame()