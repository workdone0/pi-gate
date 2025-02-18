import sqlite3

def init_db():
    conn = sqlite3.connect("dns_logs.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS dns_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def log_request(domain):
    conn = sqlite3.connect("dns_logs.db")
    c = conn.cursor()
    c.execute("INSERT INTO dns_requests (domain) VALUES (?)", (domain,))
    conn.commit()
    conn.close()
