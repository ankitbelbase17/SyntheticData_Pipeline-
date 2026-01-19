import os
import asyncio
import aioboto3
from PIL import Image
from io import BytesIO
from src.config import S3_BUCKET_NAME, S3_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY

class AsyncUploader:
    def __init__(self):
        self.session = aioboto3.Session(
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=S3_REGION
        )
    
    async def upload_data(self, image: Image.Image, text_content: str, s3_key_prefix: str, prompt_number: str):
        """
        Uploads image and text to S3 asynchronously.
        """
        print(f"Starting upload for Prompt {prompt_number} to {s3_key_prefix}...")
        try:
            async with self.session.client("s3", region_name=S3_REGION) as s3:
                # 1. Upload Image
                img_buffer = BytesIO()
                image.save(img_buffer, format="PNG")
                img_buffer.seek(0)
                
                image_key = f"{s3_key_prefix}/{prompt_number}.png"
                await s3.upload_fileobj(img_buffer, S3_BUCKET_NAME, image_key)
                
                # 2. Upload Text
                text_key = f"{s3_key_prefix}/{prompt_number}.txt"
                await s3.put_object(Body=text_content.encode('utf-8'), Bucket=S3_BUCKET_NAME, Key=text_key)
                
                print(f"✓ Successfully uploaded Prompt {prompt_number} to S3.")
                
        except Exception as e:
            print(f"❌ Error uploading Prompt {prompt_number}: {e}")

    async def get_existing_prompts(self, s3_prefix: str) -> set:
        """
        Scan S3 for existing prompt directories to support resuming.
        Returns a set of prompt numbers (strings) that are already processed.
        """
        print(f"Scanning S3 bucket '{S3_BUCKET_NAME}' at prefix '{s3_prefix}' for existing files...")
        existing_prompts = set()
        
        try:
            async with self.session.client("s3", region_name=S3_REGION) as s3:
                paginator = s3.get_paginator("list_objects_v2")
                
                # We assume the structure is prefix/prompt_number/file
                # We want to find the "prompt_number" directories.
                # A simple way is to list all keys and extract the prompt number from the path.
                async for page in paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix=s3_prefix):
                    if "Contents" not in page:
                        continue
                        
                    for obj in page["Contents"]:
                        key = obj["Key"]
                        # key format: generated_images/{prompt_number}/{filename}
                        # Remove prefix
                        relative_key = key[len(s3_prefix):].lstrip("/")
                        parts = relative_key.split("/")
                        
                        # We expect at least folder/file
                        if len(parts) >= 1:
                            # The first part should be the prompt number
                            # Ensure it's a number (or whatever naming convention)
                            # based on user request: generated_images/1/1.png
                            prompt_str = parts[0]
                            if prompt_str and prompt_str.isdigit():
                                existing_prompts.add(prompt_str)
                                
        except Exception as e:
            print(f"Warning: Could not list S3 objects (starting fresh?): {e}")
            
        print(f"Found {len(existing_prompts)} existing prompts in S3.")
        return existing_prompts