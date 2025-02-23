# pi_gate/database.py
import sqlite3
import logging
import pandas as pd

LOG_FILE = "/tmp/pi_gate.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

DATABASE_FILE = "dns_logs.db"

def init_db():
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        # Blocked 1 for true and 0 for false
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dns_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_ip TEXT,
                domain TEXT,
                blocked INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        logging.error(f"Error initializing database: {e}")

def log_query(client_ip, domain, blocked):
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO dns_requests (client_ip, domain, blocked) VALUES (?, ?, ?)", (client_ip, domain, blocked))
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        logging.error(f"Error logging query: {e}")

def fetch_logs():
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        df = pd.read_sql_query("SELECT * FROM dns_requests", conn)
        conn.close()
        return df.to_dict("records")
    except sqlite3.Error as e:
        logging.error(f"Error fetching logs: {e}")
        return []
    except NameError:
        logging.error("pandas not imported, cannot fetch logs")
        return []