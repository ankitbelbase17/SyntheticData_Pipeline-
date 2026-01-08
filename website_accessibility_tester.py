import json
import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import requests
from urllib.parse import urlparse

# Extract all websites from SCRAPE_SITE_CATEGORIES
ALL_WEBSITES = {
    "ecommerce": [
        "https://www.amazon.com/",
        "https://www.ebay.com/",
        "https://www.zalando.com/",
        "https://www.asos.com/",
        "https://www.farfetch.com/",
        "https://www.nordstrom.com/",
        "https://www.macys.com/",
        "https://www2.hm.com/",
        "https://www.uniqlo.com/",
        "https://www.shein.com/",
        "https://www.forever21.com/",
        "https://www.boohoo.com/",
        "https://www.missguided.com/",
        "https://www.urbanoutfitters.com/",
        "https://www.revolve.com/",
        "https://www.zara.com/",
        "https://www.net-a-porter.com/",
        "https://www.ssense.com/",
        "https://www.shopbop.com/",
        "https://www.anthropologie.com/",
        "https://www.lulus.com/",
        "https://www.modcloth.com/",
        "https://www.prettylittlething.com/",
        "https://www.stockx.com/",
        "https://www.depop.com/",
        "https://www.grailed.com/",
        "https://www.vinted.com/",
        "https://www.etsy.com/",
        "https://www.aliexpress.com/",
        "https://www.wish.com/",
        "https://www.target.com/",
        "https://www.walmart.com/",
        "https://www.jdsports.com/",
        "https://www.nike.com/",
        "https://www.adidas.com/",
        "https://www.levi.com/",
        "https://www.gap.com/",
        "https://www.oldnavy.com/",
        "https://www.saksfifthavenue.com/",
        "https://www.bloomingdales.com/",
        "https://www.dillards.com/",
        "https://www.kohls.com/",
        "https://www.primark.com/",
        "https://www.next.co.uk/",
        "https://www.myntra.com/",
        "https://www.flipkart.com/",
        "https://www.snapdeal.com/"
    ],
    "marketplace": [
        "https://www.facebook.com/marketplace/",
        "https://www.depop.com/",
        "https://www.grailed.com/",
        "https://www.vinted.com/",
        "https://www.etsy.com/"
    ],
    "stock_photo": [
        "https://www.gettyimages.com/",
        "https://unsplash.com/",
        "https://www.pexels.com/",
        "https://pixabay.com/",
        "https://www.shutterstock.com/"
    ],
    "social_media": [
        "https://www.instagram.com/",
        "https://www.pinterest.com/",
        "https://www.flickr.com/",
        "https://www.reddit.com/r/fashion/"
    ],
    "fashion_blog_magazine": [
        "https://www.vogue.com/",
        "https://www.harpersbazaar.com/",
        "https://www.gq.com/",
        "https://www.elle.com/",
        "https://www.highsnobiety.com/"
    ],
    "creative_commons": [
        "https://commons.wikimedia.org/",
        "https://www.flickr.com/creativecommons/"
    ]
}

