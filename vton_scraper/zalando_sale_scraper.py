"""
Zalando Sale Scraper - Download ALL images per product with pagination support
Handles: https://www.zalando.co.uk/womens-dresses-sale/ (10,041 items across 120 pages)
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


class ZalandoSaleScraper:
    def __init__(self, output_dir="vton_sale_dataset"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Each product gets its own directory
        (self.output_dir / "products").mkdir(exist_ok=True)
        (self.output_dir / "metadata").mkdir(exist_ok=True)
        (self.output_dir / "progress").mkdir(exist_ok=True)

        self.driver = None
        self.items_scraped = 0
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0'})

        # Load progress
        self.load_progress()

    def load_progress(self):
        """Load previous progress"""
        progress_file = self.output_dir / "progress" / "scraper_progress.json"
        if progress_file.exists():
            with open(progress_file, 'r') as f:
                data = json.load(f)
                self.items_scraped = data.get("items_scraped", 0)
                self.scraped_urls = set(data.get("scraped_urls", []))
                print(f"[RESUME] Loaded progress: {self.items_scraped} items scraped")
        else:
            self.scraped_urls = set()

    def save_progress(self):
        """Save progress"""
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
        """Download and validate image"""
        try:
            response = self.session.get(url, timeout=15)
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content))
                width, height = img.size

                # Accept images >= 300x300 (we want all product images)
                if width < 300 or height < 300:
                    return False, f"{width}x{height}"

                with open(filepath, 'wb') as f:
                    f.write(response.content)

                return True, f"{width}x{height}"
        except Exception as e:
            return False, str(e)
        return False, "Unknown error"

    def extract_product_id_from_url(self, url):
        """Extract unique product ID from URL"""
        # Example: https://www.zalando.co.uk/anna-field-dress-an621c26s-k11.html
        # Extract: an621c26s-k11
        match = re.search(r'([a-z0-9\-]+)\.html', url)
        if match:
            return match.group(1)
        return None

    def get_all_product_images(self, product_url):
        """Extract ALL images (models + cloth) from product page"""
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

            # Wait for images to load
            time.sleep(2)

            # Get ALL product images (not color swatches, not UI elements)
            all_images = []

            # Find all img elements with product images
            img_elements = self.driver.find_elements(By.CSS_SELECTOR, "img[src*='spp-media-p1']")

            print(f"  Found {len(img_elements)} image elements")

            seen_urls = set()

            for img_elem in img_elements:
                try:
                    src = img_elem.get_attribute("src")

                    if not src or src in seen_urls:
                        continue

                    # Skip tiny thumbnails (color swatches)
                    if "thumb" in src and "packshot" not in src:
                        continue

                    seen_urls.add(src)

                    # Get high-res version
                    high_res = src.replace("thumb", "org").replace("sq", "org")

                    # Remove URL parameters
                    if ".jpg?" in high_res:
                        high_res = high_res.split(".jpg?")[0] + ".jpg"

                    # Check if it's a video poster (skip videos)
                    if "video" in src.lower() or ".mp4" in src.lower():
                        continue

                    all_images.append(high_res)

                except Exception as e:
                    continue

            # Remove duplicates while preserving order
            unique_images = []
            for img in all_images:
                if img not in unique_images:
                    unique_images.append(img)

            print(f"  Collected {len(unique_images)} unique images")

            if len(unique_images) >= 2:
                return {
                    "title": title,
                    "url": product_url,
                    "images": unique_images
                }

            return None

        except Exception as e:
            print(f"  Error extracting images: {e}")
            return None

    def download_all_product_images(self, product_data, product_id):
        """Download all images for a product into its own directory"""

        # Create product directory
        product_dir = self.output_dir / "products" / product_id
        product_dir.mkdir(exist_ok=True)

        downloaded_images = []

        for idx, img_url in enumerate(product_data["images"]):
            try:
                # Save with numbered filename
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
                    print(f"    [{idx+1}/{len(product_data['images'])}] Downloaded: {info}")

            except Exception as e:
                print(f"    [{idx+1}/{len(product_data['images'])}] Failed: {e}")
                continue

        return downloaded_images

    def scrape_sale_page(self, sale_url, max_pages=None, max_items=None):
        """
        Scrape sale page with pagination

        Args:
            sale_url: Base URL like https://www.zalando.co.uk/womens-dresses-sale/
            max_pages: Maximum pages to scrape (None = all pages)
            max_items: Maximum items to scrape (None = all items)
        """
        print(f"\n{'='*80}")
        print(f"SCRAPING SALE: {sale_url}")
        print(f"{'='*80}")

        try:
            # Load first page
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
                # Zalando shows pagination info
                pagination = self.driver.find_elements(By.CSS_SELECTOR, "[data-testid='pagination'] button, .cat_page-numbers a")
                if pagination:
                    page_texts = [p.text for p in pagination if p.text.isdigit()]
                    total_pages = max([int(p) for p in page_texts]) if page_texts else 1
                else:
                    total_pages = 1

                print(f"\nDetected {total_pages} total pages")

                if max_pages:
                    total_pages = min(total_pages, max_pages)
                    print(f"Limited to {total_pages} pages")

            except:
                total_pages = 1

            # Scrape each page
            items_on_this_run = 0

            for page_num in range(1, total_pages + 1):
                if max_items and items_on_this_run >= max_items:
                    print(f"\n[TARGET REACHED] {items_on_this_run} items scraped in this run")
                    break

                print(f"\n{'='*80}")
                print(f"PAGE {page_num}/{total_pages}")
                print(f"{'='*80}")

                # Navigate to page
                if page_num > 1:
                    page_url = f"{sale_url}?p={page_num}"
                    self.driver.get(page_url)
                    self.random_delay(3, 5)

                # Scroll to load all products
                for _ in range(3):
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                    time.sleep(1)

                # Get all product links on this page
                product_links = []
                links = self.driver.find_elements(By.CSS_SELECTOR, "article a[href*='.html']")

                for link in links:
                    href = link.get_attribute("href")
                    if href and ".html" in href and href not in product_links:
                        product_links.append(href)

                print(f"Found {len(product_links)} products on page {page_num}")

                # Process each product
                for idx, product_url in enumerate(product_links):
                    if max_items and items_on_this_run >= max_items:
                        break

                    # Skip if already scraped
                    if product_url in self.scraped_urls:
                        print(f"\n[{idx+1}/{len(product_links)}] Skipping (already scraped)")
                        continue

                    print(f"\n[{idx+1}/{len(product_links)}] Processing...")
                    print(f"URL: {product_url[:70]}...")

                    try:
                        # Extract product ID
                        product_id = self.extract_product_id_from_url(product_url)
                        if not product_id:
                            print("  [SKIP] Could not extract product ID")
                            continue

                        # Get all images for this product
                        product_data = self.get_all_product_images(product_url)

                        if product_data and len(product_data["images"]) >= 2:
                            # Download all images to product directory
                            downloaded = self.download_all_product_images(product_data, product_id)

                            if len(downloaded) >= 2:
                                # Save metadata
                                metadata = {
                                    "item_id": self.items_scraped,
                                    "product_id": product_id,
                                    "source": "zalando_sale",
                                    "title": product_data["title"],
                                    "url": product_url,
                                    "product_directory": str(self.output_dir / "products" / product_id),
                                    "images": downloaded,
                                    "total_images": len(downloaded),
                                    "scraped_at": datetime.now().isoformat()
                                }

                                metadata_file = self.output_dir / "metadata" / f"{product_id}.json"
                                with open(metadata_file, 'w') as f:
                                    json.dump(metadata, f, indent=2)

                                self.items_scraped += 1
                                items_on_this_run += 1
                                self.scraped_urls.add(product_url)

                                print(f"  [SUCCESS] Item {self.items_scraped} | Downloaded {len(downloaded)} images")

                                # Save progress every 10 items
                                if self.items_scraped % 10 == 0:
                                    self.save_progress()
                                    print(f"\n[PROGRESS SAVED] {self.items_scraped} items total")

                            else:
                                print(f"  [SKIP] Only {len(downloaded)} images downloaded (need >= 2)")
                        else:
                            print(f"  [SKIP] Not enough images found")

                        self.random_delay(2, 4)

                    except Exception as e:
                        print(f"  [ERROR] {e}")
                        continue

            print(f"\n{'='*80}")
            print(f"SCRAPING COMPLETE!")
            print(f"{'='*80}")
            print(f"Total items scraped: {self.items_scraped}")
            print(f"Items in this run: {items_on_this_run}")

        except Exception as e:
            print(f"\nCritical error: {e}")
            import traceback
            traceback.print_exc()

    def close(self):
        self.save_progress()
        if self.driver:
            self.driver.quit()
        self.session.close()


def main():
    print("="*80)
    print("ZALANDO SALE SCRAPER - ALL IMAGES PER PRODUCT")
    print("="*80)
    print("\nOrganization:")
    print("  products/")
    print("    - product-id-1/")
    print("      - image_00.jpg  (could be model or cloth)")
    print("      - image_01.jpg")
    print("      - image_02.jpg")
    print("    - product-id-2/")
    print("      - image_00.jpg")
    print("      - image_01.jpg")
    print("="*80)

    scraper = ZalandoSaleScraper()

    try:
        scraper.init_driver(headless=False)

        # CONFIGURATION
        sale_url = "https://www.zalando.co.uk/womens-dresses-sale/"

        # For TESTING: Scrape 2 pages, max 10 items
        scraper.scrape_sale_page(sale_url, max_pages=2, max_items=10)

        # For PRODUCTION: Scrape all 120 pages, all 10,041 items
        # scraper.scrape_sale_page(sale_url, max_pages=None, max_items=None)

        print(f"\n{'='*80}")
        print("OUTPUT STRUCTURE:")
        print(f"{'='*80}")
        print(f"Directory: {scraper.output_dir.absolute()}")
        print(f"\nProducts: {len(list((scraper.output_dir / 'products').iterdir()))} folders")
        print(f"Metadata: {len(list((scraper.output_dir / 'metadata').glob('*.json')))} files")

        # Show sample product structure
        products = list((scraper.output_dir / "products").iterdir())
        if products:
            sample = products[0]
            images = list(sample.glob("*.jpg"))
            print(f"\nSample product: {sample.name}")
            print(f"  Images: {len(images)} files")
            for img in images[:3]:
                print(f"    - {img.name}")

    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Saving progress...")
        scraper.save_progress()

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

    finally:
        scraper.close()


if __name__ == "__main__":
    main()
