import os
import json
import re
from PIL import Image
from typing import Dict, Any
import requests
from io import BytesIO

def save_image(image: Image.Image, output_dir: str, filename: str):
    """
    Saves an image to the specified directory.
    """
    os.makedirs(output_dir, exist_ok=True)
    image.save(os.path.join(output_dir, filename))
    print(f"Saved image to: {os.path.join(output_dir, filename)}")

def load_image_from_url(url: str) -> Image.Image:
    """
    Loads an image from a URL.
    """
    if not url:
        raise ValueError("URL is empty")
    response = requests.get(url)
    response.raise_for_status()
    return Image.open(BytesIO(response.content)).convert("RGB")

def parse_json_response(response_str: str) -> Dict[str, Any]:
    """
    Parses JSON from a string, handling potential markdown formatting.
    """
    # Try direct parsing
    try:
        return json.loads(response_str)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code block
    match = re.search(r"```json(.*?)```", response_str, re.DOTALL)
    if match:
        json_str = match.group(1).strip()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"Failed to parse extracted JSON: {e}")
            raise ValueError("Invalid JSON format inside markdown block")
    
    # Try finding first { and last }
    start = response_str.find("{")
    end = response_str.rfind("}")
    if start != -1 and end != -1:
        json_str = response_str[start:end+1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"Failed to parse heuristically extracted JSON: {e}")
            raise ValueError("Invalid JSON format")

    raise ValueError("Could not extract JSON from response")

def ensure_directories_exist(base_dir: str):
    """
    Ensures all necessary directories exist.
    """
    dirs = [
        "input/person",
        "input/cloth",
        "output/correct_try_on",
        "output/incorrect_try_on_1",
        "output/incorrect_try_on_2",
        "output/incorrect_try_on_3",
        "output/incorrect_try_on_4",
    ]
    for d in dirs:
        os.makedirs(os.path.join(base_dir, d), exist_ok=True)