class WebsiteAccessibilityTester:
    def __init__(self):
        self.results = {}
        self.driver = None
        self.setup_driver()
    
    def setup_driver(self, headless=True):
        """Initialize Chrome WebDriver with proper options"""
        chrome_options = Options()
        if headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        try:
            self.driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            self.driver.set_page_load_timeout(15)
        except Exception as e:
            print(f"[Error] Failed to initialize WebDriver: {e}")
            self.driver = None
    
    def handle_captcha_manual(self, url):
        """
        Handle CAPTCHA with manual human intervention.
        Opens browser window and waits for user to solve CAPTCHA.
        """
        print(f"\n{'='*80}")
        print(f"[CAPTCHA] Manual intervention required for: {url}")
        print(f"{'='*80}")
        print(f"A browser window has opened. Please:")
        print(f"1. Solve the CAPTCHA manually")
        print(f"2. Complete any verification challenges")
        print(f"3. Return to this terminal and press ENTER when done")
        print(f"{'='*80}\n")
        
        # Maximize window for better visibility
        self.driver.maximize_window()
        
        try:
            # Wait for user to press ENTER
            input("[Waiting] Press ENTER after solving the CAPTCHA...")
            
            # Wait a moment for page to load after CAPTCHA
            time.sleep(3)
            
            # Check if CAPTCHA is still present
            page_source = self.driver.page_source.lower()
            captcha_indicators = [
                "recaptcha", "hcaptcha", "captcha", "verify you are human",
                "robot check", "challenge", "security check"
            ]
            
            for indicator in captcha_indicators:
                if indicator in page_source:
                    print(f"[Warning] CAPTCHA still detected. Please verify and try again.")
                    return False
            
            print(f"[Success] CAPTCHA appears to be solved. Proceeding...")
            return True
        
        except KeyboardInterrupt:
            print(f"[Cancelled] User cancelled CAPTCHA solving.")
            return False
        except Exception as e:
            print(f"[Error] Exception during manual CAPTCHA solving: {e}")
            return False
    
    def test_website_accessibility(self, url, allow_manual_captcha=True):
        """Test if a website is accessible"""
        if not self.driver:
            return {
                "status": "failed",
                "accessible": False,
                "images_extractable": False,
                "error_reason": "WebDriver not initialized",
                "error_type": "driver_error"
            }
        
        result = {
            "status": "unknown",
            "accessible": False,
            "images_extractable": False,
            "error_reason": None,
            "error_type": None,
            "images_count": 0
        }
        
        try:
            print(f"[Testing] {url}...", end=" ")
            self.driver.get(url)
            time.sleep(3)  # Wait for page to load
            
            # Check for CAPTCHA
            captcha_indicators = [
                "recaptcha", "hcaptcha", "captcha", "verify you are human",
                "robot check", "challenge", "security check"
            ]
            page_source = self.driver.page_source.lower()
            
            captcha_detected = False
            for indicator in captcha_indicators:
                if indicator in page_source:
                    captcha_detected = True
                    break
            
            if captcha_detected:
                print("[CAPTCHA DETECTED]", end=" ")
                if allow_manual_captcha:
                    # Try to solve CAPTCHA manually
                    captcha_solved = self.handle_captcha_manual(url)
                    if captcha_solved:
                        print("[MANUAL SOLVE SUCCESSFUL]")
                        # Continue with accessibility check after CAPTCHA solved
                        page_source = self.driver.page_source.lower()
                    else:
                        result["status"] = "blocked"
                        result["accessible"] = False
                        result["error_reason"] = "CAPTCHA detected - Manual solving failed/cancelled"
                        result["error_type"] = "captcha_failed_manual"
                        print("[MANUAL SOLVE FAILED]")
                        return result
                else:
                    result["status"] = "blocked"
                    result["accessible"] = False
                    result["error_reason"] = "CAPTCHA challenge detected"
                    result["error_type"] = "captcha"
                    print("[BLOCKED - CAPTCHA]")
                    return result
            
            # Check for login requirement
            login_indicators = ["sign in", "login", "log in", "authenticate", "credentials required"]
            for indicator in login_indicators:
                if indicator in page_source:
                    result["status"] = "blocked"
                    result["accessible"] = False
                    result["error_reason"] = "Login/Authentication required"
                    result["error_type"] = "credentials_required"
                    print("[BLOCKED - LOGIN REQUIRED]")
                    return result
            
            # Check for access denied
            denied_indicators = ["403", "access denied", "forbidden", "not allowed", "permission denied"]
            for indicator in denied_indicators:
                if indicator in page_source:
                    result["status"] = "blocked"
                    result["accessible"] = False
                    result["error_reason"] = "Access denied by website"
                    result["error_type"] = "access_denied"
                    print("[BLOCKED - ACCESS DENIED]")
                    return result
            
            # Try to extract images
            try:
                img_elements = self.driver.find_elements(By.TAG_NAME, 'img')
                if len(img_elements) > 0:
                    result["images_count"] = len(img_elements)
                    result["images_extractable"] = True
                    result["status"] = "success"
                    result["accessible"] = True
                    print(f"[SUCCESS - {len(img_elements)} images found]")
                else:
                    result["status"] = "success_no_images"
                    result["accessible"] = True
                    result["images_extractable"] = False
                    result["error_reason"] = "No images found on page"
                    result["error_type"] = "no_images"
                    print("[SUCCESS - NO IMAGES]")
            except Exception as e:
                result["status"] = "partial"
                result["accessible"] = True
                result["images_extractable"] = False
                result["error_reason"] = f"Could not extract images: {str(e)}"
                result["error_type"] = "extraction_error"
                print("[PARTIAL - EXTRACTION FAILED]")
        
        except TimeoutException:
            result["status"] = "timeout"
            result["accessible"] = False
            result["error_reason"] = "Page load timeout (15 seconds)"
            result["error_type"] = "timeout"
            print("[FAILED - TIMEOUT]")
        
        except WebDriverException as e:
            error_msg = str(e).lower()
            if "net::err_name_not_resolved" in error_msg:
                result["error_type"] = "dns_error"
                result["error_reason"] = "DNS resolution failed"
            elif "connection" in error_msg:
                result["error_type"] = "connection_error"
                result["error_reason"] = "Connection refused or timeout"
            elif "refused" in error_msg:
                result["error_type"] = "connection_refused"
                result["error_reason"] = "Connection refused"
            else:
                result["error_type"] = "webdriver_error"
                result["error_reason"] = str(e)
            result["status"] = "failed"
            result["accessible"] = False
            print(f"[FAILED - {result['error_type'].upper()}]")
        
        except Exception as e:
            result["status"] = "error"
            result["accessible"] = False
            result["error_reason"] = str(e)
            result["error_type"] = "unknown_error"
            print(f"[ERROR - {str(e)[:40]}...]")
        
        return result
    
    def test_all_websites(self, headless=True, allow_manual_captcha=True):
        """Test all websites"""
        print("\n" + "="*80)
        print("WEBSITE ACCESSIBILITY DIAGNOSTIC TEST")
        print(f"Mode: {'Headless' if headless else 'GUI (Manual CAPTCHA enabled)'}")
        print(f"Manual CAPTCHA Intervention: {'ENABLED' if allow_manual_captcha else 'DISABLED'}")
        print("="*80 + "\n")
        
        # Reinitialize driver with correct headless setting
        if self.driver:
            self.driver.quit()
        self.setup_driver(headless=headless)
        
        total = 0
        for category, websites in ALL_WEBSITES.items():
            self.results[category] = {}
            print(f"\n[Category: {category.upper()}]")
            print("-" * 80)
            
            for url in websites:
                total += 1
                # Remove duplicates
                if url not in [item for sublist in self.results.values() for item in sublist]:
                    result = self.test_website_accessibility(url, allow_manual_captcha=allow_manual_captcha)
                    self.results[category][url] = result
        
        if self.driver:
            self.driver.quit()
        
        print(f"\n\n{'='*80}")
        print(f"TESTING COMPLETE - {total} websites tested")
        print(f"{'='*80}\n")
        
        return self.results
    
    def save_results_to_file(self):
        """Save results to JSON file in new folder"""
        results_folder = "website_accessibility_results"
        os.makedirs(results_folder, exist_ok=True)
        
        # Create summary statistics
        summary = self._create_summary()
        
        # Prepare output dictionary
        output = {
            "test_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "summary": summary,
            "detailed_results": self.results
        }
        
        # Save to JSON
        output_file = os.path.join(results_folder, "website_accessibility_report.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"[Saved] Results saved to: {output_file}\n")
        
        # Also save a categorized summary
        categorized_file = os.path.join(results_folder, "website_categorization.json")
        categorized_summary = self._create_categorized_summary()
        with open(categorized_file, 'w', encoding='utf-8') as f:
            json.dump(categorized_summary, f, indent=2, ensure_ascii=False)
        
        print(f"[Saved] Categorized summary saved to: {categorized_file}\n")
    
    def _create_summary(self):
        """Create summary statistics"""
        summary = {
            "total_websites_tested": 0,
            "successful": 0,
            "failed": 0,
            "blocked": 0,
            "inaccessible": 0,
            "images_extractable": 0,
            "by_error_type": {},
            "successful_sites": [],
            "failed_sites": [],
            "blocked_sites": [],
            "inaccessible_sites": []
        }
        
        for category, websites in self.results.items():
            for url, result in websites.items():
                summary["total_websites_tested"] += 1
                
                if result["status"] == "success":
                    summary["successful"] += 1
                    if result["images_extractable"]:
                        summary["images_extractable"] += 1
                    summary["successful_sites"].append({
                        "url": url,
                        "category": category,
                        "images_found": result["images_count"]
                    })
                elif result["status"] == "blocked":
                    summary["blocked"] += 1
                    summary["blocked_sites"].append({
                        "url": url,
                        "category": category,
                        "reason": result["error_reason"]
                    })
                elif result["status"] in ["failed", "error"]:
                    summary["failed"] += 1
                    summary["failed_sites"].append({
                        "url": url,
                        "category": category,
                        "reason": result["error_reason"]
                    })
                else:
                    summary["inaccessible"] += 1
                    summary["inaccessible_sites"].append({
                        "url": url,
                        "category": category,
                        "reason": result["error_reason"]
                    })
                
                error_type = result["error_type"]
                if error_type:
                    if error_type not in summary["by_error_type"]:
                        summary["by_error_type"][error_type] = 0
                    summary["by_error_type"][error_type] += 1
        
        return summary
    
    def _create_categorized_summary(self):
        """Create categorized summary for easier reference"""
        categorized = {
            "accessible_and_scrapeable": [],
            "accessible_no_images": [],
            "blocked_by_captcha": [],
            "blocked_by_login": [],
            "blocked_by_access_denied": [],
            "failed_connection": [],
            "failed_timeout": [],
            "failed_dns": [],
            "failed_other": [],
            "no_access_possible": []
        }
        
        for category, websites in self.results.items():
            for url, result in websites.items():
                entry = {
                    "url": url,
                    "category": category,
                    "status": result["status"],
                    "error_reason": result["error_reason"],
                    "images_count": result.get("images_count", 0)
                }
                
                if result["status"] == "success" and result["images_extractable"]:
                    categorized["accessible_and_scrapeable"].append(entry)
                elif result["status"] == "success_no_images":
                    categorized["accessible_no_images"].append(entry)
                elif result["error_type"] == "captcha":
                    categorized["blocked_by_captcha"].append(entry)
                elif result["error_type"] == "captcha_failed_manual":
                    categorized["blocked_by_captcha"].append({
                        **entry,
                        "manual_solve_status": "failed"
                    })
                elif result["error_type"] == "credentials_required":
                    categorized["blocked_by_login"].append(entry)
                elif result["error_type"] == "access_denied":
                    categorized["blocked_by_access_denied"].append(entry)
                elif result["error_type"] == "connection_error":
                    categorized["failed_connection"].append(entry)
                elif result["error_type"] == "timeout":
                    categorized["failed_timeout"].append(entry)
                elif result["error_type"] == "dns_error":
                    categorized["failed_dns"].append(entry)
                elif result["error_type"] in ["no_images", "extraction_error"]:
                    categorized["failed_other"].append(entry)
                else:
                    categorized["no_access_possible"].append(entry)
        
        return categorized
    
    def print_summary(self):
        """Print summary to console"""
        summary = self._create_summary()
        
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        print(f"Total websites tested: {summary['total_websites_tested']}")
        print(f"Successful (accessible): {summary['successful']}")
        print(f"Images extractable: {summary['images_extractable']}")
        print(f"Blocked: {summary['blocked']}")
        print(f"Failed: {summary['failed']}")
        print(f"Inaccessible: {summary['inaccessible']}")
        
        print(f"\n{'Error Types Breakdown:':}")
        for error_type, count in summary["by_error_type"].items():
            print(f"  - {error_type}: {count}")
        
        print(f"\n{'Successful Sites:':}")
        for site in summary["successful_sites"]:
            print(f"  ✓ {site['url']} ({site['category']}) - {site['images_found']} images")
        
        print(f"\n{'Blocked by CAPTCHA:':}")
        for site in summary["blocked_sites"]:
            if site["reason"] == "CAPTCHA challenge detected":
                print(f"  ✗ {site['url']} ({site['category']})")
        
        print(f"\n{'Blocked by Login:':}")
        for site in summary["blocked_sites"]:
            if site["reason"] == "Login/Authentication required":
                print(f"  ✗ {site['url']} ({site['category']})")
        
        print(f"\n{'Failed Sites:':}")
        for site in summary["failed_sites"][:10]:  # Show first 10
            print(f"  ✗ {site['url']} - {site['reason']}")


if __name__ == "__main__":
    import sys
    
    # Parse command line arguments
    headless = True
    allow_manual_captcha = False
    
    if len(sys.argv) > 1:
        if "--gui" in sys.argv or "--no-headless" in sys.argv:
            headless = False
        if "--manual-captcha" in sys.argv:
            allow_manual_captcha = True
    
    print("\nUsage: python website_accessibility_tester.py [OPTIONS]")
    print("Options:")
    print("  --gui              : Run in GUI mode (non-headless) for better visibility")
    print("  --manual-captcha   : Enable manual CAPTCHA solving with human intervention")
    print("  --no-headless      : Same as --gui")
    print("\nExample: python website_accessibility_tester.py --gui --manual-captcha\n")
    
    tester = WebsiteAccessibilityTester()
    tester.test_all_websites(headless=headless, allow_manual_captcha=allow_manual_captcha)
    tester.print_summary()
    tester.save_results_to_file()
