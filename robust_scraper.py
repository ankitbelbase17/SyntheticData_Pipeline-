import random
import requests
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
from io import BytesIO

# Hierarchical site dictionary with probabilities
SCRAPE_SITE_CATEGORIES = {
    "ecommerce": {
        "prob": 0.45,
        "sites": [
            ("https://www.amazon.com/", 0.05), ("https://www.ebay.com/", 0.05), ("https://www.zalando.com/", 0.04), ("https://www.asos.com/", 0.04),
            ("https://www.farfetch.com/", 0.03), ("https://www.nordstrom.com/", 0.03), ("https://www.macys.com/", 0.03), ("https://www2.hm.com/", 0.03),
            ("https://www.uniqlo.com/", 0.03), ("https://www.shein.com/", 0.03), ("https://www.forever21.com/", 0.03), ("https://www.boohoo.com/", 0.03),
            ("https://www.missguided.com/", 0.03), ("https://www.urbanoutfitters.com/", 0.03), ("https://www.revolve.com/", 0.03), ("https://www.zara.com/", 0.03),
            ("https://www.net-a-porter.com/", 0.02), ("https://www.ssense.com/", 0.02), ("https://www.shopbop.com/", 0.02), ("https://www.anthropologie.com/", 0.02),
            ("https://www.lulus.com/", 0.02), ("https://www.modcloth.com/", 0.02), ("https://www.prettylittlething.com/", 0.02), ("https://www.stockx.com/", 0.02),
            ("https://www.depop.com/", 0.02), ("https://www.grailed.com/", 0.02), ("https://www.vinted.com/", 0.02), ("https://www.etsy.com/", 0.02),
            ("https://www.aliexpress.com/", 0.02), ("https://www.wish.com/", 0.02), ("https://www.target.com/", 0.02), ("https://www.walmart.com/", 0.02),
            ("https://www.jdsports.com/", 0.02), ("https://www.nike.com/", 0.02), ("https://www.adidas.com/", 0.02), ("https://www.levi.com/", 0.02),
            ("https://www.gap.com/", 0.02), ("https://www.oldnavy.com/", 0.02), ("https://www.saksfifthavenue.com/", 0.02), ("https://www.bloomingdales.com/", 0.02),
            ("https://www.dillards.com/", 0.02), ("https://www.kohls.com/", 0.02), ("https://www.primark.com/", 0.02), ("https://www.next.co.uk/", 0.02),
            ("https://www.myntra.com/", 0.02), ("https://www.flipkart.com/", 0.02), ("https://www.snapdeal.com/", 0.02)
        ]
    },
    "marketplace": {
        "prob": 0.15,
        "sites": [
            ("https://www.facebook.com/marketplace/", 0.25), ("https://www.depop.com/", 0.20), ("https://www.grailed.com/", 0.20), ("https://www.vinted.com/", 0.20), ("https://www.etsy.com/", 0.15)
        ]
    },
    "stock_photo": {
        "prob": 0.15,
        "sites": [
            ("https://www.gettyimages.com/", 0.25), ("https://unsplash.com/", 0.25), ("https://www.pexels.com/", 0.20), ("https://pixabay.com/", 0.15), ("https://www.shutterstock.com/", 0.15)
        ]
    },
    "social_media": {
        "prob": 0.10,
        "sites": [
            ("https://www.instagram.com/", 0.40), ("https://www.pinterest.com/", 0.30), ("https://www.flickr.com/", 0.15), ("https://www.reddit.com/r/fashion/", 0.15)
        ]
    },
    "fashion_blog_magazine": {
        "prob": 0.10,
        "sites": [
            ("https://www.vogue.com/", 0.30), ("https://www.harpersbazaar.com/", 0.25), ("https://www.gq.com/", 0.20), ("https://www.elle.com/", 0.15), ("https://www.highsnobiety.com/", 0.10)
        ]
    },
    "creative_commons": {
        "prob": 0.05,
        "sites": [
            ("https://commons.wikimedia.org/", 0.50), ("https://www.flickr.com/creativecommons/", 0.50)
        ]
    }
}

