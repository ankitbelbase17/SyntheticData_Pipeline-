"""
Production Zalando VTON Scraper - Scaled for 200K items
"""

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import time
import requests
from pathlib import Path
from PIL import Image
from io import BytesIO
import json
import random
from datetime import datetime


# CONFIGURATION FOR 200K SCALE
ZALANDO_SITES = {
    "uk": {
        "base_url": "https://www.zalando.co.uk",
        "categories": [
            "/womens-clothing-dresses/",
            "/womens-clothing-tops/",
            "/womens-clothing-shirts-blouses/",
            "/womens-clothing-t-shirts/",
            "/womens-clothing-jumpers-cardigans/",
            "/mens-clothing-shirts/",
            "/mens-clothing-t-shirts/",
            "/mens-clothing-polo-shirts/",
            "/mens-clothing-jumpers-cardigans/",
        ]
    },
    "de": {
        "base_url": "https://www.zalando.de",
        "categories": [
            "/damen-bekleidung-kleider/",
            "/damen-bekleidung-tops/",
            "/herren-bekleidung-hemden/",
            "/herren-bekleidung-t-shirts/",
        ]
    },
    "fr": {
        "base_url": "https://www.zalando.fr",
        "categories": [
            "/vetements-femme-robes/",
            "/vetements-femme-hauts/",
            "/vetements-homme-chemises/",
            "/vetements-homme-t-shirts/",
        ]
    },
}


