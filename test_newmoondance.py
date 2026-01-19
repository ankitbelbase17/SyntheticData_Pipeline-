"""NewMoonDance Gallery Scraper - Local PC Version
Optimized for running on local Windows/Mac/Linux with standard Selenium
Downloads product gallery images from newmoondance.com (Qipao/Cheongsam) and saves locally

SETUP FOR LOCAL PC:
1. Install Chrome browser
2. Install dependencies:
   pip install selenium pillow requests webdriver-manager
3. Run the scraper:
   python test_newmoondance.py
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


class NewMoonDanceGalleryScraperLocal:
    def __init__(self, output_dir=None):
        """
        Initialize NewMoonDance scraper for local PC

        Args:
            output_dir: Directory for saving images and metadata
        """
        # Set output directory
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = Path("./newmoondance_dataset")

        # Create directories
        self.output_dir.mkdir(exist_ok=True, parents=True)
        (self.output_dir / "products").mkdir(exist_ok=True)
        (self.output_dir / "metadata").mkdir(exist_ok=True)
        (self.output_dir / "progress").mkdir(exist_ok=True)

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
            'start_time': None,
            'end_time': None
        }

        logger.info(f"Storage: Local directory")
        logger.info(f"Output directory: {self.output_dir.absolute()}")

        self.load_progress()

    def _create_session(self):
        """Create a requests session with retry logic"""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=MAX_RETRIES,
            backoff_factor=1,  # Wait 1, 2, 4 seconds between retries
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

    def load_progress(self):
        """Load scraping progress from local storage"""
        self.scraped_urls = set()

        progress_file = self.output_dir / "progress" / "scraper_progress.json"
        if progress_file.exists():
            try:
                with open(progress_file, 'r') as f:
                    data = json.load(f)
                    self.items_scraped = data.get("items_scraped", 0)
                    self.scraped_urls = set(data.get("scraped_urls", []))
                    logger.info(f"[RESUME] {self.items_scraped} items already scraped, {len(self.scraped_urls)} URLs tracked")
            except Exception as e:
                logger.warning(f"Could not load progress: {e}")
                self.scraped_urls = set()
        else:
            logger.info("[NEW SESSION] No previous progress found")

    def save_progress(self):
        """Save scraping progress to local storage"""
        progress_file = self.output_dir / "progress" / "scraper_progress.json"
        progress_data = {
            "items_scraped": self.items_scraped,
            "scraped_urls": list(self.scraped_urls),
            "last_updated": datetime.now().isoformat(),
            "total_urls_tracked": len(self.scraped_urls),
            "storage_mode": "local",
            "source": "newmoondance.com"
        }

        try:
            with open(progress_file, 'w') as f:
                json.dump(progress_data, f, indent=2)
            logger.debug(f"Progress saved: {self.items_scraped} items")
        except Exception as e:
            logger.error(f"Failed to save progress: {e}")

    def init_driver(self):
        """Initialize Chrome driver using webdriver-manager for local PC"""
        logger.info("Initializing Chrome WebDriver for local PC...")

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

            # Local PC options
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument(
                'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )

            # Additional options for stability
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-plugins')
            chrome_options.add_argument('--disable-sync')
            chrome_options.add_argument('--disable-translate')
            chrome_options.add_argument('--disable-default-apps')
            chrome_options.add_argument('--no-first-run')
            chrome_options.add_argument('--no-default-browser-check')

            # Uncomment below to run headless (no browser window)
            chrome_options.add_argument('--headless')

            if service:
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                self.driver = webdriver.Chrome(options=chrome_options)

            self.driver.set_page_load_timeout(30)
            self.driver.implicitly_wait(10)

            logger.info("Chrome WebDriver initialized successfully")
            return self.driver

        except Exception as e:
            logger.error(f"Failed to initialize ChromeDriver: {e}")
            logger.error("Make sure Chrome is installed and run: pip install webdriver-manager")
            raise

    def random_delay(self, min_sec=2, max_sec=4):
        """Random delay to avoid detection - adaptive based on errors"""
        # Increase delay if we've had recent errors
        if self.consecutive_errors > 0:
            multiplier = 1 + (self.consecutive_errors * 0.5)
            min_sec = min_sec * multiplier
            max_sec = max_sec * multiplier
            logger.debug(f"  Adaptive delay: {min_sec:.1f}-{max_sec:.1f}s (errors: {self.consecutive_errors})")
        
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)

    def download_image(self, url, filepath):
        """
        Download image and save locally with retry logic

        Args:
            url: Image URL
            filepath: Local file path

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
                        return False, f"{width}x{height}"

                    # Save locally
                    filepath.parent.mkdir(parents=True, exist_ok=True)
                    with open(filepath, 'wb') as f:
                        f.write(response.content)

                    self.consecutive_errors = 0  # Reset on success
                    return True, f"{width}x{height}"
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
                    # Exponential backoff
                    wait_time = RETRY_DELAY * (2 ** attempt)
                    logger.info(f"  Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    
                    # Refresh session after multiple consecutive errors
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
        """Extract product ID from NewMoonDance URL"""
        # NewMoonDance URLs look like: /products/violet-mist-modern-2-piece-qipao-dress-...
        # or /collections/xxx/products/product-name
        match = re.search(r'/products/([a-z0-9\-]+(?:%[0-9A-Fa-f]{2}[a-z0-9\-]*)*)', url, re.IGNORECASE)
        if match:
            product_id = match.group(1)
            # Clean up URL-encoded characters for cleaner folder names
            product_id = re.sub(r'%[0-9A-Fa-f]{2}', '-', product_id)
            product_id = re.sub(r'-+', '-', product_id)  # Remove multiple dashes
            product_id = product_id.strip('-')
            return product_id
        return None

    def get_gallery_images_only(self, product_url):
        """
        Extract ONLY the main product gallery images from NewMoonDance product page
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

                # Extract product handle from URL for filtering
                product_handle = self.extract_product_id_from_url(product_url)
                logger.info(f"  Product handle: {product_handle}")

                time.sleep(1)  # Reduced from 2s

                gallery_images = []
                seen_urls = set()

                # Use JavaScript to extract ONLY product gallery images - not recommendations
                try:
                    js_script = """
                    var images = [];
                    var seen = new Set();
                    
                    // Patterns to exclude (non-product images)
                    var excludePatterns = ['logo', 'icon', 'badge', 'payment', 'visa', 'mastercard', 
                                          'paypal', 'amex', 'discover', 'apple-pay', 'google-pay',
                                          'shop-pay', 'avatar', 'flag', 'banner', 'promo', 'svg',
                                          'gif', 'placeholder', 'loading', 'spinner'];
                    
                    // Sections to exclude (recommendations, related products, etc.)
                    var excludeSections = ['recommend', 'related', 'upsell', 'cross-sell', 
                                           'recently-viewed', 'you-may-also', 'also-like',
                                           'collection-list', 'footer', 'complementary',
                                           'product-recommendations', 'featured-collection'];
                    
                    // Get all CDN images on the page
                    var allImgs = document.querySelectorAll('img[src*="cdn/shop"], img[src*="cdn.shopify"], img[data-src*="cdn/shop"]');
                    
                    for (var i = 0; i < allImgs.length; i++) {
                        var img = allImgs[i];
                        var src = img.src || img.getAttribute('data-src') || '';
                        
                        // Skip if no src or not from CDN
                        if (!src || (src.indexOf('cdn/shop') === -1 && src.indexOf('cdn.shopify') === -1)) {
                            continue;
                        }
                        
                        // Skip excluded image patterns
                        var srcLower = src.toLowerCase();
                        var excluded = false;
                        for (var j = 0; j < excludePatterns.length; j++) {
                            if (srcLower.indexOf(excludePatterns[j]) !== -1) {
                                excluded = true;
                                break;
                            }
                        }
                        if (excluded) continue;
                        
                        // Check if image is inside an excluded section (recommendation, related, etc.)
                        var parent = img;
                        var inExcludedSection = false;
                        for (var k = 0; k < 15; k++) {  // Check up to 15 parent levels
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
                        
                        // Convert to high-res URL
                        var highRes = src.replace(/_\\d+x\\d*\\./, '_1800x1800.');
                        highRes = highRes.split('?')[0];  // Remove query params
                        
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
                    # Fallback to simple CSS selector if JS fails
                    try:
                        all_images = self.driver.find_elements(
                            By.CSS_SELECTOR,
                            "img[src*='cdn/shop'], img[src*='cdn.shopify']"
                        )
                        for img in all_images[:20]:  # Limit to first 20
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
                    self.consecutive_errors = 0  # Reset on success
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
        """Download gallery images locally"""
        product_dir = self.output_dir / "products" / product_id
        product_dir.mkdir(exist_ok=True, parents=True)

        downloaded_images = []

        for idx, img_url in enumerate(product_data["images"]):
            try:
                filename = f"image_{idx:02d}.jpg"
                filepath = product_dir / filename

                success, info = self.download_image(img_url, filepath)

                if success:
                    image_info = {
                        "filename": filename,
                        "url": img_url,
                        "size": info,
                        "index": idx,
                        "local_path": str(filepath),
                        "storage": "local"
                    }

                    downloaded_images.append(image_info)
                    logger.info(f"    [{idx+1}/{len(product_data['images'])}] {info} -> {filepath.name}")

            except Exception as e:
                logger.error(f"Error downloading image {idx}: {e}")
                continue

        return downloaded_images

    def scrape_collection_page(self, collection_url, max_pages=None, max_items=None):
        """Scrape collection page with pagination"""
        from selenium.webdriver.common.by import By

        # Start timing
        self.stats['start_time'] = time.time()

        logger.info(f"\n{'='*80}")
        logger.info(f"SCRAPING: {collection_url}")
        logger.info(f"Max Pages: {max_pages}, Max Items: {max_items}")
        logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*80}")

        try:
            self.driver.get(collection_url)
            self.random_delay(1, 2)

            # Accept cookies/popups if present
            try:
                accept = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Accept')]")
                accept.click()
                time.sleep(2)
            except:
                pass
            
            # Close any newsletter popups
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

            # Incremental pagination
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

                # Update page stats
                self.stats['total_pages_explored'] += 1

                if page_num == 1:
                    page_url = collection_url
                else:
                    # Shopify uses ?page=N for pagination
                    sep = '&' if '?' in collection_url else '?'
                    page_url = f"{collection_url}{sep}page={page_num}"
                    self.driver.get(page_url)
                    self.random_delay(1, 2)

                # Scroll to load products
                for _ in range(3):
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                    time.sleep(1)

                # Get product links - NewMoonDance uses /products/ URLs
                product_links = []
                links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/products/']")

                for link in links:
                    href = link.get_attribute("href")
                    if href and '/products/' in href and href not in product_links:
                        # Filter out non-product links (cart, account, gift cards, etc.)
                        if not any(x in href for x in ['/cart', '/account', '/search', 'gift-card']):
                            product_links.append(href)

                logger.info(f"Found {len(product_links)} products on page {page_num}")
                self.stats['total_products_found'] += len(product_links)

                # Print page exploration summary
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
                                    "source": "newmoondance_gallery_local",
                                    "title": product_data["title"],
                                    "url": product_url,
                                    "images": downloaded,
                                    "total_images": len(downloaded),
                                    "scraped_at": datetime.now().isoformat(),
                                    "environment": "local_pc",
                                    "storage": "local",
                                    "product_directory": str(self.output_dir / "products" / product_id)
                                }

                                # Save metadata locally
                                metadata_file = self.output_dir / "metadata" / f"{product_id}.json"
                                with open(metadata_file, 'w') as f:
                                    json.dump(metadata, f, indent=2)

                                self.items_scraped += 1
                                items_this_run += 1
                                self.scraped_urls.add(product_url)
                                self.stats['successful_scrapes'] += 1
                                self.stats['total_images_downloaded'] += len(downloaded)

                                # Calculate and display timing info
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

            # End timing
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

        # Timing info
        logger.info(f"\n[TIMING]")
        logger.info(f"  Total duration:      {self._format_duration(elapsed)}")
        if self.stats['successful_scrapes'] > 0:
            avg_time = elapsed / self.stats['successful_scrapes']
            logger.info(f"  Avg per product:     {avg_time:.1f} seconds")
            products_per_min = (self.stats['successful_scrapes'] / elapsed) * 60 if elapsed > 0 else 0
            logger.info(f"  Scraping rate:       {products_per_min:.2f} products/minute")

        # Page exploration info
        logger.info(f"\n[PAGE EXPLORATION]")
        logger.info(f"  Pages explored:      {self.stats['total_pages_explored']}")
        logger.info(f"  Products found:      {self.stats['total_products_found']}")
        if self.stats['total_pages_explored'] > 0:
            avg_per_page = self.stats['total_products_found'] / self.stats['total_pages_explored']
            logger.info(f"  Avg products/page:   {avg_per_page:.1f}")

        # Product exploration info
        logger.info(f"\n[PRODUCT EXPLORATION]")
        logger.info(f"  Products explored:   {self.stats['total_products_explored']}")
        logger.info(f"  Successful scrapes:  {self.stats['successful_scrapes']}")
        logger.info(f"  Failed scrapes:      {self.stats['failed_scrapes']}")
        logger.info(f"  Skipped (duplicate): {self.stats['skipped_already_scraped']}")

        if self.stats['total_products_explored'] > 0:
            success_rate = (self.stats['successful_scrapes'] / self.stats['total_products_explored']) * 100
            logger.info(f"  Success rate:        {success_rate:.1f}%")

        # Image info
        logger.info(f"\n[IMAGES]")
        logger.info(f"  Total downloaded:    {self.stats['total_images_downloaded']}")
        if self.stats['successful_scrapes'] > 0:
            avg_images = self.stats['total_images_downloaded'] / self.stats['successful_scrapes']
            logger.info(f"  Avg per product:     {avg_images:.1f}")

        # Session info
        logger.info(f"\n[SESSION]")
        logger.info(f"  Items this run:      {items_this_run}")
        logger.info(f"  Total items scraped: {self.items_scraped}")
        logger.info(f"  Output directory:    {self.output_dir.absolute()}")
        logger.info(f"  Storage:             Local filesystem")

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
    Main function to run the scraper on local PC

    Usage:
    ```
    # Install dependencies first:
    pip install selenium pillow requests webdriver-manager

    # Run the scraper:
    python test_newmoondance.py
    ```
    """
    logger.info("="*80)
    logger.info("NEWMOONDANCE GALLERY SCRAPER - LOCAL PC VERSION")
    logger.info("Downloads Qipao/Cheongsam product images from newmoondance.com")
    logger.info("Saves images to local filesystem")
    logger.info("="*80)

    # ==========================================================================
    # CONFIGURATION
    # ==========================================================================
    # Output directory (change to your preferred location)
    output_dir = "./nuwaha_dataset"
    # ==========================================================================

    scraper = NewMoonDanceGalleryScraperLocal(output_dir=output_dir)

    try:
        scraper.init_driver()

        # NewMoonDance Qipao collection URL
        collection_url = "https://nuwahanfu.com/collections/all-dynasties"

        # PRODUCTION MODE: Scrape all pages and unlimited items
        scraper.scrape_collection_page(collection_url, max_pages=None, max_items=None)

        # TEST MODE: 10 items, 2 pages (recommended for initial testing)
        # scraper.scrape_collection_page(collection_url, max_pages=2, max_items=10)

        logger.info(f"\n[SUMMARY]")
        logger.info(f"Output directory: {scraper.output_dir.absolute()}")
        logger.info(f"Items scraped: {scraper.items_scraped}")
        logger.info(f"Storage: Local filesystem")

    except KeyboardInterrupt:
        logger.info("\n[INTERRUPTED BY USER]")

    except Exception as e:
        logger.error(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        scraper.close()


def run_scraper(collection_url="https://newmoondance.com/collections/qipao-%E6%97%97%E8%A2%8D",
                max_pages=None,
                max_items=None,
                output_dir=None):
    """
    Convenience function to run the scraper with custom parameters

    Args:
        collection_url: URL of the NewMoonDance collection page to scrape
        max_pages: Maximum number of pages to scrape (None for unlimited)
        max_items: Maximum number of items to scrape (None for unlimited)
        output_dir: Custom output directory (optional)

    Returns:
        NewMoonDanceGalleryScraperLocal: The scraper instance (for further inspection)

    Examples:
        # Basic usage:
        scraper = run_scraper(max_pages=2, max_items=10)

        # Custom URL and output:
        scraper = run_scraper(
            collection_url="https://newmoondance.com/collections/female",
            max_pages=5,
            max_items=50,
            output_dir="./my_dataset"
        )
        
        # Other available collections:
        # - https://newmoondance.com/collections/female
        # - https://newmoondance.com/collections/men
        # - https://newmoondance.com/collections/wedding-1
        # - https://newmoondance.com/collections/accessories
        # - https://newmoondance.com/collections/sales
    """
    scraper = NewMoonDanceGalleryScraperLocal(output_dir=output_dir)

    try:
        scraper.init_driver()
        scraper.scrape_collection_page(collection_url, max_pages=max_pages, max_items=max_items)
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
