from src.models import get_client_by_user_id
from src.security import decrypt_password, Spinner, BLUE, GREEN, YELLOW, RED, BOLD, END, CYAN, MAGENTA
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
                limit=limit
            )
        except Exception as e:
            error_msg = str(e)

    if error_msg:
        print(f"\n{RED}❌ Connection Error: {error_msg}{END}")
        return

    if not emails:
        print(f"\n{YELLOW}No emails found in mailbox '{client['mailbox']}'.{END}")
        return

    print(f"\n{GREEN}✔ Latest {len(emails)} emails from mailbox '{client['mailbox']}':{END}\n")
    
    for idx, mail in enumerate(emails, 1):
        print(f"{BLUE}{'=' * 60}{END}")
        print(f"{BOLD}[#{idx}] Message ID:{END} {mail['id']}")
        print(f"{BOLD}From        :{END} {mail['from']}")
        print(f"{BOLD}To          :{END} {mail['to']}")
        print(f"{BOLD}Subject     :{END} {CYAN}{mail['subject']}{END}")
        print(f"{BOLD}Date        :{END} {mail['date']}")
        
    print(f"{BLUE}{'=' * 60}{END}")


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
