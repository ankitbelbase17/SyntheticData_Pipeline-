"""Etsy Gallery Scraper - Local PC Version
Optimized for scraping Etsy marketplace listings
Downloads product gallery images from Etsy search/market pages

IMPORTANT: Etsy has strong anti-bot protection. This scraper uses:
- Undetected Chrome driver
- Random delays and human-like behavior
- Session persistence
- Stealth techniques

SETUP FOR LOCAL PC:
1. Install Chrome browser
2. Install dependencies:
   pip install selenium pillow requests webdriver-manager undetected-chromedriver
3. Run the scraper:
   python test_etsy.py

NOTE: Etsy may require login for some features. The scraper will pause for manual login if needed.
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
from urllib.parse import urljoin, urlparse, parse_qs

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


class EtsyGalleryScraperLocal:
    def __init__(self, output_dir=None):
        """
        Initialize Etsy scraper for local PC

        Args:
            output_dir: Directory for saving images and metadata
        """
        # Set output directory
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = Path("./etsy_dataset")

        # Create directories
        self.output_dir.mkdir(exist_ok=True, parents=True)
        (self.output_dir / "products").mkdir(exist_ok=True)
        (self.output_dir / "metadata").mkdir(exist_ok=True)
        (self.output_dir / "progress").mkdir(exist_ok=True)

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

        logger.info(f"Storage: Local directory")
        logger.info(f"Output directory: {self.output_dir.absolute()}")

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
            "source": "etsy.com"
        }

        try:
            with open(progress_file, 'w') as f:
                json.dump(progress_data, f, indent=2)
            logger.debug(f"Progress saved: {self.items_scraped} items")
        except Exception as e:
            logger.error(f"Failed to save progress: {e}")

    def init_driver(self):
        """Initialize undetected Chrome driver for Etsy (anti-bot bypass)"""
        logger.info("Initializing Chrome WebDriver with anti-detection...")

        try:
            # Try undetected-chromedriver first (best for Etsy)
            try:
                import undetected_chromedriver as uc
                
                options = uc.ChromeOptions()
                options.add_argument('--window-size=1920,1080')
                options.add_argument('--disable-blink-features=AutomationControlled')
                
                # WARNING: Headless mode triggers CAPTCHA on Etsy!
                # Only enable if you don't need to solve CAPTCHAs
                # options.add_argument('--headless=new')
                
                self.driver = uc.Chrome(options=options, use_subprocess=True)
                logger.info("Using undetected-chromedriver (best for Etsy)")
                
            except ImportError:
                logger.warning("undetected-chromedriver not installed. Falling back to regular Selenium.")
                logger.warning("For better success, install: pip install undetected-chromedriver")
                
                from selenium import webdriver
                from selenium.webdriver.chrome.service import Service
                from selenium.webdriver.chrome.options import Options
                
                try:
                    from webdriver_manager.chrome import ChromeDriverManager
                    service = Service(ChromeDriverManager().install())
                except ImportError:
                    service = None
                
                chrome_options = Options()
                chrome_options.add_argument('--disable-blink-features=AutomationControlled')
                chrome_options.add_argument('--window-size=1920,1080')
                chrome_options.add_argument(
                    'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
                chrome_options.add_experimental_option('useAutomationExtension', False)
                
                # WARNING: Headless mode triggers CAPTCHA on Etsy!
                # Only enable if you don't need to solve CAPTCHAs
                # chrome_options.add_argument('--headless=new')
                
                if service:
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                else:
                    self.driver = webdriver.Chrome(options=chrome_options)
                
                # Remove webdriver detection
                self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                    'source': '''
                        Object.defineProperty(navigator, 'webdriver', {
                            get: () => undefined
                        })
                    '''
                })

            self.driver.set_page_load_timeout(45)
            self.driver.implicitly_wait(10)

            logger.info("Chrome WebDriver initialized successfully")
            return self.driver

        except Exception as e:
            logger.error(f"Failed to initialize ChromeDriver: {e}")
            logger.error("Install: pip install undetected-chromedriver webdriver-manager")
            raise

    def random_delay(self, min_sec=5, max_sec=10):
        """Random delay to mimic human behavior - SLOWER for Etsy anti-bot"""
        if self.consecutive_errors > 0:
            multiplier = 1 + (self.consecutive_errors * 0.5)
            min_sec = min_sec * multiplier
            max_sec = max_sec * multiplier
            logger.debug(f"  Adaptive delay: {min_sec:.1f}-{max_sec:.1f}s (errors: {self.consecutive_errors})")
        
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)

    def human_scroll(self):
        """Scroll like a human would - random scroll distances and pauses"""
        try:
            scroll_scripts = [
                "window.scrollBy(0, window.innerHeight * 0.3);",
                "window.scrollBy(0, window.innerHeight * 0.5);",
                "window.scrollBy(0, window.innerHeight * 0.7);",
            ]
            
            for _ in range(random.randint(3, 5)):
                self.driver.execute_script(random.choice(scroll_scripts))
                time.sleep(random.uniform(0.5, 1.5))
            
            # Scroll back up a bit (human-like)
            if random.random() > 0.7:
                self.driver.execute_script("window.scrollBy(0, -200);")
                time.sleep(0.5)
                
        except Exception as e:
            logger.debug(f"Scroll error: {e}")

    def download_image(self, url, filepath):
        """Download image and save locally with retry logic"""
        # Clean Etsy image URL - get highest resolution
        url = self._get_high_res_etsy_url(url)
        
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.get(url, timeout=CONNECTION_TIMEOUT)
                if response.status_code == 200:
                    img = Image.open(BytesIO(response.content))
                    width, height = img.size

                    if width < 300 or height < 300:
                        return False, f"{width}x{height} (too small)"

                    filepath.parent.mkdir(parents=True, exist_ok=True)
                    with open(filepath, 'wb') as f:
                        f.write(response.content)

                    self.consecutive_errors = 0
                    return True, f"{width}x{height}"
                    
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

    def _get_high_res_etsy_url(self, url):
        """Convert Etsy image URL to highest resolution version"""
        if not url:
            return url
            
        # Etsy image URLs look like:
        # https://i.etsystatic.com/12345678/r/il/abc123/1234567890/il_794xN.1234567890_xxxx.jpg
        # The 794xN can be changed to larger sizes
        
        # Replace common size patterns with full size
        high_res = url
        high_res = re.sub(r'il_\d+x\d*\.', 'il_fullxfull.', high_res)
        high_res = re.sub(r'il_\d+xN\.', 'il_fullxfull.', high_res)
        
        return high_res

    def extract_product_id_from_url(self, url):
        """Extract product ID from Etsy URL"""
        # Etsy URLs look like: /listing/1234567890/product-title-here
        match = re.search(r'/listing/(\d+)', url)
        if match:
            return match.group(1)
        return None

    def get_gallery_images_only(self, product_url):
        """
        Extract product gallery images from Etsy product page
        Excludes: shop images, related products, ads, etc.
        """
        from selenium.webdriver.common.by import By
        from selenium.common.exceptions import TimeoutException, WebDriverException

        max_page_attempts = 2
        
        for page_attempt in range(max_page_attempts):
            try:
                logger.info(f"  Loading product page...")
                self.driver.get(product_url)
                self.random_delay(2, 4)
                
                # Human-like scroll to load lazy images
                self.human_scroll()

                # Get product title
                try:
                    title_selectors = [
                        "h1[data-buy-box-listing-title]",
                        "h1.wt-text-body-01",
                        "h1",
                        "[data-listing-title]"
                    ]
                    title = "Unknown"
                    for sel in title_selectors:
                        try:
                            elem = self.driver.find_element(By.CSS_SELECTOR, sel)
                            if elem.text.strip():
                                title = elem.text.strip()
                                break
                        except:
                            continue
                    logger.info(f"  Product: {title[:60]}...")
                except:
                    title = "Unknown"

                product_id = self.extract_product_id_from_url(product_url)
                logger.info(f"  Product ID: {product_id}")

                time.sleep(1)

                gallery_images = []
                seen_urls = set()

                # Method 1: JavaScript extraction from Etsy's image data
                try:
                    js_script = """
                    var images = [];
                    var seen = new Set();
                    
                    // Patterns to exclude
                    var excludePatterns = ['avatar', 'shop-icon', 'logo', 'badge', 'flag', 
                                          'payment', 'shipping', 'sprite', 'svg', 'gif',
                                          'etsy-icon', 'heart', 'star', 'placeholder'];
                    
                    // Look for main product gallery images
                    var gallerySelectors = [
                        // Main carousel images
                        '[data-carousel-container] img',
                        '[data-carousel] img',
                        '.image-carousel img',
                        '.listing-page-image-carousel img',
                        // Gallery thumbnails (can extract full size from these)
                        '.carousel-pagination img',
                        '.wt-list-inline img',
                        // Main product image
                        '.listing-page-image img',
                        '[data-listing-image] img',
                        // Fallback - any images in product section
                        '.listing-left-column img',
                        '[data-component="listing-page-image-carousel"] img'
                    ];
                    
                    for (var s = 0; s < gallerySelectors.length; s++) {
                        var imgs = document.querySelectorAll(gallerySelectors[s]);
                        for (var i = 0; i < imgs.length; i++) {
                            var img = imgs[i];
                            var src = img.src || img.getAttribute('data-src') || 
                                     img.getAttribute('data-src-zoom') || '';
                            
                            if (!src || src.indexOf('etsystatic.com') === -1) continue;
                            
                            // Check excludes
                            var srcLower = src.toLowerCase();
                            var excluded = false;
                            for (var j = 0; j < excludePatterns.length; j++) {
                                if (srcLower.indexOf(excludePatterns[j]) !== -1) {
                                    excluded = true;
                                    break;
                                }
                            }
                            if (excluded) continue;
                            
                            // Convert to high-res
                            var highRes = src.replace(/il_\\d+x\\d*\\./, 'il_fullxfull.');
                            highRes = highRes.replace(/il_\\d+xN\\./, 'il_fullxfull.');
                            highRes = highRes.split('?')[0];
                            
                            // Skip tiny thumbnails (usually navigation)
                            var width = img.naturalWidth || img.width || 0;
                            if (width > 0 && width < 50) continue;
                            
                            if (!seen.has(highRes)) {
                                seen.add(highRes);
                                images.push(highRes);
                            }
                        }
                        
                        // If we found images in a specific selector, don't check more generic ones
                        if (images.length >= 3) break;
                    }
                    
                    // Also check for zoom images in data attributes
                    var zoomImgs = document.querySelectorAll('[data-src-zoom]');
                    for (var i = 0; i < zoomImgs.length; i++) {
                        var src = zoomImgs[i].getAttribute('data-src-zoom');
                        if (src && src.indexOf('etsystatic.com') !== -1) {
                            var highRes = src.replace(/il_\\d+x\\d*\\./, 'il_fullxfull.');
                            highRes = highRes.split('?')[0];
                            if (!seen.has(highRes)) {
                                seen.add(highRes);
                                images.push(highRes);
                            }
                        }
                    }
                    
                    return images;
                    """
                    
                    raw_images = self.driver.execute_script(js_script)
                    logger.info(f"  Found {len(raw_images)} gallery images via JS")
                    
                    for img_url in raw_images:
                        if img_url not in seen_urls:
                            seen_urls.add(img_url)
                            gallery_images.append(img_url)

                except Exception as e:
                    logger.warning(f"  JavaScript extraction failed: {e}")

                # Method 2: Fallback - direct CSS selector approach
                if len(gallery_images) < 1:
                    try:
                        logger.info("  Trying fallback image extraction...")
                        selectors = [
                            "img[src*='etsystatic.com/']",
                            "img[data-src*='etsystatic.com/']",
                        ]
                        
                        for selector in selectors:
                            images = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            for img in images[:15]:  # Limit to first 15
                                try:
                                    src = img.get_attribute("src") or img.get_attribute("data-src")
                                    if src and 'etsystatic.com' in src:
                                        # Skip tiny/icon images
                                        if any(x in src.lower() for x in ['avatar', 'icon', 'badge', 'logo']):
                                            continue
                                        high_res = self._get_high_res_etsy_url(src)
                                        if high_res not in seen_urls:
                                            seen_urls.add(high_res)
                                            gallery_images.append(high_res)
                                except:
                                    continue
                                    
                            if len(gallery_images) >= 3:
                                break
                                
                    except Exception as e:
                        logger.error(f"  Fallback extraction failed: {e}")

                logger.info(f"  Total gallery images: {len(gallery_images)}")

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
                    logger.info(f"    [{idx+1}/{len(product_data['images'])}] {info} -> {filename}")

            except Exception as e:
                logger.error(f"Error downloading image {idx}: {e}")
                continue

        return downloaded_images

    def check_for_captcha(self):
        """Check if Etsy is showing an actual CAPTCHA challenge"""
        from selenium.webdriver.common.by import By
        
        try:
            # Method 1: Check for actual CAPTCHA elements (most reliable)
            captcha_selectors = [
                "iframe[src*='captcha']",
                "iframe[src*='recaptcha']",
                "iframe[src*='hcaptcha']",
                ".captcha-container",
                "#captcha",
                "[data-captcha]",
                ".g-recaptcha",
                ".h-captcha",
            ]
            
            for selector in captcha_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements and len(elements) > 0:
                        logger.debug(f"  CAPTCHA element found: {selector}")
                        return True
                except:
                    continue
            
            # Method 2: Check page title for block messages
            page_title = self.driver.title.lower() if self.driver.title else ""
            # Only trigger on explicit block pages, not normal Etsy pages
            if page_title and ('access denied' in page_title or 'robot' in page_title):
                logger.debug(f"  Blocked page title: {page_title}")
                return True
            
            # Method 3: Check for Cloudflare/bot challenge URL patterns
            current_url = self.driver.current_url.lower()
            if '/challenge' in current_url or 'captcha' in current_url:
                logger.debug(f"  Challenge URL detected: {current_url}")
                return True
                
            return False
        except Exception as e:
            logger.debug(f"  CAPTCHA check error: {e}")
            return False
            return False
        except:
            return False

    def handle_captcha(self):
        """Pause for manual CAPTCHA solving"""
        if self.check_for_captcha():
            logger.warning("\n" + "="*60)
            logger.warning("CAPTCHA DETECTED!")
            logger.warning("Please solve the CAPTCHA in the browser window.")
            logger.warning("Press ENTER when done...")
            logger.warning("="*60 + "\n")
            input()
            time.sleep(2)
            return True
        return False

    def scrape_market_page(self, market_url, max_pages=None, max_items=None):
        """Scrape Etsy market/search page with pagination"""
        from selenium.webdriver.common.by import By

        self.stats['start_time'] = time.time()

        logger.info(f"\n{'='*80}")
        logger.info(f"SCRAPING: {market_url}")
        logger.info(f"Max Pages: {max_pages}, Max Items: {max_items}")
        logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*80}")

        try:
            # Initial page load
            self.driver.get(market_url)
            self.random_delay(3, 5)
            
            # Check for CAPTCHA
            self.handle_captcha()
            
            # Human-like scrolling
            self.human_scroll()

            # Accept cookies if present
            try:
                cookie_selectors = [
                    "[data-gdpr-single-choice-accept]",
                    "button[aria-label*='Accept']",
                    ".wt-btn--filled[data-accepts-cookies]",
                    "#gdpr-single-choice-overlay button",
                ]
                for sel in cookie_selectors:
                    try:
                        btn = self.driver.find_element(By.CSS_SELECTOR, sel)
                        btn.click()
                        time.sleep(2)
                        break
                    except:
                        continue
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

                # Navigate to page
                if page_num > 1:
                    # Etsy uses page= parameter
                    sep = '&' if '?' in market_url else '?'
                    page_url = f"{market_url}{sep}page={page_num}"
                    self.driver.get(page_url)
                    self.random_delay(2, 4)
                    self.handle_captcha()

                # Scroll to load all products
                self.human_scroll()
                time.sleep(2)

                # Get product links
                product_links = []
                
                # Etsy listing selectors
                link_selectors = [
                    "a[href*='/listing/'][data-listing-id]",
                    "a.listing-link[href*='/listing/']",
                    "[data-search-results] a[href*='/listing/']",
                    ".v2-listing-card a[href*='/listing/']",
                    "a[href*='/listing/']"
                ]
                
                for selector in link_selectors:
                    try:
                        links = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for link in links:
                            href = link.get_attribute("href")
                            if href and '/listing/' in href:
                                # Clean URL - remove tracking params
                                parsed = urlparse(href)
                                clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                                if clean_url not in product_links:
                                    product_links.append(clean_url)
                    except:
                        continue
                        
                    if len(product_links) >= 10:
                        break

                logger.info(f"Found {len(product_links)} products on page {page_num}")
                self.stats['total_products_found'] += len(product_links)

                elapsed = time.time() - self.stats['start_time']
                logger.info(f"[PAGE {page_num} STATS] Products found: {len(product_links)} | Total: {self.stats['total_products_found']} | Time: {elapsed:.1f}s")

                if not product_links:
                    logger.info("No products found on this page")
                    consecutive_empty_pages += 1
                    page_num += 1
                    continue

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
                                    "source": "etsy",
                                    "title": product_data["title"],
                                    "url": product_url,
                                    "images": downloaded,
                                    "total_images": len(downloaded),
                                    "scraped_at": datetime.now().isoformat(),
                                    "storage": "local"
                                }

                                # Save metadata
                                metadata_file = self.output_dir / "metadata" / f"{product_id}.json"
                                with open(metadata_file, 'w') as f:
                                    json.dump(metadata, f, indent=2)

                                self.items_scraped += 1
                                items_this_run += 1
                                self.scraped_urls.add(product_url)
                                self.stats['successful_scrapes'] += 1
                                self.stats['total_images_downloaded'] += len(downloaded)

                                elapsed = time.time() - self.stats['start_time']
                                avg_time = elapsed / self.stats['successful_scrapes']

                                logger.info(f"  [SUCCESS] Item {self.items_scraped} | {len(downloaded)} images")
                                logger.info(f"  [TIMING] Elapsed: {elapsed:.1f}s | Avg: {avg_time:.1f}s/item")

                                if self.items_scraped % 10 == 0:
                                    self.save_progress()
                                    self._print_exploration_summary()

                        # Longer delay for Etsy (they're strict about bots)
                        self.random_delay(3, 6)

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
    Main function to run the Etsy scraper

    Usage:
    ```
    # Install dependencies first:
    pip install selenium pillow requests webdriver-manager undetected-chromedriver

    # Run the scraper:
    python test_etsy.py
    ```
    """
    logger.info("="*80)
    logger.info("ETSY GALLERY SCRAPER - LOCAL PC VERSION")
    logger.info("Downloads product images from Etsy marketplace")
    logger.info("="*80)

    # ==========================================================================
    # CONFIGURATION
    # ==========================================================================
    output_dir = "./etsy_european_clothing_dataset"
    
    # Market/search URLs to scrape
    MARKET_URLS = [
        "https://www.etsy.com/market/traditional_european_clothing",
        # Add more URLs as needed:
        # "https://www.etsy.com/market/medieval_clothing",
        # "https://www.etsy.com/market/renaissance_costume",
        # "https://www.etsy.com/search?q=traditional+european+dress",
    ]
    # ==========================================================================

    scraper = EtsyGalleryScraperLocal(output_dir=output_dir)

    try:
        scraper.init_driver()

        # Scrape all market URLs
        for idx, market_url in enumerate(MARKET_URLS):
            logger.info(f"\n{'#'*80}")
            logger.info(f"MARKET {idx+1}/{len(MARKET_URLS)}: {market_url}")
            logger.info(f"{'#'*80}")
            
            # PRODUCTION MODE: Unlimited pages and items
            scraper.scrape_market_page(market_url, max_pages=None, max_items=None)
            
            # TEST MODE: Limited scraping
            # scraper.scrape_market_page(market_url, max_pages=2, max_items=10)

        logger.info(f"\n[FINAL SUMMARY]")
        logger.info(f"Markets scraped: {len(MARKET_URLS)}")
        logger.info(f"Output directory: {scraper.output_dir.absolute()}")
        logger.info(f"Total items scraped: {scraper.items_scraped}")

    except KeyboardInterrupt:
        logger.info("\n[INTERRUPTED BY USER]")

    except Exception as e:
        logger.error(f"\nFatal error: {e}")
        traceback.print_exc()

    finally:
        scraper.close()


def run_scraper(market_url="https://www.etsy.com/market/traditional_european_clothing",
                max_pages=None,
                max_items=None,
                output_dir=None):
    """
    Convenience function to run the scraper with custom parameters

    Args:
        market_url: Etsy market/search URL to scrape
        max_pages: Maximum number of pages to scrape (None for unlimited)
        max_items: Maximum number of items to scrape (None for unlimited)
        output_dir: Custom output directory (optional)

    Returns:
        EtsyGalleryScraperLocal: The scraper instance

    Examples:
        # Basic usage:
        scraper = run_scraper(max_pages=2, max_items=10)

        # Custom URL:
        scraper = run_scraper(
            market_url="https://www.etsy.com/search?q=medieval+costume",
            max_pages=5,
            max_items=50,
            output_dir="./medieval_dataset"
        )
    """
    scraper = EtsyGalleryScraperLocal(output_dir=output_dir)

    try:
        scraper.init_driver()
        scraper.scrape_market_page(market_url, max_pages=max_pages, max_items=max_items)
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
