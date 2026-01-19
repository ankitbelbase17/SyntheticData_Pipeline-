import os
import asyncio
import aioboto3
from PIL import Image
from io import BytesIO
from src.config import S3_BUCKET_NAME, S3_REGION

class AsyncUploader:
    def __init__(self):
        self.session = aioboto3.Session()
    
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
