"""
Fixed VTON Dataset Scraper - Handles region selection and selector issues
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
import random
from PIL import Image
from io import BytesIO


class VTONScraperFixed:
    def __init__(self, output_dir="vton_dataset_test"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        (self.output_dir / "cloth_images").mkdir(exist_ok=True)
        (self.output_dir / "model_images").mkdir(exist_ok=True)
        (self.output_dir / "metadata").mkdir(exist_ok=True)

        self.driver = None
        self.items_scraped = 0
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def init_driver(self, headless=False):
        """Initialize driver"""
        options = uc.ChromeOptions()
        if headless:
            options.add_argument('--headless=new')

        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--no-sandbox')

        self.driver = uc.Chrome(options=options, version_main=None)
        self.driver.set_page_load_timeout(30)
        return self.driver

    def random_delay(self, min_sec=2, max_sec=5):
        time.sleep(random.uniform(min_sec, max_sec))

    def download_image(self, url, filepath):
        """Download and validate image"""
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content))
                width, height = img.size

                if width < 300 or height < 300:
                    return False

                with open(filepath, 'wb') as f:
                    f.write(response.content)
                return True
        except Exception as e:
            print(f"  Download error: {e}")
        return False

    def save_metadata(self, item_id, metadata):
        filepath = self.output_dir / "metadata" / f"{item_id}.json"
        with open(filepath, 'w') as f:
            json.dump(metadata, f, indent=2)

    def scrape_zalando_uk(self, max_items=3):
        """Scrape Zalando UK (works better than .com)"""
        print("\n" + "="*80)
        print("ZALANDO UK - WOMEN'S DRESSES")
        print("="*80)

        url = "https://www.zalando.co.uk/womens-clothing-dresses/"

        try:
            print(f"\n[1/4] Loading: {url}")
            self.driver.get(url)
            self.random_delay(3, 5)

            # Handle cookies
            try:
                accept_btn = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Accept')]"))
                )
                accept_btn.click()
                print("[2/4] Cookies accepted")
                self.random_delay(1, 2)
            except:
                print("[2/4] No cookie banner")

            # Scroll to load products
            print("[3/4] Loading products...")
            for i in range(3):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                time.sleep(1)

            # Find products - try multiple selectors
            products = self.driver.find_elements(By.CSS_SELECTOR, "article a[href*='/dress']")

            if not products:
                products = self.driver.find_elements(By.CSS_SELECTOR, "article a")

            print(f"[4/4] Found {len(products)} product links")

            if len(products) == 0:
                self.driver.save_screenshot("zalando_uk_debug.png")
                print("  No products found. Screenshot saved.")
                return

            # Process products
            processed = 0
            product_urls = [p.get_attribute("href") for p in products[:max_items*2]]

            for idx, product_url in enumerate(product_urls):
                if processed >= max_items:
                    break

                if not product_url or "/dress" not in product_url.lower():
                    continue

                print(f"\n  Processing {processed+1}/{max_items}...")
                print(f"  URL: {product_url[:70]}...")

                try:
                    # Open product page
                    self.driver.execute_script("window.open(arguments[0]);", product_url)
                    self.driver.switch_to.window(self.driver.window_handles[-1])
                    self.random_delay(2, 4)

                    # Extract product
                    if self.extract_zalando_product(product_url):
                        processed += 1

                    # Close tab
                    self.driver.close()
                    self.driver.switch_to.window(self.driver.window_handles[0])
                    self.random_delay(2, 3)

                except Exception as e:
                    print(f"  Error: {e}")
                    while len(self.driver.window_handles) > 1:
                        self.driver.switch_to.window(self.driver.window_handles[-1])
                        self.driver.close()
                    self.driver.switch_to.window(self.driver.window_handles[0])

            print(f"\n[OK] Zalando UK: {processed} items scraped")

        except Exception as e:
            print(f"\n[ERROR] Zalando UK error: {e}")

    def extract_zalando_product(self, url):
        """Extract Zalando product details"""
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

            # Find product images
            images = []
            img_elements = self.driver.find_elements(By.TAG_NAME, "img")

            for img in img_elements:
                src = img.get_attribute("src")
                if src and "mosaic" in src and "zalando" in src:
                    # Get high-res version
                    high_res = src.replace("thumb", "large").replace("sq", "org")
                    if high_res not in images:
                        images.append(high_res)

            print(f"    Found {len(images)} images")

            if len(images) >= 2:
                item_id = f"zalando_{self.items_scraped}"

                cloth_path = self.output_dir / "cloth_images" / f"{item_id}.jpg"
                model_path = self.output_dir / "model_images" / f"{item_id}.jpg"

                if self.download_image(images[0], cloth_path):
                    print(f"    [OK] Cloth image")
                    if self.download_image(images[1], model_path):
                        print(f"    [OK] Model image")

                        metadata = {
                            "item_id": item_id,
                            "source": "zalando_uk",
                            "title": title,
                            "url": url,
                            "cloth_image": str(cloth_path),
                            "model_image": str(model_path),
                        }
                        self.save_metadata(item_id, metadata)
                        self.items_scraped += 1
                        return True

        except Exception as e:
            print(f"    Extract error: {e}")

        return False

    def scrape_amazon(self, max_items=3):
        """Scrape Amazon with improved selectors"""
        print("\n" + "="*80)
        print("AMAZON - WOMEN'S DRESSES")
        print("="*80)

        url = "https://www.amazon.com/s?k=women+dress&rh=n:1040660"

        try:
            print(f"\n[1/4] Loading: {url}")
            self.driver.get(url)
            self.random_delay(4, 6)

            # Check for CAPTCHA
            if "captcha" in self.driver.page_source.lower():
                print("\n[WARNING]  CAPTCHA DETECTED!")
                print("Please solve the CAPTCHA in the browser window.")
                print("Waiting 30 seconds...")
                time.sleep(30)

            print("[2/4] Looking for products...")
            self.driver.execute_script("window.scrollTo(0, 800);")
            self.random_delay(2, 3)

            # Find product ASINs
            products = self.driver.find_elements(By.CSS_SELECTOR, "[data-asin]:not([data-asin=''])")
            products = [p for p in products if p.get_attribute("data-asin")]

            print(f"[3/4] Found {len(products)} products")

            if len(products) == 0:
                self.driver.save_screenshot("amazon_debug.png")
                print("  No products found. Screenshot saved.")
                return

            # Process products
            processed = 0

            for idx, product in enumerate(products[:max_items*3]):
                if processed >= max_items:
                    break

                asin = product.get_attribute("data-asin")
                if not asin or len(asin) != 10:
                    continue

                product_url = f"https://www.amazon.com/dp/{asin}"

                print(f"\n  Processing {processed+1}/{max_items}...")
                print(f"  ASIN: {asin}")

                try:
                    # Open product page
                    self.driver.execute_script("window.open(arguments[0]);", product_url)
                    self.driver.switch_to.window(self.driver.window_handles[-1])
                    self.random_delay(3, 5)

                    # Extract product
                    if self.extract_amazon_product(asin):
                        processed += 1

                    # Close tab
                    self.driver.close()
                    self.driver.switch_to.window(self.driver.window_handles[0])
                    self.random_delay(3, 5)

                except Exception as e:
                    print(f"  Error: {e}")
                    while len(self.driver.window_handles) > 1:
                        self.driver.switch_to.window(self.driver.window_handles[-1])
                        self.driver.close()
                    self.driver.switch_to.window(self.driver.window_handles[0])

            print(f"\n[OK] Amazon: {processed} items scraped")

        except Exception as e:
            print(f"\n[ERROR] Amazon error: {e}")

    def extract_amazon_product(self, asin):
        """Extract Amazon product with multiple methods"""
        try:
            # Wait for main image
            main_img = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "landingImage"))
            )

            # Get title
            try:
                title = self.driver.find_element(By.ID, "productTitle").text.strip()
            except:
                title = "Unknown"

            # Collect images
            images = []

            # Method: Click through thumbnails
            try:
                thumbs = self.driver.find_elements(By.CSS_SELECTOR, "#altImages img, .imageThumbnail img")

                for i, thumb in enumerate(thumbs[:6]):
                    try:
                        self.driver.execute_script("arguments[0].scrollIntoView();", thumb)
                        time.sleep(0.2)
                        thumb.click()
                        time.sleep(0.5)

                        main_img = self.driver.find_element(By.ID, "landingImage")
                        src = main_img.get_attribute("src")

                        if src and "amazon.com" in src:
                            # Get high-res
                            high_res = src.split("._")[0] + ".jpg"
                            if high_res not in images:
                                images.append(high_res)

                    except:
                        continue

            except Exception as e:
                print(f"    Thumbnail error: {e}")

            print(f"    Found {len(images)} images")

            if len(images) >= 2:
                item_id = f"amazon_{asin}_{self.items_scraped}"

                cloth_path = self.output_dir / "cloth_images" / f"{item_id}.jpg"
                model_path = self.output_dir / "model_images" / f"{item_id}.jpg"

                if self.download_image(images[0], cloth_path):
                    print(f"    [OK] Cloth image")
                    if self.download_image(images[1], model_path):
                        print(f"    [OK] Model image")

                        metadata = {
                            "item_id": item_id,
                            "asin": asin,
                            "source": "amazon",
                            "title": title,
                            "url": self.driver.current_url,
                            "cloth_image": str(cloth_path),
                            "model_image": str(model_path),
                        }
                        self.save_metadata(item_id, metadata)
                        self.items_scraped += 1
                        return True

        except Exception as e:
            print(f"    Extract error: {e}")

        return False

    def close(self):
        if self.driver:
            self.driver.quit()
        self.session.close()


def main():
    print("="*80)
    print("VTON SCRAPER - FIXED VERSION")
    print("="*80)
    print("\nThis will scrape 3 items from Zalando UK and 3 from Amazon")
    print("Output: vton_dataset_test/\n")

    scraper = VTONScraperFixed()

    try:
        scraper.init_driver(headless=False)

        # Test Zalando UK
        scraper.scrape_zalando_uk(max_items=3)

        # Test Amazon
        scraper.scrape_amazon(max_items=3)

        print("\n" + "="*80)
        print("SCRAPING COMPLETE!")
        print("="*80)
        print(f"Total items: {scraper.items_scraped}")
        print(f"\nOutput location: {scraper.output_dir.absolute()}")
        print(f"  - cloth_images/: {len(list((scraper.output_dir / 'cloth_images').glob('*.jpg')))} files")
        print(f"  - model_images/: {len(list((scraper.output_dir / 'model_images').glob('*.jpg')))} files")
        print(f"  - metadata/:     {len(list((scraper.output_dir / 'metadata').glob('*.json')))} files")

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

    finally:
        print("\nClosing browser...")
        scraper.close()


if __name__ == "__main__":
    main()
