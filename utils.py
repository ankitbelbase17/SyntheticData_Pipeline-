# utils.py
"""
Utility functions for image processing: aspect ratio checks, resizing, and more.
Import and use these in the scraper and other modules as needed.
"""

from PIL import Image

def check_aspect_ratio(img, allowed_ratios=[(3,4), (4,5), (1,1)], tolerance=0.05):
    """
    Check if the image aspect ratio matches any allowed ratio within a tolerance.
    """
    w, h = img.size
    aspect = w / h
    for rw, rh in allowed_ratios:
        target = rw / rh
        if abs(aspect - target) < tolerance:
            return True
    return False

def check_min_resolution(img, min_size=512):
    """
    Check if both width and height are at least min_size.
    """
    w, h = img.size
    return w >= min_size and h >= min_size

def resize_image(img, target_size=(512, 512)):
    """
    Resize image to target_size (width, height) using high-quality resampling.
    """
    return img.resize(target_size, Image.LANCZOS)

# Add more image utilities as needed
