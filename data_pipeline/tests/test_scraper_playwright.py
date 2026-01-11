"""
METHOD 2: Playwright with Stealth Plugin
Uses Playwright browser automation with stealth detection bypass
"""

import asyncio
from playwright.async_api import async_playwright
import time
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

async def test_playwright_stealth():
    """Test websites using Playwright with stealth mode"""
    print("\n" + "="*80)
    print("METHOD 2: PLAYWRIGHT WITH STEALTH MODE")
    print("="*80 + "\n")
    
    results = {
        "method": "playwright_stealth",
        "tested": 0,
        "accessible": 0,
        "blocked_by_captcha": 0,
        "failed": 0,
        "sites": {}
    }
    
    try:
        async with async_playwright() as p:
            # Launch browser with stealth options
            print("[Setup] Initializing Playwright with stealth mode...")
            browser = await p.chromium.launch(
                headless=False,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                ]
            )
            
            # Create context with stealth headers
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            # Add stealth script
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => false,
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
            """)
            
            page = await context.new_page()
            page.set_default_timeout(20000)
            
            for url in TEST_SITES:
                results["tested"] += 1
                print(f"\n[Testing] {url}...", end=" ")
                
                try:
                    await page.goto(url, wait_until='domcontentloaded')
                    await page.wait_for_timeout(3000)  # 3 second wait
                    
                    # Get page content
                    content = await page.content()
                    page_source = content.lower()
                    
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
                            "reason": "CAPTCHA detected"
                        }
                    else:
                        # Try to extract images
                        img_count = await page.locator('img').count()
                        
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
                
                except Exception as e:
                    error_msg = str(e)
                    if "timeout" in error_msg.lower():
                        print("[FAILED - TIMEOUT]")
                    else:
                        print(f"[FAILED - {error_msg[:40]}]")
                    
                    results["failed"] += 1
                    results["sites"][url] = {
                        "status": "failed",
                        "reason": error_msg[:100]
                    }
            
            await context.close()
            await browser.close()
    
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        results["error"] = str(e)
    
    # Print summary
    print(f"\n\n{'='*80}")
    print("METHOD 2 - SUMMARY")
    print(f"{'='*80}")
    print(f"Tested: {results['tested']}")
    print(f"Accessible: {results['accessible']}")
    print(f"Blocked by CAPTCHA: {results['blocked_by_captcha']}")
    print(f"Failed: {results['failed']}")
    if results['tested'] > 0:
        print(f"Success Rate: {(results['accessible']/results['tested']*100):.1f}%\n")
    
    # Save results
    os.makedirs("method_testing_results", exist_ok=True)
    with open("method_testing_results/method2_playwright_stealth.json", 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"Results saved to: method_testing_results/method2_playwright_stealth.json")
    
    return results

if __name__ == "__main__":
    asyncio.run(test_playwright_stealth())
