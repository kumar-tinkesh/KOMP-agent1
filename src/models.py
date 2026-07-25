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


# --- Client Queries ---

def create_client(conn, user_id, name, email, imap_host, app_password, imap_port=993, mailbox="INBOX"):
    """
    Inserts a new client record.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO clients (user_id, name, email, imap_host, imap_port, app_password, mailbox)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        (user_id, name, email, imap_host, imap_port, app_password, mailbox)
    )
    return cursor.lastrowid


def get_all_clients(conn):
    """
    Retrieves all clients, including their login usernames.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT 
            c.id AS client_id,
            u.id AS user_id,
            u.username,
            c.name,
            c.email,
            c.imap_host,
            c.imap_port,
            c.mailbox,
            c.is_active
        FROM clients c
        JOIN users u ON c.user_id = u.id;
        """
    )
    return cursor.fetchall()


def get_client_by_user_id(conn, user_id):
    """
    Retrieves the client record associated with a given user ID.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clients WHERE user_id = ?;", (user_id,))
    return cursor.fetchone()


def get_client_by_id(conn, client_id):
    """
    Retrieves client and associated username details by client ID.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT 
            c.*,
            u.username
        FROM clients c
        JOIN users u ON c.user_id = u.id
        WHERE c.id = ?;
        """,
        (client_id,)
    )
    return cursor.fetchone()


def update_client(conn, client_id, **kwargs):
    """
    Dynamically updates client fields passed as keyword arguments.
    """
    if not kwargs:
        return
        
    cursor = conn.cursor()
    
    # Filter valid keys to prevent injection
    valid_fields = {"name", "email", "imap_host", "imap_port", "app_password", "mailbox", "is_active"}
    updates = []
    params = []
    
    for key, value in kwargs.items():
        if key in valid_fields:
            updates.append(f"{key} = ?")
            params.append(value)
            
    if not updates:
        return
        
    params.append(client_id)
    query = f"UPDATE clients SET {', '.join(updates)} WHERE id = ?;"
    cursor.execute(query, params)


def update_user_credentials(conn, user_id, username=None, password_hash=None):
    """
    Updates user credentials.
    """
    cursor = conn.cursor()
    updates = []
    params = []
    if username is not None:
        updates.append("username = ?")
        params.append(username)
    if password_hash is not None:
        updates.append("password_hash = ?")
        params.append(password_hash)
        
    if not updates:
        return
        
    params.append(user_id)
    query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?;"
    cursor.execute(query, params)


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
