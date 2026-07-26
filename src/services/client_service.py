# pyrefly: ignore [missing-import]
from src.Models import models
# pyrefly: ignore [missing-import]
from src.Models import modelUtils
# Merge client queries into models namespace
for _name in dir(modelUtils):
    if not _name.startswith('_'):
        setattr(models, _name, getattr(modelUtils, _name))
# pyrefly: ignore [missing-import]
from src.Security.security import hash_password, encrypt_password


def add_client(conn, username, password, name, email, imap_host, app_password, imap_port=993, mailbox="INBOX"):
    """
    Business logic to add a new client.
    Performs validation, hashes user login password, encrypts IMAP password,
    and saves both user and client records inside an SQLite transaction.
    """
    # 1. Validation checks
    if not models.is_username_unique(conn, username):
        raise ValueError(f"Username '{username}' is already taken.")
    if not models.is_email_unique(conn, email):
        raise ValueError(f"Email '{email}' is already registered to another client.")

    # 2. Perform operations inside transaction context manager
    with conn:
        # Hash user password
        p_hash = hash_password(password)
        user_id = models.create_user(conn, username, p_hash, "client")
        
        # Encrypt IMAP app password
        encrypted_app_pass = encrypt_password(app_password)
        
        # Create client details
        client_id = models.create_client(
            conn, 
            user_id=user_id, 
            name=name, 
            email=email, 
            imap_host=imap_host, 
            imap_port=imap_port, 
            app_password=encrypted_app_pass, 
            mailbox=mailbox
        )
        
        return client_id


def get_clients(conn):
    """
    Retrieves all clients from the system.
    """
    return models.get_all_clients(conn)


def get_client_details_by_id(conn, client_id):
    """
    Retrieves complete client details including login username.
    """
    return models.get_client_by_id(conn, client_id)


def update_client_profile(conn, client_id, **kwargs):
    """
    Updates client and optionally user login details in a transaction.
    """
    client = models.get_client_by_id(conn, client_id)
    if not client:
        raise ValueError("Client profile not found.")
        
    user_id = client["user_id"]
    
    # Validations
    new_username = kwargs.get("username")
    if new_username and new_username != client["username"]:
        if not models.is_username_unique(conn, new_username, exclude_user_id=user_id):
            raise ValueError(f"Username '{new_username}' is already taken.")
            
    new_email = kwargs.get("email")
    if new_email and new_email != client["email"]:
        if not models.is_email_unique(conn, new_email, exclude_client_id=client_id):
            raise ValueError(f"Email '{new_email}' is already registered to another client.")

    with conn:
        # Update user fields
        user_updates = {}
        if new_username:
            user_updates["username"] = new_username
        if kwargs.get("password"):
            user_updates["password_hash"] = hash_password(kwargs.get("password"))
            
        if user_updates:
            models.update_user_credentials(conn, user_id, **user_updates)
            
        # Update client fields
        client_updates = {}
        for field in ["name", "email", "imap_host", "imap_port", "mailbox", "is_active"]:
            if field in kwargs and kwargs[field] is not None:
                client_updates[field] = kwargs[field]
                
        if kwargs.get("app_password"):
            client_updates["app_password"] = encrypt_password(kwargs.get("app_password"))
            
        if client_updates:
            models.update_client(conn, client_id, **client_updates)


def delete_client_profile(conn, client_id):
    """
    Deletes client and user records by deleting the parent user profile.
    """
    client = models.get_client_by_id(conn, client_id)
    if not client:
        raise ValueError("Client profile not found.")
        
    with conn:
        models.delete_user(conn, client["user_id"])
