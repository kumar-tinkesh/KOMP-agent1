from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from loguru import logger
import sqlite3
import io
# pyrefly: ignore [missing-import]
from fastapi_app.dependencies import get_db, require_client
# pyrefly: ignore [missing-import]
from src.Models.modelUtils import get_client_by_user_id
# pyrefly: ignore [missing-import]
from src.Security.security import decrypt_password
# pyrefly: ignore [missing-import]
from src.services import email_service

router = APIRouter(prefix="/client", tags=["Client Operations"])


class EmailFetchRequest(BaseModel):
    limit: int = Field(5, ge=1, le=50, description="Number of latest emails to retrieve")
    status_filter: str = Field("ALL", description="Filter type ('ALL', 'UNSEEN', 'SEEN')")


@router.post("/emails")
def fetch_emails(
    req: EmailFetchRequest,
    db: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(require_client)
):
    """
    Fetch the latest emails for the authenticated client using their database-stored credentials.
    The query parameters (limit and status_filter) are sent in the request body.
    """
    logger.info(
        f"Client '{current_user['username']}' (User ID: {current_user['user_id']}) "
        f"requested latest emails: limit={req.limit}, status_filter='{req.status_filter}'"
    )
    
    if req.status_filter not in ("ALL", "UNSEEN", "SEEN"):
        logger.warning(f"Invalid status_filter '{req.status_filter}' requested by '{current_user['username']}'")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="status_filter must be one of: 'ALL', 'UNSEEN', 'SEEN'"
        )

    # 1. Fetch client profile
    client = get_client_by_user_id(db, current_user["user_id"])
    if not client:
        logger.error(f"Client profile not found in database for user ID: {current_user['user_id']}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client profile not found in database."
        )

    # 2. Decrypt client's IMAP password
    try:
        decrypted_password = decrypt_password(client["app_password"])
    except Exception as e:
        logger.error(f"Failed to decrypt credentials for client email '{client['email']}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to decrypt credentials. Super Admin must reset configuration. ({str(e)})"
        )

    # 3. Call prebuilt email retrieval service
    try:
        logger.info(f"Connecting to IMAP host '{client['imap_host']}' for email '{client['email']}'...")
        emails = email_service.list_latest_emails(
            host=client["imap_host"],
            username=client["email"],
            password=decrypted_password,
            mailbox=client["mailbox"],
            limit=req.limit,
            status_filter=req.status_filter
        )
        logger.info(f"Successfully retrieved {len(emails)} emails for client '{client['email']}'")
        return {
            "client_name": client["name"],
            "email_address": client["email"],
            "mailbox": client["mailbox"],
            "status_filter": req.status_filter,
            "emails_count": len(emails),
            "emails": emails
        }
    except Exception as e:
        logger.error(f"Failed to fetch emails for client '{client['email']}' via IMAP: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"IMAP Server Error: {str(e)}"
        )


@router.get("/emails/{msg_id}/attachments/view")
def view_attachments(
    msg_id: str,
    db: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(require_client)
):
    """
    Connect to IMAP and retrieve text/metadata for all attachments on a given email.
    Performs all operations completely in-memory (RAM) without writing to server disk.
    """
    logger.info(f"Client '{current_user['username']}' requested in-memory attachment text view for email ID: {msg_id}")
    
    # 1. Fetch client profile
    client = get_client_by_user_id(db, current_user["user_id"])
    if not client:
        logger.error(f"Client profile not found in database for user ID: {current_user['user_id']}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client profile not found in database."
        )

    # 2. Decrypt client's IMAP password
    try:
        decrypted_password = decrypt_password(client["app_password"])
    except Exception as e:
        logger.error(f"Failed to decrypt credentials for client email '{client['email']}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to decrypt credentials. Super Admin must reset configuration. ({str(e)})"
        )

    # 3. Fetch in-memory attachment structures and texts
    try:
        attachments = email_service.get_email_attachments_in_memory(
            host=client["imap_host"],
            username=client["email"],
            password=decrypted_password,
            msg_id=msg_id,
            mailbox=client["mailbox"]
        )
        
        # Exclude binary content_bytes from JSON metadata response
        attachments_meta = []
        for item in attachments:
            attachments_meta.append({
                "filename": item["filename"],
                "text_content": item["text_content"]
            })
            
        logger.info(f"Successfully retrieved {len(attachments_meta)} attachments in memory for email ID: {msg_id}")
        return {
            "email_id": msg_id,
            "attachments_count": len(attachments_meta),
            "attachments": attachments_meta
        }
    except Exception as e:
        logger.error(f"Failed to fetch attachments for email ID '{msg_id}' via IMAP: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"IMAP Server or Extraction Error: {str(e)}"
        )


