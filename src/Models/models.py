import sqlite3


# --- User Queries ---

def create_user(conn, username, password_hash, role):
    """
    Inserts a new user record.
    """
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?);",
        (username, password_hash, role)
    )
    return cursor.lastrowid


def get_user_by_username(conn, username):
    """
    Retrieves a user by username.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?;", (username,))
    return cursor.fetchone()


def get_user_by_id(conn, user_id):
    """
    Retrieves a user by ID.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?;", (user_id,))
    return cursor.fetchone()


def any_admins_exist(conn) -> bool:
    """
    Checks if there are any Super Admin users registered in the system.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM users WHERE role = 'admin' LIMIT 1;")
    return cursor.fetchone() is not None


def delete_user(conn, user_id):
    """
    Deletes a user from the users table.
    Due to ON DELETE CASCADE, the linked client is also deleted.
    """
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?;", (user_id,))

# --- Validation Helpers ---

def is_username_unique(conn, username, exclude_user_id=None) -> bool:
    """
    Checks if a username is unique, optionally excluding a specific user ID (for updates).
    """
    cursor = conn.cursor()
    if exclude_user_id is not None:
        cursor.execute("SELECT 1 FROM users WHERE username = ? AND id != ? LIMIT 1;", (username, exclude_user_id))
    else:
        cursor.execute("SELECT 1 FROM users WHERE username = ? LIMIT 1;", (username,))
    return cursor.fetchone() is None


def is_email_unique(conn, email, exclude_client_id=None) -> bool:
    """
    Checks if a client email is unique, optionally excluding a specific client ID (for updates).
    """
    cursor = conn.cursor()
    if exclude_client_id is not None:
        cursor.execute("SELECT 1 FROM clients WHERE email = ? AND id != ? LIMIT 1;", (email, exclude_client_id))
    else:
        cursor.execute("SELECT 1 FROM clients WHERE email = ? LIMIT 1;", (email,))
    return cursor.fetchone() is None
