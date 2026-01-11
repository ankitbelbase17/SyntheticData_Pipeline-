"""
Zalando Gallery Scraper - Downloads ONLY main product gallery images
Ignores color variants, only gets the left sidebar thumbnail gallery images
"""

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import requests
from pathlib import Path
from PIL import Image
from io import BytesIO
import json
import random
from datetime import datetime
import re


class ZalandoGalleryScraper:
    def __init__(self, output_dir="vton_gallery_dataset"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        (self.output_dir / "products").mkdir(exist_ok=True)
        (self.output_dir / "metadata").mkdir(exist_ok=True)
        (self.output_dir / "progress").mkdir(exist_ok=True)

        self.driver = None
        self.items_scraped = 0
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0'})

        self.load_progress()

    def load_progress(self):
        progress_file = self.output_dir / "progress" / "scraper_progress.json"
        if progress_file.exists():
            with open(progress_file, 'r') as f:
                data = json.load(f)
                self.items_scraped = data.get("items_scraped", 0)
                self.scraped_urls = set(data.get("scraped_urls", []))
                print(f"[RESUME] {self.items_scraped} items already scraped")
        else:
            self.scraped_urls = set()

    def save_progress(self):
        progress_file = self.output_dir / "progress" / "scraper_progress.json"
        with open(progress_file, 'w') as f:
            json.dump({
                "items_scraped": self.items_scraped,
                "scraped_urls": list(self.scraped_urls),
                "last_updated": datetime.now().isoformat()
            }, f, indent=2)

    def init_driver(self, headless=False):
        options = uc.ChromeOptions()
        if headless:
            options.add_argument('--headless=new')
        options.add_argument('--disable-blink-features=AutomationControlled')
        self.driver = uc.Chrome(options=options, version_main=None)
        self.driver.set_page_load_timeout(30)
        if not headless:
            self.driver.maximize_window()
        return self.driver

    def random_delay(self, min_sec=2, max_sec=4):
        time.sleep(random.uniform(min_sec, max_sec))

    def download_image(self, url, filepath):
        try:
            response = self.session.get(url, timeout=15)
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content))
                width, height = img.size

                if width < 400 or height < 400:
                    return False, f"{width}x{height}"

                with open(filepath, 'wb') as f:
                    f.write(response.content)

                return True, f"{width}x{height}"
        except Exception as e:
            return False, str(e)
        return False, "Unknown error"

    def extract_product_id_from_url(self, url):
        match = re.search(r'([a-z0-9\-]+)\.html', url)
        if match:
            return match.group(1)
        return None

    def get_gallery_images_only(self, product_url):
        """
        Extract ONLY the main product gallery images (left sidebar thumbnails)
        Ignores color variant images
        """
        try:
            print(f"\n  Loading product page...")
            self.driver.get(product_url)
            self.random_delay(3, 5)

            # Get product title
            try:
                title = self.driver.find_element(By.CSS_SELECTOR, "h1").text
                print(f"  Product: {title[:60]}...")
            except:
                title = "Unknown"

            # Wait for gallery to load
            time.sleep(2)

            # Strategy: Find the left sidebar thumbnail container
            # These thumbnails are the ONLY images we want
            gallery_images = []

            # Method 1: Look for the product media gallery section
            # This is typically in a section with data-testid or specific class
            try:
                # Find thumbnail images - these are in the left sidebar
                # They typically have specific attributes or are in a specific container

                # Look for images that are part of the main product gallery
                # Zalando structure: left sidebar has small thumbnails
                thumbnail_container = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "[data-testid='product_gallery_refactored'] img, " +
                    "[class*='gallery'] img[src*='spp-media-p1'], " +
                    "[class*='thumbnail'] img[src*='spp-media-p1']"
                )

                print(f"  Found {len(thumbnail_container)} thumbnail elements")

                seen_hashes = set()

                for thumb in thumbnail_container:
                    try:
                        src = thumb.get_attribute("src")

                        if not src:
                            continue

                        # Skip if not a product image
                        if "spp-media-p1" not in src:
                            continue

                        # Extract the unique image hash from URL
                        # Example: .../spp-media-p1/abc123def456.../...
                        hash_match = re.search(r'spp-media-p1/([a-f0-9]+)', src)
                        if hash_match:
                            img_hash = hash_match.group(1)

                            # Skip if we've seen this image hash
                            if img_hash in seen_hashes:
                                continue

                            seen_hashes.add(img_hash)

                        # Get high-res version
                        high_res = src.replace("thumb", "org").replace("sq", "org")

                        # Remove URL parameters
                        if ".jpg?" in high_res:
                            high_res = high_res.split(".jpg?")[0] + ".jpg"

                        # Make sure it's not a color swatch (they're usually smaller)
                        # Color swatches have "packshot" in URL but gallery images don't
                        # OR they're in different parts of the URL structure

                        if high_res not in gallery_images:
                            gallery_images.append(high_res)
                            print(f"    Gallery image {len(gallery_images)}: {high_res[:80]}...")

                    except Exception as e:
                        continue

            except Exception as e:
                print(f"  Error finding thumbnails: {e}")

            # Method 2: If method 1 didn't work, try clicking through thumbnails
            if len(gallery_images) < 2:
                print(f"  Trying alternative method...")

                try:
                    # Find clickable thumbnail buttons in left sidebar
                    thumbnails = self.driver.find_elements(
                        By.CSS_SELECTOR,
                        "button img[src*='spp-media-p1'], " +
                        "[role='button'] img[src*='spp-media-p1']"
                    )

                    print(f"  Found {len(thumbnails)} clickable thumbnails")

                    for idx, thumb in enumerate(thumbnails[:15]):  # Max 15 images
                        try:
                            # Scroll thumbnail into view
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", thumb)
                            time.sleep(0.3)

                            # Click thumbnail
                            parent = thumb.find_element(By.XPATH, "./..")
                            parent.click()
                            time.sleep(0.5)

                            # Get the main display image
                            main_image = self.driver.find_element(
                                By.CSS_SELECTOR,
                                "[data-testid='product_gallery_refactored'] img[src*='spp-media-p1']"
                            )

                            src = main_image.get_attribute("src")

                            if src:
                                # Get high-res
                                high_res = src.replace("thumb", "org").replace("sq", "org")

                                if ".jpg?" in high_res:
                                    high_res = high_res.split(".jpg?")[0] + ".jpg"

                                if high_res not in gallery_images:
                                    gallery_images.append(high_res)
                                    print(f"    Gallery image {len(gallery_images)}: {high_res[:80]}...")

                        except Exception as e:
                            continue

                except Exception as e:
                    print(f"  Alternative method error: {e}")

            print(f"\n  Total gallery images: {len(gallery_images)}")

            if len(gallery_images) >= 2:
                return {
                    "title": title,
                    "url": product_url,
                    "images": gallery_images
                }

            return None

        except Exception as e:
            print(f"  Error: {e}")
            return None

    def download_all_gallery_images(self, product_data, product_id):
        """Download gallery images to product folder"""
        product_dir = self.output_dir / "products" / product_id
        product_dir.mkdir(exist_ok=True)

        downloaded_images = []

        for idx, img_url in enumerate(product_data["images"]):
            try:
                filename = f"image_{idx:02d}.jpg"
                filepath = product_dir / filename

                success, info = self.download_image(img_url, filepath)

                if success:
                    downloaded_images.append({
                        "filename": filename,
                        "url": img_url,
                        "size": info,
                        "index": idx
                    })
                    print(f"    [{idx+1}/{len(product_data['images'])}] {info}")

            except Exception as e:
                continue

        return downloaded_images

    def scrape_sale_page(self, sale_url, max_pages=None, max_items=None):
        """Scrape sale page with pagination"""
        print(f"\n{'='*80}")
        print(f"SCRAPING: {sale_url}")
        print(f"{'='*80}")

        try:
            self.driver.get(sale_url)
            self.random_delay(3, 5)

            # Accept cookies
            try:
                accept = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Accept')]")
                accept.click()
                time.sleep(2)
            except:
                pass

            # Detect total pages
            try:
                pagination = self.driver.find_elements(By.CSS_SELECTOR, "[data-testid='pagination'] button")
                if pagination:
                    page_texts = [p.text for p in pagination if p.text.isdigit()]
                    total_pages = max([int(p) for p in page_texts]) if page_texts else 1
                else:
                    total_pages = 1

                print(f"\nDetected {total_pages} pages")

                if max_pages:
                    total_pages = min(total_pages, max_pages)
                    print(f"Limited to {total_pages} pages")

            except:
                total_pages = 1

            items_this_run = 0

            for page_num in range(1, total_pages + 1):
                if max_items and items_this_run >= max_items:
                    break

                print(f"\n{'='*80}")
                print(f"PAGE {page_num}/{total_pages}")
                print(f"{'='*80}")

                if page_num > 1:
                    page_url = f"{sale_url}?p={page_num}"
                    self.driver.get(page_url)
                    self.random_delay(3, 5)

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

                print(f"Found {len(product_links)} products")

                for idx, product_url in enumerate(product_links):
                    if max_items and items_this_run >= max_items:
                        break

                    if product_url in self.scraped_urls:
                        print(f"\n[{idx+1}/{len(product_links)}] Skipping (already scraped)")
                        continue

                    print(f"\n[{idx+1}/{len(product_links)}] Processing...")

                    try:
                        product_id = self.extract_product_id_from_url(product_url)
                        if not product_id:
                            continue

                        # Get ONLY gallery images
                        product_data = self.get_gallery_images_only(product_url)

                        if product_data and len(product_data["images"]) >= 2:
                            downloaded = self.download_all_gallery_images(product_data, product_id)

                            if len(downloaded) >= 2:
                                metadata = {
                                    "item_id": self.items_scraped,
                                    "product_id": product_id,
                                    "source": "zalando_gallery",
                                    "title": product_data["title"],
                                    "url": product_url,
                                    "product_directory": str(self.output_dir / "products" / product_id),
                                    "images": downloaded,
                                    "total_images": len(downloaded),
                                    "scraped_at": datetime.now().isoformat()
                                }

                                with open(self.output_dir / "metadata" / f"{product_id}.json", 'w') as f:
                                    json.dump(metadata, f, indent=2)

                                self.items_scraped += 1
                                items_this_run += 1
                                self.scraped_urls.add(product_url)

                                print(f"  [SUCCESS] Item {self.items_scraped} | {len(downloaded)} gallery images")

                                if self.items_scraped % 10 == 0:
                                    self.save_progress()

                        self.random_delay(2, 4)

                    except Exception as e:
                        print(f"  [ERROR] {e}")
                        continue

            print(f"\n{'='*80}")
            print(f"COMPLETE! Items: {items_this_run}")
            print(f"{'='*80}")

        except Exception as e:
            print(f"\nError: {e}")

    def close(self):
        self.save_progress()
        if self.driver:
            self.driver.quit()
        self.session.close()


def main():
    print("="*80)
    print("ZALANDO GALLERY SCRAPER")
    print("Downloads ONLY main product gallery images (left sidebar)")
    print("Ignores color variant swatches")
    print("="*80)

    scraper = ZalandoGalleryScraper()

    try:
        scraper.init_driver(headless=False)

        # TEST: 2 pages, 5 items
        sale_url = "https://www.zalando.co.uk/womens-dresses-sale/"
        scraper.scrape_sale_page(sale_url, max_pages=2, max_items=5)

        # PRODUCTION: Uncomment below for full scrape
        # scraper.scrape_sale_page(sale_url, max_pages=None, max_items=None)

        print(f"\nOutput: {scraper.output_dir.absolute()}")
        print(f"Products: {len(list((scraper.output_dir / 'products').iterdir()))}")

    except KeyboardInterrupt:
        print("\n[INTERRUPTED]")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

    finally:
        scraper.close()


if __name__ == "__main__":
    main()
