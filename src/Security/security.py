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

ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

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