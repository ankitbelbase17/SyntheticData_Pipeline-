"""
Utility functions for batch processing
"""

import os
import json
import random
from pathlib import Path
from datetime import datetime
from easy_dict import EASY_DICT
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


def sample_easy_keywords(easy_dict):
    """
    Samples categories independently using their category probabilities for Easy mode.
    From each selected category, samples exactly one sub-item.
    Ensures at least one category is always selected.

    Returns:
        dict: {category_name: selected_item}
    """
    selected = {}

    # --- Step 1: sample categories independently ---
    for category, data in easy_dict.items():
        if random.random() < data["prob"]:
            selected[category] = weighted_choice(data["items"])[0]

    # --- Step 2: ensure at least one category is selected ---
    if not selected:
        categories = list(easy_dict.keys())
        category_weights = [easy_dict[c]["prob"] for c in categories]
        category = random.choices(categories, weights=category_weights, k=1)[0]
        selected[category] = weighted_choice(easy_dict[category]["items"])[0]

    return selected


def sample_medium_keywords(medium_dict, min_categories=4):
    """
    Samples categories independently using their category probabilities.
    From each selected category, samples exactly one sub-item.
    Enforces minimum number of categories.

    Returns:
        dict: {category_name: selected_item}
    """
    selected = {}

    # --- Step 1: sample categories independently ---
    for category, data in medium_dict.items():
        if random.random() < data["prob"]:
            selected[category] = weighted_choice(data["items"])[0]

    # --- Step 2: enforce minimum number of categories ---
    if len(selected) < min_categories:
        remaining = list(set(medium_dict.keys()) - set(selected.keys()))
        remaining_weights = [medium_dict[c]["prob"] for c in remaining]

        while len(selected) < min_categories and remaining:
            category = random.choices(remaining, weights=remaining_weights, k=1)[0]
            selected[category] = weighted_choice(medium_dict[category]["items"])[0]

            idx = remaining.index(category)
            remaining.pop(idx)
            remaining_weights.pop(idx)

    return selected


def sample_keywords(num_samples, difficulty='medium', min_categories_medium=4, min_categories_hard=3):
    """
    Sample random keywords for each prompt in the batch using the sampling dictionaries.
    
    Args:
        num_samples: Number of samples to generate
        difficulty: 'easy', 'medium', or 'hard'
        min_categories_medium: Minimum categories from medium dict
        min_categories_hard: Minimum categories from hard dict
    
    Returns:
        List of keyword strings (sampled combinations)
    """
    sampled = []
    
    for _ in range(num_samples):
        if difficulty == 'easy':
            # Use specific Easy sampling logic
            keywords_dict = sample_easy_keywords(EASY_DICT)
        elif difficulty == 'medium':
            keywords_dict = sample_medium_keywords(MEDIUM_DICT, min_categories_medium)
        elif difficulty == 'hard':
            keywords_dict = sample_keywords_from_dict(HARD_DICT, min_categories_hard)
        else:
            # Combined / default case
            keywords_dict = sample_combined_keywords(min_categories_medium, min_categories_hard)
            
        keywords_str = format_keywords_as_string(keywords_dict)
        sampled.append(keywords_str)
    
    return sampled


def create_output_folder(output_folder):
    """Create output folder if it doesn't exist"""
    Path(output_folder).mkdir(parents=True, exist_ok=True)


def save_edit_prompt(prompt, output_folder, image_name):
    """
    Save generated prompt to {image_name}_edit.txt
    
    Args:
        prompt: Single editing prompt
        output_folder: Output directory
        image_name: Name of the source image (without extension), e.g. "1" from "1.png" or "1_edit"
    """
    # Ensure image_name matches strict naming convention "X_edit"
    if not image_name.endswith("_edit"):
        base_name = image_name
        filename = f"{base_name}_edit.txt"
    else:
        filename = f"{image_name}.txt"
        
    txt_path = os.path.join(output_folder, filename)
    
    with open(txt_path, 'w') as f:
        f.write(prompt)
    
    print(f"  Saved: {txt_path}")
    return txt_path


def save_prompts(prompts, output_folder, image_name, batch_id=None):
    """
    Save generated prompts to file (Legacy mode)
    
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

def get_s3_image_files(bucket_name, prefix, extensions=('.png',)):
    """
    Get all image files from S3 bucket under a specific prefix
    
    Args:
        bucket_name: Name of S3 bucket
        prefix: S3 prefix to search in (e.g. 'p1-to-ep1/dataset/male/male/images/')
        extensions: Tuple of valid image extensions
    
    Returns:
        List of S3 URLs (s3://bucket/key)
    """
    import boto3
    s3 = boto3.client('s3')
    
    s3_files = []
    
    # List objects in folder
    paginator = s3.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)
    
    for page in pages:
        if 'Contents' in page:
            for obj in page['Contents']:
                key = obj['Key']
                if key.lower().endswith(extensions):
                    s3_files.append(f"s3://{bucket_name}/{key}")
    
    # Sort files to ensure 1.png, 2.png order if possible
    # We can try to sort by the numeric part of the filename
    try:
        s3_files.sort(key=lambda x: int(Path(x).stem))
    except (ValueError, TypeError):
        s3_files.sort()
        
    return s3_files