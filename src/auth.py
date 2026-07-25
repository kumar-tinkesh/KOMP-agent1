from src.models import get_user_by_username, get_client_by_user_id
from src.security import verify_password


class AccountDisabledError(Exception):
    """Exception raised when an inactive client tries to log in."""
    pass


def authenticate_user(conn, username, password):
    """
    Authenticate a user by validating their password against their PBKDF2 hash.
    If the user is a client, we also check if their account status is active.
    
    Returns a dict session payload on success, or None on invalid credentials.
    Raises AccountDisabledError if the client account is disabled.
    """
    user = get_user_by_username(conn, username)
    if not user:
        return None

    if not verify_password(user["password_hash"], password):
        return None

    # For client roles, verify if they are active in the clients table
    if user["role"] == "client":
        client = get_client_by_user_id(conn, user["id"])
        if client and not client["is_active"]:
            raise AccountDisabledError(
                "Access Denied: Your client account has been deactivated by the Super Admin."
            )

    return {
        "user_id": user["id"],
        "username": user["username"],
        "role": user["role"]
    }
