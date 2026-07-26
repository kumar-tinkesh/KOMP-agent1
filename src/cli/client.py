# pyrefly: ignore [missing-import]
import os
# pyrefly: ignore [missing-import]
# pyrefly: ignore [missing-import]
from src.Models.modelUtils import get_client_by_user_id
# pyrefly: ignore [missing-import]
from src.Security.security import decrypt_password, BLUE, GREEN, YELLOW, RED, BOLD, END, CYAN, MAGENTA
# pyrefly: ignore [missing-import]
from src.Security.securityUtils import Spinner
# pyrefly: ignore [missing-import]
from src.services import email_service



def client_dashboard(conn, session):
    """
    Client dashboard main menu.
    """
    user_id = session["user_id"]
    client = get_client_by_user_id(conn, user_id)
    if not client:
        print(f"\n{RED}Error: Client profile not found in database.{END}")
        return

    while True:
        print(f"\n{BOLD}{CYAN}=== CLIENT DASHBOARD ==={END}")
        print(f"Welcome, {BOLD}{client['name']}{END} ({client['email']})\n")
        print("1. List Latest Emails")
        print("2. View Connection Settings")
        print("3. Log Out")

        choice = input("\nEnter choice (1-3): ").strip()

        if choice == "1":
            # Refresh client data in case it changed
            client = get_client_by_user_id(conn, user_id)
            list_emails_flow(client)
        elif choice == "2":
            # Refresh client data in case it changed
            client = get_client_by_user_id(conn, user_id)
            view_settings_flow(client)
        elif choice == "3":
            print(f"\n{GREEN}Logged out from Client Dashboard.{END}")
            break
        else:
            print(f"\n{RED}Invalid choice. Please choose a number between 1 and 3.{END}")


