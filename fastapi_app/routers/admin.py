from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from loguru import logger
import sqlite3
# pyrefly: ignore [missing-import]
from fastapi_app.dependencies import get_db, require_admin
# pyrefly: ignore [missing-import]
from src.services import client_service

router = APIRouter(prefix="/admin", tags=["Admin Operations"])


class ClientCreate(BaseModel):
    username: str = Field(..., min_length=1, description="Login username for the client")
    password: str = Field(..., min_length=1, description="Login password for the client")
    name: str = Field(..., min_length=1, description="Name of the client")
    email: str = Field(..., description="Client email address")
    imap_host: str = Field(..., description="IMAP server host (e.g. imap.gmail.com or outlook.office365.com)")
    imap_port: int = Field(993, description="IMAP server port (usually 993)")
    app_password: str = Field(..., description="Plaintext IMAP app password")
    mailbox: str = Field("INBOX", description="Default mailbox directory")


@router.post("/clients", status_code=status.HTTP_201_CREATED)
def create_client(
    client_data: ClientCreate,
    db: sqlite3.Connection = Depends(get_db),
    admin_user: dict = Depends(require_admin)
):
    """
    Super Admin only endpoint to register a new client and configure their IMAP settings.
    """
    logger.info(
        f"Admin '{admin_user['username']}' requested client registration for: "
        f"username='{client_data.username}', email='{client_data.email}'"
    )
    try:
        client_id = client_service.add_client(
            db,
            username=client_data.username,
            password=client_data.password,
            name=client_data.name,
            email=client_data.email,
            imap_host=client_data.imap_host,
            app_password=client_data.app_password,
            imap_port=client_data.imap_port,
            mailbox=client_data.mailbox
        )
        logger.info(f"Successfully registered client '{client_data.username}' with ID {client_id}")
        return {
            "message": "Client created successfully",
            "client_id": client_id,
            "username": client_data.username,
            "email": client_data.email
        }
    except ValueError as e:
        logger.warning(f"Validation failure during client creation by '{admin_user['username']}': {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected system error during client creation by '{admin_user['username']}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database or system error: {str(e)}"
        )
