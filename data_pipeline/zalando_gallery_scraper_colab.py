"""
Zalando Gallery Scraper - Google Colab Optimized
Optimized for running on Google Colab with google-colab-selenium library
Downloads ONLY main product gallery images and saves to Google Drive

SETUP FOR GOOGLE COLAB:
1. Mount Google Drive: from google.colab import drive; drive.mount('/content/drive')
2. Install dependencies:
   !pip install google-colab-selenium pillow requests
3. Run the scraper

Note: Uses google-colab-selenium for seamless Chrome/Selenium integration in Colab
"""

import os
import sys
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

# Check if running in Colab
try:
    import google.colab
    IN_COLAB = True
except ImportError:
    IN_COLAB = False
    logger.warning("Not running in Google Colab. Some features may not work as expected.")


def install_dependencies():
    """Install required dependencies in Colab"""
    if IN_COLAB:
        import subprocess
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 
                       'google-colab-selenium', 'pillow', 'requests'], check=True)
        logger.info("Dependencies installed successfully")


def mount_google_drive():
    """Mount Google Drive in Colab"""
    if IN_COLAB:
        from google.colab import drive
        drive.mount('/content/drive')
        logger.info("Google Drive mounted at /content/drive")
        return True
    return False


class ZalandoGalleryScraperColab:
    def __init__(self, output_dir=None, use_google_drive=True):
        """
        Initialize Zalando scraper optimized for Google Colab
        
        Args:
            output_dir: Directory for saving data. If None, uses Google Drive or /content
            use_google_drive: If True and in Colab, save to Google Drive
        """
        self.use_google_drive = use_google_drive and IN_COLAB
        
        # Set output directory
        if output_dir:
            self.output_dir = Path(output_dir)
        elif self.use_google_drive:
            self.output_dir = Path("/content/drive/MyDrive/vton_gallery_dataset")
        else:
            self.output_dir = Path("/content/vton_gallery_dataset")
        
        # Create directories
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

        logger.info(f"Output directory: {self.output_dir}")
        logger.info(f"Storage: {'Google Drive' if self.use_google_drive else 'Local (Colab runtime)'}")
        
        self.load_progress()

    def load_progress(self):
        """Load scraping progress from storage"""
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
        """Save scraping progress to storage"""
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
        """Initialize Chrome driver using google-colab-selenium"""
        logger.info("Initializing Chrome WebDriver for Google Colab...")
        
        try:
            # Import google-colab-selenium
            from google_colab_selenium import Chrome
            from selenium.webdriver.chrome.options import Options
            
            chrome_options = Options()
            
            # Colab-specific options (google-colab-selenium handles most headless config)
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument(
                'user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            # Additional options for stability
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-plugins')
            chrome_options.add_argument('--disable-sync')
            chrome_options.add_argument('--disable-translate')
            chrome_options.add_argument('--disable-default-apps')
            
            # Use google-colab-selenium's Chrome class
            self.driver = Chrome(options=chrome_options)
            self.driver.set_page_load_timeout(30)
            self.driver.implicitly_wait(10)
            
            logger.info("Chrome WebDriver initialized successfully via google-colab-selenium")
            return self.driver
            
        except ImportError:
            logger.error("google-colab-selenium not installed. Run: !pip install google-colab-selenium")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize ChromeDriver: {e}")
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
        """Download gallery images and save locally"""
        product_dir = self.output_dir / "products" / product_id
        product_dir.mkdir(exist_ok=True, parents=True)

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
                        "index": idx,
                        "local_path": str(filepath)
                    })
                    logger.info(f"    [{idx+1}/{len(product_data['images'])}] {info}")

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
                    logger.info("No new products found for 3 consecutive pages — stopping.")
                    break

                logger.info(f"\n{'='*80}")
                logger.info(f"PAGE {page_num}")
                logger.info(f"{'='*80}")
                
                # Update page stats
                self.stats['total_pages_explored'] += 1

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
                self.stats['total_products_found'] += len(product_links)
                
                # Print page exploration summary
                elapsed = time.time() - self.stats['start_time']
                logger.info(f"[PAGE {page_num} STATS] Products found: {len(product_links)} | Total products so far: {self.stats['total_products_found']} | Time elapsed: {elapsed:.1f}s")

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

                    self.stats['total_products_explored'] += 1
                    logger.info(f"\n[{idx+1}/{len(product_links)}] Processing... (Product #{self.stats['total_products_explored']})")

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
                                    "source": "zalando_gallery_colab",
                                    "title": product_data["title"],
                                    "url": product_url,
                                    "product_directory": str(self.output_dir / "products" / product_id),
                                    "images": downloaded,
                                    "total_images": len(downloaded),
                                    "scraped_at": datetime.now().isoformat(),
                                    "environment": "google_colab",
                                    "storage": "google_drive" if self.use_google_drive else "colab_runtime"
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
        logger.info(f"  Output directory:    {self.output_dir}")
        logger.info(f"  Storage:             {'Google Drive' if self.use_google_drive else 'Colab Runtime'}")
        
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
    Main function to run the scraper in Google Colab
    
    Usage in Colab:
    ```python
    # Cell 1: Install dependencies
    !pip install google-colab-selenium pillow requests
    
    # Cell 2: Mount Google Drive (optional but recommended)
    from google.colab import drive
    drive.mount('/content/drive')
    
    # Cell 3: Run the scraper
    from zalando_gallery_scraper_colab import main
    main()
    ```
    """
    logger.info("="*80)
    logger.info("ZALANDO GALLERY SCRAPER - GOOGLE COLAB OPTIMIZED")
    logger.info("Downloads ONLY main product gallery images (left sidebar)")
    logger.info("Uses google-colab-selenium for Chrome integration")
    logger.info("Saves to Google Drive for persistence")
    logger.info("="*80)

    # Mount Google Drive if in Colab
    if IN_COLAB:
        try:
            mount_google_drive()
        except Exception as e:
            logger.warning(f"Could not mount Google Drive: {e}")
            logger.warning("Data will be saved to /content (lost on runtime disconnect)")

    # ==========================================================================
    # CONFIGURATION
    # ==========================================================================
    # use_google_drive: If True, saves to /content/drive/MyDrive/vton_gallery_dataset
    #                   If False, saves to /content/vton_gallery_dataset (temporary)
    # output_dir: Override default output directory (optional)
    # ==========================================================================

    use_google_drive = True  # Set to False if you don't want to use Google Drive
    output_dir = None  # Use default path based on use_google_drive setting

    scraper = ZalandoGalleryScraperColab(
        output_dir=output_dir,
        use_google_drive=use_google_drive
    )

    try:
        scraper.init_driver()

        sale_url = "https://www.zalando.co.uk/womens-dresses-sale/"
        
        # PRODUCTION MODE: Scrape all pages and unlimited items
        # scraper.scrape_sale_page(sale_url, max_pages=None, max_items=None)

        # TEST MODE: 10 items, 2 pages (recommended for initial testing in Colab)
        scraper.scrape_sale_page(sale_url, max_pages=2, max_items=10)

        logger.info(f"\n[SUMMARY]")
        logger.info(f"Output directory: {scraper.output_dir.absolute()}")
        logger.info(f"Items scraped: {scraper.items_scraped}")
        logger.info(f"Storage: {'Google Drive' if scraper.use_google_drive else 'Colab Runtime'}")

    except KeyboardInterrupt:
        logger.info("\n[INTERRUPTED BY USER]")

    except Exception as e:
        logger.error(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        scraper.close()


# For Colab notebook usage
def run_scraper(sale_url="https://www.zalando.co.uk/womens-dresses-sale/", 
                max_pages=None, 
                max_items=None,
                use_google_drive=True,
                output_dir=None):
    """
    Convenience function to run the scraper with custom parameters
    
    Args:
        sale_url: URL of the Zalando sale page to scrape
        max_pages: Maximum number of pages to scrape (None for unlimited)
        max_items: Maximum number of items to scrape (None for unlimited)
        use_google_drive: Save to Google Drive (True) or Colab runtime (False)
        output_dir: Custom output directory (optional)
    
    Returns:
        ZalandoGalleryScraperColab: The scraper instance (for further inspection)
    
    Example:
        scraper = run_scraper(max_pages=2, max_items=10)
        print(f"Scraped {scraper.items_scraped} items")
    """
    if IN_COLAB and use_google_drive:
        try:
            mount_google_drive()
        except:
            pass

    scraper = ZalandoGalleryScraperColab(
        output_dir=output_dir,
        use_google_drive=use_google_drive
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
