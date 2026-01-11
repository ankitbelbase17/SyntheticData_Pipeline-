"""
Working Zalando Scraper - Gets full-size images with models
"""

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import time
import requests
from pathlib import Path
from PIL import Image
from io import BytesIO
import json
import random


class ZalandoVTONScraper:
    def __init__(self, output_dir="vton_zalando_dataset"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        (self.output_dir / "cloth_images").mkdir(exist_ok=True)
        (self.output_dir / "model_images").mkdir(exist_ok=True)
        (self.output_dir / "metadata").mkdir(exist_ok=True)

        self.driver = None
        self.items_scraped = 0
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0'})

    def init_driver(self):
        options = uc.ChromeOptions()
        options.add_argument('--disable-blink-features=AutomationControlled')
        self.driver = uc.Chrome(options=options, version_main=None)
        self.driver.set_page_load_timeout(30)
        self.driver.maximize_window()
        return self.driver

    def random_delay(self, min_sec=2, max_sec=4):
        time.sleep(random.uniform(min_sec, max_sec))

    def download_image(self, url, filepath):
        """Download and validate image"""
        try:
            response = self.session.get(url, timeout=15)
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content))
                width, height = img.size

                # Must be at least 400x400
                if width < 400 or height < 400:
                    return False, f"{width}x{height} too small"

                with open(filepath, 'wb') as f:
                    f.write(response.content)

                return True, f"{width}x{height}"
        except Exception as e:
            return False, str(e)
        return False, "Unknown error"

    def get_full_size_images_from_product(self, product_url):
        """Extract full-size images from Zalando product page"""
        try:
            print(f"\n  Loading product...")
            self.driver.get(product_url)
            self.random_delay(3, 5)

            # Get title
            try:
                title = self.driver.find_element(By.CSS_SELECTOR, "h1").text
                print(f"  Product: {title[:50]}...")
            except:
                title = "Unknown"

            # Method 1: Look for the image carousel/gallery
            images_collected = []

            # Find the main product images (not color swatches)
            # These are usually in a specific carousel or gallery
            print(f"  Looking for image gallery...")

            # Zalando structure: Look for images with 'spp-media-p1' in src
            time.sleep(2)

            # Get all image elements that could be product images
            img_elements = self.driver.find_elements(By.CSS_SELECTOR, "img[src*='spp-media-p1']")

            print(f"  Found {len(img_elements)} potential product images")

            # Try clicking on images to open full view
            tried_images = []

            for i, img_elem in enumerate(img_elements[:10]):  # Try first 10
                try:
                    src = img_elem.get_attribute("src")

                    # Skip if already tried this URL
                    if src in tried_images:
                        continue
                    tried_images.append(src)

                    # Skip if it's a small thumbnail (color swatch)
                    if "thumb" in src or "sq" in src:
                        continue

                    print(f"\n  Trying image {i+1}...")

                    # Scroll into view
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", img_elem)
                    time.sleep(0.5)

                    # Try to click to open lightbox/full view
                    try:
                        img_elem.click()
                        time.sleep(1)

                        # Look for larger image that appeared
                        large_imgs = self.driver.find_elements(By.CSS_SELECTOR, "img[src*='spp-media-p1']")

                        for large_img in large_imgs:
                            large_src = large_img.get_attribute("src")

                            # Look for 'org' or 'large' in URL (full size indicators)
                            if large_src and large_src not in images_collected:
                                # Try to get highest quality version
                                high_res = large_src

                                # Zalando URL patterns for high-res
                                high_res = high_res.replace("thumb", "org")
                                high_res = high_res.replace("sq", "org")
                                high_res = high_res.replace("packshot", "large")

                                # Remove size restrictions from URL
                                if ".jpg?" in high_res:
                                    high_res = high_res.split(".jpg?")[0] + ".jpg"

                                images_collected.append(high_res)
                                print(f"    Added: {high_res[:80]}...")

                        # Close lightbox if it opened
                        try:
                            close_btn = self.driver.find_element(By.CSS_SELECTOR, "button[aria-label='Close']")
                            close_btn.click()
                            time.sleep(0.5)
                        except:
                            # Press ESC
                            from selenium.webdriver.common.keys import Keys
                            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
                            time.sleep(0.5)

                    except Exception as e:
                        # Image might not be clickable, that's okay
                        # Just get the src and try to upscale it
                        high_res = src.replace("thumb", "org").replace("sq", "org")
                        if ".jpg?" in high_res:
                            high_res = high_res.split(".jpg?")[0] + ".jpg"

                        if high_res not in images_collected:
                            images_collected.append(high_res)

                    if len(images_collected) >= 6:
                        break

                except Exception as e:
                    continue

            print(f"\n  Total high-res images collected: {len(images_collected)}")

            if len(images_collected) >= 2:
                return {
                    "title": title,
                    "url": product_url,
                    "images": images_collected
                }

            return None

        except Exception as e:
            print(f"  Error: {e}")
            return None

    def scrape_zalando_category(self, category_url, max_items=10):
        """Scrape products from a Zalando category page"""
        print(f"\n{'='*80}")
        print(f"SCRAPING: {category_url}")
        print(f"{'='*80}")

        try:
            self.driver.get(category_url)
            self.random_delay(3, 5)

            # Accept cookies
            try:
                accept = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Accept')]")
                accept.click()
                time.sleep(2)
            except:
                pass

            # Scroll to load products
            for _ in range(3):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                time.sleep(1)

            # Get product links
            product_links = []
            links = self.driver.find_elements(By.CSS_SELECTOR, "article a[href*='.html']")

            for link in links:
                href = link.get_attribute("href")
                if href and ".html" in href and href not in product_links:
                    product_links.append(href)

            print(f"\nFound {len(product_links)} products")

            # Process products
            items_success = 0

            for idx, product_url in enumerate(product_links[:max_items]):
                print(f"\n[{idx+1}/{min(max_items, len(product_links))}] Processing...")
                print(f"URL: {product_url[:70]}...")

                try:
                    # Get product images
                    product_data = self.get_full_size_images_from_product(product_url)

                    if product_data and len(product_data["images"]) >= 2:
                        # Download images
                        item_id = f"zalando_{self.items_scraped}"

                        # Usually first image is flat lay, second+ are model
                        cloth_path = self.output_dir / "cloth_images" / f"{item_id}.jpg"
                        model_path = self.output_dir / "model_images" / f"{item_id}.jpg"

                        print(f"\n  Downloading images...")
                        cloth_ok, cloth_info = self.download_image(product_data["images"][0], cloth_path)
                        print(f"    Cloth: {cloth_info}")

                        model_ok, model_info = self.download_image(product_data["images"][1], model_path)
                        print(f"    Model: {model_info}")

                        if cloth_ok and model_ok:
                            # Save metadata
                            metadata = {
                                "item_id": item_id,
                                "source": "zalando_uk",
                                "title": product_data["title"],
                                "url": product_url,
                                "cloth_image": str(cloth_path),
                                "model_image": str(model_path),
                                "total_images_available": len(product_data["images"]),
                                "cloth_size": cloth_info,
                                "model_size": model_info
                            }

                            with open(self.output_dir / "metadata" / f"{item_id}.json", 'w') as f:
                                json.dump(metadata, f, indent=2)

                            self.items_scraped += 1
                            items_success += 1
                            print(f"  [SUCCESS] Item {self.items_scraped} saved!")
                        else:
                            print(f"  [SKIP] Images too small or failed")
                    else:
                        print(f"  [SKIP] Not enough images found")

                    self.random_delay(2, 4)

                except Exception as e:
                    print(f"  [ERROR] {e}")
                    continue

            print(f"\n{'='*80}")
            print(f"CATEGORY COMPLETE: {items_success}/{max_items} items scraped")
            print(f"{'='*80}")

        except Exception as e:
            print(f"\nCategory error: {e}")

    def close(self):
        if self.driver:
            self.driver.quit()
        self.session.close()


def main():
    print("="*80)
    print("ZALANDO VTON SCRAPER - WORKING VERSION")
    print("="*80)

    scraper = ZalandoVTONScraper()

    try:
        scraper.init_driver()

        # Test with women's dresses (good for VTON)
        categories = [
            "https://www.zalando.co.uk/womens-clothing-dresses/",
            # Add more categories here
        ]

        for category_url in categories:
            scraper.scrape_zalando_category(category_url, max_items=5)  # Test with 5 items

        print("\n" + "="*80)
        print("SCRAPING COMPLETE!")
        print("="*80)
        print(f"Total items scraped: {scraper.items_scraped}")
        print(f"Output: {scraper.output_dir.absolute()}")
        print(f"\nCheck folders:")
        print(f"  - cloth_images/: {len(list((scraper.output_dir / 'cloth_images').glob('*.jpg')))} files")
        print(f"  - model_images/: {len(list((scraper.output_dir / 'model_images').glob('*.jpg')))} files")

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

    finally:
        scraper.close()


if __name__ == "__main__":
    main()
