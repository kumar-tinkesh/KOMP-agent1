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

        is_gmail = "gmail.com" in host.lower()
        metadata_query = "(FLAGS RFC822.SIZE X-GM-LABELS)" if is_gmail else "(FLAGS RFC822.SIZE)"

        # 1. Fetch metadata in bulk for all potential emails
        id_sequence = b",".join(email_ids)
        status, metadata_resp = mail.fetch(id_sequence, metadata_query)
        if status != "OK" or not metadata_resp:
            return []

        # Parse bulk metadata responses
        parsed_metadata = {}
        for item in metadata_resp:
            if not isinstance(item, bytes):
                continue
            item_str = item.decode('utf-8', errors='ignore')
            match_id = re.match(r'^(\d+)\s+', item_str)
            if not match_id:
                continue
            seq_id = match_id.group(1)
            
            is_read = '\\Seen' in item_str
            is_social_or_promo = is_social_or_promotional_email(item_str, "", "", None, is_gmail)
            
            size_match = re.search(r'RFC822\.SIZE\s+(\d+)', item_str, re.IGNORECASE)
            email_size = int(size_match.group(1)) if size_match else 0
            
            parsed_metadata[seq_id] = {
                "is_read": is_read,
                "is_social_or_promo": is_social_or_promo,
                "email_size": email_size
            }

        # 2. Filter out category-flagged emails and select up to `limit` active emails
        active_emails = []
        for msg_id in email_ids:
            msg_id_str = msg_id.decode('utf-8', errors='ignore')
            meta = parsed_metadata.get(msg_id_str)
            if not meta:
                continue
            if meta["is_social_or_promo"]:
                continue
            
            active_emails.append({
                "id_bytes": msg_id,
                "id_str": msg_id_str,
                "is_read": meta["is_read"],
                "email_size": meta["email_size"]
            })
            if len(active_emails) >= limit:
                break

        if not active_emails:
            return []

        # 3. Split active emails into small and large groups
        small_emails = [e for e in active_emails if e["email_size"] > 0 and e["email_size"] < 150000]
        large_emails = [e for e in active_emails if e["email_size"] == 0 or e["email_size"] >= 150000]

        # 4. Bulk fetch small email bodies
        parsed_small = {}
        if small_emails:
            small_ids = b",".join([e["id_bytes"] for e in small_emails])
            status, small_resp = mail.fetch(small_ids, "(RFC822)")
            if status == "OK" and small_resp:
                for item in small_resp:
                    if isinstance(item, tuple):
                        meta_str = item[0].decode('utf-8', errors='ignore')
                        body_bytes = item[1]
                        match_id = re.match(r'^(\d+)\s+', meta_str)
                        if match_id:
                            seq_id = match_id.group(1)
                            parsed_small[seq_id] = body_bytes

        # 5. Bulk fetch large email headers and bodystructures
        parsed_large = {}
        if large_emails:
            large_ids = b",".join([e["id_bytes"] for e in large_emails])
            status, large_resp = mail.fetch(large_ids, "(BODYSTRUCTURE BODY[HEADER.FIELDS (FROM TO SUBJECT DATE)])")
            if status == "OK" and large_resp:
                for i in range(len(large_resp)):
                    item = large_resp[i]
                    if isinstance(item, tuple):
                        meta_str = item[0].decode('utf-8', errors='ignore')
                        header_bytes = item[1]
                        match_id = re.match(r'^(\d+)\s+', meta_str)
                        if match_id:
                            seq_id = match_id.group(1)
                            
                            # Retrieve the following structure block
                            structure_str = ""
                            if i + 1 < len(large_resp) and isinstance(large_resp[i+1], bytes):
                                structure_str = large_resp[i+1].decode('utf-8', errors='ignore')
                                
                            parsed_large[seq_id] = {
                                "header_bytes": header_bytes,
                                "structure_str": structure_str
                            }

        # 6. Construct final email records list
        email_list = []
        for item in active_emails:
            seq_id = item["id_str"]
            is_read = item["is_read"]
            msg_obj = None
            subject = ""
            from_val = ""
            to_val = ""
            date_val = ""
            attachments = []

            try:
                if seq_id in parsed_small:
                    # Small email processing: Parse full message
                    msg_obj = email.message_from_bytes(parsed_small[seq_id])
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
                        for dm in drive_matches:
                            name = dm.strip()
                            if name and name not in attachments:
                                attachments.append(name)

                    # Parse Google Drive attachments in Plain Text body
                    if text_body:
                        lines = [line.strip() for line in text_body.splitlines() if line.strip()]
                        for idx, line in enumerate(lines):
                            if "drive.google.com/file/d/" in line:
                                fname = "Google Drive File"
                                if idx > 0 and lines[idx - 1] and not ("drive.google.com" in lines[idx - 1] or "http" in lines[idx - 1]):
                                    fname = lines[idx - 1].strip("<>()[]\"' ")
                                if fname and fname not in attachments:
                                    attachments.append(fname)

                elif seq_id in parsed_large:
                    # Large email processing: Parse headers + structures
                    large_data = parsed_large[seq_id]
                    header_bytes = large_data["header_bytes"]
                    structure_str = large_data["structure_str"]
                    
                    msg_obj = email.message_from_bytes(header_bytes)
                    subject_header = msg_obj.get("Subject", "")
                    subject_decoded = decode_header(subject_header)[0]
                    subject = subject_decoded[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(subject_decoded[1] or "utf-8", errors="ignore")
                        
                    from_val = msg_obj.get("From")
                    to_val = msg_obj.get("To")
                    date_val = msg_obj.get("Date")

                    # Extract filenames from BODYSTRUCTURE representation
                    found_filenames = re.findall(r'"filename"\s+"([^"]+)"', structure_str, re.IGNORECASE)
                    for fn in found_filenames:
                        decoded_parts = decode_header(fn)
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

                # Skip email if parsing failed
                if not msg_obj:
                    continue

                # Secondary filter check using headers
                if is_social_or_promotional_email("", from_val, subject, msg_obj, is_gmail):
                    continue

                email_list.append(
                    {
                        "id": seq_id,
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

