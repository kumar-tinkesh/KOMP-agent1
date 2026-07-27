import json
import time
import sqlite3
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# pyrefly: ignore [missing-import]
from src.Models import database
# pyrefly: ignore [missing-import]
from src.Security.security import encrypt_password, decrypt_password

# Authentication scheme using HTTP Bearer token (simply prompts for access token)
security_scheme = HTTPBearer()

def get_db():
    """
    Dependency injection for database connection.
    Enures proper connection opening and closing.
    """
    conn = database.get_db_connection()
    try:
        yield conn
    finally:
        conn.close()


def create_access_token(data: dict, expires_in: int = 3600) -> str:
    """
    Creates a signed/encrypted token using Fernet.
    Injects an expiration timestamp.
    """
    payload = data.copy()
    payload["exp"] = time.time() + expires_in
    payload_str = json.dumps(payload)
    return encrypt_password(payload_str)


def decode_access_token(token: str) -> dict | None:
    """
    Decrypts the token using Fernet and verifies the expiration.
    """
    try:
        payload_str = decrypt_password(token)
        payload = json.loads(payload_str)
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security_scheme)):
    """
    Dependency to fetch the authenticated user payload.
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials or token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


def require_admin(current_user: dict = Depends(get_current_user)):
    """
    Dependency to restrict access to super admin users only.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: Super Admin role required."
        )
    return current_user


def require_client(current_user: dict = Depends(get_current_user)):
    """
    Dependency to restrict access to client users only.
    """
    if current_user.get("role") != "client":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: Client role required."
        )
    return current_user
