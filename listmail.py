import os
import imaplib
import email
import re
from email.header import decode_header
from dotenv import load_dotenv
# pyrefly: ignore [missing-import]
from src.services.email_service_utils import is_social_or_promotional_email


load_dotenv()


def list_latest_emails(host, username, password, mailbox="INBOX", limit=5, status_filter="ALL"):
    """
    Connect to an IMAP server and list latest emails.
    Optimized for high performance by fetching metadata first, and filtering social/promo emails.
    """
    if status_filter not in ("ALL", "UNSEEN", "SEEN"):
        status_filter = "ALL"

    mail = imaplib.IMAP4_SSL(host)

    try:
        mail.login(username, password)

        status, _ = mail.select(mailbox)
        if status != "OK":
            raise Exception(f"Unable to open mailbox: {mailbox}")

        status, messages = mail.search(None, status_filter)
        if status != "OK":
            raise Exception("Failed to search mailbox.")

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

                subject = ""
                from_val = ""
                to_val = ""
                date_val = ""
                msg_obj = None

                # 2. Decide fetch strategy based on email size
                if email_size > 0 and email_size < 150000:
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
                
                else:
                    # Large email: Fetch only headers to keep it fast
                    status, msg_data = mail.fetch(msg_id, "(BODY[HEADER.FIELDS (FROM TO SUBJECT DATE)])")
                    if status != "OK" or not msg_data or not msg_data[0]:
                        continue
                    
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

                # 3. Apply header-based social and promotional filtering
                if is_social_or_promotional_email("", from_val, subject, msg_obj, is_gmail):
                    continue  # Skip social and promotional messages!

                email_list.append(
                    {
                        "id": msg_id.decode(),
                        "subject": subject,
                        "from": from_val,
                        "to": to_val,
                        "date": date_val,
                        "status": "Read" if is_read else "Unread",
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


def main():
    host = os.getenv("IMAP_HOST")
    username = os.getenv("EMAIL")
    password = os.getenv("APP_PASSWORD")
    mailbox = os.getenv("MAILBOX", "INBOX")
    status_filter = os.getenv("STATUS_FILTER", "ALL")

    if not host or not username or not password:
        raise ValueError(
            "Missing IMAP_HOST, EMAIL, or APP_PASSWORD in .env"
        )

    emails = list_latest_emails(
        host=host,
        username=username,
        password=password,
        mailbox=mailbox,
        limit=5,
        status_filter=status_filter
    )

    print(f"Latest {len(emails)} emails (Filter: {status_filter}):\n")

    for mail in emails:
        print("=" * 80)
        print(f"ID      : {mail['id']}")
        print(f"Status  : {mail['status'].upper()}")
        print(f"From    : {mail['from']}")
        print(f"To      : {mail['to']}")
        print(f"Subject : {mail['subject']}")
        print(f"Date    : {mail['date']}")


if __name__ == "__main__":
    main()