# pyrefly: ignore [name-defined]
import sqlite3
# pyrefly: ignore [name-defined]
import os

# DB path located at the root of the project workspace
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "mail.db"))



def get_db_connection():
    """
    Establish an SQLite database connection and return it.
    Enforces foreign keys check.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    """
    Initialize SQLite database tables if they do not exist.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin', 'client'))
    );
    """)

    # Create clients table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        imap_host TEXT NOT NULL,
        imap_port INTEGER DEFAULT 993,
        app_password TEXT NOT NULL,
        mailbox TEXT DEFAULT 'INBOX',
        is_active INTEGER DEFAULT 1 CHECK(is_active IN (0, 1)),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    conn.commit()

    # Seed default admin user if not exists
    cursor.execute("SELECT 1 FROM users WHERE role = 'admin' LIMIT 1;")
    if not cursor.fetchone():
        # pyrefly: ignore [missing-import]
        from src.Security.security import hash_password
        admin_hash = hash_password("admin")
        cursor.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?);",
            ("admin", admin_hash, "admin")
        )
        conn.commit()

    conn.close()
