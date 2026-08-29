import sqlite3
from pathlib import Path

# Path to verdict.db inside backend directory
DB_PATH = Path(__file__).resolve().parent / "verdict.db"


def get_db_connection() -> sqlite3.Connection:
    """
    Opens a connection to the SQLite database and configures
    row_factory so rows can be accessed by column name.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> None:
    """
    Initializes the SQLite database and creates the users, verdicts,
    evidence, evidence_graph_nodes, evidence_graph_edges, and incidents
    tables if they do not already exist.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Create verdicts table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS verdicts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        title TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)

    # Create evidence table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS evidence (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        verdict_id INTEGER,
        source TEXT NOT NULL,
        evidence_type TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(verdict_id) REFERENCES verdicts(id) ON DELETE CASCADE
    );
    """)

    # Create evidence_graph_nodes table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS evidence_graph_nodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        verdict_id INTEGER NOT NULL,
        node_type TEXT NOT NULL,
        label TEXT NOT NULL,
        data TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(verdict_id) REFERENCES verdicts(id) ON DELETE CASCADE
    );
    """)

    # Create evidence_graph_edges table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS evidence_graph_edges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        verdict_id INTEGER NOT NULL,
        source_node_id INTEGER NOT NULL,
        target_node_id INTEGER NOT NULL,
        relationship TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(verdict_id) REFERENCES verdicts(id) ON DELETE CASCADE,
        FOREIGN KEY(source_node_id) REFERENCES evidence_graph_nodes(id) ON DELETE CASCADE,
        FOREIGN KEY(target_node_id) REFERENCES evidence_graph_nodes(id) ON DELETE CASCADE
    );
    """)

    # Create incidents table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS incidents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        service TEXT NOT NULL,
        environment TEXT NOT NULL,
        endpoint TEXT NOT NULL,
        http_method TEXT NOT NULL,
        status_code INTEGER NOT NULL,
        exception_type TEXT NOT NULL,
        exception_message TEXT NOT NULL,
        stack_trace TEXT NOT NULL,
        request_id TEXT,
        timestamp TEXT,
        metadata TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized successfully at {DB_PATH}")
