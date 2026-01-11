"""
METHOD 1: Undetected Chrome Browser Evasion
Uses undetected-chromedriver to bypass bot detection
"""

import undetected_chromedriver as uc
import time
import json
import os
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, WebDriverException

TEST_SITES = [
    "https://www.amazon.com/",
    "https://www.ebay.com/",
    "https://www.zalando.com/",
    "https://www.shein.com/",
    "https://unsplash.com/",
    "https://pixabay.com/",
]

def test_undetected_chrome():
    """Test websites using undetected-chromedriver"""
    print("\n" + "="*80)
    print("METHOD 1: UNDETECTED CHROME BROWSER EVASION")
    print("="*80 + "\n")
    
    results = {
        "method": "undetected_chrome",
        "tested": 0,
        "accessible": 0,
        "blocked_by_captcha": 0,
        "failed": 0,
        "sites": {}
    }
    
    try:
        # Initialize undetected chrome
        print("[Setup] Initializing undetected Chrome...")
        driver = uc.Chrome(headless=False, version_main=None)
        driver.set_page_load_timeout(20)
        
        for url in TEST_SITES:
            results["tested"] += 1
            print(f"\n[Testing] {url}...", end=" ")
            
            try:
                driver.get(url)
                time.sleep(3)
                
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
                print(f"[FAILED - {str(e)[:50]}]")
                results["failed"] += 1
                results["sites"][url] = {
                    "status": "failed",
                    "reason": str(e)[:100]
                }
            except Exception as e:
                print(f"[ERROR - {str(e)[:50]}]")
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
    print("METHOD 1 - SUMMARY")
    print(f"{'='*80}")
    print(f"Tested: {results['tested']}")
    print(f"Accessible: {results['accessible']}")
    print(f"Blocked by CAPTCHA: {results['blocked_by_captcha']}")
    print(f"Failed: {results['failed']}")
    print(f"Success Rate: {(results['accessible']/results['tested']*100):.1f}%\n")
    
    # Save results
    os.makedirs("method_testing_results", exist_ok=True)
    with open("method_testing_results/method1_undetected_chrome.json", 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"Results saved to: method_testing_results/method1_undetected_chrome.json")
    
    return results

if __name__ == "__main__":
    test_undetected_chrome()
