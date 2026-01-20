"""
OPTIMIZED Qwen VLM Batch Inference Pipeline
============================================
Fixes for slow performance on Vast AI / cloud GPU rentals vs Lightning AI

Key Optimizations Applied:
1. Flash Attention 2 - Major speedup on A100/H100 (must install flash-attn)
2. BFloat16 - Better performance than Float16 on Ampere+ GPUs
3. CUDA optimizations (TF32, cuDNN benchmark, memory allocator)
4. S3 connection pooling and region-aware client
5. Proper DataLoader worker initialization
6. torch.inference_mode() instead of torch.no_grad()
7. Warmup pass to initialize CUDA kernels

Usage:
    python qwen_batch_inference_optimized.py --gender male --shard_id 0 --total_shards 7 --epochs 8 --difficulty medium

Prerequisites:
    pip install flash-attn --no-build-isolation  # For Flash Attention 2
"""

import os
import time
import torch
import argparse
import boto3
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from torch.utils.data import DataLoader
from botocore.config import Config as BotoConfig

# Import configuration and utilities
import config
from utils import (
    sample_keywords,
    create_output_folder,
    get_s3_image_files
)

# Import OPTIMIZED modules
from qwen_inference_optimized import QwenVLBatchInferenceOptimized
from s3_dataloader_optimized import S3ImageDatasetOptimized, worker_init_fn


def collate_fn(batch):
    """
    Custom collate function to handle PIL images and URLs
    Returns: (list_of_images, list_of_urls)
    """
    valid_batch = [item for item in batch if item is not None]
    
    if not valid_batch:
        return [], []

    images = [item[0] for item in valid_batch]
    urls = [item[1] for item in valid_batch]
    return images, urls


def get_optimized_s3_client(bucket_name=None):
    """Create an S3 client with connection pooling for uploads"""
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
        region_name=config.AWS_REGION_NAME,
        config=boto_config
    )


