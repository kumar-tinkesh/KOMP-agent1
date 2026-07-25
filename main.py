import sys
import os

# Ensure the root folder is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.main import main as run_app


def main():
    run_app()


if __name__ == "__main__":
    main()
