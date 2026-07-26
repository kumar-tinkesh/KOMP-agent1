import sys
import time
import threading
# pyrefly: ignore [missing-import]
from src.Security.security import BLUE, YELLOW, BOLD, END

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
