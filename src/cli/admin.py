import getpass
# pyrefly: ignore [missing-import]
from src.services import client_service
# pyrefly: ignore [missing-import]
from src.Security.security import BLUE, GREEN, YELLOW, RED, BOLD, END, CYAN, MAGENTA
# pyrefly: ignore [missing-import]
from src.Security.securityUtils import print_table


def admin_dashboard(conn, session):
    """
    Super Admin main menu loop.
    """
    while True:
        print(f"\n{BOLD}{CYAN}=== SUPER ADMIN DASHBOARD ==={END}")
        print(f"Logged in as: {BOLD}{session['username']}{END}\n")
        print("1. Create Client")
        print("2. List Clients")
        print("3. Update Client")
        print("4. Delete Client")
        print("5. Log Out")

        choice = input("\nEnter choice (1-5): ").strip()

        if choice == "1":
            create_client_flow(conn)
        elif choice == "2":
            list_clients_flow(conn)
        elif choice == "3":
            update_client_flow(conn)
        elif choice == "4":
            delete_client_flow(conn)
        elif choice == "5":
            print(f"\n{GREEN}Logged out from Admin Dashboard.{END}")
            break
        else:
            print(f"\n{RED}Invalid choice. Please choose a number between 1 and 5.{END}")


def create_client_flow(conn):
    """
    Interactive prompt sequence to register a new client user and configuration.
    """
    print(f"\n{BOLD}{MAGENTA}--- Create New Client ---{END}")
    
    username = input("Enter Login Username: ").strip()
    if not username:
        print(f"{RED}Error: Username cannot be blank.{END}")
        return

    password = getpass.getpass("Enter Login Password: ").strip()
    if not password:
        print(f"{RED}Error: Password cannot be blank.{END}")
        return

    name = input("Enter Client Name: ").strip()
    if not name:
        print(f"{RED}Error: Client name cannot be blank.{END}")
        return

    email = input("Enter Client Email: ").strip()
    if not email:
        print(f"{RED}Error: Email cannot be blank.{END}")
        return

    imap_host = input("Enter IMAP Host (e.g. imap.gmail.com): ").strip()
    if not imap_host:
        print(f"{RED}Error: IMAP host cannot be blank.{END}")
        return

    imap_port_input = input("Enter IMAP Port [Default: 993]: ").strip()
    imap_port = 993
    if imap_port_input:
        try:
            imap_port = int(imap_port_input)
        except ValueError:
            print(f"{RED}Error: Port must be a valid integer.{END}")
            return

    app_password = getpass.getpass("Enter IMAP App Password: ").strip()
    if not app_password:
        print(f"{RED}Error: App password cannot be blank.{END}")
        return

    mailbox = input("Enter Mailbox [Default: INBOX]: ").strip()
    if not mailbox:
        mailbox = "INBOX"

    try:
        client_service.add_client(
            conn,
            username=username,
            password=password,
            name=name,
            email=email,
            imap_host=imap_host,
            app_password=app_password,
            imap_port=imap_port,
            mailbox=mailbox
        )
        print(f"\n{GREEN}✔ Client '{name}' and login user '{username}' created successfully!{END}")
    except ValueError as e:
        print(f"\n{RED}❌ Error: {e}{END}")
    except Exception as e:
        print(f"\n{RED}❌ Database error occurred: {e}{END}")


def list_clients_flow(conn):
    """
    Displays a formatted database table of all clients in the system.
    """
    print(f"\n{BOLD}{MAGENTA}--- Registered Clients ---{END}")
    clients = client_service.get_clients(conn)
    if not clients:
        print(f"{YELLOW}[No clients registered in the system]{END}")
        return

    headers = ["ID", "Username", "Name", "Email", "IMAP Host", "IMAP Port", "Mailbox", "Status"]
    rows = []
    for c in clients:
        status = f"{GREEN}Active{END}" if c["is_active"] else f"{RED}Inactive{END}"
        rows.append([
            c["client_id"],
            c["username"],
            c["name"],
            c["email"],
            c["imap_host"],
            c["imap_port"],
            c["mailbox"],
            status
        ])
    print_table(headers, rows)


