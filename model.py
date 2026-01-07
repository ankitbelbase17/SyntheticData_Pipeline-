# model.py
"""
Centralized model loader for all ML/VLM/LLM models used in the codebase.
Import and use these functions in other .py files instead of loading models directly.
"""

import os
from config import HF_TOKEN, OPENAI_API_KEY, GEMINI_API_KEY

# Example: HuggingFace Transformers
from transformers import AutoModel, AutoTokenizer

# Example: CLIP (Vision-Language Model)
def load_clip_model(model_name="openai/clip-vit-base-patch16"):
    tokenizer = AutoTokenizer.from_pretrained(model_name, use_auth_token=HF_TOKEN)
    model = AutoModel.from_pretrained(model_name, use_auth_token=HF_TOKEN)
    return model, tokenizer

# Example: OpenAI GPT (for MLLM)
def load_openai_gpt():
    import openai
    openai.api_key = OPENAI_API_KEY
    return openai

# Example: Gemini API (placeholder)
def load_gemini_api():
    # Replace with actual Gemini API client if available
    return GEMINI_API_KEY

# Example: Custom VLM/MLLM endpoint
import requests

def call_custom_vlm_api(image_bytes, prompt, api_url=None):
    api_url = api_url or os.environ.get("VLM_API_URL")
    files = {"image": image_bytes}
    data = {"prompt": prompt}
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    response = requests.post(api_url, files=files, data=data, headers=headers)
    return response.json()

# Add more model loading/utilities as needed
