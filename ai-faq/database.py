import sqlite3

DB_NAME = "faq.db"

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # Allows accessing columns by name
    return conn

def init_db():
    """Initializes the database and creates the faq table if it doesn't exist."""
    print("Initializing SQLite database...")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS faq (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    
    # Check if table was created
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='faq'")
    if cursor.fetchone():
        print("Table 'faq' is ready.")
    else:
        print("Error: Table 'faq' was not created.")
        
    conn.close()