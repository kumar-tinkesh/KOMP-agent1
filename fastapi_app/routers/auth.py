from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from loguru import logger
import sqlite3
# pyrefly: ignore [missing-import]
from fastapi_app.dependencies import get_db, create_access_token
# pyrefly: ignore [missing-import]
from src.Security.auth import authenticate_user, AccountDisabledError

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, description="Username of the user")
    password: str = Field(..., min_length=1, description="Password of the user")


@router.post("/login")
def login(
    credentials: LoginRequest,
    db: sqlite3.Connection = Depends(get_db)
):
    """
    Authenticate a user (admin or client) and issue an OAuth2 Access Token.
    Expects a JSON body containing only username and password.
    """
    logger.info(f"Login attempt received for username: '{credentials.username}'")
    try:
        user_session = authenticate_user(db, credentials.username, credentials.password)
        if not user_session:
            logger.warning(f"Failed login attempt for username: '{credentials.username}' - Invalid credentials.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect username or password"
            )
        
        # Issue encrypted token containing user_id, username, and role
        access_token = create_access_token(user_session)
        logger.info(f"Successful login for user '{credentials.username}' with role '{user_session['role']}'")
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": user_session
        }
    except AccountDisabledError as e:
        logger.warning(f"Deactivated account login attempt for '{credentials.username}': {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Internal error during login for '{credentials.username}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication system error: {str(e)}"
        )
