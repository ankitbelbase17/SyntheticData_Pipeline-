
import os
import boto3
import requests
from io import BytesIO
from PIL import Image
from torch.utils.data import Dataset

class S3ImageDataset(Dataset):
    """
    Dataset class that streams images from S3.
    Use with DataLoader to enable multi-threaded prefetching.
    """
    def __init__(self, s3_urls):
        self.s3_urls = s3_urls
        # Initialize boto3 client lazily usually, but for simple workers we can do per-item or global
        # Boto3 clients are not thread-safe if shared incorrectly, so we often initialize in __getitem__ or worker_init_fn
        # However, requests via https is simpler for threading
        
    def __len__(self):
        return len(self.s3_urls)
    
    def __getitem__(self, idx):
        url = self.s3_urls[idx]
        try:
            if url.startswith("s3://"):
                # Use boto3
                # Optimization: Create client here to be safe in multiprocessing
                s3 = boto3.client('s3')
                parts = url.replace("s3://", "").split("/", 1)
                bucket, key = parts[0], parts[1]
                response = s3.get_object(Bucket=bucket, Key=key)
                img_data = response['Body'].read()
                img = Image.open(BytesIO(img_data)).convert('RGB')
            else:
                # Local file
                img = Image.open(url).convert('RGB')
                
            return img, url
        except Exception as e:
            print(f"Error loading {url}: {e}")
            # Return a placeholder or None? 
            # Ideally handle this robustly, but for now return a black image to avoid crashing the batch
            return Image.new('RGB', (224, 224)), url
