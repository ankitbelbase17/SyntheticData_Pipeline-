"""
Configuration file for VTON scraper
"""

# Target sites configuration
SITES = {
    "zalando": {
        "enabled": True,
        "search_urls": [
            "https://www.zalando.com/womens-clothing-dresses/",
            "https://www.zalando.com/womens-clothing-tops/",
            "https://www.zalando.com/womens-clothing-shirts/",
            "https://www.zalando.com/mens-clothing-shirts/",
            "https://www.zalando.com/mens-clothing-t-shirts/",
        ],
        "requires_proxy": False,
        "delay_range": (2, 5),
        "max_retries": 3
    },
    "amazon": {
        "enabled": True,
        "search_urls": [
            "https://www.amazon.com/s?k=women+dress",
            "https://www.amazon.com/s?k=women+blouse",
            "https://www.amazon.com/s?k=men+shirt",
            "https://www.amazon.com/s?k=women+top",
        ],
        "requires_proxy": False,
        "delay_range": (3, 7),
        "max_retries": 5
    },
    "shein": {
        "enabled": False,  # Enable later
        "search_urls": [
            "https://www.shein.com/Dresses-c-1727.html",
        ],
        "requires_proxy": False,
        "delay_range": (2, 5),
        "max_retries": 3
    },
    "asos": {
        "enabled": False,  # Enable later
        "search_urls": [
            "https://www.asos.com/women/dresses/cat/?cid=8799",
        ],
        "requires_proxy": False,
        "delay_range": (2, 5),
        "max_retries": 3
    }
}

# Scraping settings
SCRAPING_CONFIG = {
    "headless": False,  # Set to True for production
    "output_dir": "vton_dataset",
    "max_items_per_site": 100,  # For testing, increase to 10000+ for production
    "batch_size": 20,  # Save progress every N items
    "image_min_resolution": (400, 400),  # Minimum image size
    "timeout": 30,  # Page load timeout
    "enable_screenshots": False,  # Save screenshots for debugging
}

# Proxy configuration (optional)
PROXY_CONFIG = {
    "enabled": False,  # Set to True if you have proxies
    "proxy_list": [
        # Add your proxy list here
        # Format: "http://user:pass@ip:port" or "http://ip:port"
    ],
    "rotate_after": 50,  # Rotate proxy after N requests
}

# Rate limiting
RATE_LIMIT_CONFIG = {
    "enabled": True,
    "requests_per_minute": 20,
    "cooldown_on_error": 60,  # Seconds to wait after error
}

# User agent rotation
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
]

# Image quality filters
IMAGE_FILTERS = {
    "min_width": 400,
    "min_height": 400,
    "max_file_size_mb": 10,
    "allowed_formats": [".jpg", ".jpeg", ".png"],
}