def list_emails_flow(client):
    """
    Prompts client for a retrieval limit, decrypts stored app credentials,
    and runs the email fetching process in a threaded terminal loader spinner.
    """
    print(f"\n{BOLD}{MAGENTA}--- Fetch Latest Emails ---{END}")
    
    print("Filter options:")
    print("  1. All Emails")
    print("  2. Unread Emails Only")
    print("  3. Read Emails Only")
    filter_choice = input("Enter filter choice (1-3) [Default: 1]: ").strip()
    
    status_filter = "ALL"
    if filter_choice == "2":
        status_filter = "UNSEEN"
    elif filter_choice == "3":
        status_filter = "SEEN"
    elif filter_choice and filter_choice != "1":
        print(f"{RED}Invalid filter choice. Defaulting to 'All Emails'.{END}")

    limit_input = input("How many emails to retrieve? [Default: 5]: ").strip()
    limit = 5
    if limit_input:
        try:
            limit = int(limit_input)
            if limit <= 0:
                print(f"{RED}Error: Retrieval limit must be a positive integer.{END}")
                return
        except ValueError:
            print(f"{RED}Error: Retrieval limit must be a valid integer.{END}")
            return

    # Decrypt app password
    try:
        decrypted_password = decrypt_password(client["app_password"])
    except Exception as e:
        print(f"{RED}Error: Failed to decrypt app password. Contact Super Admin to reset credentials. ({e}){END}")
        return

    emails = []
    error_msg = None

    # Fetch email headers inside the loading spinner
    with Spinner("Connecting to IMAP server and downloading headers..."):
        try:
            emails = email_service.list_latest_emails(
                host=client["imap_host"],
                username=client["email"],
                password=decrypted_password,
                mailbox=client["mailbox"],
                limit=limit,
                status_filter=status_filter
            )
        except Exception as e:
            error_msg = str(e)

    if error_msg:
        print(f"\n{RED}❌ Connection Error: {error_msg}{END}")
        return

    if not emails:
        print(f"\n{YELLOW}No emails found in mailbox '{client['mailbox']}' matching filter '{status_filter}'.{END}")
        return

    print(f"\n{GREEN}✔ Latest {len(emails)} emails from mailbox '{client['mailbox']}' (Filter: {status_filter}):{END}\n")
    
    for idx, mail in enumerate(emails, 1):
        print(f"{BLUE}{'=' * 60}{END}")
        print(f"{BOLD}[#{idx}] Message ID:{END} {mail['id']}")
        status_color = f"{GREEN}{BOLD}" if mail["status"] == "Unread" else f"{YELLOW}"
        print(f"{BOLD}Status      :{END} {status_color}{mail['status'].upper()}{END}")
        print(f"{BOLD}From        :{END} {mail['from']}")
        print(f"{BOLD}To          :{END} {mail['to']}")
        print(f"{BOLD}Subject     :{END} {CYAN}{mail['subject']}{END}")
        print(f"{BOLD}Date        :{END} {mail['date']}")
        print(f"{BOLD}Has Attachment:{END} {mail.get('has_attachment', False)}")
        print(f"{BOLD}Attachment Count:{END} {mail.get('attachment_count', 0)}")
        if mail.get('has_attachment', False):
            names_str = ", ".join(mail.get('attachment_names', []))
            print(f"{BOLD}Attachment Names:{END} {YELLOW}{names_str}{END}")
        
    print(f"{BLUE}{'=' * 60}{END}")

    has_any_attachments = any(mail.get("has_attachment", False) for mail in emails)
    if not has_any_attachments:
        return

    download_choice = input("\nWould you like to download and extract attachments from one of these emails? (y/N): ").strip().lower()
    if download_choice != "y":
        return

    idx_input = input(f"Enter the email number (1-{len(emails)}): ").strip()
    if not idx_input:
        return
    try:
        email_idx = int(idx_input) - 1
        if email_idx < 0 or email_idx >= len(emails):
            print(f"{RED}Error: Email number must be between 1 and {len(emails)}.{END}")
            return
    except ValueError:
        print(f"{RED}Error: Invalid number.{END}")
        return

    selected_email = emails[email_idx]
    if not selected_email.get("has_attachment", False):
        print(f"{RED}Error: Selected email does not have any attachments.{END}")
        return

    print(f"\n{BOLD}Selected Email:{END} {CYAN}{selected_email['subject']}{END}")
    print("Choose action for attachments:")
    print("  1. Save attachments to disk")
    print("  2. View/Read extracted text content in terminal")
    print("  3. Both (Save and View)")
    action_choice = input("Enter choice (1-3) [Default: 3]: ").strip()
    if not action_choice:
        action_choice = "3"
    
    if action_choice not in ("1", "2", "3"):
        print(f"{RED}Invalid choice. Defaulting to '3' (Both).{END}")
        action_choice = "3"

    dest_dir = None
    temp_dir_obj = None

    if action_choice in ("1", "3"):
        default_dir = os.path.join(os.getcwd(), "downloads")
        dest_dir = input(f"Enter download directory [Default: {default_dir}]: ").strip()
        if not dest_dir:
            dest_dir = default_dir
    else:
        import tempfile
        temp_dir_obj = tempfile.TemporaryDirectory()
        dest_dir = temp_dir_obj.name

    # Decrypt app password
    try:
        decrypted_password = decrypt_password(client["app_password"])
    except Exception as e:
        print(f"{RED}Error: Failed to decrypt app password. Contact Super Admin to reset credentials. ({e}){END}")
        if temp_dir_obj:
            temp_dir_obj.cleanup()
        return

    downloaded_files = []
    error_msg = None

    with Spinner("Processing attachments..."):
        try:
            downloaded_files = email_service.download_email_attachments(
                host=client["imap_host"],
                username=client["email"],
                password=decrypted_password,
                msg_id=selected_email["id"],
                download_dir=dest_dir,
                mailbox=client["mailbox"]
            )
        except Exception as e:
            error_msg = str(e)

    if temp_dir_obj:
        # Resolve permanent path to not saved indicator
        for item in downloaded_files:
            item["saved_path"] = "[Not saved - View Only mode]"
        temp_dir_obj.cleanup()

    if error_msg:
        print(f"\n{RED}❌ Processing Error: {error_msg}{END}")
        return

    if not downloaded_files:
        print(f"\n{YELLOW}No attachments were successfully processed.{END}")
        return

    if action_choice in ("1", "3"):
        print(f"\n{GREEN}✔ Successfully processed {len(downloaded_files)} attachment(s):{END}\n")
    else:
        print(f"\n{GREEN}✔ Extracted {len(downloaded_files)} attachment(s) in View Only mode:{END}\n")

    for item in downloaded_files:
        print(f"{BLUE}{'-' * 60}{END}")
        print(f"{BOLD}File Name : {END}{GREEN}{item['filename']}{END}")
        if action_choice in ("1", "3"):
            print(f"{BOLD}Saved To  : {END}{item['saved_path']}")
        
        text_content = item.get("text_content", "")
        if action_choice in ("2", "3"):
            if text_content and not text_content.startswith("[Error:") and not text_content.startswith("[Content extraction not supported"):
                limit = 750
                preview = text_content[:limit]
                print(f"{BOLD}Content   :{END}\n{CYAN}{preview}{END}")
                if len(text_content) > limit:
                    print(f"\n{YELLOW}... [Truncated, total characters: {len(text_content)}]{END}")
            else:
                print(f"{BOLD}Content   : {END}{YELLOW}{text_content}{END}")
    print(f"{BLUE}{'-' * 60}{END}\n")


def view_settings_flow(client):
    """
    Displays current client settings (with app password hidden).
    """
    print(f"\n{BOLD}{MAGENTA}--- IMAP Connection Settings ---{END}")
    print(f"{BOLD}Client Name  : {END}{client['name']}")
    print(f"{BOLD}Email Address: {END}{client['email']}")
    print(f"{BOLD}IMAP Host    : {END}{client['imap_host']}")
    print(f"{BOLD}IMAP Port    : {END}{client['imap_port']}")
    print(f"{BOLD}Mailbox      : {END}{client['mailbox']}")
    print(f"{BOLD}App Password : {END}{YELLOW}[ENCRYPTED & MASKED]{END}")
