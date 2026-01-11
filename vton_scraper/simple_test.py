"""
Simple VTON Scraper Test - Verbose output to understand what's happening
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


def test_zalando_uk():
    """Test Zalando UK - single product"""
    print("\n" + "="*80)
    print("TEST 1: ZALANDO UK - Single Product")
    print("="*80)

    output_dir = Path("test_output")
    output_dir.mkdir(exist_ok=True)

    options = uc.ChromeOptions()
    options.add_argument('--disable-blink-features=AutomationControlled')

    driver = uc.Chrome(options=options, version_main=None)
    driver.set_page_load_timeout(30)

    try:
        # Go to a specific dress product page (known to have images)
        url = "https://www.zalando.co.uk/friboo-jersey-dress-dark-blue-fr121c0jo-k11.html"

        print(f"\n[1] Loading product page...")
        print(f"    URL: {url}")
        driver.get(url)
        time.sleep(5)

        # Save screenshot
        driver.save_screenshot("test_output/zalando_product_page.png")
        print(f"[2] Screenshot saved: test_output/zalando_product_page.png")

        # Get page title
        print(f"[3] Page title: {driver.title}")

        # Find all images
        all_images = driver.find_elements(By.TAG_NAME, "img")
        print(f"[4] Total images on page: {len(all_images)}")

        # Filter for product images
        product_images = []
        for img in all_images:
            src = img.get_attribute("src")
            if src:
                print(f"    Image src: {src[:100]}...")
                if "mosaic" in src and "zalando" in src:
                    product_images.append(src)
                    print(f"      -> PRODUCT IMAGE FOUND!")

        print(f"\n[5] Product images found: {len(product_images)}")

        if len(product_images) >= 2:
            print(f"\n[6] Testing image downloads...")

            session = requests.Session()
            session.headers.update({'User-Agent': 'Mozilla/5.0'})

            for i, img_url in enumerate(product_images[:2]):
                try:
                    print(f"\n    Downloading image {i+1}...")
                    print(f"    URL: {img_url[:80]}...")

                    response = session.get(img_url, timeout=10)

                    if response.status_code == 200:
                        img = Image.open(BytesIO(response.content))
                        width, height = img.size
                        print(f"    Size: {width}x{height}")

                        filepath = output_dir / f"zalando_test_{i+1}.jpg"
                        with open(filepath, 'wb') as f:
                            f.write(response.content)
                        print(f"    Saved: {filepath}")
                        print(f"    [SUCCESS]")
                    else:
                        print(f"    HTTP {response.status_code}")

                except Exception as e:
                    print(f"    Error: {e}")

            print(f"\n[ZALANDO TEST COMPLETE]")
            print(f"Check test_output/ folder for images")

        else:
            print(f"\n[FAILED] Not enough product images found")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()

    finally:
        driver.quit()


def test_amazon():
    """Test Amazon - see what's blocking us"""
    print("\n" + "="*80)
    print("TEST 2: AMAZON - Diagnosis")
    print("="*80)

    output_dir = Path("test_output")
    output_dir.mkdir(exist_ok=True)

    options = uc.ChromeOptions()
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    driver = uc.Chrome(options=options, version_main=None)
    driver.set_page_load_timeout(45)

    # Hide automation
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    try:
        # Try Amazon home page first
        print(f"\n[1] Testing Amazon home page...")
        driver.get("https://www.amazon.com")
        time.sleep(4)

        driver.save_screenshot("test_output/amazon_home.png")
        print(f"[2] Screenshot: test_output/amazon_home.png")

        page_text = driver.page_source.lower()

        if "captcha" in page_text or "robot" in page_text:
            print(f"\n[WARNING] Bot detection on home page!")
            print(f"Screenshot saved. You may need to:")
            print(f"  1. Use a VPN or proxy")
            print(f"  2. Solve CAPTCHA manually")
            print(f"  3. Try from a residential IP")
        else:
            print(f"[3] No bot detection on home page")

            # Try search
            print(f"\n[4] Trying search...")
            search_url = "https://www.amazon.com/s?k=dress"
            driver.get(search_url)
            time.sleep(4)

            driver.save_screenshot("test_output/amazon_search.png")
            print(f"[5] Screenshot: test_output/amazon_search.png")

            page_text = driver.page_source.lower()

            if "captcha" in page_text or "robot" in page_text:
                print(f"\n[WARNING] Bot detection on search!")
            else:
                print(f"[6] Search page loaded")

                # Find products
                products = driver.find_elements(By.CSS_SELECTOR, "[data-asin]")
                products_with_asin = [p for p in products if p.get_attribute("data-asin")]

                print(f"[7] Products found: {len(products_with_asin)}")

                if len(products_with_asin) > 0:
                    print(f"\n[AMAZON TEST SUCCESSFUL]")
                    print(f"Amazon is accessible from your IP")
                else:
                    print(f"\n[INFO] No products found")
                    print(f"Check screenshot to see what's shown")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        driver.save_screenshot("test_output/amazon_error.png")

    finally:
        print(f"\nKeeping browser open for 10 seconds...")
        print(f"Check the screenshots in test_output/ folder")
        time.sleep(10)
        driver.quit()


def main():
    print("="*80)
    print("VTON SCRAPER - SIMPLE DIAGNOSTIC TEST")
    print("="*80)
    print("\nThis will:")
    print("1. Test Zalando UK with a known product URL")
    print("2. Test Amazon access and bot detection")
    print("3. Save screenshots and images to test_output/")
    print("\n" + "="*80)

    input("\nPress Enter to start...")

    # Test Zalando
    test_zalando_uk()

    input("\nZalando test done. Press Enter for Amazon test...")

    # Test Amazon
    test_amazon()

    print("\n" + "="*80)
    print("TESTS COMPLETE")
    print("="*80)
    print(f"\nCheck test_output/ folder for:")
    print(f"  - zalando_test_1.jpg / zalando_test_2.jpg")
    print(f"  - zalando_product_page.png")
    print(f"  - amazon_home.png / amazon_search.png")
    print("\nThese files will help diagnose any issues.")


if __name__ == "__main__":
    main()
