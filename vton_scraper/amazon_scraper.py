"""
Amazon-specific scraper with enhanced bot detection handling
"""

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import requests
import json
from pathlib import Path
from datetime import datetime
import random
from PIL import Image
from io import BytesIO


class AmazonVTONScraper:
    def __init__(self, output_dir="vton_amazon_test"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        (self.output_dir / "cloth_images").mkdir(exist_ok=True)
        (self.output_dir / "model_images").mkdir(exist_ok=True)
        (self.output_dir / "metadata").mkdir(exist_ok=True)
        (self.output_dir / "debug").mkdir(exist_ok=True)

        self.driver = None
        self.session = requests.Session()
        self.items_scraped = 0

    def init_driver(self, headless=False):
        """Initialize driver with Amazon-specific settings"""
        options = uc.ChromeOptions()

        if headless:
            options.add_argument('--headless=new')

        # More aggressive anti-detection for Amazon
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--no-sandbox')
        options.add_argument('--start-maximized')

        # Set realistic browser profile
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        # Disable automation flags
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        self.driver = uc.Chrome(options=options, version_main=None)
        self.driver.set_page_load_timeout(45)

        # Execute CDP commands to hide automation
        self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

        return self.driver

    def random_delay(self, min_sec=2, max_sec=5):
        """Human-like delay"""
        time.sleep(random.uniform(min_sec, max_sec))

    def human_scroll(self):
        """Simulate human scrolling behavior"""
        # Random scrolls
        for _ in range(random.randint(2, 4)):
            scroll_amount = random.randint(300, 800)
            self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
            time.sleep(random.uniform(0.5, 1.5))

    def save_debug_screenshot(self, name):
        """Save screenshot for debugging"""
        filepath = self.output_dir / "debug" / f"{name}_{int(time.time())}.png"
        self.driver.save_screenshot(str(filepath))
        print(f"[DEBUG] Screenshot saved: {filepath}")

    def handle_captcha(self):
        """Handle CAPTCHA detection"""
        page_source = self.driver.page_source.lower()

        if "captcha" in page_source or "robot check" in page_source:
            print("\n" + "="*80)
            print("[CAPTCHA DETECTED]")
            print("="*80)
            self.save_debug_screenshot("captcha")

            print("\nOptions:")
            print("1. Solve CAPTCHA manually in browser (you have 60 seconds)")
            print("2. Skip this URL")
            print("3. Exit")

            # Wait a bit for user to see the message
            time.sleep(2)

            # Give user time to solve
            print("\n[WAITING] 60 seconds to solve CAPTCHA...")
            for i in range(60, 0, -5):
                print(f"  {i} seconds remaining...")
                time.sleep(5)

                # Check if CAPTCHA is solved
                page_source = self.driver.page_source.lower()
                if "captcha" not in page_source and "robot check" not in page_source:
                    print("[SUCCESS] CAPTCHA solved!")
                    return True

            print("[TIMEOUT] CAPTCHA not solved")
            return False

        return True

    def download_image(self, url, filepath):
        """Download image with validation"""
        try:
            response = self.session.get(url, timeout=15)
            if response.status_code == 200:
                # Validate image
                img = Image.open(BytesIO(response.content))
                width, height = img.size

                if width < 400 or height < 400:
                    print(f"[SKIP] Image too small: {width}x{height}")
                    return False

                # Save
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                return True

        except Exception as e:
            print(f"[ERROR] Download failed: {e}")

        return False

    def save_metadata(self, item_id, metadata):
        """Save metadata"""
        filepath = self.output_dir / "metadata" / f"{item_id}.json"
        with open(filepath, 'w') as f:
            json.dump(metadata, f, indent=2)

    def scrape_amazon_search(self, search_query, max_items=5):
        """Scrape Amazon search results"""
        print(f"\n[AMAZON] Starting search: {search_query}")

        # Build search URL
        search_url = f"https://www.amazon.com/s?k={search_query.replace(' ', '+')}"

        try:
            # Load search page
            print(f"[AMAZON] Loading: {search_url}")
            self.driver.get(search_url)
            self.random_delay(4, 7)

            # Check for CAPTCHA
            if not self.handle_captcha():
                print("[AMAZON] Skipping due to CAPTCHA")
                return

            # Human-like behavior
            self.human_scroll()
            self.random_delay(2, 4)

            # Find products
            print("[AMAZON] Looking for products...")

            # Try multiple selectors
            products = []

            # Selector 1: data-component-type
            try:
                products = self.driver.find_elements(By.CSS_SELECTOR, "[data-component-type='s-search-result']")
            except:
                pass

            # Selector 2: data-asin attribute
            if not products:
                try:
                    products = self.driver.find_elements(By.CSS_SELECTOR, "[data-asin]:not([data-asin=''])")
                    products = [p for p in products if p.get_attribute("data-asin")]
                except:
                    pass

            # Selector 3: div with specific class
            if not products:
                try:
                    products = self.driver.find_elements(By.CSS_SELECTOR, "div[data-index]")
                except:
                    pass

            print(f"[AMAZON] Found {len(products)} product elements")

            if len(products) == 0:
                print("[AMAZON] No products found. Saving debug screenshot...")
                self.save_debug_screenshot("no_products")
                print(f"[DEBUG] Page title: {self.driver.title}")
                return

            items_processed = 0

            for idx, product in enumerate(products[:max_items * 2]):  # Try more products
                if items_processed >= max_items:
                    break

                try:
                    # Get ASIN (Amazon product ID)
                    asin = product.get_attribute("data-asin")
                    if not asin:
                        continue

                    # Get product link
                    try:
                        link = product.find_element(By.CSS_SELECTOR, "h2 a, .a-link-normal")
                        product_url = link.get_attribute("href")
                    except:
                        # Build URL from ASIN
                        product_url = f"https://www.amazon.com/dp/{asin}"

                    print(f"\n[AMAZON] Processing {idx+1}: ASIN {asin}")

                    # Open in new tab
                    self.driver.execute_script("window.open(arguments[0]);", product_url)
                    self.driver.switch_to.window(self.driver.window_handles[-1])
                    self.random_delay(4, 7)

                    # Check for CAPTCHA on product page
                    if not self.handle_captcha():
                        self.driver.close()
                        self.driver.switch_to.window(self.driver.window_handles[0])
                        break

                    # Extract product
                    item_data = self.extract_amazon_product(asin)

                    if item_data:
                        items_processed += 1
                        self.items_scraped += 1
                        print(f"[AMAZON] Success! Total: {self.items_scraped}")

                    # Close tab
                    self.driver.close()
                    self.driver.switch_to.window(self.driver.window_handles[0])
                    self.random_delay(4, 8)  # Longer delay for Amazon

                except Exception as e:
                    print(f"[AMAZON] Error on product {idx}: {e}")

                    # Recover
                    while len(self.driver.window_handles) > 1:
                        self.driver.switch_to.window(self.driver.window_handles[-1])
                        self.driver.close()
                    self.driver.switch_to.window(self.driver.window_handles[0])
                    continue

            print(f"\n[AMAZON] Completed. Items processed: {items_processed}")

        except Exception as e:
            print(f"[AMAZON] Critical error: {e}")
            self.save_debug_screenshot("critical_error")
            import traceback
            traceback.print_exc()

    def extract_amazon_product(self, asin):
        """Extract Amazon product details"""
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

            print(f"[AMAZON] Product: {title[:50]}...")

            # Get all image URLs
            image_urls = []

            # Method 1: Click thumbnails
            try:
                thumbnails = self.driver.find_elements(By.CSS_SELECTOR, "#altImages img")
                print(f"[AMAZON] Found {len(thumbnails)} thumbnails")

                for i, thumb in enumerate(thumbnails[:8]):
                    try:
                        # Scroll thumbnail into view
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", thumb)
                        time.sleep(0.3)

                        # Click
                        thumb.click()
                        time.sleep(0.8)

                        # Get main image src
                        main_img = self.driver.find_element(By.ID, "landingImage")
                        img_src = main_img.get_attribute("src")

                        # Convert to high-res
                        if img_src and "amazon.com" in img_src:
                            # Remove size constraints
                            high_res = img_src.split("._")[0] + ".jpg"
                            if high_res not in image_urls:
                                image_urls.append(high_res)
                                print(f"[AMAZON] Image {len(image_urls)}: {high_res[:80]}...")

                    except Exception as e:
                        continue

            except Exception as e:
                print(f"[AMAZON] Thumbnail method failed: {e}")

            # Method 2: Parse image data from page
            if len(image_urls) < 2:
                try:
                    # Look for image data in JavaScript
                    scripts = self.driver.find_elements(By.TAG_NAME, "script")
                    for script in scripts:
                        content = script.get_attribute("innerHTML")
                        if content and "imageGalleryData" in content:
                            # Extract URLs (this is simplified, may need adjustment)
                            import re
                            urls = re.findall(r'"hiRes":"(https://[^"]+)"', content)
                            for url in urls[:6]:
                                if url not in image_urls:
                                    image_urls.append(url)
                            break
                except:
                    pass

            print(f"[AMAZON] Total images collected: {len(image_urls)}")

            if len(image_urls) >= 2:
                item_id = f"amazon_{asin}_{self.items_scraped}"

                # Download images
                cloth_path = self.output_dir / "cloth_images" / f"{item_id}.jpg"
                model_path = self.output_dir / "model_images" / f"{item_id}.jpg"

                cloth_ok = self.download_image(image_urls[0], cloth_path)
                model_ok = self.download_image(image_urls[1], model_path)

                if cloth_ok and model_ok:
                    # Save metadata
                    metadata = {
                        "item_id": item_id,
                        "asin": asin,
                        "source": "amazon",
                        "title": title,
                        "url": self.driver.current_url,
                        "cloth_image": str(cloth_path),
                        "model_image": str(model_path),
                        "total_images": len(image_urls),
                        "timestamp": datetime.now().isoformat()
                    }
                    self.save_metadata(item_id, metadata)
                    return metadata
                else:
                    print(f"[AMAZON] Failed to download images")
            else:
                print(f"[AMAZON] Insufficient images ({len(image_urls)} < 2)")

        except TimeoutException:
            print("[AMAZON] Timeout waiting for images")
            self.save_debug_screenshot("timeout")

        except Exception as e:
            print(f"[AMAZON] Extract error: {e}")
            self.save_debug_screenshot("extract_error")

        return None

    def close(self):
        """Clean up"""
        if self.driver:
            self.driver.quit()
        self.session.close()

        print("\n" + "="*80)
        print(f"Total items scraped: {self.items_scraped}")
        print(f"Output directory: {self.output_dir}")
        print("="*80)


def main():
    """Run Amazon scraper test"""
    print("="*80)
    print("AMAZON VTON SCRAPER - TEST")
    print("="*80)

    scraper = AmazonVTONScraper()

    try:
        scraper.init_driver(headless=False)

        # Test searches
        searches = [
            "women dress",
            "women blouse",
        ]

        for search in searches[:1]:  # Test with first search
            scraper.scrape_amazon_search(search, max_items=3)

        print("\n[COMPLETE]")

    except KeyboardInterrupt:
        print("\n[INTERRUPTED]")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()

    finally:
        input("\nPress Enter to close...")
        scraper.close()


if __name__ == "__main__":
    main()
