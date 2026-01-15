"""
Zalando Gallery Scraper with AWS S3 Support - EC2 Optimized
Optimized for running on AWS EC2 instances with Chrome in headless mode
Downloads ONLY main product gallery images and saves to AWS S3
Handles EC2-specific requirements (no display server, optimized for server environment)

SETUP FOR EC2:
1. Install Chrome: sudo yum install google-chrome-stable (Amazon Linux) or
                   sudo apt-get install google-chrome-stable (Ubuntu)
2. Install ChromeDriver: via webdriver-manager (auto-managed)
3. Attach IAM role with S3 permissions to EC2 instance (no credentials needed)
4. Set environment variables: S3_BUCKET, AWS_REGION (or pass as parameters)
5. Run: python zalando_gallery_scraper_s3_ec2.py
"""

import os
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
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

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ZalandoGalleryScraperEC2:
    def __init__(self, output_dir="/tmp/vton_gallery_dataset", use_s3=True, s3_bucket=None, aws_region=None):
        """
        Initialize Zalando scraper optimized for EC2 with optional S3 support
        
        Args:
            output_dir: Local directory for temporary storage (use /tmp on EC2)
            use_s3: If True, save to AWS S3; otherwise save locally
            s3_bucket: S3 bucket name (or set S3_BUCKET env var)
            aws_region: AWS region (or set AWS_REGION env var)
        """
        self.use_s3 = use_s3
        self.s3_bucket = s3_bucket or os.environ.get('S3_BUCKET')
        self.aws_region = aws_region or os.environ.get('AWS_REGION')
        self.output_dir = Path(output_dir)
        
        # Create local directories
        self.output_dir.mkdir(exist_ok=True, parents=True)
        (self.output_dir / "products").mkdir(exist_ok=True)
        (self.output_dir / "metadata").mkdir(exist_ok=True)
        (self.output_dir / "progress").mkdir(exist_ok=True)

        self.driver = None
        self.items_scraped = 0
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

        # Initialize S3 client if enabled
        if self.use_s3:
            if not self.s3_bucket:
                logger.warning("S3 bucket not specified. Set S3_BUCKET env var or pass s3_bucket parameter.")
                logger.warning("Falling back to local storage.")
                self.use_s3 = False
                self.s3_client = None
            else:
                try:
                    # Use IAM role credentials (automatically picked up on EC2)
                    self.s3_client = boto3.client(
                        's3',
                        region_name=self.aws_region
                    )
                    logger.info("Using IAM role for S3 authentication")
                    logger.info(f"Connected to S3 bucket: {self.s3_bucket}")
                    self._verify_s3_access()
                except ClientError as e:
                    logger.warning(f"Failed to connect to S3: {e}")
                    logger.warning("Falling back to local storage.")
                    self.use_s3 = False
                    self.s3_client = None
        else:
            self.s3_client = None

        self.load_progress()

    def _verify_s3_access(self):
        """Verify S3 credentials and bucket access"""
        try:
            self.s3_client.head_bucket(Bucket=self.s3_bucket)
            logger.info("S3 bucket access verified")
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.error(f"S3 bucket {self.s3_bucket} does not exist")
                raise
            elif e.response['Error']['Code'] == '403':
                logger.error(f"Access denied to S3 bucket {self.s3_bucket}")
                raise
            else:
                logger.error(f"Error accessing S3: {e}")
                raise

    def load_progress(self):
        """Load scraping progress from local storage"""
        progress_file = self.output_dir / "progress" / "scraper_progress.json"
        if progress_file.exists():
            try:
                with open(progress_file, 'r') as f:
                    data = json.load(f)
                    self.items_scraped = data.get("items_scraped", 0)
                    self.scraped_urls = set(data.get("scraped_urls", []))
                    logger.info(f"[RESUME] {self.items_scraped} items already scraped")
            except Exception as e:
                logger.warning(f"Could not load progress: {e}")
                self.scraped_urls = set()
        else:
            self.scraped_urls = set()

    def save_progress(self):
        """Save scraping progress to local storage"""
        progress_file = self.output_dir / "progress" / "scraper_progress.json"
        try:
            with open(progress_file, 'w') as f:
                json.dump({
                    "items_scraped": self.items_scraped,
                    "scraped_urls": list(self.scraped_urls),
                    "last_updated": datetime.now().isoformat()
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save progress: {e}")

    def init_driver(self):
        """Initialize Chrome driver optimized for EC2 headless environment"""
        logger.info("Initializing Chrome WebDriver for EC2 (headless mode)...")
        
        chrome_options = Options()
        
        # EC2-specific headless options
        chrome_options.add_argument('--headless=new')  # Modern headless mode
        chrome_options.add_argument('--no-sandbox')     # Required for root/non-privileged user
        chrome_options.add_argument('--disable-dev-shm-usage')  # Overcome limited resource problems
        chrome_options.add_argument('--disable-gpu')    # GPU not available on most EC2
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-plugins')
        
        # Disable Automation Control Features
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Window size for headless rendering
        chrome_options.add_argument('--window-size=1920,1080')
        
        # User agent (Linux user agent for EC2)
        chrome_options.add_argument(
            'user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        # Additional performance options
        chrome_options.add_argument('--disable-sync')
        chrome_options.add_argument('--disable-translate')
        chrome_options.add_argument('--disable-default-apps')
        
        try:
            # Use webdriver-manager to auto-manage ChromeDriver
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.set_page_load_timeout(30)
            self.driver.implicitly_wait(10)
            
            logger.info("Chrome WebDriver initialized successfully (headless mode)")
            return self.driver
            
        except Exception as e:
            logger.error(f"Failed to initialize ChromeDriver: {e}")
            logger.error("Ensure Chrome is installed: sudo yum install google-chrome-stable")
            raise

    def random_delay(self, min_sec=2, max_sec=4):
        """Random delay to avoid detection"""
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)

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
                self.s3_bucket,
                s3_key,
                ExtraArgs={'ContentType': 'application/octet-stream'}
            )
            logger.debug(f"Uploaded to S3: s3://{self.s3_bucket}/{s3_key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to upload {s3_key} to S3: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error uploading {s3_key}: {e}")
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
                    # Delete local file after successful S3 upload to save EC2 disk space
                    try:
                        filepath.unlink()
                        logger.debug(f"Deleted local file: {filepath}")
                    except Exception as e:
                        logger.debug(f"Could not delete local file: {e}")

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
        product_dir.mkdir(exist_ok=True, parents=True)

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
                        "s3_key": s3_key if self.use_s3 else None,
                        "storage": "s3" if self.use_s3 else "local"
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
        logger.info(f"Max Pages: {max_pages}, Max Items: {max_items}")
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

            # Incremental pagination: keep requesting pages until no new products are found
            # This is more robust than detecting total pages from pagination buttons
            items_this_run = 0
            page_num = 1
            consecutive_empty_pages = 0

            while True:
                if max_items and items_this_run >= max_items:
                    logger.info(f"Reached max_items limit ({max_items})")
                    break
                if max_pages and page_num > max_pages:
                    logger.info(f"Reached max_pages limit ({max_pages})")
                    break
                # Stop after 3 consecutive pages with no new products
                if consecutive_empty_pages >= 3:
                    logger.info("No new products found for 3 consecutive pages — stopping.")
                    break

                logger.info(f"\n{'='*80}")
                logger.info(f"PAGE {page_num}")
                logger.info(f"{'='*80}")

                if page_num == 1:
                    page_url = sale_url
                else:
                    sep = '&' if '?' in sale_url else '?'
                    page_url = f"{sale_url}{sep}p={page_num}"
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

                logger.info(f"Found {len(product_links)} products on page {page_num}")

                # Stop if no products at all on this page
                if not product_links:
                    logger.info("No products found on this page — stopping pagination.")
                    break

                # Check for new (unscraped) products
                new_links = [l for l in product_links if l not in self.scraped_urls]
                if not new_links:
                    consecutive_empty_pages += 1
                    logger.info(f"No new products on page {page_num} (consecutive empty: {consecutive_empty_pages})")
                    page_num += 1
                    continue
                else:
                    consecutive_empty_pages = 0

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
                                    "source": "zalando_gallery_ec2",
                                    "title": product_data["title"],
                                    "url": product_url,
                                    "product_directory": str(self.output_dir / "products" / product_id),
                                    "images": downloaded,
                                    "total_images": len(downloaded),
                                    "scraped_at": datetime.now().isoformat(),
                                    "environment": "ec2",
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
                                    # Delete local metadata after S3 upload to save space
                                    try:
                                        metadata_file.unlink()
                                    except:
                                        pass

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

                page_num += 1

            logger.info(f"\n{'='*80}")
            logger.info(f"COMPLETE! Items scraped this run: {items_this_run}")
            logger.info(f"Total items scraped: {self.items_scraped}")
            logger.info(f"{'='*80}")

        except Exception as e:
            logger.error(f"\nError: {e}")
            import traceback
            traceback.print_exc()

    def close(self):
        """Clean up resources"""
        self.save_progress()
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Chrome WebDriver closed")
            except Exception as e:
                logger.warning(f"Error closing driver: {e}")
        self.session.close()
        logger.info("Scraper closed successfully")


def main():
    logger.info("="*80)
    logger.info("ZALANDO GALLERY SCRAPER - EC2 OPTIMIZED")
    logger.info("Downloads ONLY main product gallery images (left sidebar)")
    logger.info("Chrome runs in HEADLESS mode - optimized for EC2 server environment")
    logger.info("Saves to AWS S3 bucket with auto-cleanup of local files")
    logger.info("="*80)

    # ==========================================================================
    # CONFIGURATION
    # ==========================================================================
    # Set these via environment variables or pass directly:
    #   export S3_BUCKET=your-bucket-name
    #   export AWS_REGION=us-east-1  (optional)
    # ==========================================================================

    # Use S3 by default, set to False for local-only mode
    use_s3 = True

    # Use home directory for EC2 storage (or /tmp if space is concern with S3 enabled)
    # Files are deleted after S3 upload, so /tmp won't fill up when use_s3=True
    output_dir = os.path.expanduser("/tmp/vton_gallery_dataset")

    # S3 bucket name (from env var or specify directly)
    s3_bucket = "my-scrapped-images"# Or set directly: "your-bucket-name"
    aws_region = "ap-south-1"  # Optional

    scraper = ZalandoGalleryScraperEC2(
        output_dir=output_dir,
        use_s3=use_s3,
        s3_bucket=s3_bucket,
        aws_region=aws_region
    )

    try:
        scraper.init_driver()

        sale_url = "https://www.zalando.co.uk/womens-dresses-sale/"
        
        # PRODUCTION MODE: Scrape all pages and unlimited items
        scraper.scrape_sale_page(sale_url, max_pages=None, max_items=None)

        # TEST MODE: 10 items, 2 pages (uncomment for testing)
        # scraper.scrape_sale_page(sale_url, max_pages=2, max_items=10)

        logger.info(f"\n[SUMMARY]")
        logger.info(f"Output directory: {scraper.output_dir.absolute()}")
        logger.info(f"Items scraped: {scraper.items_scraped}")
        if use_s3:
            logger.info(f"S3 Bucket: {scraper.s3_bucket}")
            logger.info(f"S3 Region: {scraper.aws_region}")
        else:
            logger.info(f"Storage: Local ({scraper.output_dir.absolute()})")

    except KeyboardInterrupt:
        logger.info("\n[INTERRUPTED BY USER]")

    except Exception as e:
        logger.error(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        scraper.close()


if __name__ == "__main__":
    main()
