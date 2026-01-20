import os
import time
import torch
import argparse
import math
from pathlib import Path
from itertools import cycle

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


class QwenBatchProcessor:
    def __init__(self, difficulty='medium'):
        """Initialize the batch processor with model and configuration"""
        print("="*80)
        print("Qwen VLM TRUE BATCH Inference Pipeline")
        print("="*80)
        
        # Load model once
        print("\n[1/3] Loading model...")
        self.model = QwenVLBatchInference(
            model_name=config.MODEL_NAME,
            device=config.DEVICE
        )
        
        self.difficulty = difficulty
        
        print("\n[3/3] Initialization complete!")
        print(f"✓ Keyword sampling difficulty: {difficulty.upper()}")
        print("="*80)
    
    def process_batch_multi_image(self, image_paths):
        """
        Process a batch with DIFFERENT images (one prompt per image)
        
        Args:
            image_paths: List of paths to different images for this batch
            
        Returns:
            List of responses (one per image)
        """
        actual_batch_size = len(image_paths)
        
        print(f"\n[1/3] Generating {actual_batch_size} unique prompts with sampled keywords ({self.difficulty})...")
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
        
        print(f"✓ Generated {len(full_prompts)} prompts")
        
        # Run BATCH inference with DIFFERENT images
        print(f"\n[2/3] Running BATCH inference on {config.DEVICE}...")
        print(f"Processing {actual_batch_size} different images simultaneously...")
        
        batch_start_time = time.time()
        
        # Batch process different images with different prompts
        responses = self.model.batch_inference_multi_image(
            image_sources=image_paths,
            prompts=full_prompts,
            max_new_tokens=config.MAX_NEW_TOKENS,
            temperature=config.TEMPERATURE
        )
        
        total_time = time.time() - batch_start_time
        avg_time_per_prompt = total_time / actual_batch_size
        
        print(f"✓ Batch processing complete!")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Avg per image: {avg_time_per_prompt:.3f}s")
        
        return responses, total_time

    def process_s3_group(self, bucket_name, input_prefix, output_folder, batch_size=28, shard_id=0, total_shards=1):
        """
        Process a specific group of S3 images (defined by prefix) with sharding support.
        
        Args:
            bucket_name: S3 Bucket name
            input_prefix: S3 Prefix for input images
            output_folder: Local folder pattern to save outputs (mirrored from S3 logic)
            batch_size: Batch size
            shard_id: Index of this shard (0 to total_shards-1)
            total_shards: Total number of parallel shards
        """
        print(f"\n{'#'*80}")
        print(f"S3 BATCH PROCESSING (Shard {shard_id+1}/{total_shards})")
        print(f"Bucket: {bucket_name}")
        print(f"Prefix: {input_prefix}")
        print(f"Output: {output_folder}")
        print(f"{'#'*80}")
        
        # Get all images from S3
        print("Fetching file list from S3...")
        # Only get pngs as requested
        all_files = get_s3_image_files(bucket_name, prefix=input_prefix, extensions=('.png',))
        
        if not all_files:
            print(f"No PNG images found in {bucket_name}/{input_prefix}")
            return

        total_files = len(all_files)
        print(f"Found {total_files} total images.")
        
        # --- Apply Sharding Logic ---
        # Select every Nth file starting from shard_id
        # e.g., Shard 0 of 2: 0, 2, 4... | Shard 1 of 2: 1, 3, 5...
        shard_files = all_files[shard_id::total_shards]
        
        print(f"Files assigned to this shard: {len(shard_files)}")
        print(f"Batch size: {batch_size}")
        print(f"{'#'*80}\n")
        
        create_output_folder(output_folder)
        
        total_processed = 0
        total_start_time = time.time()
        
        # Process in batches
        num_batches = (len(shard_files) + batch_size - 1) // batch_size
        
        for i in range(0, len(shard_files), batch_size):
            batch_files = shard_files[i:i+batch_size]
            batch_idx = (i // batch_size) + 1
            
            print(f"\n{'='*80}")
            print(f"BATCH {batch_idx}/{num_batches} ({len(batch_files)} images)")
            print(f"{'='*80}")
            
            # Process this batch
            responses, batch_time = self.process_batch_multi_image(batch_files)
            
            # Save results strictly to the designated output folder
            print(f"\n[3/3] Saving individual results to {output_folder}...")
            for img_path, response in zip(batch_files, responses):
                # Parse filename from s3 path: s3://bucket/.../1.png -> 1
                filename = Path(img_path).stem # "1"
                
                # Format: 1_edit.txt
                save_edit_prompt(response, output_folder, f"{filename}_edit")
            
            total_processed += len(batch_files)
            
        total_processing_time = time.time() - total_start_time
        
        print(f"\n\n{'#'*80}")
        print(f"SHARD {shard_id+1}/{total_shards} COMPLETE")
        print(f"{'#'*80}")
        print(f"Images processed: {total_processed}")
        print(f"Total time: {total_processing_time:.2f}s")
        print(f"{'#'*80}\n")
        

def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description="Qwen VLM Batch Inference")
    parser.add_argument("--difficulty", type=str, choices=['easy', 'medium', 'hard'], default='medium', help="Sampler difficulty")
    parser.add_argument("--bucket", type=str, default="vton-pe", help="S3 Bucket Name")
    parser.add_argument("--batch_size", type=int, default=28, help="Batch size")
    
    # New arguments for parallel execution
    parser.add_argument("--gender", type=str, choices=['male', 'female'], required=True, help="Process 'male' or 'female' partition")
    parser.add_argument("--shard_id", type=int, default=0, help="Shard index (0-indexed)")
    parser.add_argument("--total_shards", type=int, default=1, help="Total number of parallel shards")
    
    args = parser.parse_args()
    
    # Initialize processor
    processor = QwenBatchProcessor(difficulty=args.difficulty)
    
    # Define Strict Paths
    if args.gender == 'male':
        input_prefix = "p1-to-ep1/dataset/male/male/images/"
        # Output: p1-to-ep1/dataset/edit_prompts/edit_male/
        # We map this to a local path to simulate the structure or save directly
        # The prompt implies saving LOCALLY under this structure? Or S3?
        # Typically "stored in individual .txt files" implies local generation first.
        # Assuming local structure mirroring.
        output_folder = "p1-to-ep1/dataset/edit_prompts/edit_male"
    else:
        input_prefix = "p1-to-ep1/dataset/female/female/images/"
        output_folder = "p1-to-ep1/dataset/edit_prompts/edit_female"
    
    # Run Sharded Processing
    processor.process_s3_group(
        bucket_name=args.bucket,
        input_prefix=input_prefix,
        output_folder=output_folder,
        batch_size=args.batch_size,
        shard_id=args.shard_id,
        total_shards=args.total_shards
    )
    
    print("\n✓ Processing complete!")


if __name__ == "__main__":
    main()