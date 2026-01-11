"""
Advanced VTON Dataset Scraper with Rate Limiting, Proxy Support, and Error Recovery
"""

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import requests
import os
import json
from pathlib import Path
from urllib.parse import urljoin, urlparse
import random
from PIL import Image
from io import BytesIO
import threading
from datetime import datetime, timedelta
from config import *


class RateLimiter:
    """Rate limiter to control request frequency"""
    def __init__(self, requests_per_minute):
        self.requests_per_minute = requests_per_minute
        self.min_interval = 60.0 / requests_per_minute
        self.last_request = 0
        self.lock = threading.Lock()

    def wait(self):
        """Wait if necessary to respect rate limit"""
        with self.lock:
            elapsed = time.time() - self.last_request
            if elapsed < self.min_interval:
                sleep_time = self.min_interval - elapsed
                time.sleep(sleep_time)
            self.last_request = time.time()


class ProxyManager:
    """Manage proxy rotation"""
    def __init__(self, proxy_list):
        self.proxy_list = proxy_list
        self.current_index = 0
        self.request_count = 0
        self.rotate_after = PROXY_CONFIG["rotate_after"]

    def get_proxy(self):
        """Get current proxy"""
        if not self.proxy_list:
            return None
        return self.proxy_list[self.current_index]

    def rotate(self):
        """Rotate to next proxy"""
        if self.proxy_list:
            self.current_index = (self.current_index + 1) % len(self.proxy_list)
            self.request_count = 0
            print(f"[PROXY] Rotated to proxy {self.current_index + 1}/{len(self.proxy_list)}")

    def increment(self):
        """Increment request count and rotate if needed"""
        self.request_count += 1
        if self.request_count >= self.rotate_after:
            self.rotate()


