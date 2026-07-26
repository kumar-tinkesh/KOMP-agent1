import imaplib
import email
import re
from email.header import decode_header

try:
    # pyrefly: ignore [missing-import]
    import pypdf
except ImportError:
    pypdf = None

try:
    # pyrefly: ignore [missing-import]
    import docx
except ImportError:
    docx = None

try:
    # pyrefly: ignore [missing-import]
    import openpyxl
except ImportError:
    openpyxl = None

try:
    import xlrd
except ImportError:
    xlrd = None



# IMAP exception classes are imported from email_service_utils at the bottom of the file



def list_latest_emails(host, username, password, mailbox="INBOX", limit=5, status_filter="ALL"):
    """
    Connects to an IMAP server and retrieves the latest emails.

    Args:
        host: IMAP server address
        username: Email address
        password: App password (plaintext decrypted)
        mailbox: Mailbox name
        limit: Number of emails to fetch
        status_filter: Filter type ('ALL', 'UNSEEN', 'SEEN')

    Returns:
        List[dict]: Details of retrieved emails.
    """
    if status_filter not in ("ALL", "UNSEEN", "SEEN"):
        status_filter = "ALL"

    try:
        mail = imaplib.IMAP4_SSL(host)
    except Exception as e:
        raise IMAPConnectionError(f"Could not establish connection to host '{host}': {e}")

    try:
        try:
            mail.login(username, password)
        except imaplib.IMAP4.error as e:
            raise IMAPAuthenticationError(
                f"Failed to authenticate user '{username}' on IMAP server: {e}"
            )

        try:
            status, _ = mail.select(mailbox)
            if status != "OK":
                raise IMAPMailboxError(f"Unable to open mailbox: '{mailbox}'")
        except Exception as e:
            if not isinstance(e, IMAPMailboxError):
                raise IMAPMailboxError(f"Error selecting mailbox '{mailbox}': {e}")
            raise e

        status, messages = mail.search(None, status_filter)
        if status != "OK":
            raise IMAPMailboxError("Failed to list messages in the selected mailbox.")

        email_ids = messages[0].split()
        if not email_ids:
            return []

        # Get latest email ids
        email_ids = email_ids[-limit:]
        email_ids.reverse()  # Newest emails first

        email_list = []

        for msg_id in email_ids:
            try:
                status, msg_data = mail.fetch(msg_id, "(FLAGS RFC822)")
                if status != "OK" or not msg_data or not msg_data[0]:
                    continue

                flags_metadata = msg_data[0][0]
                is_read = b'\\Seen' in flags_metadata

                msg = email.message_from_bytes(msg_data[0][1])

                subject_header = msg.get("Subject", "")
                subject_decoded = decode_header(subject_header)[0]
                subject = subject_decoded[0]

                if isinstance(subject, bytes):
                    subject = subject.decode(
                        subject_decoded[1] or "utf-8",
                        errors="ignore"
                    )

                attachments = []
                html_body = ""
                text_body = ""
                for part in msg.walk():
                    content_type = part.get_content_type()
                    if content_type == "text/plain":
                        try:
                            payload = part.get_payload(decode=True)
                            if payload:
                                text_body += payload.decode('utf-8', errors='ignore')
                        except Exception:
                            pass
                    elif content_type == "text/html":
                        try:
                            payload = part.get_payload(decode=True)
                            if payload:
                                html_body += payload.decode('utf-8', errors='ignore')
                        except Exception:
                            pass

                    filename = part.get_filename()
                    if filename:
                        decoded_filename_parts = decode_header(filename)
                        decoded_filename = ""
                        for decoded_text, encoding in decoded_filename_parts:
                            if isinstance(decoded_text, bytes):
                                try:
                                    decoded_filename += decoded_text.decode(encoding or "utf-8", errors="ignore")
                                except Exception:
                                    decoded_filename += decoded_text.decode("utf-8", errors="ignore")
                            else:
                                decoded_filename += decoded_text
                        if decoded_filename not in attachments:
                            attachments.append(decoded_filename)
                    elif part.get_content_disposition() == 'attachment':
                        attachments.append("unnamed_attachment")

                # Parse Google Drive attachments in HTML body
                if html_body:
                    drive_pattern = r'href="https://drive\.google\.com/file/d/[^"]+"[^>]*aria-label="([^"]+)"'
                    drive_matches = re.findall(drive_pattern, html_body)
                    if not drive_matches:
                        span_pattern = r'class="[^"]*gmail_drive_chip[^"]*".*?<span dir="ltr"[^>]*>([^<]+)</span>'
                        drive_matches = re.findall(span_pattern, html_body, re.DOTALL)
                    for match in drive_matches:
                        name = match.strip()
                        if name and name not in attachments:
                            attachments.append(name)

                # Parse Google Drive attachments in Plain Text body
                if text_body:
                    lines = [line.strip() for line in text_body.splitlines() if line.strip()]
                    for idx, line in enumerate(lines):
                        if "drive.google.com/file/d/" in line:
                            filename = "Google Drive File"
                            if idx > 0 and lines[idx - 1] and not ("drive.google.com" in lines[idx - 1] or "http" in lines[idx - 1]):
                                filename = lines[idx - 1].strip("<>()[]\"' ")
                            if filename and filename not in attachments:
                                attachments.append(filename)

                email_list.append(
                    {
                        "id": msg_id.decode("utf-8", errors="ignore"),
                        "subject": subject,
                        "from": msg.get("From"),
                        "to": msg.get("To"),
                        "date": msg.get("Date"),
                        "status": "Read" if is_read else "Unread",
                        "has_attachment": len(attachments) > 0,
                        "attachment_count": len(attachments),
                        "attachment_names": attachments,
                    }
                )
            except Exception:
                # Continue fetching other emails even if one fails
                continue

        return email_list

    finally:
        try:
            mail.logout()
        except:
            pass


# pyrefly: ignore [missing-import]
from src.services.email_service_utils import (
    IMAPConnectionError,
    IMAPAuthenticationError,
    IMAPMailboxError,
    extract_text_from_attachment,
    download_email_attachments,
    extract_drive_links,
    download_file_from_google_drive,
)

