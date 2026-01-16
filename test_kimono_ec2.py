"""Kimurakami Gallery Scraper - EC2 Version with S3 Support
Downloads product gallery images from kimurakami.com with AWS S3 integration
Optimized for headless operation on EC2 instances

SETUP FOR EC2:
1. Install dependencies:
   pip install selenium pillow requests boto3 webdriver-manager

2. Install Chrome browser:
   # Amazon Linux 2
   sudo amazon-linux-extras install epel
   sudo yum install -y chromium chromium-headless

   # Ubuntu
   sudo apt-get update
   sudo apt-get install -y chromium-browser

3. Configure AWS credentials (choose one):
   - IAM Role attached to EC2 instance (recommended)
   - Environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
   - AWS CLI: aws configure

4. Run the scraper:
   python test_kimono_ec2.py
"""

import os
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from pathlib import Path
from PIL import Image
from io import BytesIO
import json
import random
from datetime import datetime
import re
import logging

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

# Try to import boto3 for S3 support
try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    logger.warning("boto3 not available. Install with: pip install boto3")


class KimurakamiGalleryScraperEC2:
    def __init__(
        self,
        output_dir=None,
        use_s3=True,
        s3_bucket=None,
        aws_region="us-east-1",
        aws_access_key_id=None,
        aws_secret_access_key=None
    ):
        """
        Initialize Kimurakami scraper for EC2 with S3 integration

        Args:
            output_dir: Local directory for temporary storage
            use_s3: Whether to upload to AWS S3 (default: True)
            s3_bucket: S3 bucket name (or set S3_BUCKET env var)
            aws_region: AWS region (default: us-east-1)
            aws_access_key_id: AWS access key (or use IAM role/env var)
            aws_secret_access_key: AWS secret key (or use IAM role/env var)
        """
        # S3 Configuration
        self.use_s3 = use_s3
        self.s3_bucket = s3_bucket or os.environ.get('S3_BUCKET')
        self.aws_region = aws_region or os.environ.get('AWS_REGION', 'us-east-1')
        self.s3_client = None

        # Initialize S3 if enabled
        if self.use_s3:
            if not BOTO3_AVAILABLE:
                logger.error("=" * 60)
                logger.error("S3 UPLOAD REQUESTED BUT boto3 IS NOT INSTALLED!")
                logger.error("Run: pip install boto3")
                logger.error("=" * 60)
                logger.warning("Falling back to local storage.")
                self.use_s3 = False
            elif not self.s3_bucket:
                logger.warning("S3 bucket not specified. Set S3_BUCKET env var or pass s3_bucket parameter.")
                logger.warning("Falling back to local storage.")
                self.use_s3 = False
            else:
                logger.info("=" * 60)
                logger.info("INITIALIZING AWS S3 CONNECTION")
                logger.info(f"  Bucket: {self.s3_bucket}")
                logger.info(f"  Region: {self.aws_region}")
                logger.info("=" * 60)
                self._init_s3_client(aws_access_key_id, aws_secret_access_key)

        # Set output directory (used for temporary storage when S3 is enabled)
        if output_dir:
            self.output_dir = Path(output_dir)
        elif self.use_s3:
            self.output_dir = Path("/tmp/kimurakami_dataset")  # Temporary for S3 uploads
        else:
            # Use home directory for local storage on EC2
            self.output_dir = Path(os.path.expanduser("~/kimurakami_dataset"))

        # Create directories
        self.output_dir.mkdir(exist_ok=True, parents=True)
        (self.output_dir / "products_anish").mkdir(exist_ok=True)
        (self.output_dir / "metadata_anish").mkdir(exist_ok=True)
        (self.output_dir / "progress_anish").mkdir(exist_ok=True)

        self.driver = None
        self.items_scraped = 0
        self.session = self._create_session()
        self.consecutive_errors = 0  # Track consecutive errors for adaptive delays

        # Statistics tracking
        self.stats = {
            'total_pages_explored': 0,
            'total_products_found': 0,
            'total_products_explored': 0,
            'successful_scrapes': 0,
            'failed_scrapes': 0,
            'skipped_already_scraped': 0,
            'total_images_downloaded': 0,
            's3_uploads_successful': 0,
            's3_uploads_failed': 0,
            'start_time': None,
            'end_time': None
        }

        # Log storage configuration
        if self.use_s3:
            logger.info(f"Storage: AWS S3 (bucket: {self.s3_bucket}, region: {self.aws_region})")
        else:
            logger.info(f"Storage: Local ({self.output_dir})")
        logger.info(f"Temporary directory: {self.output_dir}")

        self.load_progress()

    def _create_session(self):
        """Create a requests session with retry logic"""
        session = requests.Session()
        
        # Configure retry strategy
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
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
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

    def _init_s3_client(self, aws_access_key_id=None, aws_secret_access_key=None):
        """Initialize S3 client with credentials"""
        try:
            # Get credentials from parameters or environment
            access_key = aws_access_key_id or os.environ.get('AWS_ACCESS_KEY_ID')
            secret_key = aws_secret_access_key or os.environ.get('AWS_SECRET_ACCESS_KEY')

            logger.info(f"  Access Key provided: {'Yes' if access_key else 'No (using IAM role/default chain)'}")
            logger.info(f"  Secret Key provided: {'Yes' if secret_key else 'No (using IAM role/default chain)'}")

            if access_key and secret_key:
                # Use explicit credentials
                self.s3_client = boto3.client(
                    's3',
                    region_name=self.aws_region,
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key
                )
                logger.info("  ✓ S3 client initialized with provided credentials")
            else:
                # Try default credential chain (IAM role on EC2, ~/.aws/credentials, etc.)
                self.s3_client = boto3.client(
                    's3',
                    region_name=self.aws_region
                )
                logger.info("  ✓ S3 client initialized with IAM role/default credential chain")

            # Verify bucket access
            self._verify_s3_access()

            logger.info("=" * 60)
            logger.info("S3 CONNECTION SUCCESSFUL!")
            logger.info(f"  Ready to upload to: s3://{self.s3_bucket}/")
            logger.info("=" * 60)

        except Exception as e:
            logger.error("=" * 60)
            logger.error(f"FAILED to initialize S3 client: {e}")
            logger.error("=" * 60)
            logger.warning("Falling back to local storage.")
            self.use_s3 = False
            self.s3_client = None

    def _verify_s3_access(self):
        """Verify S3 credentials and bucket access"""
        logger.info(f"  Verifying bucket access: {self.s3_bucket}...")
        try:
            self.s3_client.head_bucket(Bucket=self.s3_bucket)
            logger.info(f"  ✓ S3 bucket access verified: {self.s3_bucket}")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.error(f"  ✗ S3 bucket {self.s3_bucket} does not exist")
            elif error_code == '403':
                logger.error(f"  ✗ Access denied to S3 bucket {self.s3_bucket}")
            else:
                logger.error(f"  ✗ Error accessing S3: {e}")
            raise

    def upload_to_s3(self, file_path, s3_key, content_type='image/jpeg'):
        """
        Upload file to S3

        Args:
            file_path: Local file path
            s3_key: S3 object key (path in bucket)
            content_type: MIME type of the file

        Returns:
            bool: True if successful
        """
        if not self.use_s3:
            logger.debug(f"S3 disabled, skipping upload of {s3_key}")
            return False

        if not self.s3_client:
            logger.error(f"S3 client not initialized, cannot upload {s3_key}")
            return False

        try:
            logger.debug(f"Uploading {file_path} to s3://{self.s3_bucket}/{s3_key}")
            self.s3_client.upload_file(
                str(file_path),
                self.s3_bucket,
                s3_key,
                ExtraArgs={'ContentType': content_type}
            )
            self.stats['s3_uploads_successful'] += 1
            logger.info(f"    ✓ S3: {s3_key}")
            return True
        except ClientError as e:
            logger.error(f"    ✗ S3 upload failed for {s3_key}: {e}")
            self.stats['s3_uploads_failed'] += 1
            return False
        except Exception as e:
            logger.error(f"    ✗ Unexpected error uploading {s3_key}: {e}")
            self.stats['s3_uploads_failed'] += 1
            return False

    def upload_json_to_s3(self, data, s3_key):
        """
        Upload JSON data directly to S3 without saving locally first

        Args:
            data: Dictionary to upload as JSON
            s3_key: S3 object key

        Returns:
            bool: True if successful
        """
        if not self.use_s3 or not self.s3_client:
            return False

        try:
            json_data = json.dumps(data, indent=2)
            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=s3_key,
                Body=json_data,
                ContentType='application/json'
            )
            logger.debug(f"Uploaded JSON to S3: s3://{self.s3_bucket}/{s3_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to upload JSON to S3: {e}")
            return False

    def load_progress_from_s3(self):
        """
        Load scraping progress from S3

        Returns:
            dict or None: Progress data if found, None otherwise
        """
        if not self.use_s3 or not self.s3_client:
            return None

        s3_progress_key = "progress_anish/scraper_progress.json"

        try:
            response = self.s3_client.get_object(
                Bucket=self.s3_bucket,
                Key=s3_progress_key
            )
            data = json.loads(response['Body'].read().decode('utf-8'))
            logger.info(f"[S3] Loaded progress from s3://{self.s3_bucket}/{s3_progress_key}")
            return data
        except self.s3_client.exceptions.NoSuchKey:
            logger.info(f"[S3] No progress file found in S3 (first run)")
            return None
        except Exception as e:
            logger.warning(f"[S3] Could not load progress from S3: {e}")
            return None

    def load_progress(self):
        """
        Load scraping progress from storage (S3 first, then local)
        Prioritizes S3 for cross-session resume capability
        """
        self.scraped_urls = set()
        data = None

        # Try loading from S3 first (for cross-session resume)
        if self.use_s3:
            data = self.load_progress_from_s3()
            if data:
                self.items_scraped = data.get("items_scraped", 0)
                self.scraped_urls = set(data.get("scraped_urls", []))
                logger.info(f"[RESUME from S3] {self.items_scraped} items already scraped, {len(self.scraped_urls)} URLs tracked")

                # Also save locally for this session
                self._save_progress_locally(data)
                return

        # Fall back to local progress file
        progress_file = self.output_dir / "progress_anish" / "scraper_progress.json"
        if progress_file.exists():
            try:
                with open(progress_file, 'r') as f:
                    data = json.load(f)
                    self.items_scraped = data.get("items_scraped", 0)
                    self.scraped_urls = set(data.get("scraped_urls", []))
                    logger.info(f"[RESUME from local] {self.items_scraped} items already scraped, {len(self.scraped_urls)} URLs tracked")
            except Exception as e:
                logger.warning(f"Could not load local progress: {e}")
                self.scraped_urls = set()
        else:
            logger.info("[NEW SESSION] No previous progress found")

    def _save_progress_locally(self, data=None):
        """Save progress data to local file"""
        progress_file = self.output_dir / "progress_anish" / "scraper_progress.json"
        try:
            if data is None:
                data = {
                    "items_scraped": self.items_scraped,
                    "scraped_urls": list(self.scraped_urls),
                    "last_updated": datetime.now().isoformat(),
                    "total_urls_tracked": len(self.scraped_urls),
                    "storage_mode": "s3" if self.use_s3 else "local"
                }
            with open(progress_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Progress saved locally: {self.items_scraped} items")
        except Exception as e:
            logger.error(f"Failed to save progress locally: {e}")

    def save_progress(self):
        """Save scraping progress to both S3 and local storage"""
        progress_data = {
            "items_scraped": self.items_scraped,
            "scraped_urls": list(self.scraped_urls),
            "last_updated": datetime.now().isoformat(),
            "total_urls_tracked": len(self.scraped_urls),
            "storage_mode": "s3" if self.use_s3 else "local"
        }

        # Save locally first
        self._save_progress_locally(progress_data)

        # Upload to S3 if enabled
        if self.use_s3:
            s3_key = "progress_anish/scraper_progress.json"
            if self.upload_json_to_s3(progress_data, s3_key):
                logger.debug(f"Progress uploaded to S3: {s3_key}")

    def init_driver(self):
        """Initialize Chrome driver for EC2 (headless mode)"""
        logger.info("Initializing Chrome WebDriver for EC2...")

        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.chrome.options import Options

            # Try to use webdriver-manager for automatic driver management
            try:
                from webdriver_manager.chrome import ChromeDriverManager
                service = Service(ChromeDriverManager().install())
            except ImportError:
                logger.warning("webdriver-manager not installed. Using system ChromeDriver.")
                service = None

            chrome_options = Options()

            # EC2 headless options
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument(
                'user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )

            # Additional options for EC2 stability
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-plugins')
            chrome_options.add_argument('--disable-sync')
            chrome_options.add_argument('--disable-translate')
            chrome_options.add_argument('--disable-default-apps')
            chrome_options.add_argument('--no-first-run')
            chrome_options.add_argument('--no-default-browser-check')
            chrome_options.add_argument('--single-process')  # May help on low-memory instances
            chrome_options.add_argument('--disable-setuid-sandbox')
            chrome_options.add_argument('--remote-debugging-port=9222')

            # Memory optimization
            chrome_options.add_argument('--disable-software-rasterizer')
            chrome_options.add_argument('--disable-background-networking')
            chrome_options.add_argument('--disable-background-timer-throttling')

            if service:
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                self.driver = webdriver.Chrome(options=chrome_options)

            self.driver.set_page_load_timeout(30)
            self.driver.implicitly_wait(10)

            logger.info("Chrome WebDriver initialized successfully (headless mode)")
            return self.driver

        except Exception as e:
            logger.error(f"Failed to initialize ChromeDriver: {e}")
            logger.error("Make sure Chrome/Chromium is installed on your EC2 instance")
            logger.error("For Amazon Linux 2: sudo amazon-linux-extras install epel && sudo yum install -y chromium")
            logger.error("For Ubuntu: sudo apt-get install -y chromium-browser")
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

    def download_image(self, url, filepath, s3_key=None):
        """
        Download image and optionally upload to S3 with retry logic

        Args:
            url: Image URL
            filepath: Local file path
            s3_key: S3 object key (optional)

        Returns:
            tuple: (success, info, s3_uploaded)
        """
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.get(url, timeout=CONNECTION_TIMEOUT)
                if response.status_code == 200:
                    img = Image.open(BytesIO(response.content))
                    width, height = img.size

                    if width < 400 or height < 400:
                        return False, f"{width}x{height}", False

                    # Save locally first
                    filepath.parent.mkdir(parents=True, exist_ok=True)
                    with open(filepath, 'wb') as f:
                        f.write(response.content)

                    s3_uploaded = False
                    # Upload to S3 if enabled
                    if self.use_s3 and s3_key:
                        s3_uploaded = self.upload_to_s3(filepath, s3_key)
                        if s3_uploaded:
                            try:
                                filepath.unlink()
                                logger.debug(f"Deleted local file: {filepath}")
                            except Exception as e:
                                logger.debug(f"Could not delete local file: {e}")

                    self.consecutive_errors = 0  # Reset on success
                    return True, f"{width}x{height}", s3_uploaded
                elif response.status_code == 429:  # Rate limited
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
                    return False, f"Connection failed after {MAX_RETRIES} attempts", False
                    
            except Exception as e:
                logger.error(f"Error downloading {url}: {e}")
                return False, str(e), False

        return False, "Unknown error", False

    def extract_product_id_from_url(self, url):
        """Extract product ID from Kimurakami URL"""
        # Kimurakami URLs look like: /products/black-kimono-dress
        match = re.search(r'/products/([a-z0-9\-]+)', url)
        if match:
            return match.group(1)
        return None

    def get_gallery_images_only(self, product_url):
        """
        Extract ONLY the main product gallery images from Kimurakami product page
        Excludes: "Pair it with" recommendations, related products, icons, etc.
        """
        from selenium.webdriver.common.by import By
        from selenium.common.exceptions import TimeoutException, WebDriverException

        max_page_attempts = 2
        
        for page_attempt in range(max_page_attempts):
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

                # Extract product handle from URL for filtering
                product_handle = self.extract_product_id_from_url(product_url)
                logger.info(f"  Product handle: {product_handle}")

                time.sleep(2)

                gallery_images = []
                seen_filenames = set()

                # Method 1: Find gallery images specifically in the product gallery section
                try:
                    gallery_selectors = [
                        ".product__media img[src*='cdn/shop']",
                        ".product-gallery img[src*='cdn/shop']",
                        ".product-single__media img[src*='cdn/shop']",
                        ".product-images img[src*='cdn/shop']",
                        "[data-product-media-type='image'] img",
                        ".product__main-photos img[src*='cdn/shop']",
                        ".product__thumbs img[src*='cdn/shop']",
                        ".product-single__thumbnails img[src*='cdn/shop']",
                    ]

                    all_gallery_images = []
                    for selector in gallery_selectors:
                        try:
                            images = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            all_gallery_images.extend(images)
                        except:
                            continue

                    # If specific selectors didn't work, try anchor tags with high-res URLs
                    if len(all_gallery_images) == 0:
                        anchors = self.driver.find_elements(
                            By.CSS_SELECTOR,
                            "a[href*='cdn/shop/files'][href*='1800x1800'], a[href*='cdn/shop/products'][href*='1800x1800']"
                        )

                        for anchor in anchors:
                            try:
                                href = anchor.get_attribute("href")
                                if not href:
                                    continue

                                filename_match = re.search(r'/([^/]+?)(?:[-_]\d+)?(?:_\d+x\d+)?\.(?:jpg|png|webp)', href, re.IGNORECASE)
                                if filename_match:
                                    filename = filename_match.group(1).lower()
                                    product_words = product_handle.replace('-', ' ').split()
                                    if any(word in filename for word in product_words if len(word) > 3):
                                        if href not in gallery_images:
                                            gallery_images.append(href.split('?')[0])
                                            seen_filenames.add(filename)
                            except:
                                continue

                    logger.info(f"  Found {len(all_gallery_images)} elements in gallery selectors")

                    # Process gallery images found via selectors
                    for img in all_gallery_images:
                        try:
                            src = img.get_attribute("src")
                            if not src or 'cdn/shop' not in src:
                                continue

                            # Skip non-product images
                            if any(x in src.lower() for x in ['logo', 'icon', 'badge', 'payment', 'visa', 'mastercard',
                                                               'obi-belt', 'socks', 'tabi', 'nagajuban']):
                                continue

                            filename_match = re.search(r'/([^/]+?)(?:[-_]\d+)?(?:_\d+x\d*)?\.(?:jpg|png|webp)', src, re.IGNORECASE)
                            if filename_match:
                                filename = filename_match.group(1).lower()

                                product_words = product_handle.replace('-', ' ').split()
                                is_product_image = any(word in filename for word in product_words if len(word) > 3)

                                if not is_product_image:
                                    continue

                                if filename in seen_filenames:
                                    continue
                                seen_filenames.add(filename)

                            # Convert to high-res version
                            high_res = re.sub(r'_\d+x\d*\.', '_1800x1800.', src)
                            if '?' in high_res:
                                high_res = high_res.split('?')[0]

                            if high_res not in gallery_images:
                                gallery_images.append(high_res)
                                logger.debug(f"    Gallery image {len(gallery_images)}: {high_res[:80]}...")

                        except Exception as e:
                            logger.debug(f"Error processing image: {e}")
                            continue

                except Exception as e:
                    logger.error(f"  Error finding gallery images: {e}")

                # Method 2: Fallback - match by product name
                if len(gallery_images) < 2:
                    logger.info(f"  Trying fallback method - matching by product name...")
                    try:
                        all_images = self.driver.find_elements(
                            By.CSS_SELECTOR,
                            "img[src*='cdn/shop/files'], img[src*='cdn/shop/products']"
                        )

                        for img in all_images:
                            try:
                                src = img.get_attribute("src")
                                if not src:
                                    continue

                                if any(x in src.lower() for x in ['logo', 'icon', 'badge', 'payment', 'visa', 'mastercard',
                                                                   'obi-belt', 'japanese-obi', 'socks', 'tabi', 'nagajuban',
                                                                   'geta', 'sandal', 'zori', 'haori', 'hanten']):
                                    continue

                                filename_match = re.search(r'/([^/]+?)(?:[-_]\d+)?(?:_\d+x\d*)?\.(?:jpg|png|webp)', src, re.IGNORECASE)
                                if filename_match:
                                    filename = filename_match.group(1).lower()

                                    product_words = product_handle.replace('-', ' ').split()
                                    is_product_image = any(word in filename for word in product_words if len(word) > 3)

                                    if not is_product_image:
                                        continue

                                    if filename in seen_filenames:
                                        continue
                                    seen_filenames.add(filename)

                                    high_res = re.sub(r'_\d+x\d*\.', '_1800x1800.', src)
                                    if '?' in high_res:
                                        high_res = high_res.split('?')[0]

                                    if high_res not in gallery_images:
                                        gallery_images.append(high_res)
                                        logger.debug(f"    Fallback image {len(gallery_images)}: {high_res[:80]}...")
                            except:
                                continue

                    except Exception as e:
                        logger.error(f"  Fallback method error: {e}")

                logger.info(f"  Total gallery images (filtered): {len(gallery_images)}")

                if len(gallery_images) >= 1:
                    # Reset consecutive errors on success
                    self.consecutive_errors = 0
                    return {
                        "title": title,
                        "url": product_url,
                        "images": gallery_images
                    }

                return None
                
            except TimeoutException as e:
                logger.warning(f"  Timeout loading page (attempt {page_attempt + 1}/{max_page_attempts}): {e}")
                self.consecutive_errors += 1
                if page_attempt < max_page_attempts - 1:
                    wait_time = RETRY_DELAY * (page_attempt + 1)
                    logger.info(f"  Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue
                    
            except WebDriverException as e:
                logger.warning(f"  WebDriver error (attempt {page_attempt + 1}/{max_page_attempts}): {e}")
                self.consecutive_errors += 1
                
                # Try to recover WebDriver after multiple failures
                if self.consecutive_errors >= 5:
                    logger.warning("  Too many consecutive errors, restarting WebDriver...")
                    try:
                        self.driver.quit()
                    except:
                        pass
                    time.sleep(5)
                    self._setup_driver()
                    self.consecutive_errors = 0
                    
                if page_attempt < max_page_attempts - 1:
                    wait_time = RETRY_DELAY * (page_attempt + 1)
                    logger.info(f"  Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue
                    
            except Exception as e:
                logger.error(f"  Error: {e}")
                self.consecutive_errors += 1
                return None
                
        return None

    def download_all_gallery_images(self, product_data, product_id):
        """Download gallery images, optionally upload to S3"""
        product_dir = self.output_dir / "products_anish" / product_id
        product_dir.mkdir(exist_ok=True, parents=True)

        downloaded_images = []

        for idx, img_url in enumerate(product_data["images"]):
            try:
                filename = f"image_{idx:02d}.jpg"
                filepath = product_dir / filename

                # S3 key: products_anish/product_id/image_00.jpg
                s3_key = f"products_anish/{product_id}/{filename}" if self.use_s3 else None

                success, info, s3_uploaded = self.download_image(img_url, filepath, s3_key)

                if success:
                    image_info = {
                        "filename": filename,
                        "url": img_url,
                        "size": info,
                        "index": idx
                    }

                    if self.use_s3:
                        image_info["s3_key"] = s3_key
                        image_info["s3_uri"] = f"s3://{self.s3_bucket}/{s3_key}"
                        image_info["s3_uploaded"] = s3_uploaded
                        image_info["storage"] = "s3" if s3_uploaded else "local"
                    else:
                        image_info["local_path"] = str(filepath)
                        image_info["storage"] = "local"

                    downloaded_images.append(image_info)

                    storage_indicator = "→S3" if s3_uploaded else "→local"
                    logger.info(f"    [{idx+1}/{len(product_data['images'])}] {info} {storage_indicator}")

            except Exception as e:
                logger.error(f"Error downloading image {idx}: {e}")
                continue

        return downloaded_images

    def scrape_sale_page(self, sale_url, max_pages=None, max_items=None):
        """Scrape sale page with pagination"""
        from selenium.webdriver.common.by import By

        # Start timing
        self.stats['start_time'] = time.time()

        logger.info(f"\n{'='*80}")
        logger.info(f"SCRAPING: {sale_url}")
        logger.info(f"Max Pages: {max_pages}, Max Items: {max_items}")
        logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
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
                    logger.info("No new products found for 3 consecutive pages — stopping.")
                    break

                logger.info(f"\n{'='*80}")
                logger.info(f"PAGE {page_num}")
                logger.info(f"{'='*80}")

                self.stats['total_pages_explored'] += 1

                if page_num == 1:
                    page_url = sale_url
                else:
                    sep = '&' if '?' in sale_url else '?'
                    page_url = f"{sale_url}{sep}page={page_num}"
                    self.driver.get(page_url)
                    self.random_delay(3, 5)

                # Scroll to load products
                for _ in range(3):
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                    time.sleep(1)

                # Get product links - Kimurakami uses /products/ URLs
                product_links = []
                links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/products/']")

                for link in links:
                    href = link.get_attribute("href")
                    if href and '/products/' in href and href not in product_links:
                        product_links.append(href)

                logger.info(f"Found {len(product_links)} products on page {page_num}")
                self.stats['total_products_found'] += len(product_links)

                elapsed = time.time() - self.stats['start_time']
                logger.info(f"[PAGE {page_num} STATS] Products found: {len(product_links)} | Total: {self.stats['total_products_found']} | Time: {elapsed:.1f}s")

                if not product_links:
                    logger.info("No products found on this page — stopping pagination.")
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

                    logger.info(f"\n[{idx+1}/{len(product_links)}] Processing: {product_url[:60]}...")
                    self.stats['total_products_explored'] += 1

                    try:
                        product_id = self.extract_product_id_from_url(product_url)
                        if not product_id:
                            logger.warning(f"  Could not extract product ID")
                            continue

                        product_data = self.get_gallery_images_only(product_url)

                        if product_data and len(product_data["images"]) >= 1:
                            downloaded = self.download_all_gallery_images(product_data, product_id)

                            if len(downloaded) >= 1:
                                metadata = {
                                    "item_id": self.items_scraped,
                                    "product_id": product_id,
                                    "source": "kimurakami_gallery_ec2",
                                    "title": product_data["title"],
                                    "url": product_url,
                                    "images": downloaded,
                                    "total_images": len(downloaded),
                                    "scraped_at": datetime.now().isoformat(),
                                    "environment": "ec2",
                                    "storage": "s3" if self.use_s3 else "local"
                                }

                                if self.use_s3:
                                    metadata["s3_bucket"] = self.s3_bucket
                                    metadata["s3_prefix"] = f"products_anish/{product_id}/"

                                # Save metadata locally
                                metadata_file = self.output_dir / "metadata_anish" / f"{product_id}.json"
                                with open(metadata_file, 'w') as f:
                                    json.dump(metadata, f, indent=2)

                                # Upload metadata to S3
                                if self.use_s3:
                                    s3_metadata_key = f"metadata_anish/{product_id}.json"
                                    self.upload_json_to_s3(metadata, s3_metadata_key)

                                self.items_scraped += 1
                                items_this_run += 1
                                self.scraped_urls.add(product_url)
                                self.stats['successful_scrapes'] += 1
                                self.stats['total_images_downloaded'] += len(downloaded)

                                elapsed = time.time() - self.stats['start_time']
                                avg_time = elapsed / self.stats['successful_scrapes'] if self.stats['successful_scrapes'] > 0 else 0

                                logger.info(f"  [SUCCESS] Item {self.items_scraped} | {len(downloaded)} gallery images")
                                logger.info(f"  [TIMING] Elapsed: {elapsed:.1f}s | Avg per item: {avg_time:.1f}s")

                                if self.items_scraped % 10 == 0:
                                    self.save_progress()
                                    self._print_exploration_summary()

                        self.random_delay(2, 4)

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
            import traceback
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

        if self.use_s3:
            logger.info(f"S3 uploads success:    {self.stats['s3_uploads_successful']}")
            logger.info(f"S3 uploads failed:     {self.stats['s3_uploads_failed']}")

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

        if self.use_s3:
            logger.info(f"\n[S3 UPLOADS]")
            logger.info(f"  Successful:          {self.stats['s3_uploads_successful']}")
            logger.info(f"  Failed:              {self.stats['s3_uploads_failed']}")
            logger.info(f"  Bucket:              {self.s3_bucket}")
            logger.info(f"  Region:              {self.aws_region}")

        logger.info(f"\n[SESSION]")
        logger.info(f"  Items this run:      {items_this_run}")
        logger.info(f"  Total items scraped: {self.items_scraped}")
        logger.info(f"  Output directory:    {self.output_dir}")
        storage_mode = "AWS S3" if self.use_s3 else "Local"
        logger.info(f"  Storage:             {storage_mode}")

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
    Main function to run the scraper on EC2

    Usage:
    ```bash
    # Install dependencies:
    pip install selenium pillow requests boto3 webdriver-manager

    # Set environment variables (or use IAM role):
    export S3_BUCKET=your-bucket-name
    export AWS_REGION=us-east-1

    # Run the scraper:
    python test_kimono_ec2.py
    ```
    """
    logger.info("=" * 80)
    logger.info("KIMURAKAMI GALLERY SCRAPER - EC2 VERSION")
    logger.info("Downloads product gallery images from kimurakami.com")
    logger.info("Uploads to AWS S3 for persistent storage")
    logger.info("=" * 80)

    # ==========================================================================
    # CONFIGURATION - Edit these settings as needed
    # ==========================================================================

    # S3 Configuration
    USE_S3 = True  # Set to False to save locally only
    S3_BUCKET = os.environ.get('S3_BUCKET', 'your-bucket-name')
    AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', None)  # None = use IAM role
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', None)  # None = use IAM role

    # ==========================================================================

    scraper = KimurakamiGalleryScraperEC2(
        use_s3=USE_S3,
        s3_bucket=S3_BUCKET,
        aws_region=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )

    try:
        scraper.init_driver()

        # Kimurakami collections URL
        sale_url = "https://kimurakami.com/collections/japanese-kimono-dress"

        # PRODUCTION MODE: Scrape all pages and unlimited items
        scraper.scrape_sale_page(sale_url, max_pages=None, max_items=None)

        # TEST MODE: 10 items, 2 pages (recommended for initial testing)
        # scraper.scrape_sale_page(sale_url, max_pages=2, max_items=10)

        logger.info(f"\n[SUMMARY]")
        logger.info(f"Output directory: {scraper.output_dir}")
        logger.info(f"Items scraped: {scraper.items_scraped}")
        if scraper.use_s3:
            logger.info(f"S3 bucket: {scraper.s3_bucket}")

    except KeyboardInterrupt:
        logger.info("\n[INTERRUPTED BY USER]")

    except Exception as e:
        logger.error(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        scraper.close()


def run_scraper(
    sale_url="https://kimurakami.com/collections/japanese-kimono-dress",
    max_pages=None,
    max_items=None,
    use_s3=True,
    s3_bucket=None,
    aws_region="us-east-1",
    aws_access_key_id=None,
    aws_secret_access_key=None,
    output_dir=None
):
    """
    Convenience function to run the scraper with custom parameters

    Args:
        sale_url: URL of the Kimurakami collection page to scrape
        max_pages: Maximum number of pages to scrape (None for unlimited)
        max_items: Maximum number of items to scrape (None for unlimited)
        use_s3: Whether to upload to S3 (default: True)
        s3_bucket: S3 bucket name
        aws_region: AWS region
        aws_access_key_id: AWS access key (or use IAM role)
        aws_secret_access_key: AWS secret key (or use IAM role)
        output_dir: Custom output directory

    Returns:
        KimurakamiGalleryScraperEC2: The scraper instance

    Examples:
        # With IAM role (recommended for EC2):
        scraper = run_scraper(
            s3_bucket="my-bucket",
            max_items=100
        )

        # With explicit credentials:
        scraper = run_scraper(
            s3_bucket="my-bucket",
            aws_access_key_id="AKIA...",
            aws_secret_access_key="...",
            max_items=50
        )

        # Local storage only:
        scraper = run_scraper(
            use_s3=False,
            output_dir="/home/ec2-user/data",
            max_items=50
        )
    """
    scraper = KimurakamiGalleryScraperEC2(
        output_dir=output_dir,
        use_s3=use_s3,
        s3_bucket=s3_bucket,
        aws_region=aws_region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key
    )

    try:
        scraper.init_driver()
        scraper.scrape_sale_page(sale_url, max_pages=max_pages, max_items=max_items)
    except KeyboardInterrupt:
        logger.info("\n[INTERRUPTED BY USER]")
    except Exception as e:
        logger.error(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        scraper.close()

    return scraper


if __name__ == "__main__":
    main()