class QwenBatchProcessorOptimized:
    """
    Optimized batch processor with all performance fixes applied
    """
    
    def __init__(self, difficulty='medium', use_flash_attention=True, use_compile=False):
        """Initialize the batch processor with optimized model"""
        print("="*80)
        print("Qwen VLM OPTIMIZED Batch Inference Pipeline")
        print("="*80)
        
        # Print environment info for debugging
        self._print_environment_info()
        
        # Load optimized model
        print("\n[1/3] Loading optimized model...")
        self.model = QwenVLBatchInferenceOptimized(
            model_name=config.MODEL_NAME,
            device=config.DEVICE,
            use_flash_attention=use_flash_attention,
            use_compile=use_compile
        )
        
        self.difficulty = difficulty
        
        # Thread pool for async saving with optimized S3 client
        self.save_executor = ThreadPoolExecutor(max_workers=8)  # Increased from 4
        
        print("\n[3/3] Initialization complete!")
        print(f"✓ Keyword sampling difficulty: {difficulty.upper()}")
        print("="*80)
    
    def _print_environment_info(self):
        """Print environment information for debugging performance issues"""
        print("\n[Environment Info]")
        print(f"  PyTorch: {torch.__version__}")
        print(f"  CUDA Available: {torch.cuda.is_available()}")
        
        if torch.cuda.is_available():
            print(f"  CUDA Version: {torch.version.cuda}")
            print(f"  GPU: {torch.cuda.get_device_name(0)}")
            print(f"  GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
            
            # Check compute capability for Flash Attention compatibility
            major, minor = torch.cuda.get_device_capability()
            print(f"  Compute Capability: {major}.{minor}")
            
            if major >= 8:
                print("  ✓ GPU supports Flash Attention 2 (Ampere or newer)")
            else:
                print("  ⚠ GPU may not support Flash Attention 2 (requires Ampere+)")
        
        # Check for flash-attn installation
        try:
            import flash_attn
            print(f"  ✓ flash-attn installed: {flash_attn.__version__}")
        except ImportError:
            print("  ⚠ flash-attn NOT installed - run: pip install flash-attn --no-build-isolation")
    
    def process_batch_multi_image(self, images):
        """
        Process a batch with DIFFERENT images (one prompt per image)
        """
        actual_batch_size = len(images)
        
        keyword_samples = sample_keywords(
            actual_batch_size,
            difficulty=self.difficulty,
            min_categories_medium=config.MIN_CATEGORIES_FROM_MEDIUM,
            min_categories_hard=config.MIN_CATEGORIES_FROM_HARD
        )
        
        full_prompts = []
        for keywords in keyword_samples:
            if keywords:
                prompt = f"{config.SYSTEM_PROMPT}\n\nKeywords: {keywords}"
            else:
                prompt = config.SYSTEM_PROMPT
            full_prompts.append(prompt)
        
        responses = self.model.batch_inference_multi_image(
            image_sources=images,
            prompts=full_prompts,
            max_new_tokens=config.MAX_NEW_TOKENS,
            temperature=config.TEMPERATURE
        )
        
        return responses

    def save_batch_results(self, batch_files, responses, output_folder, bucket_name=None, epoch=0):
        """Background task to upload results directly to S3"""
        s3_client = get_optimized_s3_client(bucket_name) if bucket_name else None
        
        for img_path, response in zip(batch_files, responses):
            filename = Path(img_path).stem 
            
            if bucket_name:
                try:
                    s3_key = f"{output_folder}/{filename}_{epoch}_edit.txt".replace("\\", "/")
                    
                    s3_client.put_object(
                        Bucket=bucket_name,
                        Key=s3_key,
                        Body=response.encode('utf-8')
                    )
                except Exception as e:
                    print(f"  Failed to upload {filename} to S3: {e}")

    def get_existing_s3_files(self, bucket_name, prefix):
        """Retrieve a set of existing filenames in the output folder to allow resuming"""
        print(f"Checking for existing files in s3://{bucket_name}/{prefix}...")
        s3 = get_optimized_s3_client(bucket_name)
        paginator = s3.get_paginator('list_objects_v2')
        existing_files = set()
        
        try:
            for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        existing_files.add(Path(obj['Key']).name)
        except Exception as e:
            print(f"Warning: Could not list existing files ({e}). Assuming empty.")
            
        print(f"Found {len(existing_files)} existing output files.")
        return existing_files

    def process_s3_group(self, bucket_name, input_prefix, output_folder, batch_size=28, shard_id=0, total_shards=1, epochs=1):
        """
        Process a specific group of S3 images with sharding support.
        Uses optimized DataLoader and S3 client.
        """
        print(f"\n{'#'*80}")
        print(f"S3 BATCH PROCESSING (Shard {shard_id+1}/{total_shards})")
        print(f"Bucket: {bucket_name}")
        print(f"Prefix: {input_prefix}")
        print(f"Output: {output_folder}")
        print(f"Epochs: {epochs}")
        print(f"{'#'*80}")
        
        # Fetch existing outputs for resume capability
        existing_outputs = self.get_existing_s3_files(bucket_name, output_folder)
        
        # Get all images from S3
        print("Fetching file list from S3...")
        all_files = get_s3_image_files(bucket_name, prefix=input_prefix, extensions=('.png',))
        
        if not all_files:
            print(f"No PNG images found in {bucket_name}/{input_prefix}")
            return

        total_files = len(all_files)
        print(f"Found {total_files} total images.")
        
        # Sharding logic
        base_chunk_size = total_files // total_shards
        start_idx = shard_id * base_chunk_size
        
        if shard_id == total_shards - 1:
            end_idx = total_files
        else:
            end_idx = start_idx + base_chunk_size
        
        if start_idx >= total_files:
            shard_files = []
        else:
            shard_files = all_files[start_idx:end_idx]
        
        print(f"Sharding Strategy: Sequential Contiguous Blocks")
        print(f"Shard {shard_id}: Indices {start_idx} to {end_idx}")
        print(f"Files assigned to this shard: {len(shard_files)}")
        print(f"Batch size: {batch_size}")
        print(f"{'#'*80}\n")
        
        if not shard_files:
            print("No files to process.")
            return

        # Use optimized dataset with worker init for connection pooling
        dataset = S3ImageDatasetOptimized(shard_files, bucket_name=bucket_name)
        loader = DataLoader(
            dataset,
            batch_size=batch_size,
            shuffle=False,
            num_workers=4,
            collate_fn=collate_fn,
            prefetch_factor=2,
            worker_init_fn=worker_init_fn,  # Initialize S3 client per worker
            persistent_workers=True  # Keep workers alive between epochs
        )
        
        num_batches = len(loader)
        total_overall_processed = 0
        pipeline_start_time = time.time()
        
        for epoch in range(epochs):
            print(f"\n{'='*40}")
            print(f"STARTING EPOCH {epoch+1}/{epochs}")
            print(f"{'='*40}")
            
            epoch_start_time = time.time()
            epoch_processed = 0
            
            for i, (batch_images, batch_urls) in enumerate(loader, 1):
                # Resume logic: Filter batch
                images_to_process = []
                urls_to_process = []
                
                for img, url in zip(batch_images, batch_urls):
                    stem = Path(url).stem
                    expected_filename = f"{stem}_{epoch}_edit.txt"
                    if expected_filename not in existing_outputs:
                        images_to_process.append(img)
                        urls_to_process.append(url)
                
                if not images_to_process:
                    print(f"Epoch {epoch+1} | Batch {i}/{num_batches} - All skipped (already exist).")
                    continue
                    
                batch_start = time.time()
                print(f"[Shard {shard_id}] Epoch {epoch+1} | Batch {i}/{num_batches} ({len(images_to_process)}/{len(batch_images)} imgs)...", end="", flush=True)
                
                # GPU Inference
                responses = self.process_batch_multi_image(images_to_process)
                
                # Async Save
                self.save_executor.submit(
                    self.save_batch_results, 
                    list(urls_to_process), 
                    list(responses), 
                    output_folder,
                    bucket_name,
                    epoch
                )
                
                batch_time = time.time() - batch_start
                epoch_processed += len(images_to_process)
                total_overall_processed += len(images_to_process)
                
                # Print timing with images/sec for better monitoring
                imgs_per_sec = len(images_to_process) / batch_time if batch_time > 0 else 0
                print(f" Done ({batch_time:.2f}s, {imgs_per_sec:.1f} img/s)")
            
            epoch_time = time.time() - epoch_start_time
            print(f"\nEpoch {epoch+1} complete: {epoch_processed} images in {epoch_time:.1f}s ({epoch_processed/epoch_time:.1f} img/s)")
            
        # Wait for all saves to finish
        self.save_executor.shutdown(wait=True)
            
        total_time = time.time() - pipeline_start_time
        
        print(f"\n\n{'#'*80}")
        print(f"SHARD {shard_id+1}/{total_shards} COMPLETE")
        print(f"{'#'*80}")
        print(f"Total Images Processed: {total_overall_processed} (over {epochs} epochs)")
        print(f"Total Pipeline Time: {total_time:.2f}s")
        print(f"Average Throughput: {total_overall_processed/total_time:.1f} images/sec")
        print(f"{'#'*80}\n")
        

def main():
    """Main execution function"""
    
    parser = argparse.ArgumentParser(description="Qwen VLM OPTIMIZED Batch Inference")
    parser.add_argument("--difficulty", type=str, choices=['easy', 'medium', 'hard'], default='medium', help="Sampler difficulty")
    parser.add_argument("--bucket", type=str, default=config.S3_BUCKET_NAME, help="S3 Bucket Name")
    parser.add_argument("--batch_size", type=int, default=config.BATCH_SIZE, help="Batch size")
    
    parser.add_argument("--gender", type=str, choices=['male', 'female'], required=True, help="Process 'male' or 'female' partition")
    parser.add_argument("--shard_id", type=int, default=0, help="Shard index (0-indexed)")
    parser.add_argument("--total_shards", type=int, default=1, help="Total number of parallel shards")
    parser.add_argument("--epochs", type=int, default=8, help="Number of times to process dataset (Expansion factor)")
    
    # New optimization flags
    parser.add_argument("--no-flash-attention", action="store_true", help="Disable Flash Attention 2")
    parser.add_argument("--use-compile", action="store_true", help="Enable torch.compile() (slower first run)")

    args = parser.parse_args()
    
    # Initialize optimized processor
    processor = QwenBatchProcessorOptimized(
        difficulty=args.difficulty,
        use_flash_attention=not args.no_flash_attention,
        use_compile=args.use_compile
    )
    
    # Define paths
    if args.gender == 'male':
        input_prefix = "dataset/male/male/images/"
        output_folder = f"dataset/edit_prompts/{args.difficulty}/edit_male/partition_{args.shard_id}"
    else:
        input_prefix = "dataset/female/female/images/"
        output_folder = f"dataset/edit_prompts/{args.difficulty}/edit_female/partition_{args.shard_id}"
    
    # Run optimized processing
    processor.process_s3_group(
        bucket_name=args.bucket,
        input_prefix=input_prefix,
        output_folder=output_folder,
        batch_size=args.batch_size,
        shard_id=args.shard_id,
        total_shards=args.total_shards,
        epochs=args.epochs
    )
    
    print("\n✓ Processing complete!")


if __name__ == "__main__":
    main()
