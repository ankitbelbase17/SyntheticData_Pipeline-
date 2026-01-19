import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# S3 Configuration
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "my-bucket")
S3_REGION = os.getenv("S3_REGION", "us-east-1")
S3_PREFIX = os.getenv("S3_PREFIX", "generated_images")

# Run Configuration
OUTPUT_BASE_DIR = Path("output")
OUTPUT_BASE_DIR.mkdir(exist_ok=True)