class AdvancedVTONScraper:
    def __init__(self, output_dir=None):
        self.output_dir = Path(output_dir or SCRAPING_CONFIG["output_dir"])
        self.output_dir.mkdir(exist_ok=True)

        # Create subdirectories
        (self.output_dir / "cloth_images").mkdir(exist_ok=True)
        (self.output_dir / "model_images").mkdir(exist_ok=True)
        (self.output_dir / "metadata").mkdir(exist_ok=True)
        (self.output_dir / "progress").mkdir(exist_ok=True)

        self.driver = None
        self.items_scraped = 0
        self.session = requests.Session()

        # Initialize rate limiter
        if RATE_LIMIT_CONFIG["enabled"]:
            self.rate_limiter = RateLimiter(RATE_LIMIT_CONFIG["requests_per_minute"])
        else:
            self.rate_limiter = None

        # Initialize proxy manager
        if PROXY_CONFIG["enabled"]:
            self.proxy_manager = ProxyManager(PROXY_CONFIG["proxy_list"])
        else:
            self.proxy_manager = None

        # Load progress
        self.progress = self.load_progress()
        self.items_scraped = self.progress.get("items_scraped", 0)

        # Statistics
        self.stats = {
            "total_items": 0,
            "successful": 0,
            "failed": 0,
            "errors": [],
            "start_time": datetime.now().isoformat()
        }

    def get_random_user_agent(self):
        """Get random user agent"""
        return random.choice(USER_AGENTS)

    def init_driver(self, headless=None):
        """Initialize undetected Chrome driver with advanced options"""
        if headless is None:
            headless = SCRAPING_CONFIG["headless"]

        options = uc.ChromeOptions()

        if headless:
            options.add_argument('--headless=new')

        # Anti-detection measures
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-web-security')
        options.add_argument('--disable-features=IsolateOrigins,site-per-process')

        # Random user agent
        user_agent = self.get_random_user_agent()
        options.add_argument(f'--user-agent={user_agent}')

        # Proxy support
        if self.proxy_manager:
            proxy = self.proxy_manager.get_proxy()
            if proxy:
                options.add_argument(f'--proxy-server={proxy}')

        # Performance optimizations
        prefs = {
            "profile.managed_default_content_settings.images": 1,  # Load images
            "profile.default_content_setting_values.notifications": 2,  # Block notifications
        }
        options.add_experimental_option("prefs", prefs)

        self.driver = uc.Chrome(options=options, version_main=None)
        self.driver.set_page_load_timeout(SCRAPING_CONFIG["timeout"])

        # Session headers
        self.session.headers.update({'User-Agent': user_agent})

        return self.driver

    def random_delay(self, min_seconds=None, max_seconds=None):
        """Add random delay to mimic human behavior"""
        if min_seconds is None:
            min_seconds = 2
        if max_seconds is None:
            max_seconds = 5

        time.sleep(random.uniform(min_seconds, max_seconds))

    def apply_rate_limit(self):
        """Apply rate limiting"""
        if self.rate_limiter:
            self.rate_limiter.wait()

    def download_image(self, url, filepath, validate=True):
        """Download and optionally validate image"""
        try:
            self.apply_rate_limit()

            response = self.session.get(url, timeout=15)
            if response.status_code == 200:
                # Validate image if requested
                if validate:
                    img = Image.open(BytesIO(response.content))
                    width, height = img.size

                    # Check minimum resolution
                    if (width < IMAGE_FILTERS["min_width"] or
                        height < IMAGE_FILTERS["min_height"]):
                        print(f"[SKIP] Image too small: {width}x{height}")
                        return False

                    # Check file size
                    size_mb = len(response.content) / (1024 * 1024)
                    if size_mb > IMAGE_FILTERS["max_file_size_mb"]:
                        print(f"[SKIP] Image too large: {size_mb:.2f}MB")
                        return False

                # Save image
                with open(filepath, 'wb') as f:
                    f.write(response.content)

                return True

        except Exception as e:
            print(f"[ERROR] Downloading {url}: {e}")
            self.stats["errors"].append({
                "type": "download_error",
                "url": url,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })

        return False

    def save_metadata(self, item_id, metadata):
        """Save metadata for each item"""
        filepath = self.output_dir / "metadata" / f"{item_id}.json"
        with open(filepath, 'w') as f:
            json.dump(metadata, f, indent=2)

    def save_progress(self):
        """Save scraping progress"""
        progress_file = self.output_dir / "progress" / "progress.json"
        progress_data = {
            "items_scraped": self.items_scraped,
            "last_updated": datetime.now().isoformat(),
            "stats": self.stats
        }
        with open(progress_file, 'w') as f:
            json.dump(progress_data, f, indent=2)

    def load_progress(self):
        """Load scraping progress"""
        progress_file = self.output_dir / "progress" / "progress.json"
        if progress_file.exists():
            with open(progress_file, 'r') as f:
                return json.load(f)
        return {}

    def handle_cookie_consent(self):
        """Handle cookie consent popups"""
        try:
            # Common cookie consent button texts
            button_texts = [
                "Accept", "Accept All", "Agree", "Allow All",
                "Akzeptieren", "Alle akzeptieren", "Accepter"
            ]

            for text in button_texts:
                try:
                    button = self.driver.find_element(
                        By.XPATH,
                        f"//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text.lower()}')]"
                    )
                    button.click()
                    print("[INFO] Cookie consent accepted")
                    self.random_delay(1, 2)
                    return
                except:
                    continue

        except Exception as e:
            pass

    def check_bot_detection(self):
        """Check if bot detection is present"""
        page_source = self.driver.page_source.lower()
        indicators = ["captcha", "robot check", "access denied", "forbidden"]

        for indicator in indicators:
            if indicator in page_source:
                print(f"[WARNING] Bot detection detected: {indicator}")
                return True

        return False

    def scrape_zalando(self, search_url, max_items=10):
        """Scrape Zalando with advanced features"""
        print(f"\n[ZALANDO] Starting: {search_url}")

        site_config = SITES["zalando"]
        min_delay, max_delay = site_config["delay_range"]

        try:
            self.apply_rate_limit()
            self.driver.get(search_url)
            self.random_delay(3, 5)

            # Handle cookie consent
            self.handle_cookie_consent()

            # Scroll to load more products
            for _ in range(3):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                self.random_delay(1, 2)

            # Find products
            products = self.driver.find_elements(By.CSS_SELECTOR, "article")
            print(f"[ZALANDO] Found {len(products)} products")

            items_processed = 0

            for idx, product in enumerate(products):
                if items_processed >= max_items:
                    break

                try:
                    # Get product link
                    link_element = product.find_element(By.TAG_NAME, "a")
                    product_url = link_element.get_attribute("href")

                    # Skip if already scraped
                    product_id = product_url.split("/")[-1].split(".")[0]
                    if self.is_already_scraped(product_id, "zalando"):
                        print(f"[ZALANDO] Skipping already scraped: {product_id}")
                        continue

                    print(f"\n[ZALANDO] Processing {idx+1}/{len(products)}: {product_id}")

                    # Open in new tab
                    self.driver.execute_script("window.open(arguments[0]);", product_url)
                    self.driver.switch_to.window(self.driver.window_handles[-1])
                    self.random_delay(min_delay, max_delay)

                    # Extract details
                    item_data = self.extract_zalando_product(product_id)

                    if item_data:
                        items_processed += 1
                        self.items_scraped += 1
                        self.stats["successful"] += 1

                        # Save progress periodically
                        if self.items_scraped % SCRAPING_CONFIG["batch_size"] == 0:
                            self.save_progress()
                            print(f"[PROGRESS] Saved at {self.items_scraped} items")

                    # Close tab
                    self.driver.close()
                    self.driver.switch_to.window(self.driver.window_handles[0])
                    self.random_delay(min_delay, max_delay)

                    # Update proxy if needed
                    if self.proxy_manager:
                        self.proxy_manager.increment()

                except Exception as e:
                    print(f"[ZALANDO] Error on product {idx}: {e}")
                    self.stats["failed"] += 1
                    self.stats["errors"].append({
                        "site": "zalando",
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    })

                    # Recover
                    while len(self.driver.window_handles) > 1:
                        self.driver.switch_to.window(self.driver.window_handles[-1])
                        self.driver.close()
                    self.driver.switch_to.window(self.driver.window_handles[0])

            print(f"\n[ZALANDO] Completed. Items: {items_processed}")

        except Exception as e:
            print(f"[ZALANDO] Critical error: {e}")

    def extract_zalando_product(self, product_id):
        """Extract Zalando product with retry logic"""
        max_retries = SITES["zalando"]["max_retries"]

        for attempt in range(max_retries):
            try:
                # Wait for images
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "img"))
                )

                # Get title
                try:
                    title = self.driver.find_element(By.CSS_SELECTOR, "h1").text
                except:
                    title = "Unknown"

                # Find images
                img_elements = self.driver.find_elements(By.TAG_NAME, "img")
                product_images = []

                for img in img_elements:
                    src = img.get_attribute("src")
                    if src and "mosaic" in src:
                        # Get high-res version
                        high_res = src.replace("sq", "org").replace("thumb", "large")
                        if high_res not in product_images:
                            product_images.append(high_res)

                print(f"[ZALANDO] Found {len(product_images)} images")

                if len(product_images) >= 2:
                    item_id = f"zalando_{product_id}_{self.items_scraped}"

                    # Download images
                    cloth_path = self.output_dir / "cloth_images" / f"{item_id}.jpg"
                    model_path = self.output_dir / "model_images" / f"{item_id}.jpg"

                    cloth_ok = self.download_image(product_images[0], cloth_path)
                    model_ok = self.download_image(product_images[1], model_path)

                    if cloth_ok and model_ok:
                        # Save metadata
                        metadata = {
                            "item_id": item_id,
                            "product_id": product_id,
                            "source": "zalando",
                            "title": title,
                            "url": self.driver.current_url,
                            "cloth_image": str(cloth_path),
                            "model_image": str(model_path),
                            "total_images": len(product_images),
                            "timestamp": datetime.now().isoformat()
                        }
                        self.save_metadata(item_id, metadata)
                        print(f"[ZALANDO] Success: {item_id}")
                        return metadata

                return None

            except Exception as e:
                print(f"[ZALANDO] Extract error (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    self.random_delay(2, 4)
                continue

        return None

    def is_already_scraped(self, product_id, source):
        """Check if product already scraped"""
        metadata_dir = self.output_dir / "metadata"
        for metadata_file in metadata_dir.glob(f"{source}_{product_id}_*.json"):
            return True
        return False

    def close(self):
        """Clean up and save final progress"""
        self.save_progress()
        if self.driver:
            self.driver.quit()
        self.session.close()

        # Print final statistics
        print("\n" + "="*80)
        print("SCRAPING STATISTICS")
        print("="*80)
        print(f"Total items scraped: {self.items_scraped}")
        print(f"Successful: {self.stats['successful']}")
        print(f"Failed: {self.stats['failed']}")
        print(f"Output directory: {self.output_dir}")


def main():
    """Run advanced scraper"""
    print("="*80)
    print("ADVANCED VTON DATASET SCRAPER")
    print("="*80)

    scraper = AdvancedVTONScraper()

    try:
        scraper.init_driver()

        # Scrape Zalando
        if SITES["zalando"]["enabled"]:
            for url in SITES["zalando"]["search_urls"][:1]:  # Test with first URL
                scraper.scrape_zalando(url, max_items=5)

        print("\n[COMPLETE] Scraping finished")

    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Stopping scraper...")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()

    finally:
        scraper.close()


if __name__ == "__main__":
    main()
