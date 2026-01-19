"""
Generic Web Scraper with Crawlbase API Support
Downloads product gallery images from e-commerce sites with comprehensive features.

Features:
- Scrapes sale pages and individual product pages
- Extracts main product gallery images (excludes color variants)
- Converts thumbnails to high-resolution URLs
- Image validation and deduplication
- Pagination support with auto-stop
- Resume capability after interruption
- Anti-detection measures
- Structured metadata and logging

Usage:
    python any_scraper.py
"""

import requests
import os
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs, urlencode
import hashlib
import json
import re
import logging
from datetime import datetime
from pathlib import Path
from PIL import Image
from io import BytesIO

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AnyScraper:
    """
    Generic e-commerce product image scraper using Crawlbase API.
    Supports pagination, resume, deduplication, and structured output.
    """

    def __init__(self, api_key, output_dir="downloaded_images", min_image_size=400):
        """
        Initialize the scraper.

        Args:
            api_key: Crawlbase API token
            output_dir: Directory for saving images and metadata
            min_image_size: Minimum width/height for images (default 400px)
        """
        self.api_key = api_key
        self.output_dir = Path(output_dir)
        self.min_image_size = min_image_size
        self.items_scraped = 0
        self.scraped_urls = set()
        self.seen_image_hashes = set()

        # Create directory structure
        self.output_dir.mkdir(exist_ok=True, parents=True)
        (self.output_dir / "products").mkdir(exist_ok=True)
        (self.output_dir / "metadata").mkdir(exist_ok=True)
        (self.output_dir / "progress").mkdir(exist_ok=True)

        # Setup session with realistic headers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

        # Load previous progress
        self.load_progress()

        logger.info(f"Scraper initialized. Output directory: {self.output_dir.absolute()}")

    def load_progress(self):
        """Load scraping progress from disk for resume capability."""
        progress_file = self.output_dir / "progress" / "scraper_progress.json"
        if progress_file.exists():
            try:
                with open(progress_file, 'r') as f:
                    data = json.load(f)
                    self.items_scraped = data.get("items_scraped", 0)
                    self.scraped_urls = set(data.get("scraped_urls", []))
                    self.seen_image_hashes = set(data.get("seen_image_hashes", []))
                    logger.info(f"[RESUME] Loaded progress: {self.items_scraped} items already scraped")
            except Exception as e:
                logger.warning(f"Could not load progress: {e}")
                self.scraped_urls = set()
                self.seen_image_hashes = set()
        else:
            logger.info("No previous progress found. Starting fresh.")

    def save_progress(self):
        """Save scraping progress to disk."""
        progress_file = self.output_dir / "progress" / "scraper_progress.json"
        try:
            with open(progress_file, 'w') as f:
                json.dump({
                    "items_scraped": self.items_scraped,
                    "scraped_urls": list(self.scraped_urls),
                    "seen_image_hashes": list(self.seen_image_hashes),
                    "last_updated": datetime.now().isoformat()
                }, f, indent=2)
            logger.debug("Progress saved")
        except Exception as e:
            logger.error(f"Failed to save progress: {e}")

    def fetch_page(self, url):
        """
        Fetch page content using Crawlbase API.

        Args:
            url: URL to fetch

        Returns:
            BeautifulSoup object or None if failed
        """
        params = {
            "token": self.api_key,
            "url": url,
            "smart": "true"
        }

        try:
            logger.debug(f"Fetching: {url}")
            response = requests.get("https://api.crawlbase.com/", params=params, timeout=30)

            if response.status_code == 200:
                # Check for Crawlbase API errors in response
                if "pc_status" in response.text[:100]:
                    try:
                        error_data = json.loads(response.text)
                        if error_data.get("pc_status") != 200:
                            logger.error(f"Crawlbase error: {error_data}")
                            return None
                    except json.JSONDecodeError:
                        pass

                return BeautifulSoup(response.text, "html.parser")
            else:
                logger.error(f"Failed to fetch {url}: HTTP {response.status_code}")
                return None

        except requests.Timeout:
            logger.error(f"Timeout fetching {url}")
            return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def extract_product_id(self, url):
        """
        Extract product ID from URL.
        Handles various URL formats from different e-commerce sites.

        Args:
            url: Product URL

        Returns:
            Product ID string or None
        """
        # Amazon: /dp/ASIN or /gp/product/ASIN
        amazon_match = re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})', url)
        if amazon_match:
            return amazon_match.group(1)

        # Zalando style: product-name.html
        zalando_match = re.search(r'/([a-z0-9\-]+)\.html', url)
        if zalando_match:
            return zalando_match.group(1)

        # Nykaa Fashion: /product-name/p/SKU123 or /p/SKU123
        nykaa_match = re.search(r'/p/([a-zA-Z0-9_-]+)', url)
        if nykaa_match:
            return nykaa_match.group(1)

        # Generic: last path segment before query
        parsed = urlparse(url)
        path_parts = [p for p in parsed.path.split('/') if p]
        if path_parts:
            # Remove .html extension if present
            product_id = re.sub(r'\.html?$', '', path_parts[-1])
            return product_id

        # Fallback: hash of URL
        return hashlib.md5(url.encode()).hexdigest()[:16]

    def get_image_hash(self, image_url):
        """
        Generate hash for image URL to detect duplicates.
        Extracts unique identifier from URL patterns.

        Args:
            image_url: Image URL

        Returns:
            Hash string
        """
        # Try to extract unique image ID from common patterns
        patterns = [
            r'/([a-f0-9]{32,})',  # Hash-based IDs
            r'images/([^/]+)\.',  # Image filename
            r'/(\d+)_',  # Numeric IDs
        ]

        for pattern in patterns:
            match = re.search(pattern, image_url)
            if match:
                return match.group(1)

        # Fallback: hash the URL
        return hashlib.md5(image_url.encode()).hexdigest()

    def convert_to_high_res(self, image_url):
        """
        Convert thumbnail URL to high-resolution version.
        Handles patterns from various e-commerce sites.

        Args:
            image_url: Original image URL

        Returns:
            High-resolution image URL
        """
        high_res = image_url

        # Amazon: Convert to large image
        if 'amazon' in image_url or 'media-amazon' in image_url:
            # Replace size indicators like _SX300_ or _AC_SY300_ with _SL1500_
            high_res = re.sub(r'\._[A-Z]{2}_[A-Z0-9_]+_\.', '._SL1500_.', high_res)
            high_res = re.sub(r'\._[A-Z]+\d+_\.', '._SL1500_.', high_res)

        # Zalando: Convert thumb to original
        elif 'zalando' in image_url or 'spp-media' in image_url:
            high_res = high_res.replace("thumb", "org").replace("sq", "org")
            if ".jpg?" in high_res:
                high_res = high_res.split(".jpg?")[0] + ".jpg"

        # Nykaa Fashion: Convert to high-res
        elif 'nykaa' in image_url or 'akamaized' in image_url:
            # Nykaa uses patterns like w_150,h_150 or tr:w-150,h-150
            # Remove size constraints to get full resolution
            high_res = re.sub(r'/w_\d+,h_\d+/', '/', high_res)
            high_res = re.sub(r'/tr:[^/]+/', '/', high_res)
            high_res = re.sub(r'\?.*$', '', high_res)  # Remove query params

        # Generic: Try common patterns
        else:
            # Remove common thumbnail indicators
            high_res = re.sub(r'[-_](thumb|small|medium|sm|md|xs|s|m)\b', '', high_res, flags=re.IGNORECASE)
            high_res = re.sub(r'/thumb/', '/large/', high_res)
            high_res = re.sub(r'/small/', '/large/', high_res)
            high_res = re.sub(r'\?.*$', '', high_res)  # Remove query params that might limit size

        return high_res

    def validate_and_download_image(self, url, filepath):
        """
        Download and validate image.

        Args:
            url: Image URL
            filepath: Local path to save

        Returns:
            tuple: (success: bool, info: str with dimensions or error)
        """
        try:
            # Add referer header to bypass CDN restrictions
            # Use the main site as referer, not the CDN domain
            if 'nykaa' in url or 'akamaized' in url:
                referer = 'https://www.nykaafashion.com/'
            else:
                referer = urlparse(url).scheme + '://' + urlparse(url).netloc + '/'
            
            headers = {
                'Referer': referer,
                'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'Sec-Fetch-Dest': 'image',
                'Sec-Fetch-Mode': 'no-cors',
                'Sec-Fetch-Site': 'cross-site',
            }
            response = self.session.get(url, timeout=15, headers=headers)
            if response.status_code != 200:
                return False, f"HTTP {response.status_code}"

            # Check content type - should be an image
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' in content_type or 'application/json' in content_type:
                return False, f"Not an image (Content-Type: {content_type})"
            
            # Check if response looks like HTML (error page)
            if response.content[:100].strip().startswith(b'<') or b'<!DOCTYPE' in response.content[:100]:
                return False, "Received HTML instead of image (blocked by CDN)"

            # Validate with PIL
            try:
                img = Image.open(BytesIO(response.content))
                width, height = img.size
            except Exception as e:
                return False, f"Invalid image: {e}"

            # Check minimum size
            if width < self.min_image_size or height < self.min_image_size:
                return False, f"Too small: {width}x{height}"

            # Save image
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, 'wb') as f:
                f.write(response.content)

            return True, f"{width}x{height}"

        except requests.Timeout:
            return False, "Timeout"
        except Exception as e:
            return False, str(e)

    def extract_product_images(self, soup, product_url):
        """
        Extract main product gallery images from page.
        Excludes color variants and duplicates.

        Args:
            soup: BeautifulSoup object of product page
            product_url: Product URL for context

        Returns:
            list of high-resolution image URLs
        """
        gallery_images = []
        seen_hashes = set()

        # Determine site type
        site_type = "generic"
        if "amazon" in product_url:
            site_type = "amazon"
        elif "zalando" in product_url:
            site_type = "zalando"
        elif "nykaa" in product_url:
            site_type = "nykaa"

        # Strategy 1: Amazon-specific selectors
        if site_type == "amazon":
            # Main image
            main_img = soup.select_one('#landingImage, #imgBlkFront, .a-dynamic-image')
            if main_img:
                src = main_img.get('data-old-hires') or main_img.get('data-a-dynamic-image') or main_img.get('src')
                if src:
                    # Handle data-a-dynamic-image JSON
                    if src.startswith('{'):
                        try:
                            urls = json.loads(src)
                            src = max(urls.keys(), key=lambda x: urls[x][0] * urls[x][1])
                        except:
                            pass
                    if src and not src.startswith('data:'):
                        high_res = self.convert_to_high_res(src)
                        img_hash = self.get_image_hash(high_res)
                        if img_hash not in seen_hashes:
                            seen_hashes.add(img_hash)
                            gallery_images.append(high_res)

            # Thumbnail gallery
            thumbs = soup.select('#altImages img, .imageThumbnail img, #imageBlock img')
            for thumb in thumbs:
                src = thumb.get('src') or thumb.get('data-old-hires')
                if not src or src.startswith('data:'):
                    continue

                # Skip video thumbnails
                if 'play-button' in src.lower() or 'video' in thumb.get('class', []):
                    continue

                high_res = self.convert_to_high_res(src)
                img_hash = self.get_image_hash(high_res)

                if img_hash not in seen_hashes:
                    seen_hashes.add(img_hash)
                    gallery_images.append(high_res)

        # Strategy 2: Zalando-specific selectors
        elif site_type == "zalando":
            selectors = [
                "[data-testid='product_gallery_refactored'] img",
                "[class*='gallery'] img[src*='spp-media']",
                "[class*='thumbnail'] img[src*='spp-media']",
                "button img[src*='spp-media']"
            ]

            for selector in selectors:
                imgs = soup.select(selector)
                for img in imgs:
                    src = img.get('src')
                    if not src or 'spp-media' not in src:
                        continue

                    high_res = self.convert_to_high_res(src)
                    img_hash = self.get_image_hash(high_res)

                    if img_hash not in seen_hashes:
                        seen_hashes.add(img_hash)
                        gallery_images.append(high_res)

        # Strategy 3: Nykaa Fashion-specific selectors
        elif site_type == "nykaa":
            # Nykaa product page selectors
            selectors = [
                '.product-images img',
                '.pdp-image-carousel img',
                '[class*="ProductImage"] img',
                '[class*="product-gallery"] img',
                '[class*="slider"] img',
                '[class*="carousel"] img',
                'img[src*="nykaa"]',
                'img[src*="akamaized"]',
            ]

            for selector in selectors:
                imgs = soup.select(selector)
                for img in imgs:
                    src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                    if not src or src.startswith('data:'):
                        continue

                    # Skip tiny icons and non-product images
                    skip_patterns = ['icon', 'logo', 'sprite', 'placeholder', 'lazy']
                    if any(pattern in src.lower() for pattern in skip_patterns):
                        continue

                    src = urljoin(product_url, src)
                    high_res = self.convert_to_high_res(src)
                    img_hash = self.get_image_hash(high_res)

                    if img_hash not in seen_hashes:
                        seen_hashes.add(img_hash)
                        gallery_images.append(high_res)

        # Strategy 4: Generic approach
        else:
            # Common gallery selectors
            selectors = [
                '.product-gallery img',
                '.product-images img',
                '[data-gallery] img',
                '.gallery img',
                '.carousel img',
                '.slider img',
                '.product-image img',
                '.main-image img',
                '#product-images img',
            ]

            for selector in selectors:
                imgs = soup.select(selector)
                for img in imgs:
                    src = img.get('src') or img.get('data-src') or img.get('data-lazy')
                    if not src or src.startswith('data:'):
                        continue

                    src = urljoin(product_url, src)
                    high_res = self.convert_to_high_res(src)
                    img_hash = self.get_image_hash(high_res)

                    if img_hash not in seen_hashes:
                        seen_hashes.add(img_hash)
                        gallery_images.append(high_res)

        # Fallback: Find all product-related images
        if len(gallery_images) < 2:
            all_imgs = soup.find_all('img')
            for img in all_imgs:
                src = img.get('src') or img.get('data-src') or img.get('data-lazy')
                if not src or src.startswith('data:'):
                    continue

                # Skip common non-product images
                skip_patterns = [
                    'logo', 'icon', 'badge', 'banner', 'sprite',
                    'pixel', 'tracking', 'ad', 'promo', 'nav',
                    'footer', 'header', 'social', 'button'
                ]
                if any(pattern in src.lower() for pattern in skip_patterns):
                    continue

                src = urljoin(product_url, src)
                high_res = self.convert_to_high_res(src)
                img_hash = self.get_image_hash(high_res)

                if img_hash not in seen_hashes:
                    seen_hashes.add(img_hash)
                    gallery_images.append(high_res)

        return gallery_images

    def extract_product_title(self, soup):
        """
        Extract product title from page.

        Args:
            soup: BeautifulSoup object

        Returns:
            Product title string
        """
        # Try common title selectors
        selectors = [
            '#productTitle',
            'h1.product-title',
            'h1[data-testid="product-title"]',
            '.product-name h1',
            'h1',
        ]

        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                title = element.get_text(strip=True)
                if title and len(title) > 3:
                    return title[:200]  # Limit length

        return "Unknown Product"

    def scrape_product(self, product_url):
        """
        Scrape a single product page.

        Args:
            product_url: Product URL

        Returns:
            dict with product data or None if failed
        """
        logger.info(f"  Fetching product page...")
        soup = self.fetch_page(product_url)

        if not soup:
            return None

        title = self.extract_product_title(soup)
        logger.info(f"  Product: {title[:60]}...")

        images = self.extract_product_images(soup, product_url)
        logger.info(f"  Found {len(images)} gallery images")

        if len(images) >= 2:
            return {
                "title": title,
                "url": product_url,
                "images": images
            }

        return None

    def download_product_images(self, product_data, product_id):
        """
        Download all images for a product.

        Args:
            product_data: Product data dict with images list
            product_id: Product ID for folder naming

        Returns:
            list of downloaded image info dicts
        """
        product_dir = self.output_dir / "products" / product_id
        product_dir.mkdir(exist_ok=True, parents=True)

        downloaded_images = []

        for idx, img_url in enumerate(product_data["images"]):
            # Check for global duplicates
            img_hash = self.get_image_hash(img_url)
            if img_hash in self.seen_image_hashes:
                logger.debug(f"    Skipping duplicate image: {img_url[:50]}...")
                continue

            filename = f"image_{idx:02d}.jpg"
            filepath = product_dir / filename

            success, info = self.validate_and_download_image(img_url, filepath)

            if success:
                self.seen_image_hashes.add(img_hash)
                downloaded_images.append({
                    "filename": filename,
                    "url": img_url,
                    "size": info,
                    "index": idx
                })
                logger.info(f"    [{idx+1}/{len(product_data['images'])}] Downloaded: {info}")
            else:
                logger.info(f"    [{idx+1}/{len(product_data['images'])}] SKIPPED: {info} - {img_url[:80]}")

        return downloaded_images

    def extract_product_links(self, soup, base_url):
        """
        Extract product links from a listing page.

        Args:
            soup: BeautifulSoup object
            base_url: Base URL for resolving relative links

        Returns:
            list of product URLs
        """
        product_links = []

        # Determine site type for specific selectors
        site_type = "generic"
        if "nykaa" in base_url:
            site_type = "nykaa"
        elif "amazon" in base_url:
            site_type = "amazon"
        elif "zalando" in base_url:
            site_type = "zalando"

        # Nykaa Fashion specific selectors
        if site_type == "nykaa":
            selectors = [
                'a[href*="/p/"]',  # Nykaa product URLs contain /p/SKU
                '[class*="product"] a[href*="/p/"]',
                '[class*="Product"] a[href*="/p/"]',
                '.product-card a',
                '.product-list a[href*="/p/"]',
                '[data-product] a',
            ]
        else:
            # Generic/other site selectors
            selectors = [
                'article a[href*=".html"]',  # Zalando style
                'a[href*="/dp/"]',  # Amazon style
                'a[href*="/product/"]',
                'a[href*="/p/"]',
                '.product-card a',
                '.product-item a',
                '.product-link',
                '[data-product] a',
            ]

        for selector in selectors:
            links = soup.select(selector)
            for link in links:
                href = link.get('href')
                if href:
                    full_url = urljoin(base_url, href)
                    # For Nykaa, ensure it's a product page (contains /p/)
                    if site_type == "nykaa":
                        if '/p/' in full_url and full_url not in product_links:
                            product_links.append(full_url)
                    elif full_url not in product_links:
                        product_links.append(full_url)

        return product_links

    def scrape_listing_page(self, listing_url, max_pages=None, max_items=None):
        """
        Scrape a listing/sale page with pagination.

        Args:
            listing_url: Starting URL
            max_pages: Maximum pages to scrape (None for unlimited)
            max_items: Maximum items to scrape (None for unlimited)
        """
        logger.info("=" * 80)
        logger.info(f"SCRAPING LISTING: {listing_url}")
        logger.info(f"Max Pages: {max_pages or 'Unlimited'}, Max Items: {max_items or 'Unlimited'}")
        logger.info("=" * 80)

        items_this_run = 0
        page_num = 1
        consecutive_empty_pages = 0

        while True:
            # Check limits
            if max_items and items_this_run >= max_items:
                logger.info(f"Reached max_items limit ({max_items})")
                break
            if max_pages and page_num > max_pages:
                logger.info(f"Reached max_pages limit ({max_pages})")
                break
            if consecutive_empty_pages >= 3:
                logger.info("No new products for 3 consecutive pages - stopping")
                break

            logger.info(f"\n{'='*60}")
            logger.info(f"PAGE {page_num}")
            logger.info(f"{'='*60}")

            # Build page URL
            if page_num == 1:
                page_url = listing_url
            else:
                # Add pagination parameter
                parsed = urlparse(listing_url)
                params = parse_qs(parsed.query)
                params['p'] = [str(page_num)]
                new_query = urlencode(params, doseq=True)
                page_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{new_query}"

            soup = self.fetch_page(page_url)
            if not soup:
                logger.error(f"Failed to fetch page {page_num}")
                consecutive_empty_pages += 1
                page_num += 1
                continue

            # Extract product links
            product_links = self.extract_product_links(soup, page_url)
            logger.info(f"Found {len(product_links)} products on page {page_num}")

            if not product_links:
                logger.info("No products found - stopping pagination")
                break

            # Check for new products
            new_links = [l for l in product_links if l not in self.scraped_urls]
            if not new_links:
                consecutive_empty_pages += 1
                logger.info(f"No new products on page {page_num} (consecutive empty: {consecutive_empty_pages})")
                page_num += 1
                continue
            else:
                consecutive_empty_pages = 0

            # Process each product
            for idx, product_url in enumerate(product_links):
                if max_items and items_this_run >= max_items:
                    break

                if product_url in self.scraped_urls:
                    logger.info(f"\n[{idx+1}/{len(product_links)}] Skipping (already scraped)")
                    continue

                logger.info(f"\n[{idx+1}/{len(product_links)}] Processing...")

                try:
                    product_id = self.extract_product_id(product_url)
                    if not product_id:
                        logger.warning("  Could not extract product ID")
                        continue

                    product_data = self.scrape_product(product_url)

                    if product_data and len(product_data["images"]) >= 2:
                        downloaded = self.download_product_images(product_data, product_id)

                        if len(downloaded) >= 2:
                            # Save metadata
                            metadata = {
                                "item_id": self.items_scraped,
                                "product_id": product_id,
                                "source": "any_scraper",
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
                            items_this_run += 1
                            self.scraped_urls.add(product_url)

                            logger.info(f"  [SUCCESS] Item {self.items_scraped} | {len(downloaded)} images saved")

                            # Save progress periodically
                            if self.items_scraped % 10 == 0:
                                self.save_progress()

                except Exception as e:
                    logger.error(f"  [ERROR] {e}")
                    continue

            page_num += 1

        # Final summary
        logger.info(f"\n{'='*80}")
        logger.info("SCRAPING COMPLETE")
        logger.info(f"Items scraped this run: {items_this_run}")
        logger.info(f"Total items scraped: {self.items_scraped}")
        logger.info(f"{'='*80}")

    def scrape_single_product(self, product_url):
        """
        Scrape a single product URL.

        Args:
            product_url: Product URL to scrape
        """
        logger.info("=" * 80)
        logger.info(f"SCRAPING PRODUCT: {product_url}")
        logger.info("=" * 80)

        if product_url in self.scraped_urls:
            logger.info("Product already scraped. Skipping.")
            return

        try:
            product_id = self.extract_product_id(product_url)
            product_data = self.scrape_product(product_url)

            if product_data:
                downloaded = self.download_product_images(product_data, product_id)

                if downloaded:
                    # Save metadata
                    metadata = {
                        "item_id": self.items_scraped,
                        "product_id": product_id,
                        "source": "any_scraper",
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
                    self.scraped_urls.add(product_url)
                    self.save_progress()

                    logger.info(f"\n[SUCCESS] Downloaded {len(downloaded)} images")
                else:
                    logger.warning("No valid images downloaded")
            else:
                logger.warning("Could not extract product data")

        except Exception as e:
            logger.error(f"Error scraping product: {e}")

    def close(self):
        """Clean up resources."""
        self.save_progress()
        self.session.close()
        logger.info("Scraper closed successfully")


def main():
    """Main entry point."""
    logger.info("=" * 80)
    logger.info("GENERIC WEB SCRAPER WITH CRAWLBASE")
    logger.info("Downloads product gallery images with validation and deduplication")
    logger.info("=" * 80)

    # ==========================================================================
    # CONFIGURATION
    # ==========================================================================
    api_key = os.environ.get("CRAWLBASE_TOKEN", "ABCDEFGHIJKLMNOPQRST")  # Replace with your Crawlbase API key
    output_dir = "downloaded_images"

    # Nykaa Fashion listing page
    listing_url = "https://www.nykaafashion.com/men/topwear/t-shirts/c/6825"

    # Example single product (uncomment to use):
    # product_url = "https://www.nykaafashion.com/product-name/p/SKU123"
    # ==========================================================================

    scraper = AnyScraper(
        api_key=api_key,
        output_dir=output_dir,
        min_image_size=400
    )

    try:
        # Scrape Nykaa Fashion listing page - no limits (scrape all pages and items)
        scraper.scrape_listing_page(listing_url, max_pages=None, max_items=None)

        # Or scrape single product:
        # scraper.scrape_single_product(product_url)

        logger.info(f"\n[SUMMARY]")
        logger.info(f"Output directory: {scraper.output_dir.absolute()}")
        logger.info(f"Total items scraped: {scraper.items_scraped}")

    except KeyboardInterrupt:
        logger.info("\n[INTERRUPTED BY USER]")

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        scraper.close()


if __name__ == "__main__":
    main()