def update_client_flow(conn):
    """
    Prompts Super Admin to modify specific client settings.
    """
    print(f"\n{BOLD}{MAGENTA}--- Update Client Profile ---{END}")
    client_id_input = input("Enter Client ID to update: ").strip()
    if not client_id_input:
        return

    try:
        client_id = int(client_id_input)
    except ValueError:
        print(f"{RED}Error: Client ID must be an integer.{END}")
        return

    client = client_service.get_client_details_by_id(conn, client_id)
    if not client:
        print(f"{RED}Error: Client with ID {client_id} not found.{END}")
        return

    print(f"\n{YELLOW}Updating details for client '{client['name']}' (Username: {client['username']}).{END}")
    print("Press [Enter] on any field to keep its current value.\n")

    username = input(f"New Username [Current: {client['username']}]: ").strip() or None
    password = getpass.getpass("New Login Password [Leave blank to keep current]: ").strip() or None
    name = input(f"New Name [Current: {client['name']}]: ").strip() or None
    email = input(f"New Email [Current: {client['email']}]: ").strip() or None
    imap_host = input(f"New IMAP Host [Current: {client['imap_host']}]: ").strip() or None

    imap_port_input = input(f"New IMAP Port [Current: {client['imap_port']}]: ").strip()
    imap_port = None
    if imap_port_input:
        try:
            imap_port = int(imap_port_input)
        except ValueError:
            print(f"{RED}Error: Port must be an integer.{END}")
            return

    app_password = getpass.getpass("New IMAP App Password [Leave blank to keep current]: ").strip() or None
    mailbox = input(f"New Mailbox [Current: {client['mailbox']}]: ").strip() or None

    status_input = input(
        f"Status (active/inactive) [Current: {'active' if client['is_active'] else 'inactive'}]: "
    ).strip().lower()
    
    is_active = None
    if status_input:
        if status_input == "active":
            is_active = 1
        elif status_input == "inactive":
            is_active = 0
        else:
            print(f"{RED}Error: Status must be either 'active' or 'inactive'.{END}")
            return

    # Package updates
    updates = {}
    if username:
        updates["username"] = username
    if password:
        updates["password"] = password
    if name:
        updates["name"] = name
    if email:
        updates["email"] = email
    if imap_host:
        updates["imap_host"] = imap_host
    if imap_port is not None:
        updates["imap_port"] = imap_port
    if app_password:
        updates["app_password"] = app_password
    if mailbox:
        updates["mailbox"] = mailbox
    if is_active is not None:
        updates["is_active"] = is_active

    if not updates:
        print(f"\n{YELLOW}No updates entered. Profile remains unchanged.{END}")
        return

    try:
        client_service.update_client_profile(conn, client_id, **updates)
        print(f"\n{GREEN}✔ Client profile updated successfully!{END}")
    except ValueError as e:
        print(f"\n{RED}❌ Error: {e}{END}")
    except Exception as e:
        print(f"\n{RED}❌ Database error: {e}{END}")


def delete_client_flow(conn):
    """
    Deletes client user profile and configuration settings.
    """
    print(f"\n{BOLD}{RED}--- Delete Client Account ---{END}")
    client_id_input = input("Enter Client ID to delete: ").strip()
    if not client_id_input:
        return

    try:
        client_id = int(client_id_input)
    except ValueError:
        print(f"{RED}Error: Client ID must be an integer.{END}")
        return

    client = client_service.get_client_details_by_id(conn, client_id)
    if not client:
        print(f"{RED}Error: Client with ID {client_id} not found.{END}")
        return

    # Double confirm high-risk action
    confirm = input(
        f"\n{RED}{BOLD}WARNING:{END}{YELLOW} Are you sure you want to permanently delete the client '{client['name']}'? "
        f"This deletes their login account and all stored IMAP configurations. (y/N): "
    ).strip().lower()
    
    if confirm != "y":
        print("Deletion cancelled.")
        return

    try:
        client_service.delete_client_profile(conn, client_id)
        print(f"\n{GREEN}✔ Client '{client['name']}' deleted successfully.{END}")
    except Exception as e:
        print(f"\n{RED}❌ Error: {e}{END}")
