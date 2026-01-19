"""
Utility functions for batch processing
"""

import os
import json
import random
from pathlib import Path
from datetime import datetime
from hard_dict import HARD_DICT
from medium_dict import MEDIUM_DICT


def weighted_choice(items: dict, k=1):
    """
    Selects k keys from a dict {item: weight}
    """
    keys = list(items.keys())
    weights = list(items.values())
    return random.choices(keys, weights=weights, k=k)


def sample_keywords_from_dict(source_dict, min_categories):
    """
    Samples categories independently using their category probabilities.
    From each selected category, samples exactly one sub-item.
    
    Args:
        source_dict: Dictionary with category probabilities and items
        min_categories: Minimum number of categories to sample
    
    Returns:
        dict: {category_name: selected_item}
    """
    selected = {}
    
    # Step 1: sample categories independently
    for category, data in source_dict.items():
        if random.random() < data["prob"]:
            selected[category] = weighted_choice(data["items"])[0]
    
    # Step 2: enforce minimum number of categories
    if len(selected) < min_categories:
        remaining = list(set(source_dict.keys()) - set(selected.keys()))
        remaining_weights = [source_dict[c]["prob"] for c in remaining]
        
        while len(selected) < min_categories and remaining:
            category = random.choices(remaining, weights=remaining_weights, k=1)[0]
            selected[category] = weighted_choice(source_dict[category]["items"])[0]
            
            idx = remaining.index(category)
            remaining.pop(idx)
            remaining_weights.pop(idx)
    
    return selected


def sample_combined_keywords(min_categories_medium, min_categories_hard):
    """
    Sample keywords from both MEDIUM_DICT and HARD_DICT and combine them.
    Hard keywords take precedence over medium ones.
    
    Args:
        min_categories_medium: Minimum categories from medium dict
        min_categories_hard: Minimum categories from hard dict
    
    Returns:
        dict: Combined keywords {category: selected_item}
    """
    medium_keywords = sample_keywords_from_dict(MEDIUM_DICT, min_categories_medium)
    hard_keywords = sample_keywords_from_dict(HARD_DICT, min_categories_hard)
    
    # Merge: medium first, then hard (hard takes precedence)
    combined = {**medium_keywords, **hard_keywords}
    
    return combined


def format_keywords_as_string(keywords_dict):
    """
    Convert keywords dictionary to a formatted string for the prompt.
    
    Args:
        keywords_dict: Dictionary of {category: selected_item}
    
    Returns:
        str: Formatted keyword string
    """
    items = [f"{item}" for item in keywords_dict.values()]
    return ", ".join(items)


def sample_keywords(num_samples, min_categories_medium, min_categories_hard):
    """
    Sample random keywords for each prompt in the batch using the sampling dictionaries.
    
    Args:
        num_samples: Number of samples to generate
        min_categories_medium: Minimum categories from medium dict
        min_categories_hard: Minimum categories from hard dict
    
    Returns:
        List of keyword strings (sampled combinations)
    """
    sampled = []
    for _ in range(num_samples):
        keywords_dict = sample_combined_keywords(min_categories_medium, min_categories_hard)
        keywords_str = format_keywords_as_string(keywords_dict)
        sampled.append(keywords_str)
    
    return sampled


def create_output_folder(output_folder):
    """Create output folder if it doesn't exist"""
    Path(output_folder).mkdir(parents=True, exist_ok=True)


def save_prompts(prompts, output_folder, image_name, batch_id=None):
    """
    Save generated prompts to file
    
    Args:
        prompts: List of generated prompts
        output_folder: Output directory
        image_name: Name of the source image
        batch_id: Optional batch identifier
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_suffix = f"_batch{batch_id}" if batch_id is not None else ""
    
    # Save as JSON
    json_filename = f"{image_name}_{timestamp}{batch_suffix}_prompts.json"
    json_path = os.path.join(output_folder, json_filename)
    
    output_data = {
        "image": image_name,
        "timestamp": timestamp,
        "batch_size": len(prompts),
        "prompts": prompts
    }
    
    with open(json_path, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    # Also save as plain text (one per line)
    txt_filename = f"{image_name}_{timestamp}{batch_suffix}_prompts.txt"
    txt_path = os.path.join(output_folder, txt_filename)
    
    with open(txt_path, 'w') as f:
        for i, prompt in enumerate(prompts, 1):
            f.write(f"# Prompt {i}\n{prompt}\n\n")
    
    print(f"✓ Saved prompts to:")
    print(f"  - {json_path}")
    print(f"  - {txt_path}")
    
    return json_path, txt_path


def get_image_files(image_folder, extensions=('.png', '.jpg', '.jpeg', '.webp')):
    """
    Get all image files from folder
    
    Args:
        image_folder: Path to folder containing images
        extensions: Tuple of valid image extensions
    
    Returns:
        List of image file paths
    """
    if not os.path.exists(image_folder):
        raise FileNotFoundError(f"Image folder not found: {image_folder}")
    
    image_files = []
    for ext in extensions:
        image_files.extend(Path(image_folder).glob(f"*{ext}"))
    
    return sorted([str(f) for f in image_files])