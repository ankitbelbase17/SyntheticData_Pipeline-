"""NewMoonDance Gallery Scraper - EC2/S3 Version
Optimized for running on AWS EC2 with direct S3 uploads
Downloads product gallery images from Shopify stores and uploads to S3

SETUP FOR EC2:
1. Launch EC2 instance with IAM role that has S3 access
2. Install Chrome:
   sudo apt-get update
   sudo apt-get install -y chromium-browser
3. Install dependencies:
   pip install selenium pillow requests webdriver-manager boto3
4. Run the scraper:
   python test_newmoondance_ec2.py
"""

import time
import random
import json
import re
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from pathlib import Path
from PIL import Image
from io import BytesIO
import logging
import traceback
from datetime import datetime

# AWS S3
try:
    import boto3
    from botocore.exceptions import ClientError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False
    print("WARNING: boto3 not installed. S3 uploads will not work.")

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds
CONNECTION_TIMEOUT = 30

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NewMoonDanceGalleryScraperS3:
    def __init__(self, s3_bucket, s3_prefix="newmoondance_dataset", aws_region="us-east-1"):
        """
        Initialize NewMoonDance scraper for EC2 with S3 uploads

        Args:
            s3_bucket: S3 bucket name for storing images and metadata
            s3_prefix: Prefix (folder) in S3 bucket
            aws_region: AWS region for S3
        """
        if not HAS_BOTO3:
            raise ImportError("boto3 is required for S3 uploads. Install with: pip install boto3")
        
        self.s3_bucket = s3_bucket
        self.s3_prefix = s3_prefix.rstrip('/')
        self.aws_region = aws_region
        
        # Initialize S3 client
        self.s3_client = boto3.client('s3', region_name=aws_region)
        
        # Verify bucket access
        try:
            self.s3_client.head_bucket(Bucket=s3_bucket)
            logger.info(f"S3 bucket verified: s3://{s3_bucket}/{s3_prefix}/")
        except ClientError as e:
            logger.error(f"Cannot access S3 bucket {s3_bucket}: {e}")
            raise

        self.driver = None
        self.items_scraped = 0
        self.session = self._create_session()
        self.consecutive_errors = 0

        # Statistics tracking
        self.stats = {
            'total_pages_explored': 0,
            'total_products_found': 0,
            'total_products_explored': 0,
            'successful_scrapes': 0,
            'failed_scrapes': 0,
            'skipped_already_scraped': 0,
            'total_images_downloaded': 0,
            'start_time': None,
            'end_time': None
        }

        logger.info(f"Storage: AWS S3")
        logger.info(f"S3 Path: s3://{s3_bucket}/{s3_prefix}/")

        self.load_progress()

    def _create_session(self):
        """Create a requests session with retry logic"""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=MAX_RETRIES,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        })
        
        return session

    def _refresh_session(self):
        """Refresh the requests session when connection issues occur"""
        logger.info("  Refreshing HTTP session...")
        try:
            self.session.close()
        except:
            pass
        self.session = self._create_session()
        time.sleep(RETRY_DELAY)

    def _s3_key(self, *parts):
        """Build S3 key from parts"""
        return f"{self.s3_prefix}/{'/'.join(parts)}"

    def _upload_to_s3(self, data, key, content_type='application/octet-stream'):
        """Upload data to S3"""
        try:
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=key,
                Body=data,
                ContentType=content_type
            )
            return True
        except ClientError as e:
            logger.error(f"S3 upload failed for {key}: {e}")
            return False

    def _download_from_s3(self, key):
        """Download data from S3"""
        try:
            response = self.s3_client.get_object(Bucket=self.s3_bucket, Key=key)
            return response['Body'].read()
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                return None
            logger.error(f"S3 download failed for {key}: {e}")
            return None

    def _s3_key_exists(self, key):
        """Check if S3 key exists"""
        try:
            self.s3_client.head_object(Bucket=self.s3_bucket, Key=key)
            return True
        except ClientError:
            return False

    def load_progress(self):
        """Load scraping progress from S3"""
        self.scraped_urls = set()

        progress_key = self._s3_key("progress", "scraper_progress.json")
        data = self._download_from_s3(progress_key)
        
        if data:
            try:
                progress = json.loads(data.decode('utf-8'))
                self.items_scraped = progress.get("items_scraped", 0)
                self.scraped_urls = set(progress.get("scraped_urls", []))
                logger.info(f"[RESUME] {self.items_scraped} items already scraped, {len(self.scraped_urls)} URLs tracked")
            except Exception as e:
                logger.warning(f"Could not load progress: {e}")
                self.scraped_urls = set()
        else:
            logger.info("[NEW SESSION] No previous progress found")

    def save_progress(self):
        """Save scraping progress to S3"""
        progress_key = self._s3_key("progress", "scraper_progress.json")
        progress_data = {
            "items_scraped": self.items_scraped,
            "scraped_urls": list(self.scraped_urls),
            "last_updated": datetime.now().isoformat(),
            "total_urls_tracked": len(self.scraped_urls),
            "storage_mode": "s3",
            "s3_bucket": self.s3_bucket,
            "s3_prefix": self.s3_prefix
        }

        if self._upload_to_s3(json.dumps(progress_data, indent=2), progress_key, 'application/json'):
            logger.debug(f"Progress saved to S3: {self.items_scraped} items")
        else:
            logger.error("Failed to save progress to S3")

    def init_driver(self):
        """Initialize Chrome driver for EC2 (headless)"""
        logger.info("Initializing Chrome WebDriver for EC2...")

        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.chrome.options import Options

            chrome_options = Options()

            # EC2 headless options
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument(
                'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )

            # Additional EC2 stability options
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-plugins')
            chrome_options.add_argument('--disable-sync')
            chrome_options.add_argument('--disable-translate')
            chrome_options.add_argument('--disable-default-apps')
            chrome_options.add_argument('--no-first-run')
            chrome_options.add_argument('--no-default-browser-check')
            chrome_options.add_argument('--single-process')
            chrome_options.add_argument('--disable-setuid-sandbox')

            # Try webdriver-manager first, then system chromium
            try:
                from webdriver_manager.chrome import ChromeDriverManager
                from webdriver_manager.core.os_manager import ChromeType
                service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            except Exception:
                # Fallback to system chromedriver
                try:
                    service = Service('/usr/bin/chromedriver')
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                except Exception:
                    # Last resort - let Selenium find it
                    self.driver = webdriver.Chrome(options=chrome_options)

            self.driver.set_page_load_timeout(30)
            self.driver.implicitly_wait(10)

            logger.info("Chrome WebDriver initialized successfully")
            return self.driver

        except Exception as e:
            logger.error(f"Failed to initialize ChromeDriver: {e}")
            logger.error("Make sure chromium-browser is installed: sudo apt-get install chromium-browser")
            raise

    def random_delay(self, min_sec=2, max_sec=4):
        """Random delay to avoid detection - adaptive based on errors"""
        if self.consecutive_errors > 0:
            multiplier = 1 + (self.consecutive_errors * 0.5)
            min_sec = min_sec * multiplier
            max_sec = max_sec * multiplier
            logger.debug(f"  Adaptive delay: {min_sec:.1f}-{max_sec:.1f}s (errors: {self.consecutive_errors})")
        
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)

    def download_and_upload_image(self, url, s3_key):
        """
        Download image and upload directly to S3

        Args:
            url: Image URL
            s3_key: S3 key for the image

        Returns:
            tuple: (success, info)
        """
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.get(url, timeout=CONNECTION_TIMEOUT)
                if response.status_code == 200:
                    img = Image.open(BytesIO(response.content))
                    width, height = img.size

                    if width < 400 or height < 400:
                        return False, f"{width}x{height} (too small)"

                    # Upload to S3
                    content_type = 'image/jpeg'
                    if url.lower().endswith('.png'):
                        content_type = 'image/png'
                    elif url.lower().endswith('.webp'):
                        content_type = 'image/webp'

                    if self._upload_to_s3(response.content, s3_key, content_type):
                        self.consecutive_errors = 0
                        return True, f"{width}x{height}"
                    else:
                        return False, "S3 upload failed"
                        
                elif response.status_code == 429:
                    logger.warning(f"  Rate limited, waiting {RETRY_DELAY * 2}s...")
                    time.sleep(RETRY_DELAY * 2)
                    continue

            except (requests.exceptions.ConnectionError, 
                    requests.exceptions.Timeout,
                    requests.exceptions.ChunkedEncodingError) as e:
                self.consecutive_errors += 1
                logger.warning(f"  Connection error (attempt {attempt + 1}/{MAX_RETRIES}): {type(e).__name__}")
                
                if attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_DELAY * (2 ** attempt)
                    logger.info(f"  Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    
                    if self.consecutive_errors >= 3:
                        self._refresh_session()
                        self.consecutive_errors = 0
                else:
                    return False, f"Connection failed after {MAX_RETRIES} attempts"
                    
            except Exception as e:
                logger.error(f"Error downloading {url}: {e}")
                return False, str(e)

        return False, "Unknown error"

    def extract_product_id_from_url(self, url):
        """Extract product ID from URL"""
        match = re.search(r'/products/([a-z0-9\-]+(?:%[0-9A-Fa-f]{2}[a-z0-9\-]*)*)', url, re.IGNORECASE)
        if match:
            product_id = match.group(1)
            product_id = re.sub(r'%[0-9A-Fa-f]{2}', '-', product_id)
            product_id = re.sub(r'-+', '-', product_id)
            product_id = product_id.strip('-')
            return product_id
        return None

    def get_gallery_images_only(self, product_url):
        """
        Extract ONLY the main product gallery images
        Excludes: recommendations, related products, icons, etc.
        """
        from selenium.webdriver.common.by import By
        from selenium.common.exceptions import TimeoutException, WebDriverException

        max_page_attempts = 2
        
        for page_attempt in range(max_page_attempts):
            try:
                logger.info(f"  Loading product page...")
                self.driver.get(product_url)
                self.random_delay(1, 2)

                # Get product title
                try:
                    title = self.driver.find_element(By.CSS_SELECTOR, "h1").text
                    logger.info(f"  Product: {title[:60]}...")
                except:
                    title = "Unknown"

                product_handle = self.extract_product_id_from_url(product_url)
                logger.info(f"  Product handle: {product_handle}")

                time.sleep(1)

                gallery_images = []
                seen_urls = set()

                # Use JavaScript to extract ONLY product gallery images
                try:
                    js_script = """
                    var images = [];
                    var seen = new Set();
                    
                    var excludePatterns = ['logo', 'icon', 'badge', 'payment', 'visa', 'mastercard', 
                                          'paypal', 'amex', 'discover', 'apple-pay', 'google-pay',
                                          'shop-pay', 'avatar', 'flag', 'banner', 'promo', 'svg',
                                          'gif', 'placeholder', 'loading', 'spinner'];
                    
                    var excludeSections = ['recommend', 'related', 'upsell', 'cross-sell', 
                                           'recently-viewed', 'you-may-also', 'also-like',
                                           'collection-list', 'footer', 'complementary',
                                           'product-recommendations', 'featured-collection'];
                    
                    var allImgs = document.querySelectorAll('img[src*="cdn/shop"], img[src*="cdn.shopify"], img[data-src*="cdn/shop"]');
                    
                    for (var i = 0; i < allImgs.length; i++) {
                        var img = allImgs[i];
                        var src = img.src || img.getAttribute('data-src') || '';
                        
                        if (!src || (src.indexOf('cdn/shop') === -1 && src.indexOf('cdn.shopify') === -1)) {
                            continue;
                        }
                        
                        var srcLower = src.toLowerCase();
                        var excluded = false;
                        for (var j = 0; j < excludePatterns.length; j++) {
                            if (srcLower.indexOf(excludePatterns[j]) !== -1) {
                                excluded = true;
                                break;
                            }
                        }
                        if (excluded) continue;
                        
                        var parent = img;
                        var inExcludedSection = false;
                        for (var k = 0; k < 15; k++) {
                            parent = parent.parentElement;
                            if (!parent) break;
                            var parentClass = (parent.className || '').toLowerCase();
                            var parentId = (parent.id || '').toLowerCase();
                            var parentDataSection = (parent.getAttribute('data-section-type') || '').toLowerCase();
                            
                            for (var m = 0; m < excludeSections.length; m++) {
                                if (parentClass.indexOf(excludeSections[m]) !== -1 || 
                                    parentId.indexOf(excludeSections[m]) !== -1 ||
                                    parentDataSection.indexOf(excludeSections[m]) !== -1) {
                                    inExcludedSection = true;
                                    break;
                                }
                            }
                            if (inExcludedSection) break;
                        }
                        if (inExcludedSection) continue;
                        
                        var highRes = src.replace(/_\\d+x\\d*\\./, '_1800x1800.');
                        highRes = highRes.split('?')[0];
                        
                        if (!seen.has(highRes)) {
                            seen.add(highRes);
                            images.push(highRes);
                        }
                    }
                    
                    return images;
                    """
                    
                    raw_images = self.driver.execute_script(js_script)
                    logger.info(f"  Found {len(raw_images)} product gallery images")
                    
                    for img_url in raw_images:
                        if img_url not in seen_urls:
                            seen_urls.add(img_url)
                            gallery_images.append(img_url)

                except Exception as e:
                    logger.error(f"  JavaScript extraction error: {e}")
                    # Fallback
                    try:
                        all_images = self.driver.find_elements(
                            By.CSS_SELECTOR,
                            "img[src*='cdn/shop'], img[src*='cdn.shopify']"
                        )
                        for img in all_images[:20]:
                            try:
                                src = img.get_attribute("src")
                                if src and 'cdn/shop' in src:
                                    high_res = re.sub(r'_\d+x\d*\.', '_1800x1800.', src)
                                    high_res = re.sub(r'\?.*$', '', high_res)
                                    if high_res not in seen_urls:
                                        seen_urls.add(high_res)
                                        gallery_images.append(high_res)
                            except:
                                continue
                    except Exception as e2:
                        logger.error(f"  Fallback method error: {e2}")

                logger.info(f"  Total gallery images (filtered): {len(gallery_images)}")

                if len(gallery_images) >= 1:
                    self.consecutive_errors = 0
                    return {
                        "title": title,
                        "url": product_url,
                        "images": gallery_images
                    }

                return None

            except (TimeoutException, WebDriverException) as e:
                self.consecutive_errors += 1
                logger.warning(f"  Page load error (attempt {page_attempt + 1}/{max_page_attempts}): {type(e).__name__}")
                
                if page_attempt < max_page_attempts - 1:
                    logger.info(f"  Waiting {RETRY_DELAY}s before retry...")
                    time.sleep(RETRY_DELAY)
                    
                    if self.consecutive_errors >= 5:
                        logger.info("  Restarting WebDriver due to repeated errors...")
                        try:
                            self.driver.quit()
                        except:
                            pass
                        time.sleep(RETRY_DELAY)
                        self.init_driver()
                        self.consecutive_errors = 0
                else:
                    logger.error(f"  Failed to load product page after {max_page_attempts} attempts")
                    return None

            except Exception as e:
                logger.error(f"  Error: {e}")
                self.consecutive_errors += 1
                return None
        
        return None

    def download_all_gallery_images(self, product_data, product_id):
        """Download gallery images and upload to S3"""
        downloaded_images = []

        for idx, img_url in enumerate(product_data["images"]):
            try:
                filename = f"image_{idx:02d}.jpg"
                s3_key = self._s3_key("products", product_id, filename)

                success, info = self.download_and_upload_image(img_url, s3_key)

                if success:
                    image_info = {
                        "filename": filename,
                        "url": img_url,
                        "size": info,
                        "index": idx,
                        "s3_key": s3_key,
                        "s3_uri": f"s3://{self.s3_bucket}/{s3_key}",
                        "storage": "s3"
                    }

                    downloaded_images.append(image_info)
                    logger.info(f"    [{idx+1}/{len(product_data['images'])}] {info} -> s3://.../{product_id}/{filename}")

            except Exception as e:
                logger.error(f"Error downloading image {idx}: {e}")
                continue

        return downloaded_images

    def scrape_collection_page(self, collection_url, max_pages=None, max_items=None):
        """Scrape collection page with pagination"""
        from selenium.webdriver.common.by import By

        self.stats['start_time'] = time.time()

        logger.info(f"\n{'='*80}")
        logger.info(f"SCRAPING: {collection_url}")
        logger.info(f"Max Pages: {max_pages}, Max Items: {max_items}")
        logger.info(f"S3 Destination: s3://{self.s3_bucket}/{self.s3_prefix}/")
        logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*80}")

        try:
            self.driver.get(collection_url)
            self.random_delay(1, 2)

            # Accept cookies/popups
            try:
                accept = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Accept')]")
                accept.click()
                time.sleep(2)
            except:
                pass
            
            try:
                close_buttons = self.driver.find_elements(By.CSS_SELECTOR, "[aria-label='Close'], .popup-close, .modal-close")
                for btn in close_buttons:
                    try:
                        btn.click()
                        time.sleep(1)
                    except:
                        pass
            except:
                pass

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
                if consecutive_empty_pages >= 3:
                    logger.info("No new products found for 3 consecutive pages - stopping.")
                    break

                logger.info(f"\n{'='*80}")
                logger.info(f"PAGE {page_num}")
                logger.info(f"{'='*80}")

                self.stats['total_pages_explored'] += 1

                if page_num == 1:
                    page_url = collection_url
                else:
                    sep = '&' if '?' in collection_url else '?'
                    page_url = f"{collection_url}{sep}page={page_num}"
                    self.driver.get(page_url)
                    self.random_delay(1, 2)

                for _ in range(3):
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                    time.sleep(1)

                product_links = []
                links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/products/']")

                for link in links:
                    href = link.get_attribute("href")
                    if href and '/products/' in href and href not in product_links:
                        if not any(x in href for x in ['/cart', '/account', '/search', 'gift-card']):
                            product_links.append(href)

                logger.info(f"Found {len(product_links)} products on page {page_num}")
                self.stats['total_products_found'] += len(product_links)

                elapsed = time.time() - self.stats['start_time']
                logger.info(f"[PAGE {page_num} STATS] Products found: {len(product_links)} | Total products so far: {self.stats['total_products_found']} | Time elapsed: {elapsed:.1f}s")

                if not product_links:
                    logger.info("No products found on this page - stopping pagination.")
                    break

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
                        self.stats['skipped_already_scraped'] += 1
                        continue

                    self.stats['total_products_explored'] += 1
                    logger.info(f"\n[{idx+1}/{len(product_links)}] Processing... (Product #{self.stats['total_products_explored']})")

                    try:
                        product_id = self.extract_product_id_from_url(product_url)
                        if not product_id:
                            continue

                        product_data = self.get_gallery_images_only(product_url)

                        if product_data and len(product_data["images"]) >= 1:
                            downloaded = self.download_all_gallery_images(product_data, product_id)

                            if len(downloaded) >= 1:
                                metadata = {
                                    "item_id": self.items_scraped,
                                    "product_id": product_id,
                                    "source": "shopify_gallery_s3",
                                    "title": product_data["title"],
                                    "url": product_url,
                                    "images": downloaded,
                                    "total_images": len(downloaded),
                                    "scraped_at": datetime.now().isoformat(),
                                    "environment": "ec2",
                                    "storage": "s3",
                                    "s3_bucket": self.s3_bucket,
                                    "s3_prefix": f"{self.s3_prefix}/products/{product_id}"
                                }

                                # Save metadata to S3
                                metadata_key = self._s3_key("metadata", f"{product_id}.json")
                                self._upload_to_s3(json.dumps(metadata, indent=2), metadata_key, 'application/json')

                                self.items_scraped += 1
                                items_this_run += 1
                                self.scraped_urls.add(product_url)
                                self.stats['successful_scrapes'] += 1
                                self.stats['total_images_downloaded'] += len(downloaded)

                                elapsed = time.time() - self.stats['start_time']
                                avg_time_per_item = elapsed / self.stats['successful_scrapes'] if self.stats['successful_scrapes'] > 0 else 0

                                logger.info(f"  [SUCCESS] Item {self.items_scraped} | {len(downloaded)} gallery images")
                                logger.info(f"  [TIMING] Elapsed: {elapsed:.1f}s | Avg per item: {avg_time_per_item:.1f}s")

                                if self.items_scraped % 10 == 0:
                                    self.save_progress()
                                    self._print_exploration_summary()

                        self.random_delay(1, 2)

                    except Exception as e:
                        logger.error(f"  [ERROR] {e}")
                        self.stats['failed_scrapes'] += 1
                        continue

                page_num += 1

            self.stats['end_time'] = time.time()

            logger.info(f"\n{'='*80}")
            logger.info(f"SCRAPING COMPLETE!")
            logger.info(f"{'='*80}")
            self._print_final_summary(items_this_run)

        except Exception as e:
            self.stats['end_time'] = time.time()
            logger.error(f"\nError: {e}")
            traceback.print_exc()
            self._print_final_summary(items_this_run if 'items_this_run' in locals() else 0)

    def _format_duration(self, seconds):
        """Format duration in human-readable format"""
        if seconds < 60:
            return f"{seconds:.1f} seconds"
        elif seconds < 3600:
            mins = seconds / 60
            return f"{mins:.1f} minutes ({seconds:.0f}s)"
        else:
            hours = seconds / 3600
            mins = (seconds % 3600) / 60
            return f"{hours:.1f} hours ({int(hours)}h {int(mins)}m)"

    def _print_exploration_summary(self):
        """Print intermediate exploration summary"""
        elapsed = time.time() - self.stats['start_time'] if self.stats['start_time'] else 0

        logger.info(f"\n{'-'*60}")
        logger.info(f"EXPLORATION SUMMARY (at {self._format_duration(elapsed)})")
        logger.info(f"{'-'*60}")
        logger.info(f"Pages explored:        {self.stats['total_pages_explored']}")
        logger.info(f"Products found:        {self.stats['total_products_found']}")
        logger.info(f"Products explored:     {self.stats['total_products_explored']}")
        logger.info(f"Successful scrapes:    {self.stats['successful_scrapes']}")
        logger.info(f"Failed scrapes:        {self.stats['failed_scrapes']}")
        logger.info(f"Skipped (duplicate):   {self.stats['skipped_already_scraped']}")
        logger.info(f"Total images:          {self.stats['total_images_downloaded']}")

        if self.stats['successful_scrapes'] > 0:
            avg_time = elapsed / self.stats['successful_scrapes']
            logger.info(f"Avg time per product:  {avg_time:.1f}s")
        logger.info(f"{'-'*60}\n")

    def _print_final_summary(self, items_this_run):
        """Print final summary with timing information"""
        elapsed = (self.stats['end_time'] - self.stats['start_time']) if self.stats['start_time'] and self.stats['end_time'] else 0

        logger.info(f"\n{'#'*80}")
        logger.info(f"FINAL SCRAPING REPORT")
        logger.info(f"{'#'*80}")

        logger.info(f"\n[TIMING]")
        logger.info(f"  Total duration:      {self._format_duration(elapsed)}")
        if self.stats['successful_scrapes'] > 0:
            avg_time = elapsed / self.stats['successful_scrapes']
            logger.info(f"  Avg per product:     {avg_time:.1f} seconds")
            products_per_min = (self.stats['successful_scrapes'] / elapsed) * 60 if elapsed > 0 else 0
            logger.info(f"  Scraping rate:       {products_per_min:.2f} products/minute")

        logger.info(f"\n[PAGE EXPLORATION]")
        logger.info(f"  Pages explored:      {self.stats['total_pages_explored']}")
        logger.info(f"  Products found:      {self.stats['total_products_found']}")
        if self.stats['total_pages_explored'] > 0:
            avg_per_page = self.stats['total_products_found'] / self.stats['total_pages_explored']
            logger.info(f"  Avg products/page:   {avg_per_page:.1f}")

        logger.info(f"\n[PRODUCT EXPLORATION]")
        logger.info(f"  Products explored:   {self.stats['total_products_explored']}")
        logger.info(f"  Successful scrapes:  {self.stats['successful_scrapes']}")
        logger.info(f"  Failed scrapes:      {self.stats['failed_scrapes']}")
        logger.info(f"  Skipped (duplicate): {self.stats['skipped_already_scraped']}")

        if self.stats['total_products_explored'] > 0:
            success_rate = (self.stats['successful_scrapes'] / self.stats['total_products_explored']) * 100
            logger.info(f"  Success rate:        {success_rate:.1f}%")

        logger.info(f"\n[IMAGES]")
        logger.info(f"  Total downloaded:    {self.stats['total_images_downloaded']}")
        if self.stats['successful_scrapes'] > 0:
            avg_images = self.stats['total_images_downloaded'] / self.stats['successful_scrapes']
            logger.info(f"  Avg per product:     {avg_images:.1f}")

        logger.info(f"\n[SESSION]")
        logger.info(f"  Items this run:      {items_this_run}")
        logger.info(f"  Total items scraped: {self.items_scraped}")
        logger.info(f"  S3 Bucket:           {self.s3_bucket}")
        logger.info(f"  S3 Prefix:           {self.s3_prefix}")
        logger.info(f"  Storage:             AWS S3")

        logger.info(f"\n{'#'*80}\n")

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
    """
    Main function to run the scraper on EC2 with S3 uploads

    Usage:
    ```
    # Install dependencies first:
    pip install selenium pillow requests webdriver-manager boto3
    sudo apt-get install chromium-browser

    # Set environment variables or use IAM role:
    export AWS_ACCESS_KEY_ID=your_key
    export AWS_SECRET_ACCESS_KEY=your_secret
    export AWS_DEFAULT_REGION=us-east-1

    # Run the scraper:
    python test_newmoondance_ec2.py
    ```
    """
    logger.info("="*80)
    logger.info("SHOPIFY GALLERY SCRAPER - EC2/S3 VERSION")
    logger.info("Downloads product images and uploads directly to S3")
    logger.info("="*80)

    # ==========================================================================
    # CONFIGURATION - MODIFY THESE VALUES
    # ==========================================================================
    S3_BUCKET = "your-bucket-name"  # <-- Change this!
    S3_PREFIX = "newmoondance_dataset"
    AWS_REGION = "us-east-1"
    
    # Collection URL to scrape
    COLLECTION_URL = "https://newmoondance.com/collections/qipao-%E6%97%97%E8%A2%8D"
    # ==========================================================================

    scraper = NewMoonDanceGalleryScraperS3(
        s3_bucket=S3_BUCKET,
        s3_prefix=S3_PREFIX,
        aws_region=AWS_REGION
    )

    try:
        scraper.init_driver()

        # PRODUCTION MODE: Scrape all pages and unlimited items
        scraper.scrape_collection_page(COLLECTION_URL, max_pages=None, max_items=None)

        # TEST MODE: 10 items, 2 pages (recommended for initial testing)
        # scraper.scrape_collection_page(COLLECTION_URL, max_pages=2, max_items=10)

        logger.info(f"\n[SUMMARY]")
        logger.info(f"S3 Location: s3://{S3_BUCKET}/{S3_PREFIX}/")
        logger.info(f"Items scraped: {scraper.items_scraped}")
        logger.info(f"Storage: AWS S3")

    except KeyboardInterrupt:
        logger.info("\n[INTERRUPTED BY USER]")

    except Exception as e:
        logger.error(f"\nFatal error: {e}")
        traceback.print_exc()

    finally:
        scraper.close()


