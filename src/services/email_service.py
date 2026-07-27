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
    Optimized for high performance by fetching metadata first, and filtering social/promo emails.
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

        # Get a larger window of email IDs to account for filtered messages
        fetch_limit = max(limit * 3, limit + 10)
        email_ids = email_ids[-fetch_limit:]
        email_ids.reverse()  # Newest emails first

        email_list = []
        is_gmail = "gmail.com" in host.lower()
        metadata_query = "(FLAGS RFC822.SIZE X-GM-LABELS)" if is_gmail else "(FLAGS RFC822.SIZE)"

        for msg_id in email_ids:
            if len(email_list) >= limit:
                break

            try:
                # 1. Fetch metadata first (extremely fast check)
                status, metadata_resp = mail.fetch(msg_id, metadata_query)
                if status != "OK" or not metadata_resp or not metadata_resp[0]:
                    continue

                first_item = metadata_resp[0]
                if isinstance(first_item, tuple):
                    first_item = first_item[0]

                metadata_str = first_item.decode('utf-8', errors='ignore') if isinstance(first_item, bytes) else str(first_item)
                
                # Check seen flag
                is_read = b'\\Seen' in first_item if isinstance(first_item, bytes) else '\\Seen' in str(first_item)

                # Check Gmail category labels (fast check)
                if is_social_or_promotional_email(metadata_str, "", "", None, is_gmail):
                    continue

                # Parse email size in bytes
                size_match = re.search(r'RFC822\.SIZE\s+(\d+)', metadata_str, re.IGNORECASE)
                email_size = int(size_match.group(1)) if size_match else 0

                attachments = []
                subject = ""
                from_val = ""
                to_val = ""
                date_val = ""
                msg_obj = None

                # 2. Decide fetch strategy based on email size (avoid downloading large attachments during listing)
                if email_size > 0 and email_size < 150000:
                    # Small email: Fetch full RFC822 body for complete parsing (including Drive links)
                    status, msg_data = mail.fetch(msg_id, "(RFC822)")
                    if status != "OK" or not msg_data or not msg_data[0]:
                        continue
                    
                    msg_obj = email.message_from_bytes(msg_data[0][1])
                    
                    subject_header = msg_obj.get("Subject", "")
                    subject_decoded = decode_header(subject_header)[0]
                    subject = subject_decoded[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(subject_decoded[1] or "utf-8", errors="ignore")
                    
                    from_val = msg_obj.get("From")
                    to_val = msg_obj.get("To")
                    date_val = msg_obj.get("Date")

                    html_body = ""
                    text_body = ""
                    for part in msg_obj.walk():
                        content_type = part.get_content_type()
                        if content_type == "text/plain":
                            try:
                                payload = part.get_payload(decode=True)
                                if payload:
                                    text_body += payload.decode('utf-8', errors='ignore')
                            except:
                                pass
                        elif content_type == "text/html":
                            try:
                                payload = part.get_payload(decode=True)
                                if payload:
                                    html_body += payload.decode('utf-8', errors='ignore')
                            except:
                                pass

                        filename = part.get_filename()
                        if filename:
                            decoded_filename_parts = decode_header(filename)
                            decoded_filename = ""
                            for decoded_text, encoding in decoded_filename_parts:
                                if isinstance(decoded_text, bytes):
                                    try:
                                        decoded_filename += decoded_text.decode(encoding or "utf-8", errors="ignore")
                                    except:
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
                
                else:
                    # Large email: Fetch only HEADERS and BODYSTRUCTURE to keep it extremely fast
                    status, msg_data = mail.fetch(msg_id, "(BODYSTRUCTURE BODY[HEADER.FIELDS (FROM TO SUBJECT DATE)])")
                    if status != "OK" or not msg_data or not msg_data[0]:
                        continue
                    
                    meta_str = msg_data[0][0].decode('utf-8', errors='ignore') if isinstance(msg_data[0][0], bytes) else str(msg_data[0][0])
                    raw_headers = msg_data[0][1]
                    
                    msg_obj = email.message_from_bytes(raw_headers)
                    subject_header = msg_obj.get("Subject", "")
                    subject_decoded = decode_header(subject_header)[0]
                    subject = subject_decoded[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(subject_decoded[1] or "utf-8", errors="ignore")
                        
                    from_val = msg_obj.get("From")
                    to_val = msg_obj.get("To")
                    date_val = msg_obj.get("Date")
                    
                    # Extract standard attachment filenames from BODYSTRUCTURE response
                    found_filenames = re.findall(r'"filename"\s+"([^"]+)"', meta_str, re.IGNORECASE)
                    for fname in found_filenames:
                        decoded_parts = decode_header(fname)
                        decoded_fname = ""
                        for decoded_text, encoding in decoded_parts:
                            if isinstance(decoded_text, bytes):
                                try:
                                    decoded_fname += decoded_text.decode(encoding or "utf-8", errors="ignore")
                                except:
                                    decoded_fname += decoded_text.decode("utf-8", errors="ignore")
                            else:
                                decoded_fname += decoded_text
                        if decoded_fname and decoded_fname not in attachments:
                            attachments.append(decoded_fname)

                # 3. Apply header-based social and promotional filtering
                if is_social_or_promotional_email("", from_val, subject, msg_obj, is_gmail):
                    continue  # Skip social and promotional messages!

                email_list.append(
                    {
                        "id": msg_id.decode("utf-8", errors="ignore"),
                        "subject": subject,
                        "from": from_val,
                        "to": to_val,
                        "date": date_val,
                        "status": "Read" if is_read else "Unread",
                        "has_attachment": len(attachments) > 0,
                        "attachment_count": len(attachments),
                        "attachment_names": attachments,
                    }
                )
            except Exception:
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
    is_social_or_promotional_email,
    get_email_attachments_in_memory,
)

