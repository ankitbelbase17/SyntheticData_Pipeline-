"""
Optimized S3 Image Dataset with connection pooling and caching
Fixes slow S3 downloads on Vast AI / cloud GPU rentals
"""

import os
import boto3
from botocore.config import Config as BotoConfig
from io import BytesIO
from PIL import Image
from torch.utils.data import Dataset
from functools import lru_cache
import config


# Global S3 client with connection pooling - reused across workers
_s3_client = None


def get_s3_client():
    """
    Get a cached S3 client with optimized connection settings.
    Uses connection pooling for better performance.
    """
    global _s3_client
    if _s3_client is None:
        # Configure boto3 with connection pooling and retries
        boto_config = BotoConfig(
            max_pool_connections=50,  # Increase from default 10
            retries={
                'max_attempts': 3,
                'mode': 'adaptive'  # Adaptive retry mode
            },
            connect_timeout=5,
            read_timeout=30,
            # Use S3 Transfer Acceleration if available
            s3={
                'use_accelerate_endpoint': False,  # Set True if bucket has acceleration enabled
                'addressing_style': 'virtual'
            }
        )
        
        _s3_client = boto3.client(
            's3',
            aws_access_key_id=config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
            region_name=config.AWS_REGION_NAME,
            config=boto_config
        )
    return _s3_client


def get_optimal_region_client(bucket_name: str):
    """
    Create an S3 client in the same region as the bucket for minimum latency.
    This is especially important for Vast AI which may be in a different region.
    """
    try:
        # First, determine the bucket's region
        temp_client = boto3.client(
            's3',
            aws_access_key_id=config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
        )
        
        response = temp_client.get_bucket_location(Bucket=bucket_name)
        bucket_region = response.get('LocationConstraint') or 'us-east-1'
        
        print(f"✓ Bucket '{bucket_name}' is in region: {bucket_region}")
        
        # Check if we're using a different region
        if bucket_region != config.AWS_REGION_NAME:
            print(f"⚠ Config region ({config.AWS_REGION_NAME}) differs from bucket region ({bucket_region})")
            print(f"  → Using bucket region for optimal latency")
        
        # Create optimized client in the correct region
        boto_config = BotoConfig(
            max_pool_connections=50,
            retries={'max_attempts': 3, 'mode': 'adaptive'},
            connect_timeout=5,
            read_timeout=30,
        )
        
        return boto3.client(
            's3',
            aws_access_key_id=config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
            region_name=bucket_region,  # Use bucket's actual region!
            config=boto_config
        )
        
    except Exception as e:
        print(f"⚠ Could not determine bucket region ({e}), using default")
        return get_s3_client()


class S3ImageDatasetOptimized(Dataset):
    """
    Optimized Dataset class for S3 images with:
    - Connection pooling
    - Proper error handling
    - Pre-warmed connections
    """
    
    def __init__(self, s3_urls, bucket_name=None):
        """
        Args:
            s3_urls: List of S3 URLs (s3://bucket/key format)
            bucket_name: Optional bucket name for region-optimized client
        """
        self.s3_urls = s3_urls
        self._client = None
        self._bucket_name = bucket_name
        
        # Parse bucket from first URL if not provided
        if not self._bucket_name and s3_urls:
            first_url = s3_urls[0]
            if first_url.startswith("s3://"):
                self._bucket_name = first_url.replace("s3://", "").split("/", 1)[0]
    
    def _get_client(self):
        """Lazy-load S3 client (important for multiprocessing DataLoader workers)"""
        if self._client is None:
            self._client = get_s3_client()
        return self._client
    
    def __len__(self):
        return len(self.s3_urls)
    
    def __getitem__(self, idx):
        url = self.s3_urls[idx]
        try:
            if url.startswith("s3://"):
                s3 = self._get_client()
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
            return None


# Worker initialization function for DataLoader
def worker_init_fn(worker_id):
    """
    Initialize S3 client for each DataLoader worker.
    This ensures each worker has its own connection.
    """
    global _s3_client
    _s3_client = None  # Reset to force new client in this worker
    get_s3_client()  # Pre-warm the connection


# Backward compatibility alias
S3ImageDataset = S3ImageDatasetOptimized
