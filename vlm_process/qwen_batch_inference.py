import os
import time
import torch
import argparse
import math
from pathlib import Path
from itertools import cycle
from concurrent.futures import ThreadPoolExecutor
from torch.utils.data import DataLoader

# Import configuration and utilities
import config
from utils import (
    sample_keywords,
    create_output_folder,
    save_prompts,
    save_edit_prompt,
    get_image_files,
    get_s3_image_files
)
from qwen_inference import QwenVLBatchInference
from s3_dataloader import S3ImageDataset

def collate_fn(batch):
    """
    Custom collate function to handle PIL images and URLs
    Returns: (list_of_images, list_of_urls)
    """
    images = [item[0] for item in batch]
    urls = [item[1] for item in batch]
    return images, urls

class QwenBatchProcessor:
    def __init__(self, difficulty='medium'):
        """Initialize the batch processor with model and configuration"""
        print("="*80)
        print("Qwen VLM TRUE BATCH Inference Pipeline (Async/Parallel)")
        print("="*80)
        
        # Load model once
        print("\n[1/3] Loading model...")
        self.model = QwenVLBatchInference(
            model_name=config.MODEL_NAME,
            device=config.DEVICE
        )
        
        self.difficulty = difficulty
        # Thread pool for async saving
        self.save_executor = ThreadPoolExecutor(max_workers=4)
        
        print("\n[3/3] Initialization complete!")
        print(f"✓ Keyword sampling difficulty: {difficulty.upper()}")
        print("="*80)
    
    def process_batch_multi_image(self, images):
        """
        Process a batch with DIFFERENT images (one prompt per image)
        
        Args:
            images: List of PIL Image objects
            
        Returns:
            List of responses (one per image)
        """
        actual_batch_size = len(images)
        
        # print(f"Generating prompts for {actual_batch_size} images...")
        keyword_samples = sample_keywords(
            actual_batch_size,
            difficulty=self.difficulty,
            min_categories_medium=config.MIN_CATEGORIES_FROM_MEDIUM,
            min_categories_hard=config.MIN_CATEGORIES_FROM_HARD
        )
        
        # Create full prompts with system prompt prefix
        full_prompts = []
        for keywords in keyword_samples:
            if keywords:
                prompt = f"{config.SYSTEM_PROMPT}\n\nKeywords: {keywords}"
            else:
                prompt = config.SYSTEM_PROMPT
            full_prompts.append(prompt)
        
        # Run BATCH inference with PRE-LOADED images
        responses = self.model.batch_inference_multi_image(
            image_sources=images,
            prompts=full_prompts,
            max_new_tokens=config.MAX_NEW_TOKENS,
            temperature=config.TEMPERATURE
        )
        
        return responses

    def save_batch_results(self, batch_files, responses, output_folder, bucket_name=None, epoch=0):
        """Background task to upload results directly to S3"""
        # Create S3 client inside thread if needed, or use a new one per thread
        s3_client = boto3.client('s3') if bucket_name else None
        
        for img_path, response in zip(batch_files, responses):
            # Parse filename from s3 path: s3://bucket/.../1.png -> 1
            filename = Path(img_path).stem 
            
            if bucket_name:
                try:
                    # S3 Key: output_folder/filename_epoch_edit.txt
                    # Ensure we form the key correctly
                    s3_key = f"{output_folder}/{filename}_{epoch}_edit.txt".replace("\\", "/")
                    
                    # Upload directly from memory
                    s3_client.put_object(
                        Bucket=bucket_name,
                        Key=s3_key,
                        Body=response.encode('utf-8')
                    )
                    # print(f"  Uploaded to s3://{bucket_name}/{s3_key}")
                except Exception as e:
                    print(f"  Failed to upload {filename} to S3: {e}")
            else:
                 # Fallback: if no bucket, we print/skip since local save is disabled
                 pass

    def get_existing_s3_files(self, bucket_name, prefix):
        """Retrieve a set of existing filenames in the output folder to allow resuming"""
        print(f"Checking for existing files in s3://{bucket_name}/{prefix}...")
        s3 = boto3.client('s3')
        paginator = s3.get_paginator('list_objects_v2')
        existing_files = set()
        
        try:
            for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        # Store just the filename "1_0_edit.txt"
                        existing_files.add(Path(obj['Key']).name)
        except Exception as e:
            print(f"Warning: Could not list existing files ({e}). Assuming empty.")
            
        print(f"Found {len(existing_files)} existing output files.")
        return existing_files

    def process_s3_group(self, bucket_name, input_prefix, output_folder, batch_size=28, shard_id=0, total_shards=1, epochs=1):
        """
        Process a specific group of S3 images (defined by prefix) with sharding support.
        Uses DataLoader for async prefetching and ThreadPool for async saving/uploading.
        Loops for `epochs` times to generate multiple variants per image.
        Checks for existing files to resume progress.
        """
        print(f"\n{'#'*80}")
        print(f"S3 BATCH PROCESSING (Shard {shard_id+1}/{total_shards})")
        print(f"Bucket: {bucket_name}")
        print(f"Prefix: {input_prefix}")
        print(f"Output: {output_folder}")
        print(f"Epochs: {epochs}")
        print(f"{'#'*80}")
        
        # 1. Fetch existing outputs for resume capability
        existing_outputs = self.get_existing_s3_files(bucket_name, output_folder)
        
        # Ensure 'folder' exists in S3 (S3 is flat, but this checks connectivity/permissions)
        try:
             # Check if we can write to this prefix
             # We don't need to explicitly "create" folders in S3, but we can verify access.
             pass
        except Exception:
             pass
        
        # Get all images from S3 (Listing is fast enough to do synchronously)
        print("Fetching file list from S3...")
        all_files = get_s3_image_files(bucket_name, prefix=input_prefix, extensions=('.png',))
        
        if not all_files:
            print(f"No PNG images found in {bucket_name}/{input_prefix}")
            return

        total_files = len(all_files)
        print(f"Found {total_files} total images.")
        
        # --- Apply Sharding Logic (Sequential Contiguous Blocks) ---
        # "Last shard contains remaining ones" logic:
        # Use floor division for the base size. The last shard gets base + remainder.
        if total_shards > total_files:
             # Edge case: More shards than files. 
             # Distribute 1 file per shard until run out.
             # This is a bit complex to fit into "last shard gets remainder" strictly, 
             # but let's stick to the requested logic:
             # Floor = 0. Shard 0..N-2 gets 0. Shard N-1 gets All. 
             # This might not be distinct enough, but statistically unlikely for this dataset (28k images).
             # Better approach for stability:
             base_chunk_size = total_files // total_shards
        else:
             base_chunk_size = total_files // total_shards
             
        start_idx = shard_id * base_chunk_size
        
        if shard_id == total_shards - 1:
            # Last shard guarantees picking up everything until the end
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
        
        # create_output_folder(output_folder) # Local folder not needed for S3 direct upload
        
        # --- Setup DataLoader for Async Prefetching ---
        if not shard_files:
            print("No files to process.")
            return

        dataset = S3ImageDataset(shard_files)
        loader = DataLoader(
            dataset,
            batch_size=batch_size,
            shuffle=False,
            num_workers=4,        # Parallel download workers
            collate_fn=collate_fn,
            prefetch_factor=2     # Prefetch next batches
        )
        
        num_batches = len(loader)
        total_overall_processed = 0
        pipeline_start_time = time.time()
        
        for epoch in range(epochs):
            print(f"\n{'='*40}")
            print(f"STARTING EPOCH {epoch+1}/{epochs}")
            print(f"{'='*40}")
            
            for i, (batch_images, batch_urls) in enumerate(loader, 1):
                # --- Resume Logic: Filter batch ---
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
                print(f"Epoch {epoch+1} | Batch {i}/{num_batches} ({len(images_to_process)}/{len(batch_images)} imgs)...", end="", flush=True)
                
                # --- GPU Inference (Synchronous) ---
                # Random sampling happens inside here for each call, 
                # ensuring unique keywords for each epoch/image combo
                responses = self.process_batch_multi_image(images_to_process)
                
                # --- Async Save ---
                self.save_executor.submit(
                    self.save_batch_results, 
                    list(urls_to_process), 
                    list(responses), 
                    output_folder,
                    bucket_name,
                    epoch # Pass epoch index for naming
                )
                
                batch_time = time.time() - batch_start
                total_overall_processed += len(images_to_process)
                print(f" Done ({batch_time:.2f}s)")
            
        # Wait for all saves to finish
        self.save_executor.shutdown(wait=True)
            
        total_time = time.time() - pipeline_start_time
        
        print(f"\n\n{'#'*80}")
        print(f"SHARD {shard_id+1}/{total_shards} COMPLETE")
        print(f"{'#'*80}")
        print(f"Total Images Processed: {total_overall_processed} (over {epochs} epochs)")
        print(f"Total Pipeline Time: {total_time:.2f}s")
        print(f"{'#'*80}\n")
        

