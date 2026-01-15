import requests
import os
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import hashlib

url = "https://www.amazon.com/Runaway-Label-Womens-Sondrey-Casanova/dp/B0DQWJYG1D/?th=1&psc=1"
api_key = "CRAWLBASE_TOKEN"  # Replace with your actual Crawlbase API token

# Create output directory for images
output_dir = "downloaded_images"
os.makedirs(output_dir, exist_ok=True)

params = {
    "token": api_key,
    "url": url,
    "smart": "true"
}

response = requests.get("https://api.crawlbase.com/", params=params)

if response.status_code == 200:
    soup = BeautifulSoup(response.text, "html.parser")

    # Find all image tags
    img_tags = soup.find_all("img")
    print(f"Found {len(img_tags)} images")

    downloaded_count = 0
    for i, img in enumerate(img_tags):
        # Get image URL from src or data-src attributes
        img_url = img.get("src") or img.get("data-src") or img.get("data-old-hires")

        if not img_url:
            continue

        # Skip base64 encoded images and tiny placeholders
        if img_url.startswith("data:"):
            continue

        # Make absolute URL if relative
        img_url = urljoin(url, img_url)

        try:
            # Download the image
            img_response = requests.get(img_url, timeout=10)
            if img_response.status_code == 200:
                # Determine file extension from URL or content-type
                parsed_url = urlparse(img_url)
                ext = os.path.splitext(parsed_url.path)[1]
                if not ext or len(ext) > 5:
                    content_type = img_response.headers.get("Content-Type", "")
                    if "jpeg" in content_type or "jpg" in content_type:
                        ext = ".jpg"
                    elif "png" in content_type:
                        ext = ".png"
                    elif "gif" in content_type:
                        ext = ".gif"
                    elif "webp" in content_type:
                        ext = ".webp"
                    else:
                        ext = ".jpg"

                # Create unique filename using hash
                filename = hashlib.md5(img_url.encode()).hexdigest()[:12] + ext
                filepath = os.path.join(output_dir, filename)

                with open(filepath, "wb") as f:
                    f.write(img_response.content)

                downloaded_count += 1
                print(f"Downloaded: {filename} from {img_url[:80]}...")
        except Exception as e:
            print(f"Failed to download {img_url[:50]}...: {e}")

    print(f"\nTotal images downloaded: {downloaded_count}")
else:
    print(f"Failed to fetch page: {response.status_code}")