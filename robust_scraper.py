import random
import requests
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
from io import BytesIO

# Probabilistic website dictionary
SCRAPE_SITES = [
    ("https://www.amazon.com/", 0.05),
    ("https://www.ebay.com/", 0.05),
    ("https://www.zalando.com/", 0.04),
    ("https://www.asos.com/", 0.04),
    ("https://www.farfetch.com/", 0.03),
    ("https://www.nordstrom.com/", 0.03),
    ("https://www.macys.com/", 0.03),
    ("https://www2.hm.com/", 0.03),
    ("https://www.uniqlo.com/", 0.03),
    ("https://www.shein.com/", 0.03),
    ("https://www.forever21.com/", 0.03),
    ("https://www.boohoo.com/", 0.03),
    ("https://www.missguided.com/", 0.03),
    ("https://www.urbanoutfitters.com/", 0.03),
    ("https://www.revolve.com/", 0.03),
    ("https://www.zara.com/", 0.03),
    ("https://www.net-a-porter.com/", 0.02),
    ("https://www.ssense.com/", 0.02),
    ("https://www.shopbop.com/", 0.02),
    ("https://www.anthropologie.com/", 0.02),
    ("https://www.lulus.com/", 0.02),
    ("https://www.modcloth.com/", 0.02),
    ("https://www.prettylittlething.com/", 0.02),
    ("https://www.stockx.com/", 0.02),
    ("https://www.depop.com/", 0.02),
    ("https://www.grailed.com/", 0.02),
    ("https://www.vinted.com/", 0.02),
    ("https://www.etsy.com/", 0.02),
    ("https://www.pinterest.com/", 0.02),
    ("https://www.instagram.com/", 0.02),
    ("https://www.facebook.com/marketplace/", 0.02),
    ("https://www.reddit.com/r/fashion/", 0.02),
    ("https://www.flickr.com/", 0.02),
    ("https://www.gettyimages.com/", 0.02),
    ("https://unsplash.com/", 0.02),
    ("https://www.pexels.com/", 0.02),
    ("https://pixabay.com/", 0.02),
    ("https://www.shutterstock.com/", 0.02),
    ("https://www.aliexpress.com/", 0.02),
    ("https://www.wish.com/", 0.02),
    ("https://www.target.com/", 0.02),
    ("https://www.walmart.com/", 0.02),
    ("https://www.jdsports.com/", 0.02),
    ("https://www.nike.com/", 0.02),
    ("https://www.adidas.com/", 0.02),
    ("https://www.levi.com/", 0.02),
    ("https://www.gap.com/", 0.02),
    ("https://www.oldnavy.com/", 0.02),
    ("https://www.saksfifthavenue.com/", 0.02),
    ("https://www.bloomingdales.com/", 0.02),
    ("https://www.dillards.com/", 0.02),
    ("https://www.kohls.com/", 0.02),
    ("https://www.primark.com/", 0.02),
    ("https://www.next.co.uk/", 0.02),
    ("https://www.myntra.com/", 0.02),
    ("https://www.flipkart.com/", 0.02),
    ("https://www.snapdeal.com/", 0.02)
]

def weighted_sample_sites(sites, k=4):
    """Sample k sites according to their probabilities."""
    sites, probs = zip(*sites)
    chosen = random.choices(sites, weights=probs, k=k)
    return chosen

def scrape_images_from_site(site_url, max_images=10):
    """Dummy scraper: In practice, use BeautifulSoup/Scrapy for robust scraping."""
    # This is a placeholder for actual scraping logic
    # Here, we just simulate image URLs
    return [f"{site_url}/image_{i}.jpg" for i in range(max_images)]

def download_and_filter_image(img_url, gemma_prompt):
    try:
        response = requests.get(img_url, timeout=5)
        img = Image.open(BytesIO(response.content))
        # Here, you would call GEMMA MLLM with the prompt and image
        # For now, we simulate acceptance
        accepted = True  # Replace with actual GEMMA call
        if accepted:
            img.save(f"images/{img_url.split('/')[-1]}")
            return img_url
    except Exception:
        pass
    return None

def robust_scraper():
    sampled_sites = weighted_sample_sites(SCRAPE_SITES, k=4)
    all_img_urls = []
    for site in sampled_sites:
        img_urls = scrape_images_from_site(site)
        all_img_urls.extend(img_urls)
    # GEMMA MLLM prompt
    gemma_prompt = '''
Role: Vision-Language Model (GEMMA)
Task: Filter images for virtual try-on synthetic dataset creation
Context: Images should contain humans in diverse clothing, poses, body shapes, and visible human characteristics (e.g., prosthetic limb, wheelchair user, visible birthmark, tattoo, hijab, turban, hearing aid, albinism, etc.). Images may be candid, in the wild, and do not need to be aesthetic or perfect. Diversity and richness are prioritized over beauty or perfection.
Constraints:
- Accept images with 1-3 people, clothing clearly visible
- Exclude close-up faces, accessories-only, product-only shots
- Accept occlusions, imperfect lighting, candid settings
- Aspect ratio: 3:4, 4:5, 1:1 or similar; min resolution 512x512
Output Format:
- For each image: {{'accepted': True/False, 'reason': '...'}}
'''
    # Download and filter images in parallel
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda url: download_and_filter_image(url, gemma_prompt), all_img_urls))
    accepted_imgs = [r for r in results if r]
    print(f"Accepted images: {accepted_imgs}")

if __name__ == "__main__":
    robust_scraper()
