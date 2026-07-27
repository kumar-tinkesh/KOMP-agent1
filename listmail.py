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

        is_gmail = "gmail.com" in host.lower()
        metadata_query = "(FLAGS RFC822.SIZE X-GM-LABELS)" if is_gmail else "(FLAGS RFC822.SIZE)"

        # 1. Bulk fetch metadata
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

        # 2. Select up to `limit` active emails
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

        # 5. Bulk fetch large email headers
        parsed_large = {}
        if large_emails:
            large_ids = b",".join([e["id_bytes"] for e in large_emails])
            status, large_resp = mail.fetch(large_ids, "(BODY[HEADER.FIELDS (FROM TO SUBJECT DATE)])")
            if status == "OK" and large_resp:
                for item in large_resp:
                    if isinstance(item, tuple):
                        meta_str = item[0].decode('utf-8', errors='ignore')
                        header_bytes = item[1]
                        match_id = re.match(r'^(\d+)\s+', meta_str)
                        if match_id:
                            seq_id = match_id.group(1)
                            parsed_large[seq_id] = header_bytes

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

            try:
                if seq_id in parsed_small:
                    msg_obj = email.message_from_bytes(parsed_small[seq_id])
                elif seq_id in parsed_large:
                    msg_obj = email.message_from_bytes(parsed_large[seq_id])

                if not msg_obj:
                    continue

                subject_header = msg_obj.get("Subject", "")
                subject_decoded = decode_header(subject_header)[0]
                subject = subject_decoded[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(subject_decoded[1] or "utf-8", errors="ignore")
                
                from_val = msg_obj.get("From")
                to_val = msg_obj.get("To")
                date_val = msg_obj.get("Date")

                # Secondary filter check
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