@router.get("/emails/{msg_id}/attachments/download")
def download_attachment(
    msg_id: str,
    filename: str,
    db: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(require_client)
):
    """
    Download a specific attachment from an email as a binary file stream.
    Performs all operations completely in-memory (RAM) without writing to server disk.
    """
    logger.info(f"Client '{current_user['username']}' requested download of attachment '{filename}' from email ID: {msg_id}")
    
    # 1. Fetch client profile
    client = get_client_by_user_id(db, current_user["user_id"])
    if not client:
        logger.error(f"Client profile not found in database for user ID: {current_user['user_id']}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client profile not found in database."
        )

    # 2. Decrypt client's IMAP password
    try:
        decrypted_password = decrypt_password(client["app_password"])
    except Exception as e:
        logger.error(f"Failed to decrypt credentials for client email '{client['email']}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to decrypt credentials. Super Admin must reset configuration. ({str(e)})"
        )

    # 3. Retrieve attachments in memory and find the requested filename
    try:
        attachments = email_service.get_email_attachments_in_memory(
            host=client["imap_host"],
            username=client["email"],
            password=decrypted_password,
            msg_id=msg_id,
            mailbox=client["mailbox"]
        )
        
        target_bytes = None
        for item in attachments:
            if item["filename"].lower() == filename.lower():
                target_bytes = item["content_bytes"]
                break
                
        if target_bytes is None:
            logger.warning(f"Attachment '{filename}' not found for email ID '{msg_id}'. Available: {[a['filename'] for a in attachments]}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Attachment '{filename}' not found for this email."
            )
            
        logger.info(f"Streaming attachment '{filename}' ({len(target_bytes)} bytes) back to client...")
        return StreamingResponse(
            io.BytesIO(target_bytes),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download attachment for email ID '{msg_id}' via IMAP: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"IMAP Server or Extraction Error: {str(e)}"
        )


import json

INVOICE_EXTRACTION_PROMPT = """
You are an expert invoice and timesheet data parser.
Analyze the provided document text context and extract all billing/timesheet information.

Generate a JSON response containing the following structure:
{
  "invoice_number": null or string,
  "invoice_date": null or string,
  "billing_period": null or string,
  "client_name": null or string,
  "contractors": [
    {
      "name": null or string,
      "position": null or string,
      "hourly_rate": null or string,
      "total_hours": null or string,
      "amount_due": null or string,
      "payable_to": null or string,
      "tasks": [
        {
          "task_name": string,
          "date": string,
          "duration": string
        }
      ]
    }
  ],
  "total_amount_due": null or string,
  "additional_metadata": {
     // Put any other key-value pairs found in the document that do not fit the fixed schema above
  },
  "additional_notes": null or string
}

Return ONLY the raw JSON object. Do not wrap the JSON in markdown code blocks like ```json ... ```.
"""

def parse_llm_json(response_text: str) -> dict:
    cleaned = response_text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except Exception as e:
        logger.warning(f"Failed to parse LLM structured response as JSON: {e}. Raw text: {response_text}")
        return {"raw_text": response_text, "parsing_error": str(e)}


@router.get("/emails/{msg_id}/attachments/analyze")
def analyze_attachments(
    msg_id: str,
    db: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(require_client)
):
    """
    Fetch all attachments for the given email in RAM, run them through the Gemini structured extraction client,
    and return parsed key-value invoice/timesheet fields (supporting multi-person structures and dynamic metadata).
    """
    logger.info(f"Client '{current_user['username']}' requested LLM extraction analysis for email ID: {msg_id}")
    
    # 1. Fetch client profile
    client = get_client_by_user_id(db, current_user["user_id"])
    if not client:
        logger.error(f"Client profile not found in database for user ID: {current_user['user_id']}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client profile not found in database."
        )

    # 2. Decrypt client's IMAP password
    try:
        decrypted_password = decrypt_password(client["app_password"])
    except Exception as e:
        logger.error(f"Failed to decrypt credentials for client email '{client['email']}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to decrypt credentials. Super Admin must reset configuration. ({str(e)})"
        )

    # 3. Retrieve attachments in RAM
    try:
        attachments = email_service.get_email_attachments_in_memory(
            host=client["imap_host"],
            username=client["email"],
            password=decrypted_password,
            msg_id=msg_id,
            mailbox=client["mailbox"]
        )
    except Exception as e:
        logger.error(f"Failed to retrieve attachments for email ID '{msg_id}' via IMAP: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"IMAP Server or Extraction Error: {str(e)}"
        )

    if not attachments:
        return {
            "email_id": msg_id,
            "message": "No attachments found to analyze.",
            "analyzed_count": 0,
            "results": []
        }

    # 4. Initialize GeminiClient
    # pyrefly: ignore [missing-import]
    from llm.geminiClient import GeminiClient
    llm = GeminiClient()

    # 5. Run extraction on each attachment
    results = []
    for item in attachments:
        filename = item["filename"]
        text_content = item["text_content"]

        if not text_content or "[Error" in text_content:
            results.append({
                "filename": filename,
                "status": "Skipped (no content or error)",
                "extracted_data": None
            })
            continue

        try:
            # Call generate_structured with our specialized invoice parser prompt
            raw_response = llm.generate_structured(
                context=text_content,
                prompt=INVOICE_EXTRACTION_PROMPT
            )
            extracted_json = parse_llm_json(raw_response)
            results.append({
                "filename": filename,
                "status": "Success",
                "extracted_data": extracted_json
            })
        except Exception as e:
            logger.error(f"Error running LLM structuring for attachment '{filename}': {e}")
            results.append({
                "filename": filename,
                "status": f"Error: {str(e)}",
                "extracted_data": None
            })

    return {
        "email_id": msg_id,
        "analyzed_count": len(results),
        "results": results
    }
