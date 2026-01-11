"""
Utility functions for image processing: aspect ratio checks, resizing, and more.
Import and use these in the scraper and other modules as needed.
"""

from PIL import Image
import json
import os
from typing import Dict, Any
from pathlib import Path

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

def save_json_metadata(data: Dict[str, Any], output_path: str) -> None:
    """Save structured metadata/analysis as JSON."""
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"[Utils] Saved JSON metadata to {output_path}")

def load_json_metadata(input_path: str) -> Dict[str, Any]:
    """Load JSON metadata/analysis file."""
    with open(input_path, 'r') as f:
        return json.load(f)

def create_dataset_index(images_dir: str, output_json: str) -> Dict[str, Any]:
    """
    Create an index of all images and metadata in a dataset directory.
    Useful for organizing VL outputs, edited images, etc.
    """
    index = {
        "images": [],
        "total_count": 0,
        "directory": images_dir
    }
    
    for img_file in Path(images_dir).glob("*.jpg"):
        index["images"].append({
            "filename": img_file.name,
            "path": str(img_file),
            "size": img_file.stat().st_size
        })
    
    index["total_count"] = len(index["images"])
    
    # Save index
    save_json_metadata(index, output_json)
    
    return index
