import imaplib
import email
from email.header import decode_header


class IMAPConnectionError(Exception):
    """Raised when connecting to the IMAP server fails."""
    pass


class IMAPAuthenticationError(Exception):
    """Raised when logging in to the IMAP server fails."""
    pass


class IMAPMailboxError(Exception):
    """Raised when selecting or reading from the mailbox fails."""
    pass


def list_latest_emails(host, username, password, mailbox="INBOX", limit=5):
    """
    Connects to an IMAP server and retrieves the latest emails.

    Args:
        host: IMAP server address
        username: Email address
        password: App password (plaintext decrypted)
        mailbox: Mailbox name
        limit: Number of emails to fetch

    Returns:
        List[dict]: Details of retrieved emails.
    """
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

        status, messages = mail.search(None, "ALL")
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
                status, msg_data = mail.fetch(msg_id, "(RFC822)")
                if status != "OK" or not msg_data or not msg_data[0]:
                    continue

                msg = email.message_from_bytes(msg_data[0][1])

                subject_header = msg.get("Subject", "")
                subject_decoded = decode_header(subject_header)[0]
                subject = subject_decoded[0]

                if isinstance(subject, bytes):
                    subject = subject.decode(
                        subject_decoded[1] or "utf-8",
                        errors="ignore"
                    )

                email_list.append(
                    {
                        "id": msg_id.decode("utf-8", errors="ignore"),
                        "subject": subject,
                        "from": msg.get("From"),
                        "to": msg.get("To"),
                        "date": msg.get("Date"),
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
