"""
METHOD 3: Selenium with Advanced Evasion Techniques
Uses Selenium with multiple evasion tactics:
- User agent rotation
- Random delays
- Disable automation flags
- Remove headless indicators
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, WebDriverException
import time
import random
import json
import os

TEST_SITES = [
    "https://www.amazon.com/",
    "https://www.ebay.com/",
    "https://www.zalando.com/",
    "https://www.shein.com/",
    "https://unsplash.com/",
    "https://pixabay.com/",
]

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
]

def test_selenium_advanced_evasion():
    """Test websites using Selenium with advanced evasion techniques"""
    print("\n" + "="*80)
    print("METHOD 3: SELENIUM WITH ADVANCED EVASION TECHNIQUES")
    print("="*80 + "\n")
    
    results = {
        "method": "selenium_advanced_evasion",
        "tested": 0,
        "accessible": 0,
        "blocked_by_captcha": 0,
        "failed": 0,
        "sites": {}
    }
    
    try:
        chrome_options = Options()
        
        # Evasion techniques
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Additional stealth arguments
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--start-maximized')
        chrome_options.add_argument('--disable-web-resources')
        chrome_options.add_argument('--disable-sync')
        chrome_options.add_argument('--disable-plugins')
        chrome_options.add_argument('--disable-images')  # Don't load images for speed
        
        # Random user agent
        user_agent = random.choice(USER_AGENTS)
        chrome_options.add_argument(f'user-agent={user_agent}')
        
        print(f"[Setup] Using User-Agent: {user_agent[:60]}...")
        print("[Setup] Initializing Chrome with advanced evasion...\n")
        
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        driver.set_page_load_timeout(20)
        
        # Add stealth JavaScript
        stealth_js = """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false,
            });
            window.chrome = {
                runtime: {}
            };
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
        """
        
        for url in TEST_SITES:
            results["tested"] += 1
            print(f"[Testing] {url}...", end=" ")
            
            try:
                # Random delay between requests (2-5 seconds)
                time.sleep(random.uniform(2, 5))
                
                # Execute stealth JavaScript before loading page
                driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                    "source": stealth_js
                })
                
                driver.get(url)
                time.sleep(random.uniform(2, 4))
                
                # Check for CAPTCHA
                page_source = driver.page_source.lower()
                captcha_indicators = [
                    "recaptcha", "hcaptcha", "captcha", "verify you are human",
                    "robot check", "challenge"
                ]
                
                has_captcha = any(indicator in page_source for indicator in captcha_indicators)
                
                if has_captcha:
                    print("[BLOCKED - CAPTCHA]")
                    results["blocked_by_captcha"] += 1
                    results["sites"][url] = {
                        "status": "blocked_captcha",
                        "reason": "CAPTCHA detected"
                    }
                else:
                    # Try to extract images
                    img_elements = driver.find_elements(By.TAG_NAME, 'img')
                    img_count = len(img_elements)
                    
                    if img_count > 0:
                        print(f"[SUCCESS - {img_count} images]")
                        results["accessible"] += 1
                        results["sites"][url] = {
                            "status": "success",
                            "images_found": img_count
                        }
                    else:
                        print("[SUCCESS - NO IMAGES]")
                        results["accessible"] += 1
                        results["sites"][url] = {
                            "status": "success_no_images",
                            "images_found": 0
                        }
            
            except TimeoutException:
                print("[FAILED - TIMEOUT]")
                results["failed"] += 1
                results["sites"][url] = {
                    "status": "failed",
                    "reason": "Page load timeout"
                }
            except WebDriverException as e:
                print(f"[FAILED - {str(e)[:40]}]")
                results["failed"] += 1
                results["sites"][url] = {
                    "status": "failed",
                    "reason": str(e)[:100]
                }
            except Exception as e:
                print(f"[ERROR - {str(e)[:40]}]")
                results["failed"] += 1
                results["sites"][url] = {
                    "status": "error",
                    "reason": str(e)[:100]
                }
        
        driver.quit()
    
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        results["error"] = str(e)
    
    # Print summary
    print(f"\n\n{'='*80}")
    print("METHOD 3 - SUMMARY")
    print(f"{'='*80}")
    print(f"Tested: {results['tested']}")
    print(f"Accessible: {results['accessible']}")
    print(f"Blocked by CAPTCHA: {results['blocked_by_captcha']}")
    print(f"Failed: {results['failed']}")
    if results['tested'] > 0:
        print(f"Success Rate: {(results['accessible']/results['tested']*100):.1f}%\n")
    
    # Save results
    os.makedirs("method_testing_results", exist_ok=True)
    with open("method_testing_results/method3_selenium_advanced_evasion.json", 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"Results saved to: method_testing_results/method3_selenium_advanced_evasion.json")
    
    return results

if __name__ == "__main__":
    test_selenium_advanced_evasion()
