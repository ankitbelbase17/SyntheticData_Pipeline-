"""
Zalando Gallery Scraper with AWS S3 Support
Downloads ONLY main product gallery images and saves to AWS S3
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
import boto3
from botocore.exceptions import ClientError
import logging

# Import config
import sys
sys.path.insert(0, '..')
from config import AWS_S3_BUCKET, AWS_S3_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ZalandoGalleryScraper:
    def __init__(self, output_dir="vton_gallery_dataset", use_s3=True):
        """
        Initialize Zalando scraper with optional S3 support
        
        Args:
            output_dir: Local directory for temporary storage
            use_s3: If True, save to AWS S3; otherwise save locally
        """
        self.use_s3 = use_s3
        self.output_dir = Path(output_dir)
        
        # Create local directories
        self.output_dir.mkdir(exist_ok=True)
        (self.output_dir / "products").mkdir(exist_ok=True)
        (self.output_dir / "metadata").mkdir(exist_ok=True)
        (self.output_dir / "progress").mkdir(exist_ok=True)

        self.driver = None
        self.items_scraped = 0
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0'})

        # Initialize S3 client if enabled
        if self.use_s3:
            try:
                self.s3_client = boto3.client(
                    's3',
                    region_name=AWS_S3_REGION,
                    aws_access_key_id=AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
                )
                logger.info(f"Connected to S3 bucket: {AWS_S3_BUCKET}")
                self._verify_s3_access()
            except ClientError as e:
                logger.error(f"Failed to connect to S3: {e}")
                raise
        else:
            self.s3_client = None

        self.load_progress()

    def _verify_s3_access(self):
        """Verify S3 credentials and bucket access"""
        try:
            self.s3_client.head_bucket(Bucket=AWS_S3_BUCKET)
            logger.info("S3 bucket access verified")
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.error(f"S3 bucket {AWS_S3_BUCKET} does not exist")
                raise
            elif e.response['Error']['Code'] == '403':
                logger.error(f"Access denied to S3 bucket {AWS_S3_BUCKET}")
                raise
            else:
                logger.error(f"Error accessing S3: {e}")
                raise

    def load_progress(self):
        """Load scraping progress from local storage"""
        progress_file = self.output_dir / "progress" / "scraper_progress.json"
        if progress_file.exists():
            with open(progress_file, 'r') as f:
                data = json.load(f)
                self.items_scraped = data.get("items_scraped", 0)
                self.scraped_urls = set(data.get("scraped_urls", []))
                logger.info(f"[RESUME] {self.items_scraped} items already scraped")
        else:
            self.scraped_urls = set()

    def save_progress(self):
        """Save scraping progress to local storage"""
        progress_file = self.output_dir / "progress" / "scraper_progress.json"
        with open(progress_file, 'w') as f:
            json.dump({
                "items_scraped": self.items_scraped,
                "scraped_urls": list(self.scraped_urls),
                "last_updated": datetime.now().isoformat()
            }, f, indent=2)

    def init_driver(self, headless=False):
        """Initialize undetected Chrome driver"""
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
        """Random delay to avoid detection"""
        time.sleep(random.uniform(min_sec, max_sec))

    def upload_to_s3(self, file_path, s3_key):
        """
        Upload file to S3
        
        Args:
            file_path: Local file path
            s3_key: S3 object key (path in bucket)
        
        Returns:
            bool: True if successful
        """
        if not self.use_s3:
            return True

        try:
            self.s3_client.upload_file(
                str(file_path),
                AWS_S3_BUCKET,
                s3_key,
                ExtraArgs={'ContentType': 'application/octet-stream'}
            )
            logger.debug(f"Uploaded to S3: s3://{AWS_S3_BUCKET}/{s3_key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to upload {s3_key} to S3: {e}")
            return False

    def download_image(self, url, filepath, s3_key=None):
        """
        Download image and optionally save to S3
        
        Args:
            url: Image URL
            filepath: Local file path
            s3_key: S3 object key (if saving to S3)
        
        Returns:
            tuple: (success, info)
        """
        try:
            response = self.session.get(url, timeout=15)
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content))
                width, height = img.size

                if width < 400 or height < 400:
                    return False, f"{width}x{height}"

                # Save locally first
                filepath.parent.mkdir(parents=True, exist_ok=True)
                with open(filepath, 'wb') as f:
                    f.write(response.content)

                # Upload to S3 if enabled
                if self.use_s3 and s3_key:
                    if not self.upload_to_s3(filepath, s3_key):
                        return False, "S3 upload failed"

                return True, f"{width}x{height}"
        except Exception as e:
            logger.error(f"Error downloading {url}: {e}")
            return False, str(e)
        return False, "Unknown error"

    def extract_product_id_from_url(self, url):
        """Extract product ID from Zalando URL"""
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
            logger.info(f"  Loading product page...")
            self.driver.get(product_url)
            self.random_delay(3, 5)

            # Get product title
            try:
                title = self.driver.find_element(By.CSS_SELECTOR, "h1").text
                logger.info(f"  Product: {title[:60]}...")
            except:
                title = "Unknown"

            time.sleep(2)

            gallery_images = []
            seen_hashes = set()

            # Method 1: Find thumbnail images in left sidebar
            try:
                thumbnail_container = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "[data-testid='product_gallery_refactored'] img, " +
                    "[class*='gallery'] img[src*='spp-media-p1'], " +
                    "[class*='thumbnail'] img[src*='spp-media-p1']"
                )

                logger.info(f"  Found {len(thumbnail_container)} thumbnail elements")

                for thumb in thumbnail_container:
                    try:
                        src = thumb.get_attribute("src")

                        if not src or "spp-media-p1" not in src:
                            continue

                        # Extract unique image hash
                        hash_match = re.search(r'spp-media-p1/([a-f0-9]+)', src)
                        if hash_match:
                            img_hash = hash_match.group(1)
                            if img_hash in seen_hashes:
                                continue
                            seen_hashes.add(img_hash)

                        # Get high-res version
                        high_res = src.replace("thumb", "org").replace("sq", "org")
                        if ".jpg?" in high_res:
                            high_res = high_res.split(".jpg?")[0] + ".jpg"

                        if high_res not in gallery_images:
                            gallery_images.append(high_res)
                            logger.debug(f"    Gallery image {len(gallery_images)}: {high_res[:80]}...")

                    except Exception as e:
                        logger.debug(f"Error processing thumbnail: {e}")
                        continue

            except Exception as e:
                logger.error(f"  Error finding thumbnails: {e}")

            # Method 2: Click through thumbnails if method 1 didn't work
            if len(gallery_images) < 2:
                logger.info(f"  Trying alternative method...")
                try:
                    thumbnails = self.driver.find_elements(
                        By.CSS_SELECTOR,
                        "button img[src*='spp-media-p1'], " +
                        "[role='button'] img[src*='spp-media-p1']"
                    )

                    logger.info(f"  Found {len(thumbnails)} clickable thumbnails")

                    for idx, thumb in enumerate(thumbnails[:15]):
                        try:
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", thumb)
                            time.sleep(0.3)

                            parent = thumb.find_element(By.XPATH, "./..")
                            parent.click()
                            time.sleep(0.5)

                            main_image = self.driver.find_element(
                                By.CSS_SELECTOR,
                                "[data-testid='product_gallery_refactored'] img[src*='spp-media-p1']"
                            )

                            src = main_image.get_attribute("src")
                            if src:
                                high_res = src.replace("thumb", "org").replace("sq", "org")
                                if ".jpg?" in high_res:
                                    high_res = high_res.split(".jpg?")[0] + ".jpg"

                                if high_res not in gallery_images:
                                    gallery_images.append(high_res)
                                    logger.debug(f"    Gallery image {len(gallery_images)}: {high_res[:80]}...")

                        except Exception as e:
                            logger.debug(f"Error in alternative method: {e}")
                            continue

                except Exception as e:
                    logger.error(f"  Alternative method error: {e}")

            logger.info(f"\n  Total gallery images: {len(gallery_images)}")

            if len(gallery_images) >= 2:
                return {
                    "title": title,
                    "url": product_url,
                    "images": gallery_images
                }

            return None

        except Exception as e:
            logger.error(f"  Error: {e}")
            return None

    def download_all_gallery_images(self, product_data, product_id):
        """Download gallery images and optionally save to S3"""
        product_dir = self.output_dir / "products" / product_id
        product_dir.mkdir(exist_ok=True)

        downloaded_images = []

        for idx, img_url in enumerate(product_data["images"]):
            try:
                filename = f"image_{idx:02d}.jpg"
                filepath = product_dir / filename
                
                # S3 key: s3://bucket/products/product_id/image_00.jpg
                s3_key = f"products/{product_id}/{filename}" if self.use_s3 else None

                success, info = self.download_image(img_url, filepath, s3_key)

                if success:
                    downloaded_images.append({
                        "filename": filename,
                        "url": img_url,
                        "size": info,
                        "index": idx,
                        "s3_key": s3_key if self.use_s3 else None
                    })
                    logger.info(f"    [{idx+1}/{len(product_data['images'])}] {info}")

            except Exception as e:
                logger.error(f"Error downloading image {idx}: {e}")
                continue

        return downloaded_images

    def scrape_sale_page(self, sale_url, max_pages=None, max_items=None):
        """Scrape sale page with pagination"""
        logger.info(f"\n{'='*80}")
        logger.info(f"SCRAPING: {sale_url}")
        logger.info(f"{'='*80}")

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

                logger.info(f"\nDetected {total_pages} pages")

                if max_pages:
                    total_pages = min(total_pages, max_pages)
                    logger.info(f"Limited to {total_pages} pages")

            except:
                total_pages = 1

            items_this_run = 0

            for page_num in range(1, total_pages + 1):
                if max_items and items_this_run >= max_items:
                    break

                logger.info(f"\n{'='*80}")
                logger.info(f"PAGE {page_num}/{total_pages}")
                logger.info(f"{'='*80}")

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

                logger.info(f"Found {len(product_links)} products")

                for idx, product_url in enumerate(product_links):
                    if max_items and items_this_run >= max_items:
                        break

                    if product_url in self.scraped_urls:
                        logger.info(f"\n[{idx+1}/{len(product_links)}] Skipping (already scraped)")
                        continue

                    logger.info(f"\n[{idx+1}/{len(product_links)}] Processing...")

                    try:
                        product_id = self.extract_product_id_from_url(product_url)
                        if not product_id:
                            continue

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
                                    "scraped_at": datetime.now().isoformat(),
                                    "storage": "s3" if self.use_s3 else "local"
                                }

                                # Save metadata locally
                                metadata_file = self.output_dir / "metadata" / f"{product_id}.json"
                                with open(metadata_file, 'w') as f:
                                    json.dump(metadata, f, indent=2)

                                # Upload metadata to S3 if enabled
                                if self.use_s3:
                                    s3_metadata_key = f"metadata/{product_id}.json"
                                    self.upload_to_s3(metadata_file, s3_metadata_key)

                                self.items_scraped += 1
                                items_this_run += 1
                                self.scraped_urls.add(product_url)

                                logger.info(f"  [SUCCESS] Item {self.items_scraped} | {len(downloaded)} gallery images")

                                if self.items_scraped % 10 == 0:
                                    self.save_progress()

                        self.random_delay(2, 4)

                    except Exception as e:
                        logger.error(f"  [ERROR] {e}")
                        continue

            logger.info(f"\n{'='*80}")
            logger.info(f"COMPLETE! Items: {items_this_run}")
            logger.info(f"{'='*80}")

        except Exception as e:
            logger.error(f"\nError: {e}")

    def close(self):
        """Clean up resources"""
        self.save_progress()
        if self.driver:
            self.driver.quit()
        self.session.close()
        logger.info("Scraper closed")


def main():
    logger.info("="*80)
    logger.info("ZALANDO GALLERY SCRAPER WITH AWS S3 SUPPORT")
    logger.info("Downloads ONLY main product gallery images (left sidebar)")
    logger.info("Saves to AWS S3 bucket")
    logger.info("="*80)

    # Use S3 by default, set to False for local-only mode
    use_s3 = True

    scraper = ZalandoGalleryScraper(use_s3=use_s3)

    try:
        scraper.init_driver(headless=False)

        sale_url = "https://www.zalando.co.uk/womens-dresses-sale/"
        
        # PRODUCTION MODE: Scrape all pages
        # scraper.scrape_sale_page(sale_url, max_pages=None, max_items=None)

        # TEST MODE: 5 items, 2 pages
        scraper.scrape_sale_page(sale_url, max_pages=2, max_items=5)

        logger.info(f"\nOutput: {scraper.output_dir.absolute()}")
        logger.info(f"Products: {len(list((scraper.output_dir / 'products').iterdir()))}")
        if use_s3:
            logger.info(f"S3 Bucket: {AWS_S3_BUCKET}")

    except KeyboardInterrupt:
        logger.info("\n[INTERRUPTED]")

    except Exception as e:
        logger.error(f"\nError: {e}")
        import traceback
        traceback.print_exc()

    finally:
        scraper.close()


if __name__ == "__main__":
    main()
