import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# S3 Configuration
# WARNING: Hardcoded credentials. In production, use environment variables or IAM roles.
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "vton-cloth")
S3_REGION = os.getenv("S3_REGION", "ap-south-1")
S3_PREFIX = os.getenv("S3_PREFIX", "generated_images")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

# Run Configuration
OUTPUT_BASE_DIR = Path("output")
OUTPUT_BASE_DIR.mkdir(exist_ok=True)