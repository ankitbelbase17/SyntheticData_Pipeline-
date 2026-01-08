"""
METHOD 4: Requests + Scraping (No Browser)
Uses requests library with realistic headers and rate limiting
Fastest approach but may fail for JavaScript-heavy sites
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import time
import random
from urllib.parse import urljoin

TEST_SITES = [
    "https://www.amazon.com/",
    "https://www.ebay.com/",
    "https://www.zalando.com/",
    "https://www.shein.com/",
    "https://unsplash.com/",
    "https://pixabay.com/",
]

HEADERS_LIST = [
    {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Referer': 'https://www.google.com/',
    },
    {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    },
]

def test_requests_scraping():
    """Test websites using requests library (no browser)"""
    print("\n" + "="*80)
    print("METHOD 4: REQUESTS + BEAUTIFULSOUP (NO BROWSER)")
    print("="*80 + "\n")
    
    results = {
        "method": "requests_no_browser",
        "tested": 0,
        "accessible": 0,
        "blocked_by_captcha": 0,
        "failed": 0,
        "sites": {}
    }
    
    # Create session with connection pooling
    session = requests.Session()
    session.headers.update(random.choice(HEADERS_LIST))
    
    for url in TEST_SITES:
        results["tested"] += 1
        print(f"[Testing] {url}...", end=" ")
        
        try:
            # Random delay (1-3 seconds)
            time.sleep(random.uniform(1, 3))
            
            # Make request with timeout
            response = session.get(url, timeout=15, allow_redirects=True)
            
            # Check status code
            if response.status_code == 403:
                print("[BLOCKED - ACCESS DENIED (403)]")
                results["failed"] += 1
                results["sites"][url] = {
                    "status": "blocked",
                    "reason": "HTTP 403 Forbidden"
                }
                continue
            
            if response.status_code == 429:
                print("[BLOCKED - RATE LIMIT (429)]")
                results["blocked_by_captcha"] += 1
                results["sites"][url] = {
                    "status": "rate_limited",
                    "reason": "HTTP 429 Too Many Requests"
                }
                continue
            
            if response.status_code != 200:
                print(f"[FAILED - HTTP {response.status_code}]")
                results["failed"] += 1
                results["sites"][url] = {
                    "status": "failed",
                    "reason": f"HTTP {response.status_code}"
                }
                continue
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            page_source = response.text.lower()
            
            # Check for CAPTCHA
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
                    "reason": "CAPTCHA detected in HTML"
                }
            else:
                # Extract images
                img_tags = soup.find_all('img')
                img_count = len(img_tags)
                
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
        
        except requests.exceptions.Timeout:
            print("[FAILED - TIMEOUT]")
            results["failed"] += 1
            results["sites"][url] = {
                "status": "failed",
                "reason": "Request timeout"
            }
        
        except requests.exceptions.ConnectionError:
            print("[FAILED - CONNECTION ERROR]")
            results["failed"] += 1
            results["sites"][url] = {
                "status": "failed",
                "reason": "Connection error"
            }
        
        except Exception as e:
            print(f"[ERROR - {str(e)[:40]}]")
            results["failed"] += 1
            results["sites"][url] = {
                "status": "error",
                "reason": str(e)[:100]
            }
    
    session.close()
    
    # Print summary
    print(f"\n\n{'='*80}")
    print("METHOD 4 - SUMMARY")
    print(f"{'='*80}")
    print(f"Tested: {results['tested']}")
    print(f"Accessible: {results['accessible']}")
    print(f"Blocked by CAPTCHA: {results['blocked_by_captcha']}")
    print(f"Failed: {results['failed']}")
    if results['tested'] > 0:
        print(f"Success Rate: {(results['accessible']/results['tested']*100):.1f}%\n")
    
    # Save results
    os.makedirs("method_testing_results", exist_ok=True)
    with open("method_testing_results/method4_requests_no_browser.json", 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"Results saved to: method_testing_results/method4_requests_no_browser.json")
    
    return results

if __name__ == "__main__":
    test_requests_scraping()