# Expanded clothes diversity dictionary with probabilities
CLOTHES_DIVERSITY = {
    "tops": [
        ("t-shirt", 0.15), ("shirt", 0.10), ("blouse", 0.08), ("sweater", 0.07), ("tank top", 0.06), ("hoodie", 0.08), ("cardigan", 0.05), ("blazer", 0.04), ("kurta", 0.04), ("hanbok jeogori", 0.01), ("kimono top", 0.01), ("dashiki", 0.01), ("boubou", 0.01), ("poncho", 0.01), ("choli", 0.01), ("ao dai top", 0.01)
    ],
    "bottoms": [
        ("jeans", 0.18), ("trousers", 0.10), ("shorts", 0.10), ("skirt", 0.08), ("leggings", 0.08), ("joggers", 0.06), ("chinos", 0.05), ("cargo pants", 0.05), ("lungi", 0.02), ("dhoti", 0.02), ("sarong", 0.01), ("hanbok baji", 0.01), ("kimono hakama", 0.01), ("kilt", 0.01), ("shwals", 0.01), ("ao dai pants", 0.01)
    ],
    "dresses": [
        ("maxi dress", 0.10), ("midi dress", 0.10), ("mini dress", 0.10), ("sundress", 0.08), ("cheongsam/qipao", 0.03), ("hanbok chima", 0.01), ("kimono", 0.01), ("abaya", 0.02), ("kaftan", 0.02), ("lehenga", 0.02), ("dirndl", 0.01), ("ao dai dress", 0.01), ("boubou dress", 0.01), ("sari", 0.03)
    ],
    "outerwear": [
        ("jacket", 0.10), ("coat", 0.08), ("bomber jacket", 0.05), ("denim jacket", 0.06), ("leather jacket", 0.06), ("parka", 0.04), ("poncho", 0.03), ("trench coat", 0.04), ("duffle coat", 0.02), ("kimono", 0.01), ("hanbok durumagi", 0.01), ("dashiki robe", 0.01), ("abaya", 0.02), ("kaftan", 0.02)
    ],
    "full_body": [
        ("jumpsuit", 0.10), ("romper", 0.08), ("overall", 0.07), ("tracksuit", 0.06), ("onesie", 0.05), ("sari", 0.05), ("lehenga choli", 0.03), ("hanbok", 0.02), ("kimono", 0.02), ("boubou", 0.01), ("kaftan", 0.01), ("dirndl", 0.01), ("ao dai", 0.01)
    ],
    "headwear": [
        ("baseball cap", 0.10), ("beanie", 0.08), ("turban", 0.04), ("hijab", 0.04), ("fedora", 0.03), ("beret", 0.03), ("headscarf", 0.03), ("pagri", 0.01), ("sombrero", 0.01), ("tam", 0.01)
    ],
    "footwear": [
        ("sneakers", 0.15), ("sandals", 0.10), ("boots", 0.10), ("loafers", 0.08), ("flip-flops", 0.07), ("heels", 0.07), ("juttis", 0.02), ("geta", 0.01), ("zori", 0.01), ("brogues", 0.01), ("espadrilles", 0.01)
    ],
    "accessories": [
        ("belt", 0.10), ("scarf", 0.08), ("gloves", 0.07), ("sunglasses", 0.07), ("watch", 0.07), ("bracelet", 0.05), ("necklace", 0.05), ("bindi", 0.01), ("maang tikka", 0.01), ("amulet", 0.01), ("anklet", 0.01)
    ]
}

def download_and_filter_image(img_url, gemma_prompt, folder):
    try:
        response = requests.get(img_url, timeout=5)
        img = Image.open(BytesIO(response.content))
        # Here, you would call GEMMA MLLM with the prompt and image
        # For now, we simulate acceptance
        accepted = True  # Replace with actual GEMMA call
        if accepted:
            import os
            os.makedirs(folder, exist_ok=True)
            img.save(f"{folder}/{img_url.split('/')[-1]}")
            return img_url
    except Exception:
        pass
    return None

def weighted_sample_dict(dct):
    keys = list(dct.keys())
    probs = [sum(prob for _, prob in dct[k]) for k in keys]
    chosen = random.choices(keys, weights=probs, k=1)[0]
    return chosen

def weighted_sample_items(items, k=1):
    names, probs = zip(*items)
    chosen = random.choices(names, weights=probs, k=k)
    return chosen

# Hierarchical site sampling

def weighted_sample_sites_hierarchical(site_dict, k=4):
    """Sample k sites from hierarchical site dictionary according to category and site probabilities."""
    categories = list(site_dict.keys())
    cat_probs = [site_dict[cat]["prob"] for cat in categories]
    chosen_cats = random.choices(categories, weights=cat_probs, k=k)
    chosen_sites = []
    for cat in chosen_cats:
        sites, probs = zip(*site_dict[cat]["sites"])
        chosen_sites.append(random.choices(sites, weights=probs, k=1)[0])
    return chosen_sites

def robust_scraper():
    # Sample 4 sites for human images (hierarchical)
    sampled_sites = weighted_sample_sites_hierarchical(SCRAPE_SITE_CATEGORIES, k=4)
    all_img_urls = []
    for site in sampled_sites:
        img_urls = scrape_images_from_site(site)
        all_img_urls.extend(img_urls)

    # Sample cloth category and name for cloth images
    cloth_category = weighted_sample_dict(CLOTHES_DIVERSITY)
    cloth_names = weighted_sample_items(CLOTHES_DIVERSITY[cloth_category], k=2)
    cloth_img_urls = []
    for cloth_name in cloth_names:
        # Simulate cloth image URLs
        cloth_img_urls.extend([f"cloth/{cloth_category}/{cloth_name}_{i}.jpg" for i in range(5)])

    # GEMMA MLLM prompt for human images
    gemma_prompt_human = '''
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

    # GEMMA MLLM prompt for cloth images
    gemma_prompt_cloth = f'''
Role: Vision-Language Model (GEMMA)
Task: Filter images for cloth diversity scraping
Context: Images should contain clear, unobstructed views of individual clothing items (category: {cloth_category}, names: {', '.join(cloth_names)}). Diversity in garment type, color, material, and style is prioritized. Images may be product shots, flat lays, or mannequin displays.
Constraints:
- Accept images with single clothing item, no human present
- Exclude images with multiple garments, humans, or accessories
- Accept imperfect backgrounds, lighting, and occlusions
- Aspect ratio: 3:4, 4:5, 1:1 or similar; min resolution 512x512
Output Format:
- For each image: {{'accepted': True/False, 'reason': '...'}}
'''

    # Download and filter human images in parallel
    with ThreadPoolExecutor(max_workers=8) as executor:
        results_human = list(executor.map(lambda url: download_and_filter_image(url, gemma_prompt_human, "images/human"), all_img_urls))
        results_cloth = list(executor.map(lambda url: download_and_filter_image(url, gemma_prompt_cloth, "images/cloth"), cloth_img_urls))
    accepted_imgs_human = [r for r in results_human if r]
    accepted_imgs_cloth = [r for r in results_cloth if r]
    print(f"Accepted human images: {accepted_imgs_human}")
    print(f"Accepted cloth images: {accepted_imgs_cloth}")

if __name__ == "__main__":
    robust_scraper()