def main():
    """Main execution function"""
    
    # Apply AWS Credentials from config if set and not default
    if config.AWS_ACCESS_KEY_ID and "your_access_key" not in config.AWS_ACCESS_KEY_ID:
        os.environ["AWS_ACCESS_KEY_ID"] = config.AWS_ACCESS_KEY_ID
    if config.AWS_SECRET_ACCESS_KEY and "your_secret_key" not in config.AWS_SECRET_ACCESS_KEY:
        os.environ["AWS_SECRET_ACCESS_KEY"] = config.AWS_SECRET_ACCESS_KEY
    if config.AWS_REGION_NAME:
        os.environ["AWS_REGION_NAME"] = config.AWS_REGION_NAME

    parser = argparse.ArgumentParser(description="Qwen VLM Batch Inference")
    parser.add_argument("--difficulty", type=str, choices=['easy', 'medium', 'hard'], default='medium', help="Sampler difficulty")
    parser.add_argument("--bucket", type=str, default=config.S3_BUCKET_NAME, help="S3 Bucket Name")
    parser.add_argument("--batch_size", type=int, default=config.BATCH_SIZE, help="Batch size")
    
    # New arguments for parallel execution
    parser.add_argument("--gender", type=str, choices=['male', 'female'], required=True, help="Process 'male' or 'female' partition")
    parser.add_argument("--shard_id", type=int, default=0, help="Shard index (0-indexed)")
    parser.add_argument("--total_shards", type=int, default=1, help="Total number of parallel shards")
    parser.add_argument("--epochs", type=int, default=8, help="Number of times to process dataset (Expansion factor)")

    args = parser.parse_args()
    
    # Initialize processor
    processor = QwenBatchProcessor(difficulty=args.difficulty)
    
    # Define Strict Paths
    if args.gender == 'male':
        input_prefix = "p1-to-ep1/dataset/male/male/images/"
        output_folder = f"p1-to-ep1/dataset/edit_prompts/{args.difficulty}/edit_male/partition_{args.shard_id}"
    else:
        input_prefix = "p1-to-ep1/dataset/female/female/images/"
        output_folder = f"p1-to-ep1/dataset/edit_prompts/{args.difficulty}/edit_female/partition_{args.shard_id}"
    
    # Run Sharded Processing
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