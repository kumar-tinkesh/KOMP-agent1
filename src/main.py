import sys
import os

# Ensure the parent directory is in sys.path so 'from src import ...' works
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import getpass
from src import database, models, auth
from src.cli.admin import admin_dashboard
from src.cli.client import client_dashboard
from src.security import BOLD, GREEN, YELLOW, RED, END, CYAN


def login_flow(conn):
    """
    Collects credentials and authenticates user, returning a session if successful.
    """
    print(f"\n{BOLD}{CYAN}--- USER LOG IN ---{END}")
    username = input("Username: ").strip()
    if not username:
        print(f"{RED}Error: Username cannot be blank.{END}")
        return None

    password = getpass.getpass("Password: ").strip()
    if not password:
        print(f"{RED}Error: Password cannot be blank.{END}")
        return None

    try:
        session = auth.authenticate_user(conn, username, password)
        if session:
            print(f"\n{GREEN}✔ Login successful! Welcoming {session['username']}.{END}")
            return session
        else:
            print(f"\n{RED}❌ Error: Invalid username or password.{END}")
            return None
    except auth.AccountDisabledError as e:
        print(f"\n{RED}❌ {e}{END}")
        return None
    except Exception as e:
        print(f"\n{RED}❌ System authentication error: {e}{END}")
        return None


def main():
    """
    Core runtime bootstrap and primary CLI interface loop.
    """
    # 1. Initialize SQLite Database schemas
    try:
        database.init_db()
    except Exception as e:
        print(f"{RED}CRITICAL: Database initialization failed: {e}{END}")
        sys.exit(1)

    # 2. Connect to the database
    conn = database.get_db_connection()

    try:
        # 3. Setup is handled by database initialization seeding.

        # 4. Main application menu loop
        while True:
            print(f"\n{BOLD}{CYAN}=================================================={END}")
            print(f"{BOLD}{CYAN}      MULTI-TENANT IMAP EMAIL MANAGER (CLI)       {END}")
            print(f"{BOLD}{CYAN}=================================================={END}")
            print("1. Log In")
            print("2. Exit")

            choice = input("\nEnter choice (1-2): ").strip()

            if choice == "1":
                session = login_flow(conn)
                if session:
                    # Route based on user roles
                    if session["role"] == "admin":
                        admin_dashboard(conn, session)
                    elif session["role"] == "client":
                        client_dashboard(conn, session)
            elif choice == "2":
                print(f"\n{GREEN}Thank you for using Multi-Tenant IMAP Email Manager. Goodbye!{END}")
                break
            else:
                print(f"\n{RED}Invalid choice. Please enter 1 or 2.{END}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
