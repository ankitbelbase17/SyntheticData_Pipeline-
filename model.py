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
# Qwen 2.5 VL Model
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
import torch

def load_qwen_vl_model(model_name="Qwen/Qwen2-VL-7B-Instruct", device=None):
    """Load Qwen VL model for multi-image analysis and prompt generation."""
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    
    model = Qwen2VLForConditionalGeneration.from_pretrained(
        model_name,
        torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        attn_implementation="flash_attention_2" if device == "cuda" else "eager"
    ).to(device)
    
    processor = AutoProcessor.from_pretrained(model_name)
    
    return model, processor, device
# Add more model loading/utilities as needed
