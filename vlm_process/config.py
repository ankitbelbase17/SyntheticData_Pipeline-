import os

# Paths
IMAGE_FOLDER = "./data/images"
OUTPUT_FOLDER = "./outputs/prompts"

# AWS S3 Configuration
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "p1-to-ep1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "your_access_key_here")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "your_secret_key_here")
AWS_REGION_NAME = os.getenv("AWS_REGION_NAME", "us-east-1")

# Model settings
MODEL_NAME = "Qwen/Qwen3-VL-4B-Instruct"
DEVICE = "cuda"  # H100 GPU

# Inference settings
BATCH_SIZE = 32  # Number of prompts to process per batch
MAX_NEW_TOKENS = 512
TEMPERATURE = 0.7

# Prompt generation settings
TOTAL_PROMPTS = 128  # Total number of prompts to generate (across all images, cycling)
# Images will be cycled through until this total is reached

# Keyword sampling configuration
MIN_CATEGORIES_FROM_HARD = 3
MIN_CATEGORIES_FROM_MEDIUM = 4

# System prompt that will be prefixed to all prompts
SYSTEM_PROMPT = """You are an image-editing prompt generator for a diffusion-based image editing model specialized in fashion and virtual try-on tasks. You will receive an image and a set of sampled attribute keywords (e.g., camera orientation, pose, body characteristics, lighting, occlusion, or special conditions). These hints are guidance only, not phrases to be copied. Your output must be a single, concise editing instruction that modifies the given image to create a realistic, diverse virtual try-on sample suitable for dataset generation. Follow these rules strictly: Do not describe or summarize the original image; the editing model already has access to it. Focus only on what should be changed or added, not on what already exists. Ensure the instruction is compatible with image-conditioned editing models (natural language, spatially aware, no layout explanations). Avoid copying or repeating common template keywords verbatim; integrate concepts naturally. Prefer edits that increase dataset diversity, such as fit, color, lighting, background context, or subtle body-aware adjustments. Preserves identity, body proportions, and pose unless the edit explicitly requires variation. Do not include reasoning, or formatting, preambles — output only the editing prompt yet detailed prompts to edit the image.output should use imperative verbs also clear edit instructions and guide describing the editing task detailed"""