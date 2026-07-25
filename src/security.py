import os
import sys
import time
import hashlib
import threading
from cryptography.fernet import Fernet
from dotenv import load_dotenv

# Define terminal colors for rich aesthetic
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
END = "\033[0m"

ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Make sure env is loaded
load_dotenv(ENV_PATH)


# --- Cryptography Helpers ---

def get_or_create_key():
    """
    Retrieves the encryption key from .env or generates it if not present.
    """
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        # Generate new Fernet key
        key_bytes = Fernet.generate_key()
        key = key_bytes.decode()
        
        # Write/append to .env
        if os.path.exists(ENV_PATH):
            with open(ENV_PATH, "r") as f:
                content = f.read()
            if "ENCRYPTION_KEY=" not in content:
                # Add newline if needed
                suffix = "\n" if not content.endswith("\n") else ""
                with open(ENV_PATH, "a") as f:
                    f.write(f"{suffix}ENCRYPTION_KEY={key}\n")
        else:
            with open(ENV_PATH, "w") as f:
                f.write(f"ENCRYPTION_KEY={key}\n")
                
        # Set in current environment
        os.environ["ENCRYPTION_KEY"] = key
        
    return key.encode()


def encrypt_password(password: str) -> str:
    """
    Encrypts a plaintext password using Fernet encryption.
    """
    key = get_or_create_key()
    f = Fernet(key)
    return f.encrypt(password.encode("utf-8")).decode("utf-8")


def decrypt_password(encrypted_password: str) -> str:
    """
    Decrypts a Fernet encrypted password.
    """
    key = get_or_create_key()
    f = Fernet(key)
    return f.decrypt(encrypted_password.encode("utf-8")).decode("utf-8")


# --- Password Hashing Helpers ---

def hash_password(password: str) -> str:
    """
    Hashes a password using PBKDF2-HMAC-SHA256 with a unique salt.
    Returns string representation 'salt_hex:hash_hex'
    """
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        100000
    )
    return f"{salt.hex()}:{key.hex()}"


def verify_password(stored_password_hash: str, password: str) -> bool:
    """
    Verifies an entered password against the stored pbkdf2 hash.
    """
    try:
        salt_hex, key_hex = stored_password_hash.split(":")
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(key_hex)
        
        actual_key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            100000
        )
        return actual_key == expected_key
    except (ValueError, TypeError):
        return False


# --- UI Helpers: Loading Spinner ---

class Spinner:
    """
    A terminal loader spinner running on a background thread.
    Usage:
        with Spinner("Fetching data..."):
            # perform network task
    """
    def __init__(self, message="Working..."):
        self.message = message
        self.spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.stop_running = threading.Event()
        self.thread = None

    def _spin(self):
        idx = 0
        while not self.stop_running.is_set():
            sys.stdout.write(f"\r{YELLOW}{self.spinner_chars[idx]} {self.message}{END}")
            sys.stdout.flush()
            idx = (idx + 1) % len(self.spinner_chars)
            time.sleep(0.08)
        sys.stdout.write("\r\033[K")  # Clear the line
        sys.stdout.flush()

    def __enter__(self):
        self.stop_running.clear()
        self.thread = threading.Thread(target=self._spin)
        self.thread.daemon = True
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_running.set()
        if self.thread:
            self.thread.join()


# --- UI Helpers: Formatted Table Printer ---

def print_table(headers, rows):
    """
    Outputs query results in a beautifully styled ASCII/ANSI CLI table.
    """
    if not rows:
        print(f"\n{YELLOW}[No records found]{END}\n")
        return
    
    # Force elements to string
    str_headers = [str(h) for h in headers]
    str_rows = [[str(item) for item in row] for row in rows]
    
    # Calculate column widths
    widths = [len(h) for h in str_headers]
    for row in str_rows:
        for idx, val in enumerate(row):
            widths[idx] = max(widths[idx], len(val))
            
    # Box styles
    h_border = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    
    # Print headers with color
    print(f"\n{BLUE}{h_border}{END}")
    header_str = "|" + "|".join(f" {BOLD}{str_headers[i].ljust(widths[i])}{END} " for i in range(len(str_headers))) + "|"
    print(header_str)
    print(f"{BLUE}{h_border}{END}")
    
    # Print data rows
    for row in str_rows:
        row_str = "|" + "|".join(f" {row[i].ljust(widths[i])} " for i in range(len(row))) + "|"
        print(row_str)
        
    print(f"{BLUE}{h_border}{END}\n")
