"""Kimurakami Gallery Scraper - Local PC Version
Optimized for running on local Windows/Mac/Linux with standard Selenium
Downloads product gallery images from kimurakami.com and saves locally

SETUP FOR LOCAL PC:
1. Install Chrome browser
2. Install dependencies:
   pip install selenium pillow requests webdriver-manager
3. Run the scraper:
   python test_kimono.py
"""

import time
import requests
from pathlib import Path
from PIL import Image
from io import BytesIO
import json
import random
from datetime import datetime
import re
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class KimurakamiGalleryScraperLocal:
    def __init__(self, output_dir=None):
        """
        Initialize Kimurakami scraper for local PC

        Args:
            output_dir: Directory for saving images and metadata
        """
        # Set output directory
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = Path("./vton_gallery_dataset")

        # Create directories
        self.output_dir.mkdir(exist_ok=True, parents=True)
        (self.output_dir / "products_anishlocal").mkdir(exist_ok=True)
        (self.output_dir / "metadata_anishlocal").mkdir(exist_ok=True)
        (self.output_dir / "progress_anishlocal").mkdir(exist_ok=True)

        self.driver = None
        self.items_scraped = 0
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

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

    def load_progress(self):
        """Load scraping progress from local storage"""
        self.scraped_urls = set()

        progress_file = self.output_dir / "progress_anishlocal" / "scraper_progress.json"
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
        progress_file = self.output_dir / "progress_anishlocal" / "scraper_progress.json"
        progress_data = {
            "items_scraped": self.items_scraped,
            "scraped_urls": list(self.scraped_urls),
            "last_updated": datetime.now().isoformat(),
            "total_urls_tracked": len(self.scraped_urls),
            "storage_mode": "local"
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
        """Random delay to avoid detection"""
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)

    def download_image(self, url, filepath):
        """
        Download image and save locally

        Args:
            url: Image URL
            filepath: Local file path

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

                # Save locally
                filepath.parent.mkdir(parents=True, exist_ok=True)
                with open(filepath, 'wb') as f:
                    f.write(response.content)

                return True, f"{width}x{height}"

        except Exception as e:
            logger.error(f"Error downloading {url}: {e}")
            return False, str(e)

        return False, "Unknown error"

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
            # Look for the main product gallery container and its images
            try:
                # Shopify typically has product gallery in specific containers
                # First, try to find images that are in the product media/gallery section
                gallery_selectors = [
                    # Main product gallery selectors for Shopify themes
                    ".product__media img[src*='cdn/shop']",
                    ".product-gallery img[src*='cdn/shop']",
                    ".product-single__media img[src*='cdn/shop']",
                    ".product-images img[src*='cdn/shop']",
                    "[data-product-media-type='image'] img",
                    ".product__main-photos img[src*='cdn/shop']",
                    # Thumbnail gallery
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

                # If specific selectors didn't work, try a more targeted approach
                if len(all_gallery_images) == 0:
                    # Get images that link to high-res versions (typical gallery behavior)
                    # Gallery images are usually inside anchor tags that open larger versions
                    anchors = self.driver.find_elements(
                        By.CSS_SELECTOR,
                        "a[href*='cdn/shop/files'][href*='1800x1800'], a[href*='cdn/shop/products'][href*='1800x1800']"
                    )
                    
                    for anchor in anchors:
                        try:
                            href = anchor.get_attribute("href")
                            if not href:
                                continue
                            
                            # Check if this image belongs to the current product
                            # by checking if filename contains product handle
                            filename_match = re.search(r'/([^/]+?)(?:[-_]\d+)?(?:_\d+x\d+)?\.(?:jpg|png|webp)', href, re.IGNORECASE)
                            if filename_match:
                                filename = filename_match.group(1).lower()
                                # Only include if filename relates to current product
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
                        if any(x in src.lower() for x in ['logo', 'icon', 'badge', 'payment', 'visa', 'mastercard', 'obi-belt', 'socks', 'tabi', 'nagajuban']):
                            continue

                        # Extract filename
                        filename_match = re.search(r'/([^/]+?)(?:[-_]\d+)?(?:_\d+x\d*)?\.(?:jpg|png|webp)', src, re.IGNORECASE)
                        if filename_match:
                            filename = filename_match.group(1).lower()
                            
                            # Check if this image is for the current product
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

            # Method 2: If still no images, try finding by product handle in URL
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
                            
                            # Skip unwanted images
                            if any(x in src.lower() for x in ['logo', 'icon', 'badge', 'payment', 'visa', 'mastercard', 
                                                               'obi-belt', 'japanese-obi', 'socks', 'tabi', 'nagajuban',
                                                               'geta', 'sandal', 'zori', 'haori', 'hanten']):
                                continue
                            
                            # Extract and check filename
                            filename_match = re.search(r'/([^/]+?)(?:[-_]\d+)?(?:_\d+x\d*)?\.(?:jpg|png|webp)', src, re.IGNORECASE)
                            if filename_match:
                                filename = filename_match.group(1).lower()
                                
                                # Match product handle words
                                product_words = product_handle.replace('-', ' ').split()
                                is_product_image = any(word in filename for word in product_words if len(word) > 3)
                                
                                if not is_product_image:
                                    continue
                                
                                if filename in seen_filenames:
                                    continue
                                seen_filenames.add(filename)
                                
                                # Convert to high-res
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
        """Download gallery images locally"""
        product_dir = self.output_dir / "products_anishlocal" / product_id
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
                    page_url = sale_url
                else:
                    # Shopify uses ?page=N for pagination
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
                        # Filter out non-product links (cart, account, etc.)
                        # Note: Kimurakami URLs include collection path like /collections/xxx/products/yyy
                        if not any(x in href for x in ['/cart', '/account', '/search']):
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
                                    "source": "kimurakami_gallery_local",
                                    "title": product_data["title"],
                                    "url": product_url,
                                    "images": downloaded,
                                    "total_images": len(downloaded),
                                    "scraped_at": datetime.now().isoformat(),
                                    "environment": "local_pc",
                                    "storage": "local",
                                    "product_directory": str(self.output_dir / "products_anishlocal" / product_id)
                                }

                                # Save metadata locally
                                metadata_file = self.output_dir / "metadata_anishlocal" / f"{product_id}.json"
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

                        self.random_delay(2, 4)

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
    python test_kimono.py
    ```
    """
    logger.info("="*80)
    logger.info("KIMURAKAMI GALLERY SCRAPER - LOCAL PC VERSION")
    logger.info("Downloads product gallery images from kimurakami.com")
    logger.info("Saves images to local filesystem")
    logger.info("="*80)

    # ==========================================================================
    # CONFIGURATION
    # ==========================================================================
    # Output directory (change to your preferred location)
    output_dir = "./vton_gallery_dataset"
    # ==========================================================================

    scraper = KimurakamiGalleryScraperLocal(output_dir=output_dir)

    try:
        scraper.init_driver()

        # Kimurakami collections URL - change to scrape different categories
        sale_url = "https://kimurakami.com/collections/japanese-kimono-dress"

        # PRODUCTION MODE: Scrape all pages and unlimited items
        scraper.scrape_sale_page(sale_url, max_pages=None, max_items=None)

        # TEST MODE: 10 items, 2 pages (recommended for initial testing)
        # scraper.scrape_sale_page(sale_url, max_pages=2, max_items=10)

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


def run_scraper(sale_url="https://kimurakami.com/collections/japanese-kimono-dress",
                max_pages=None,
                max_items=None,
                output_dir=None):
    """
    Convenience function to run the scraper with custom parameters

    Args:
        sale_url: URL of the Kimurakami collection page to scrape
        max_pages: Maximum number of pages to scrape (None for unlimited)
        max_items: Maximum number of items to scrape (None for unlimited)
        output_dir: Custom output directory (optional)

    Returns:
        KimurakamiGalleryScraperLocal: The scraper instance (for further inspection)

    Examples:
        # Basic usage:
        scraper = run_scraper(max_pages=2, max_items=10)

        # Custom URL and output:
        scraper = run_scraper(
            sale_url="https://kimurakami.com/collections/japanese-women-clothing",
            max_pages=5,
            max_items=50,
            output_dir="./my_dataset"
        )
    """
    scraper = KimurakamiGalleryScraperLocal(output_dir=output_dir)

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
