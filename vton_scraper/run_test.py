"""
Quick runner script for testing the VTON scraper
"""

import sys
from pathlib import Path

def main():
    print("="*80)
    print("VTON SCRAPER - QUICK TEST")
    print("="*80)
    print("\nChoose test mode:")
    print("1. Test scraper (Zalando + Amazon, 3 items each)")
    print("2. Advanced scraper (Zalando only, 5 items)")
    print("3. Exit")

    choice = input("\nEnter choice (1-3): ").strip()

    if choice == "1":
        print("\n[INFO] Running test scraper...")
        from vton_scraper_test import main as test_main
        test_main()

    elif choice == "2":
        print("\n[INFO] Running advanced scraper...")
        from advanced_scraper import main as advanced_main
        advanced_main()

    elif choice == "3":
        print("Exiting...")
        sys.exit(0)

    else:
        print("[ERROR] Invalid choice")


if __name__ == "__main__":
    main()