class ProductionVTONScraper:
    def __init__(self, output_dir="vton_production_dataset", target_items=200000):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        (self.output_dir / "cloth_images").mkdir(exist_ok=True)
        (self.output_dir / "model_images").mkdir(exist_ok=True)
        (self.output_dir / "metadata").mkdir(exist_ok=True)
        (self.output_dir / "progress").mkdir(exist_ok=True)

        self.driver = None
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0'})

        self.items_scraped = 0
        self.target_items = target_items
        self.items_failed = 0

        # Load progress
        self.load_progress()

    def load_progress(self):
        """Load previous progress"""
        progress_file = self.output_dir / "progress" / "scraper_progress.json"
        if progress_file.exists():
            with open(progress_file, 'r') as f:
                data = json.load(f)
                self.items_scraped = data.get("items_scraped", 0)
                self.items_failed = data.get("items_failed", 0)
                print(f"\n[RESUME] Loaded progress: {self.items_scraped} items scraped")

    def save_progress(self):
        """Save progress"""
        progress_file = self.output_dir / "progress" / "scraper_progress.json"
        with open(progress_file, 'w') as f:
            json.dump({
                "items_scraped": self.items_scraped,
                "items_failed": self.items_failed,
                "last_updated": datetime.now().isoformat(),
                "progress_percent": (self.items_scraped / self.target_items) * 100
            }, f, indent=2)

    def init_driver(self):
        options = uc.ChromeOptions()
        options.add_argument('--headless=new')  # Headless for production
        options.add_argument('--disable-blink-features=AutomationControlled')
        self.driver = uc.Chrome(options=options, version_main=None)
        self.driver.set_page_load_timeout(30)
        return self.driver

    def random_delay(self, min_sec=2, max_sec=4):
        time.sleep(random.uniform(min_sec, max_sec))

    def download_image(self, url, filepath):
        """Download and validate image"""
        try:
            response = self.session.get(url, timeout=15)
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content))
                width, height = img.size

                if width < 400 or height < 400:
                    return False, f"{width}x{height} too small"

                with open(filepath, 'wb') as f:
                    f.write(response.content)

                return True, f"{width}x{height}"
        except Exception as e:
            return False, str(e)
        return False, "Unknown error"

    def get_product_images(self, product_url):
        """Extract images from product page"""
        try:
            self.driver.get(product_url)
            self.random_delay(3, 5)

            title = self.driver.find_element(By.CSS_SELECTOR, "h1").text

            images_collected = []
            img_elements = self.driver.find_elements(By.CSS_SELECTOR, "img[src*='spp-media-p1']")

            tried_urls = set()

            for img_elem in img_elements[:10]:
                try:
                    src = img_elem.get_attribute("src")

                    if not src or src in tried_urls:
                        continue

                    tried_urls.add(src)

                    if "thumb" in src or "sq" in src:
                        continue

                    high_res = src.replace("thumb", "org").replace("sq", "org")

                    if ".jpg?" in high_res:
                        high_res = high_res.split(".jpg?")[0] + ".jpg"

                    if high_res not in images_collected:
                        images_collected.append(high_res)

                    if len(images_collected) >= 6:
                        break

                except:
                    continue

            if len(images_collected) >= 2:
                return {"title": title, "url": product_url, "images": images_collected}

            return None

        except Exception as e:
            return None

    def scrape_category(self, base_url, category_path, items_per_category=1000):
        """Scrape a single category"""
        full_url = base_url + category_path

        print(f"\n{'='*80}")
        print(f"Category: {category_path}")
        print(f"Target: {items_per_category} items")
        print(f"{'='*80}")

        try:
            self.driver.get(full_url)
            self.random_delay(3, 5)

            # Accept cookies
            try:
                accept = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Accept')]")
                accept.click()
                time.sleep(2)
            except:
                pass

            # Pagination - scroll and load more
            for scroll in range(5):  # Adjust for more products
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)

            # Get product links
            product_links = []
            links = self.driver.find_elements(By.CSS_SELECTOR, "article a[href*='.html']")

            for link in links:
                href = link.get_attribute("href")
                if href and ".html" in href and href not in product_links:
                    product_links.append(href)

            print(f"Found {len(product_links)} products")

            # Process products
            items_success = 0

            for idx, product_url in enumerate(product_links):
                if self.items_scraped >= self.target_items:
                    print(f"\n[TARGET REACHED] {self.items_scraped} items!")
                    return

                if items_success >= items_per_category:
                    break

                try:
                    product_data = self.get_product_images(product_url)

                    if product_data and len(product_data["images"]) >= 2:
                        item_id = f"zalando_{self.items_scraped}"

                        cloth_path = self.output_dir / "cloth_images" / f"{item_id}.jpg"
                        model_path = self.output_dir / "model_images" / f"{item_id}.jpg"

                        cloth_ok, cloth_info = self.download_image(product_data["images"][0], cloth_path)
                        model_ok, model_info = self.download_image(product_data["images"][1], model_path)

                        if cloth_ok and model_ok:
                            metadata = {
                                "item_id": item_id,
                                "source": "zalando",
                                "title": product_data["title"],
                                "url": product_url,
                                "cloth_image": str(cloth_path),
                                "model_image": str(model_path),
                                "cloth_size": cloth_info,
                                "model_size": model_info,
                                "scraped_at": datetime.now().isoformat()
                            }

                            with open(self.output_dir / "metadata" / f"{item_id}.json", 'w') as f:
                                json.dump(metadata, f, indent=2)

                            self.items_scraped += 1
                            items_success += 1

                            # Save progress every 20 items
                            if self.items_scraped % 20 == 0:
                                self.save_progress()
                                print(f"\n[PROGRESS] {self.items_scraped}/{self.target_items} ({(self.items_scraped/self.target_items)*100:.1f}%)")

                    self.random_delay(2, 4)

                except Exception as e:
                    self.items_failed += 1
                    continue

            print(f"\nCategory complete: {items_success} items")

        except Exception as e:
            print(f"\nCategory error: {e}")

    def run(self):
        """Main scraping loop"""
        print("="*80)
        print("PRODUCTION VTON SCRAPER")
        print("="*80)
        print(f"Target: {self.target_items} items")
        print(f"Starting from: {self.items_scraped} items")
        print(f"Output: {self.output_dir}")
        print("="*80)

        try:
            self.init_driver()

            # Scrape all sites and categories
            for site_code, site_data in ZALANDO_SITES.items():
                if self.items_scraped >= self.target_items:
                    break

                base_url = site_data["base_url"]
                print(f"\n\n{'#'*80}")
                print(f"SITE: {site_code.upper()} - {base_url}")
                print(f"{'#'*80}")

                for category in site_data["categories"]:
                    if self.items_scraped >= self.target_items:
                        break

                    self.scrape_category(base_url, category, items_per_category=5000)

            print("\n" + "="*80)
            print("SCRAPING COMPLETE!")
            print("="*80)
            print(f"Total items: {self.items_scraped}")
            print(f"Failed: {self.items_failed}")
            print(f"Success rate: {(self.items_scraped/(self.items_scraped+self.items_failed))*100:.1f}%")

        except KeyboardInterrupt:
            print("\n\n[INTERRUPTED] Saving progress...")
            self.save_progress()

        except Exception as e:
            print(f"\nError: {e}")

        finally:
            self.save_progress()
            if self.driver:
                self.driver.quit()


if __name__ == "__main__":
    # For testing: set target to 50 items
    # For production: set target to 200000
    scraper = ProductionVTONScraper(target_items=50)  # Change to 200000 for full run
    scraper.run()
