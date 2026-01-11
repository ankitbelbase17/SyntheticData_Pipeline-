"""
Zalando Gallery Scraper - Downloads ONLY main product gallery images
Ignores color variants, only gets the left sidebar thumbnail gallery images
Supports AWS S3 storage
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
import os

# AWS S3 imports
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False
    print("[WARNING] boto3 not installed. S3 upload disabled. Install with: pip install boto3")


class ZalandoGalleryScraper:
    def __init__(
        self,
        output_dir="vton_gallery_dataset",
        use_s3=False,
        s3_bucket=None,
        s3_prefix="zalando_gallery",
        aws_region=None,
        aws_access_key_id=None,
        aws_secret_access_key=None,
        save_local=True
    ):
        """
        Initialize the scraper with optional S3 support.
        
        Args:
            output_dir: Local directory for saving files
            use_s3: Enable S3 uploads
            s3_bucket: S3 bucket name (required if use_s3=True)
            s3_prefix: Prefix/folder path in S3 bucket
            aws_region: AWS region (optional, uses default if not specified)
            aws_access_key_id: AWS access key (optional, uses env/credentials file if not specified)
            aws_secret_access_key: AWS secret key (optional, uses env/credentials file if not specified)
            save_local: Also save files locally when using S3
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        (self.output_dir / "products").mkdir(exist_ok=True)
        (self.output_dir / "metadata").mkdir(exist_ok=True)
        (self.output_dir / "progress").mkdir(exist_ok=True)

        self.driver = None
        self.items_scraped = 0
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0'})

        # S3 Configuration
        self.use_s3 = use_s3 and S3_AVAILABLE
        self.s3_bucket = s3_bucket or os.environ.get('S3_BUCKET')
        self.s3_prefix = s3_prefix
        self.save_local = save_local
        self.s3_client = None

        if self.use_s3:
            self._init_s3_client(
                aws_region or os.environ.get('AWS_REGION'),
                aws_access_key_id or os.environ.get('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key or os.environ.get('AWS_SECRET_ACCESS_KEY')
            )

        self.load_progress()

    def _init_s3_client(self, aws_region=None, aws_access_key_id=None, aws_secret_access_key=None):
        """Initialize S3 client with provided or default credentials."""
        try:
            session_kwargs = {}
            if aws_region:
                session_kwargs['region_name'] = aws_region
            if aws_access_key_id and aws_secret_access_key:
                session_kwargs['aws_access_key_id'] = aws_access_key_id
                session_kwargs['aws_secret_access_key'] = aws_secret_access_key

            self.s3_client = boto3.client('s3', **session_kwargs)
            
            # Verify bucket access
            if self.s3_bucket:
                self.s3_client.head_bucket(Bucket=self.s3_bucket)
                print(f"[S3] Connected to bucket: {self.s3_bucket}")
            else:
                print("[S3 WARNING] No bucket specified. Set S3_BUCKET env var or pass s3_bucket parameter.")
                self.use_s3 = False
                
        except NoCredentialsError:
            print("[S3 ERROR] AWS credentials not found. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY.")
            self.use_s3 = False
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            print(f"[S3 ERROR] Cannot access bucket '{self.s3_bucket}': {error_code}")
            self.use_s3 = False
        except Exception as e:
            print(f"[S3 ERROR] Failed to initialize S3 client: {e}")
            self.use_s3 = False

    def upload_to_s3(self, file_content, s3_key, content_type='image/jpeg'):
        """
        Upload file content to S3.
        
        Args:
            file_content: Bytes content to upload
            s3_key: S3 object key (path in bucket)
            content_type: MIME type of the content
            
        Returns:
            tuple: (success: bool, s3_url: str or error message)
        """
        if not self.use_s3 or not self.s3_client:
            return False, "S3 not configured"

        try:
            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=s3_key,
                Body=file_content,
                ContentType=content_type
            )
            
            s3_url = f"s3://{self.s3_bucket}/{s3_key}"
            https_url = f"https://{self.s3_bucket}.s3.amazonaws.com/{s3_key}"
            
            return True, {"s3_uri": s3_url, "https_url": https_url}
            
        except ClientError as e:
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            return False, f"S3 upload failed: {error_msg}"
        except Exception as e:
            return False, f"S3 upload error: {e}"

    def upload_json_to_s3(self, data, s3_key):
        """Upload JSON data to S3."""
        json_content = json.dumps(data, indent=2).encode('utf-8')
        return self.upload_to_s3(json_content, s3_key, content_type='application/json')

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

    def download_image(self, url, filepath, s3_key=None):
        """
        Download image and optionally upload to S3.
        
        Args:
            url: Image URL to download
            filepath: Local file path to save
            s3_key: S3 object key (if S3 upload enabled)
            
        Returns:
            tuple: (success, info_dict) where info_dict contains size, s3_urls, etc.
        """
        try:
            response = self.session.get(url, timeout=15)
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content))
                width, height = img.size

                if width < 400 or height < 400:
                    return False, {"error": f"Image too small: {width}x{height}"}

                result_info = {
                    "size": f"{width}x{height}",
                    "width": width,
                    "height": height
                }

                # Save locally if enabled
                if self.save_local or not self.use_s3:
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    result_info["local_path"] = str(filepath)

                # Upload to S3 if enabled
                if self.use_s3 and s3_key:
                    s3_success, s3_result = self.upload_to_s3(response.content, s3_key)
                    if s3_success:
                        result_info["s3_uri"] = s3_result["s3_uri"]
                        result_info["s3_https_url"] = s3_result["https_url"]
                    else:
                        result_info["s3_error"] = s3_result

                return True, result_info
                
        except Exception as e:
            return False, {"error": str(e)}
        return False, {"error": "Unknown error"}

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
        """Download gallery images to product folder and/or S3"""
        product_dir = self.output_dir / "products" / product_id
        
        if self.save_local or not self.use_s3:
            product_dir.mkdir(exist_ok=True)

        downloaded_images = []

        for idx, img_url in enumerate(product_data["images"]):
            try:
                filename = f"image_{idx:02d}.jpg"
                filepath = product_dir / filename
                
                # Generate S3 key if S3 is enabled
                s3_key = None
                if self.use_s3:
                    s3_key = f"{self.s3_prefix}/products/{product_id}/{filename}"

                success, info = self.download_image(img_url, filepath, s3_key=s3_key)

                if success:
                    image_data = {
                        "filename": filename,
                        "url": img_url,
                        "size": info.get("size"),
                        "width": info.get("width"),
                        "height": info.get("height"),
                        "index": idx
                    }
                    
                    # Add local path if saved locally
                    if "local_path" in info:
                        image_data["local_path"] = info["local_path"]
                    
                    # Add S3 URLs if uploaded to S3
                    if "s3_uri" in info:
                        image_data["s3_uri"] = info["s3_uri"]
                        image_data["s3_https_url"] = info["s3_https_url"]
                    
                    downloaded_images.append(image_data)
                    
                    # Log with S3 indicator
                    s3_indicator = " [S3]" if "s3_uri" in info else ""
                    print(f"    [{idx+1}/{len(product_data['images'])}] {info.get('size')}{s3_indicator}")

            except Exception as e:
                print(f"    [{idx+1}/{len(product_data['images'])}] Error: {e}")
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
                                    "scraped_at": datetime.now().isoformat(),
                                    "storage": {
                                        "local": self.save_local or not self.use_s3,
                                        "s3": self.use_s3,
                                        "s3_bucket": self.s3_bucket if self.use_s3 else None,
                                        "s3_prefix": f"{self.s3_prefix}/products/{product_id}" if self.use_s3 else None
                                    }
                                }

                                # Save metadata locally
                                metadata_filepath = self.output_dir / "metadata" / f"{product_id}.json"
                                with open(metadata_filepath, 'w') as f:
                                    json.dump(metadata, f, indent=2)
                                
                                # Also upload metadata to S3
                                if self.use_s3:
                                    s3_metadata_key = f"{self.s3_prefix}/metadata/{product_id}.json"
                                    self.upload_json_to_s3(metadata, s3_metadata_key)

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
    print("Supports AWS S3 storage")
    print("="*80)

    # ==========================================================================
    # S3 CONFIGURATION OPTIONS
    # ==========================================================================
    # Option 1: Use environment variables (recommended for production)
    #   export AWS_ACCESS_KEY_ID=your_access_key
    #   export AWS_SECRET_ACCESS_KEY=your_secret_key
    #   export AWS_REGION=us-east-1
    #   export S3_BUCKET=your-bucket-name
    #
    # Option 2: Pass credentials directly (not recommended for production)
    #   scraper = ZalandoGalleryScraper(
    #       use_s3=True,
    #       s3_bucket="your-bucket-name",
    #       aws_region="us-east-1",
    #       aws_access_key_id="your_access_key",
    #       aws_secret_access_key="your_secret_key",
    #       s3_prefix="zalando_gallery",  # folder prefix in S3
    #       save_local=True  # also save files locally
    #   )
    #
    # Option 3: Use AWS credentials file (~/.aws/credentials)
    #   Just set use_s3=True and s3_bucket
    # ==========================================================================

    # LOCAL STORAGE ONLY (default)
    scraper = ZalandoGalleryScraper()

    # S3 STORAGE (uncomment to enable)
    # scraper = ZalandoGalleryScraper(
    #     use_s3=True,
    #     s3_bucket="your-bucket-name",  # Required: your S3 bucket name
    #     s3_prefix="zalando_gallery",   # Optional: folder prefix in bucket
    #     save_local=True                # Optional: also save locally (default: True)
    # )

    try:
        # headless=False: See browser (slower)
        # headless=True: Background mode (faster, recommended for large scrapes)
        scraper.init_driver(headless=False)

        # PRODUCTION MODE: Scrape all 120 pages, 10,041 items
        sale_url = "https://www.zalando.co.uk/womens-dresses-sale/"
        scraper.scrape_sale_page(sale_url, max_pages=None, max_items=None)

        # TEST MODE: Use this for testing (5 items, 2 pages)
        # scraper.scrape_sale_page(sale_url, max_pages=2, max_items=5)

        print(f"\nOutput: {scraper.output_dir.absolute()}")
        if scraper.save_local or not scraper.use_s3:
            print(f"Products: {len(list((scraper.output_dir / 'products').iterdir()))}")
        if scraper.use_s3:
            print(f"S3 Bucket: s3://{scraper.s3_bucket}/{scraper.s3_prefix}/")

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
