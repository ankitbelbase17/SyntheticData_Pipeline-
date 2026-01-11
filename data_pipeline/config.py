# config.py - Data Pipeline Configuration
# Main configuration file with AWS S3 support

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ============================================================================
# AWS S3 CONFIGURATION
# ============================================================================

# S3 Bucket Settings
AWS_S3_BUCKET = os.getenv('AWS_S3_BUCKET', 'your-synthetic-data-bucket')
AWS_S3_REGION = os.getenv('AWS_S3_REGION', 'us-east-1')

# AWS IAM User Credentials
# IMPORTANT: Use environment variables or AWS credentials file, NOT hardcoded values
# To set environment variables:
#   export AWS_ACCESS_KEY_ID="your_access_key"
#   export AWS_SECRET_ACCESS_KEY="your_secret_key"
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', None)
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', None)

# Validate S3 credentials
if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
    raise ValueError(
        "AWS credentials not found. Please set AWS_ACCESS_KEY_ID and "
        "AWS_SECRET_ACCESS_KEY environment variables or add them to .env file"
    )

# S3 Storage Paths
S3_PRODUCTS_PREFIX = "products"
S3_METADATA_PREFIX = "metadata"
S3_IMAGES_PREFIX = "images"
S3_OUTPUTS_PREFIX = "outputs"

# ============================================================================
# API KEYS AND TOKENS
# ============================================================================

# HuggingFace API Token
HF_TOKEN = os.getenv('HF_TOKEN', 'your_huggingface_token_here')

# OpenAI API Key
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', 'your_openai_api_key_here')

# Gemini API Key
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'your_gemini_api_key_here')

# Custom VLM/MLLM endpoints
VLM_API_URL = os.getenv('VLM_API_URL', 'https://your-vlm-endpoint.example.com')
MLLM_API_URL = os.getenv('MLLM_API_URL', 'https://your-mllm-endpoint.example.com')

# ============================================================================
# QWEN VL CONFIGURATION
# ============================================================================

QWEN_VL_MODEL = "Qwen/Qwen2-VL-7B-Instruct"
QWEN_VL_DEVICE = os.getenv('QWEN_VL_DEVICE', 'cuda')
QWEN_VL_MAX_TOKENS = 512

# ============================================================================
# EDIT-BASED MODEL CONFIGURATION
# ============================================================================

EDIT_MODEL = "timbrooks/instruct-pix2pix"
EDIT_MODEL_DEVICE = os.getenv('EDIT_MODEL_DEVICE', 'cuda')
EDIT_NUM_INFERENCE_STEPS = 50
EDIT_IMAGE_GUIDANCE_SCALE = 1.5
EDIT_GUIDANCE_SCALE = 7.5

# ============================================================================
# LOCAL OUTPUT DIRECTORIES (for temporary cache before S3 upload)
# ============================================================================

OUTPUT_DIRS = {
    "images": os.getenv('LOCAL_IMAGES_DIR', "images/"),
    "vl_analysis": os.getenv('LOCAL_VL_ANALYSIS_DIR', "outputs/vl_analysis/"),
    "edited_images": os.getenv('LOCAL_EDITED_IMAGES_DIR', "outputs/edited_images/"),
    "dataset_index": os.getenv('LOCAL_DATASET_INDEX_DIR', "outputs/dataset_index/"),
    "scraper_output": os.getenv('LOCAL_SCRAPER_OUTPUT_DIR', "vton_gallery_dataset/")
}

# ============================================================================
# SCRAPER CONFIGURATION
# ============================================================================

# Zalando Scraper Settings
ZALANDO_SCRAPER_HEADLESS = os.getenv('ZALANDO_SCRAPER_HEADLESS', 'False').lower() == 'true'
ZALANDO_SCRAPER_MAX_PAGES = int(os.getenv('ZALANDO_SCRAPER_MAX_PAGES', '0'))  # 0 = all pages
ZALANDO_SCRAPER_MAX_ITEMS = int(os.getenv('ZALANDO_SCRAPER_MAX_ITEMS', '0'))  # 0 = no limit
ZALANDO_SCRAPER_DELAY_MIN = int(os.getenv('ZALANDO_SCRAPER_DELAY_MIN', '2'))
ZALANDO_SCRAPER_DELAY_MAX = int(os.getenv('ZALANDO_SCRAPER_DELAY_MAX', '4'))

# Use S3 for scraper output
ZALANDO_USE_S3 = os.getenv('ZALANDO_USE_S3', 'True').lower() == 'true'

# ============================================================================
# IMAGE PROCESSING CONFIGURATION
# ============================================================================

# Image Quality Checks
MIN_IMAGE_WIDTH = 400
MIN_IMAGE_HEIGHT = 400

# Allowed Aspect Ratios
ALLOWED_ASPECT_RATIOS = [(3, 4), (4, 5), (1, 1)]
ASPECT_RATIO_TOLERANCE = 0.05

# Image Resizing
DEFAULT_IMAGE_SIZE = (512, 512)

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_FILE = os.getenv('LOG_FILE', 'logs/data_pipeline.log')

# ============================================================================
# DATABASE/CHECKPOINT CONFIGURATION
# ============================================================================

# Progress Checkpoints
SAVE_PROGRESS_EVERY = 10  # Save progress every N items

# Metadata Storage Format
METADATA_FORMAT = 'json'  # 'json' or 'csv'

# ============================================================================
# THREADING AND PERFORMANCE
# ============================================================================

NUM_DOWNLOAD_WORKERS = int(os.getenv('NUM_DOWNLOAD_WORKERS', '4'))
NUM_PROCESSING_WORKERS = int(os.getenv('NUM_PROCESSING_WORKERS', '2'))
IMAGE_DOWNLOAD_TIMEOUT = 15  # seconds

# ============================================================================
# VALIDATION AND QUALITY CONTROL
# ============================================================================

# Enable validation checks
ENABLE_IMAGE_VALIDATION = True
ENABLE_METADATA_VALIDATION = True

# Skip validation for specific conditions
SKIP_DUPLICATE_CHECK = False
SKIP_SIZE_CHECK = False

# ============================================================================
# NETWORKING AND PROXIES (Optional)
# ============================================================================

# Proxy configuration (if needed)
USE_PROXY = os.getenv('USE_PROXY', 'False').lower() == 'true'
PROXY_URL = os.getenv('PROXY_URL', None)

# Request retry configuration
MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 0.3

# ============================================================================
# ENVIRONMENT
# ============================================================================

ENV = os.getenv('ENV', 'development')  # 'development', 'staging', 'production'
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