def run_scraper(collection_url="https://newmoondance.com/collections/qipao-%E6%97%97%E8%A2%8D",
                s3_bucket=None,
                s3_prefix="newmoondance_dataset",
                aws_region="us-east-1",
                max_pages=None,
                max_items=None):
    """
    Convenience function to run the scraper with custom parameters

    Args:
        collection_url: URL of the collection page to scrape
        s3_bucket: S3 bucket name (required)
        s3_prefix: Prefix (folder) in S3 bucket
        aws_region: AWS region for S3
        max_pages: Maximum number of pages to scrape (None for unlimited)
        max_items: Maximum number of items to scrape (None for unlimited)

    Returns:
        NewMoonDanceGalleryScraperS3: The scraper instance

    Examples:
        # Basic usage:
        scraper = run_scraper(
            s3_bucket="my-bucket",
            max_pages=2,
            max_items=10
        )

        # Full production run:
        scraper = run_scraper(
            collection_url="https://newmoondance.com/collections/female",
            s3_bucket="my-bucket",
            s3_prefix="female_collection",
            max_pages=None,
            max_items=None
        )
    """
    if not s3_bucket:
        raise ValueError("s3_bucket is required for S3 uploads")
    
    scraper = NewMoonDanceGalleryScraperS3(
        s3_bucket=s3_bucket,
        s3_prefix=s3_prefix,
        aws_region=aws_region
    )

    try:
        scraper.init_driver()
        scraper.scrape_collection_page(collection_url, max_pages=max_pages, max_items=max_items)
    except KeyboardInterrupt:
        logger.info("\n[INTERRUPTED BY USER]")
    except Exception as e:
        logger.error(f"\nError: {e}")
        traceback.print_exc()
    finally:
        scraper.close()

    return scraper


if __name__ == "__main__":
    main()
