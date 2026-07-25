import os
import imaplib
import email
from email.header import decode_header
from dotenv import load_dotenv


load_dotenv()


def list_latest_emails(host, username, password, mailbox="INBOX", limit=5):
    """
    Connect to an IMAP server and list latest emails.

    Args:
        host: IMAP server address
        username: Email address
        password: App password
        mailbox: Mailbox name
        limit: Number of emails to fetch

    Returns:
        List[dict]: Email details
    """

    mail = imaplib.IMAP4_SSL(host)

    try:
        mail.login(username, password)

        status, _ = mail.select(mailbox)
        if status != "OK":
            raise Exception(f"Unable to open mailbox: {mailbox}")

        status, messages = mail.search(None, "ALL")
        if status != "OK":
            raise Exception("Failed to search mailbox.")

        # Get latest emails only
        email_ids = messages[0].split()
        email_ids = email_ids[-limit:]
        email_ids.reverse()  # newest first

        email_list = []

        for msg_id in email_ids:
            status, msg_data = mail.fetch(msg_id, "(RFC822)")

            if status != "OK":
                continue

            msg = email.message_from_bytes(msg_data[0][1])

            subject_data = decode_header(msg.get("Subject", ""))[0]
            subject = subject_data[0]

            if isinstance(subject, bytes):
                subject = subject.decode(
                    subject_data[1] or "utf-8",
                    errors="ignore"
                )

            email_list.append(
                {
                    "id": msg_id.decode(),
                    "subject": subject,
                    "from": msg.get("From"),
                    "to": msg.get("To"),
                    "date": msg.get("Date"),
                }
            )

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

    if not host or not username or not password:
        raise ValueError(
            "Missing IMAP_HOST, EMAIL, or APP_PASSWORD in .env"
        )

    emails = list_latest_emails(
        host=host,
        username=username,
        password=password,
        mailbox=mailbox,
        limit=5
    )

    print(f"Latest {len(emails)} emails:\n")

    for mail in emails:
        print("=" * 80)
        print(f"ID      : {mail['id']}")
        print(f"From    : {mail['from']}")
        print(f"To      : {mail['to']}")
        print(f"Subject : {mail['subject']}")
        print(f"Date    : {mail['date']}")


if __name__ == "__main__":
    main()