# config.py
# Store all API keys, tokens, and sensitive configuration here.
# DO NOT commit this file to public repositories.

# Example: HuggingFace token
HF_TOKEN = "your_huggingface_token_here"

# Example: OpenAI API key
OPENAI_API_KEY = "your_openai_api_key_here"

# Example: Gemini API key
GEMINI_API_KEY = "your_gemini_api_key_here"

# Example: Custom VLM/MLLM endpoint
VLM_API_URL = "https://your-vlm-endpoint.example.com"
MLLM_API_URL = "https://your-mllm-endpoint.example.com"

# Qwen VL Configuration
QWEN_VL_MODEL = "Qwen/Qwen2-VL-7B-Instruct"  # Model name or "Qwen/Qwen2.5-VL-7B-Instruct" if available
QWEN_VL_DEVICE = "cuda"  # "cuda" or "cpu"
QWEN_VL_MAX_TOKENS = 512

# Edit-based Model Configuration (InstructPix2Pix)
EDIT_MODEL = "timbrooks/instruct-pix2pix"
EDIT_MODEL_DEVICE = "cuda"  # "cuda" or "cpu"
EDIT_NUM_INFERENCE_STEPS = 50
EDIT_IMAGE_GUIDANCE_SCALE = 1.5
EDIT_GUIDANCE_SCALE = 7.5

# Output directories
OUTPUT_DIRS = {
    "images": "images/",
    "vl_analysis": "outputs/vl_analysis/",
    "edited_images": "outputs/edited_images/",
    "dataset_index": "outputs/dataset_index/"
}

