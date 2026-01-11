"""
VTON Dataset Scraper - Test Version
Scrapes clothing images with model images from e-commerce sites
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

class VTONScraper:
    def __init__(self, output_dir="vton_dataset_test"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Create subdirectories
        (self.output_dir / "cloth_images").mkdir(exist_ok=True)
        (self.output_dir / "model_images").mkdir(exist_ok=True)
        (self.output_dir / "metadata").mkdir(exist_ok=True)

        self.driver = None
        self.items_scraped = 0
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

    def init_driver(self, headless=False):
        """Initialize undetected Chrome driver"""
        options = uc.ChromeOptions()
        if headless:
            options.add_argument('--headless')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--no-sandbox')
        options.add_argument(f'--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        self.driver = uc.Chrome(options=options, version_main=None)
        self.driver.set_page_load_timeout(30)
        return self.driver

    def random_delay(self, min_seconds=2, max_seconds=5):
        """Add random delay to mimic human behavior"""
        time.sleep(random.uniform(min_seconds, max_seconds))

    def download_image(self, url, filepath):
        """Download image from URL"""
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                return True
        except Exception as e:
            print(f"Error downloading {url}: {e}")
        return False

    def save_metadata(self, item_id, metadata):
        """Save metadata for each item"""
        filepath = self.output_dir / "metadata" / f"{item_id}.json"
        with open(filepath, 'w') as f:
            json.dump(metadata, f, indent=2)

    def scrape_zalando_test(self, max_items=5):
        """
        Test scraper for Zalando
        Zalando typically shows both product images and model wearing images
        """
        print("\n[ZALANDO TEST] Starting...")

        # Start with a search query for specific clothing
        search_url = "https://www.zalando.com/womens-clothing-dresses/"

        try:
            self.driver.get(search_url)
            self.random_delay(3, 5)

            # Handle cookie consent if present - try multiple approaches
            try:
                # Method 1: Look for Accept/Agree buttons
                accept_button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'agree')]"))
                )
                accept_button.click()
                print("[ZALANDO] Cookie consent accepted")
                self.random_delay(1, 2)
            except:
                try:
                    # Method 2: Find by common cookie button IDs
                    buttons = self.driver.find_elements(By.TAG_NAME, "button")
                    for button in buttons[:10]:
                        text = button.text.lower()
                        if any(word in text for word in ["accept", "agree", "allow"]):
                            button.click()
                            print("[ZALANDO] Cookie consent accepted (method 2)")
                            self.random_delay(1, 2)
                            break
                except:
                    print("[ZALANDO] No cookie consent found or already accepted")

            # Find product cards
            print("[ZALANDO] Looking for product cards...")
            self.driver.execute_script("window.scrollTo(0, 800);")
            self.random_delay(2, 3)

            # Try multiple selectors for products
            products = []

            # Selector 1: article tags
            products = self.driver.find_elements(By.CSS_SELECTOR, "article")

            # Selector 2: If no articles, try data-testid
            if len(products) == 0:
                products = self.driver.find_elements(By.CSS_SELECTOR, "[data-testid*='product'], [data-testid*='item']")

            # Selector 3: Try class-based selectors
            if len(products) == 0:
                products = self.driver.find_elements(By.CSS_SELECTOR, ".cat_articleCard, ._4bRO5V")

            print(f"[ZALANDO] Found {len(products)} product elements")

            # Debug: save screenshot if no products found
            if len(products) == 0:
                screenshot_path = "zalando_debug.png"
                self.driver.save_screenshot(screenshot_path)
                print(f"[ZALANDO] No products found. Screenshot saved to {screenshot_path}")
                print(f"[ZALANDO] Page title: {self.driver.title}")
                return

            items_processed = 0

            for idx, product in enumerate(products[:max_items]):
                try:
                    # Get the product link
                    link_element = product.find_element(By.TAG_NAME, "a")
                    product_url = link_element.get_attribute("href")

                    print(f"\n[ZALANDO] Processing item {idx+1}/{max_items}")
                    print(f"URL: {product_url}")

                    # Open product page in new tab
                    self.driver.execute_script("window.open(arguments[0]);", product_url)
                    self.driver.switch_to.window(self.driver.window_handles[-1])
                    self.random_delay(3, 4)

                    # Extract product details
                    item_data = self.extract_zalando_product_details()

                    if item_data:
                        items_processed += 1
                        self.items_scraped += 1
                        print(f"[ZALANDO] Successfully scraped item {items_processed}")

                    # Close tab and switch back
                    self.driver.close()
                    self.driver.switch_to.window(self.driver.window_handles[0])
                    self.random_delay(2, 3)

                except Exception as e:
                    print(f"[ZALANDO] Error processing product {idx}: {e}")
                    # Try to recover by closing extra tabs
                    while len(self.driver.window_handles) > 1:
                        self.driver.switch_to.window(self.driver.window_handles[-1])
                        self.driver.close()
                    self.driver.switch_to.window(self.driver.window_handles[0])
                    continue

            print(f"\n[ZALANDO] Test completed. Items processed: {items_processed}")

        except Exception as e:
            print(f"[ZALANDO] Critical error: {e}")

    def extract_zalando_product_details(self):
        """Extract product details from Zalando product page"""
        try:
            # Wait for images to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "img"))
            )

            # Get product title
            try:
                title = self.driver.find_element(By.CSS_SELECTOR, "h1").text
            except:
                title = "Unknown"

            # Find all images on the page
            img_elements = self.driver.find_elements(By.TAG_NAME, "img")
            print(f"[ZALANDO] Found {len(img_elements)} total images")

            # Filter for high-quality product images
            product_images = []
            for img in img_elements:
                src = img.get_attribute("src")
                if src and "mosaic" in src and any(size in src for size in ["large", "pdp-gallery"]):
                    product_images.append(src)

            print(f"[ZALANDO] Found {len(product_images)} product images")

            if len(product_images) >= 2:
                # Usually first image is flat lay, second is model wearing
                item_id = f"zalando_{self.items_scraped}"

                # Download cloth image (flat lay)
                cloth_path = self.output_dir / "cloth_images" / f"{item_id}.jpg"
                cloth_downloaded = self.download_image(product_images[0], cloth_path)

                # Download model image
                model_path = self.output_dir / "model_images" / f"{item_id}.jpg"
                model_downloaded = self.download_image(product_images[1], model_path)

                if cloth_downloaded and model_downloaded:
                    # Save metadata
                    metadata = {
                        "item_id": item_id,
                        "source": "zalando",
                        "title": title,
                        "url": self.driver.current_url,
                        "cloth_image": str(cloth_path),
                        "model_image": str(model_path),
                        "total_images_found": len(product_images),
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    self.save_metadata(item_id, metadata)
                    print(f"[ZALANDO] Downloaded images for {item_id}")
                    return metadata

        except Exception as e:
            print(f"[ZALANDO] Error extracting product: {e}")

        return None

    def scrape_amazon_test(self, max_items=5):
        """
        Test scraper for Amazon
        Amazon structure is different and may have bot detection
        """
        print("\n[AMAZON TEST] Starting...")

        # Start with a search query
        search_url = "https://www.amazon.com/s?k=women+dress"

        try:
            self.driver.get(search_url)
            self.random_delay(3, 5)

            # Check for bot detection
            page_source = self.driver.page_source.lower()
            if "captcha" in page_source or "robot check" in page_source:
                print("[AMAZON] ⚠️  Bot detection encountered!")
                print("[AMAZON] You may need to solve CAPTCHA manually...")
                input("Press Enter after solving CAPTCHA...")

            # Find product cards
            print("[AMAZON] Looking for product cards...")
            self.driver.execute_script("window.scrollTo(0, 800);")
            self.random_delay(2, 3)

            # Amazon uses div with data-component-type attribute
            products = self.driver.find_elements(By.CSS_SELECTOR, "[data-component-type='s-search-result']")
            print(f"[AMAZON] Found {len(products)} product elements")

            items_processed = 0

            for idx, product in enumerate(products[:max_items]):
                try:
                    # Get the product link
                    link_element = product.find_element(By.CSS_SELECTOR, "h2 a")
                    product_url = link_element.get_attribute("href")

                    print(f"\n[AMAZON] Processing item {idx+1}/{max_items}")
                    print(f"URL: {product_url}")

                    # Open product page in new tab
                    self.driver.execute_script("window.open(arguments[0]);", product_url)
                    self.driver.switch_to.window(self.driver.window_handles[-1])
                    self.random_delay(3, 4)

                    # Extract product details
                    item_data = self.extract_amazon_product_details()

                    if item_data:
                        items_processed += 1
                        self.items_scraped += 1
                        print(f"[AMAZON] Successfully scraped item {items_processed}")

                    # Close tab and switch back
                    self.driver.close()
                    self.driver.switch_to.window(self.driver.window_handles[0])
                    self.random_delay(3, 5)  # Longer delay for Amazon

                except Exception as e:
                    print(f"[AMAZON] Error processing product {idx}: {e}")
                    # Try to recover
                    while len(self.driver.window_handles) > 1:
                        self.driver.switch_to.window(self.driver.window_handles[-1])
                        self.driver.close()
                    self.driver.switch_to.window(self.driver.window_handles[0])
                    continue

            print(f"\n[AMAZON] Test completed. Items processed: {items_processed}")

        except Exception as e:
            print(f"[AMAZON] Critical error: {e}")

    def extract_amazon_product_details(self):
        """Extract product details from Amazon product page"""
        try:
            # Wait for images to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "landingImage"))
            )

            # Get product title
            try:
                title = self.driver.find_element(By.ID, "productTitle").text
            except:
                title = "Unknown"

            # Get main image
            main_img = self.driver.find_element(By.ID, "landingImage")
            main_img_src = main_img.get_attribute("src")

            # Find thumbnail images to get all variants
            thumbnails = self.driver.find_elements(By.CSS_SELECTOR, ".imageThumbnail img")

            # Get high-res versions of images
            image_urls = []

            # Click through thumbnails to load different images
            for thumb in thumbnails[:6]:  # Check first 6 thumbnails
                try:
                    thumb.click()
                    self.random_delay(0.5, 1)

                    # Get the updated main image
                    main_img = self.driver.find_element(By.ID, "landingImage")
                    img_src = main_img.get_attribute("src")

                    # Convert to high-res URL if possible
                    if img_src:
                        # Amazon image URL pattern - remove size restrictions
                        high_res = img_src.split("._")[0] + ".jpg"
                        if high_res not in image_urls:
                            image_urls.append(high_res)

                except Exception as e:
                    print(f"[AMAZON] Error clicking thumbnail: {e}")
                    continue

            print(f"[AMAZON] Found {len(image_urls)} product images")

            if len(image_urls) >= 2:
                item_id = f"amazon_{self.items_scraped}"

                # Download first two images (often cloth + model)
                cloth_path = self.output_dir / "cloth_images" / f"{item_id}.jpg"
                cloth_downloaded = self.download_image(image_urls[0], cloth_path)

                model_path = self.output_dir / "model_images" / f"{item_id}.jpg"
                model_downloaded = self.download_image(image_urls[1], model_path)

                if cloth_downloaded and model_downloaded:
                    # Save metadata
                    metadata = {
                        "item_id": item_id,
                        "source": "amazon",
                        "title": title,
                        "url": self.driver.current_url,
                        "cloth_image": str(cloth_path),
                        "model_image": str(model_path),
                        "total_images_found": len(image_urls),
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    self.save_metadata(item_id, metadata)
                    print(f"[AMAZON] Downloaded images for {item_id}")
                    return metadata

        except Exception as e:
            print(f"[AMAZON] Error extracting product: {e}")
            import traceback
            traceback.print_exc()

        return None

    def close(self):
        """Clean up resources"""
        if self.driver:
            self.driver.quit()
        self.session.close()


def main():
    """Run test scraping"""
    print("="*80)
    print("VTON DATASET SCRAPER - TEST MODE")
    print("="*80)

    scraper = VTONScraper(output_dir="vton_dataset_test")

    try:
        scraper.init_driver(headless=False)

        # Test Zalando first (known to work)
        print("\n\n" + "="*80)
        print("TESTING: ZALANDO")
        print("="*80)
        scraper.scrape_zalando_test(max_items=3)

        # Test Amazon
        print("\n\n" + "="*80)
        print("TESTING: AMAZON")
        print("="*80)
        scraper.scrape_amazon_test(max_items=3)

        print("\n\n" + "="*80)
        print("TEST COMPLETED")
        print("="*80)
        print(f"Total items scraped: {scraper.items_scraped}")
        print(f"Output directory: {scraper.output_dir}")
        print(f"\nCheck the following folders:")
        print(f"  - cloth_images/")
        print(f"  - model_images/")
        print(f"  - metadata/")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()

    finally:
        print("\nClosing browser...")
        scraper.close()


if __name__ == "__main__":
    main()
