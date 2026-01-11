"""
Test scraper with specific Zalando product URL
This will show us exactly what data is available and how to extract it
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


def test_zalando_specific_url():
    """Test with the specific Zalando URL provided by user"""

    # Your specific URL
    url = "https://www.zalando.co.uk/tommy-jeans-original-tee-regular-fit-basic-t-shirt-tob22o018-a11.html"

    print("="*80)
    print("TESTING ZALANDO WITH YOUR SPECIFIC URL")
    print("="*80)
    print(f"\nURL: {url}\n")

    # Setup output
    output_dir = Path("test_output")
    output_dir.mkdir(exist_ok=True)

    # Initialize driver
    options = uc.ChromeOptions()
    options.add_argument('--disable-blink-features=AutomationControlled')

    driver = uc.Chrome(options=options, version_main=None)
    driver.set_page_load_timeout(30)
    driver.maximize_window()

    try:
        print("[STEP 1] Loading product page...")
        driver.get(url)
        time.sleep(5)

        # Save initial screenshot
        driver.save_screenshot("test_output/page_initial.png")
        print("[STEP 2] Initial screenshot saved")

        # Get page title
        print(f"[STEP 3] Page title: {driver.title}")

        # Check for cookie banner and accept
        try:
            print("[STEP 4] Looking for cookie banner...")
            cookie_buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'Accept') or contains(text(), 'Agree')]")
            if cookie_buttons:
                cookie_buttons[0].click()
                print("         Cookie banner accepted")
                time.sleep(2)
            else:
                print("         No cookie banner found")
        except Exception as e:
            print(f"         No cookie banner (this is fine)")

        # Scroll down to load lazy images
        print("[STEP 5] Scrolling to load images...")
        for i in range(3):
            driver.execute_script(f"window.scrollTo(0, {(i+1)*500});")
            time.sleep(0.5)

        # Find ALL images on page
        print("\n[STEP 6] Analyzing all images on page...")
        all_imgs = driver.find_elements(By.TAG_NAME, "img")
        print(f"         Total <img> tags found: {len(all_imgs)}")

        # Categorize images
        product_images = []
        other_images = []

        for idx, img in enumerate(all_imgs):
            src = img.get_attribute("src")
            alt = img.get_attribute("alt")

            if src:
                # Check if it's a product image
                if any(keyword in src for keyword in ["mosaic", "img-product", "packshot"]):
                    product_images.append({
                        "index": idx,
                        "src": src,
                        "alt": alt
                    })
                    print(f"\n   [PRODUCT IMAGE {len(product_images)}]")
                    print(f"   Alt: {alt}")
                    print(f"   URL: {src[:100]}...")
                else:
                    other_images.append(src[:80])

        print(f"\n[STEP 7] Summary:")
        print(f"         Product images: {len(product_images)}")
        print(f"         Other images: {len(other_images)}")

        # Try different selectors for product images
        print("\n[STEP 8] Testing different image selectors...")

        selectors = [
            ("CSS: img[src*='mosaic']", By.CSS_SELECTOR, "img[src*='mosaic']"),
            ("CSS: img[src*='packshot']", By.CSS_SELECTOR, "img[src*='packshot']"),
            ("CSS: .z-navicat-header_image", By.CSS_SELECTOR, ".z-navicat-header_image"),
            ("CSS: [class*='image']", By.CSS_SELECTOR, "[class*='image']"),
        ]

        for name, by, selector in selectors:
            try:
                elements = driver.find_elements(by, selector)
                print(f"   {name}: {len(elements)} found")
            except:
                print(f"   {name}: Error")

        # Look for image gallery or carousel
        print("\n[STEP 9] Looking for image gallery/carousel...")
        try:
            gallery = driver.find_elements(By.CSS_SELECTOR, "[data-testid*='image'], [class*='gallery'], [class*='carousel']")
            print(f"         Gallery elements found: {len(gallery)}")
        except:
            print(f"         No gallery found")

        # Save detailed screenshot
        driver.save_screenshot("test_output/page_full.png")
        print("\n[STEP 10] Full page screenshot saved")

        # Now try to download the product images we found
        if len(product_images) >= 2:
            print(f"\n[STEP 11] Attempting to download top 2 product images...")

            session = requests.Session()
            session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

            downloaded = []

            for i, img_data in enumerate(product_images[:2]):
                img_url = img_data["src"]

                # Try to get high-res version
                high_res_url = img_url.replace("thumb", "large").replace("sq", "org")

                print(f"\n   Image {i+1}:")
                print(f"   Original: {img_url[:80]}...")
                print(f"   High-res: {high_res_url[:80]}...")

                try:
                    response = session.get(high_res_url, timeout=10)

                    if response.status_code == 200:
                        img = Image.open(BytesIO(response.content))
                        width, height = img.size
                        size_kb = len(response.content) / 1024

                        print(f"   Downloaded: {width}x{height} pixels, {size_kb:.1f} KB")

                        # Save
                        filename = f"zalando_image_{i+1}.jpg"
                        filepath = output_dir / filename
                        with open(filepath, 'wb') as f:
                            f.write(response.content)

                        print(f"   Saved: {filepath}")
                        downloaded.append({
                            "filename": filename,
                            "url": high_res_url,
                            "size": f"{width}x{height}",
                            "alt": img_data["alt"]
                        })
                    else:
                        print(f"   Failed: HTTP {response.status_code}")

                except Exception as e:
                    print(f"   Error: {e}")

            # Save metadata
            if downloaded:
                metadata = {
                    "url": url,
                    "title": driver.title,
                    "images_downloaded": len(downloaded),
                    "images": downloaded
                }

                with open(output_dir / "metadata.json", 'w') as f:
                    json.dump(metadata, f, indent=2)

                print(f"\n[SUCCESS] Downloaded {len(downloaded)} images!")
                print(f"Metadata saved to: test_output/metadata.json")

        else:
            print(f"\n[ISSUE] Found only {len(product_images)} product images, need at least 2")
            print(f"This might be a selector issue. Let me save the page HTML for analysis...")

            with open(output_dir / "page_source.html", 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            print(f"Page HTML saved to: test_output/page_source.html")

        print("\n" + "="*80)
        print("TEST COMPLETE")
        print("="*80)
        print(f"\nCheck the test_output/ folder:")
        print(f"  - page_initial.png      (screenshot when page loads)")
        print(f"  - page_full.png         (screenshot after scrolling)")
        print(f"  - zalando_image_1.jpg   (downloaded product image)")
        print(f"  - zalando_image_2.jpg   (downloaded model image)")
        print(f"  - metadata.json         (image details)")

        # Keep browser open for manual inspection
        print(f"\nBrowser will stay open for 30 seconds so you can inspect...")
        print(f"You can manually check what images are visible on the page.")
        time.sleep(30)

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        driver.save_screenshot("test_output/error.png")

    finally:
        driver.quit()


def test_amazon_with_login_check():
    """Test Amazon and check if login helps"""

    print("\n" + "="*80)
    print("TESTING AMAZON (Login Check)")
    print("="*80)

    output_dir = Path("test_output")
    output_dir.mkdir(exist_ok=True)

    options = uc.ChromeOptions()
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    driver = uc.Chrome(options=options, version_main=None)
    driver.set_page_load_timeout(45)
    driver.maximize_window()

    # Hide automation
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    try:
        print("\n[STEP 1] Loading Amazon...")
        driver.get("https://www.amazon.com")
        time.sleep(5)

        page_source = driver.page_source.lower()

        if "captcha" in page_source or "robot" in page_source:
            print("[STEP 2] BOT DETECTION FOUND!")
            print("\nAmazon has detected automation and is blocking access.")
            print("This is NOT about being logged in - it's bot detection.")
            print("\nSolutions:")
            print("  1. Use residential proxies")
            print("  2. Use a VPN")
            print("  3. Run from a different network")
            print("  4. Try Amazon alternatives (other sites)")

            driver.save_screenshot("test_output/amazon_blocked.png")
        else:
            print("[STEP 2] Amazon loaded successfully!")
            print("\nAmazon is accessible from your IP.")
            print("Login is NOT required for scraping products.")

            driver.save_screenshot("test_output/amazon_success.png")

            # Try a product page
            print("\n[STEP 3] Testing a product page...")
            product_url = "https://www.amazon.com/dp/B07ZPKN6YR"  # Sample dress
            driver.get(product_url)
            time.sleep(5)

            driver.save_screenshot("test_output/amazon_product.png")
            print("[STEP 4] Product page screenshot saved")

        print("\nBrowser will stay open for 30 seconds for inspection...")
        time.sleep(30)

    except Exception as e:
        print(f"\n[ERROR] {e}")
        driver.save_screenshot("test_output/amazon_error.png")

    finally:
        driver.quit()


def main():
    print("="*80)
    print("SPECIFIC URL TESTING - AUTO RUN")
    print("="*80)
    print("\nThis will:")
    print("1. Test your specific Zalando URL")
    print("2. Show exactly what images are available")
    print("3. Download them if possible")
    print("4. Check Amazon access (login not needed)")
    print("\n" + "="*80)

    # Test Zalando with your URL
    test_zalando_specific_url()

    print("\n\nNow testing Amazon...")
    time.sleep(2)

    # Test Amazon
    test_amazon_with_login_check()

    print("\n" + "="*80)
    print("ALL TESTS COMPLETE")
    print("="*80)
    print("\nCheck test_output/ folder for results!")


if __name__ == "__main__":
    main()
