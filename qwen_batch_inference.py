import os
import time
import torch
import argparse
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
        
        # Create output folder
        print("\n[2/3] Setting up output folder...")
        create_output_folder(config.OUTPUT_FOLDER)
        print(f"✓ Output folder: {config.OUTPUT_FOLDER}")
        
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

    def process_images_from_s3(self, bucket_name, batch_size=28):
        """
        Process images from S3 bucket folders 'males' and 'females'
        
        Args:
            bucket_name: S3 Bucket name
            batch_size: Batch size (default 28)
        """
        print(f"\n{'#'*80}")
        print(f"S3 BATCH PROCESSING (Bucket: {bucket_name})")
        print(f"{'#'*80}")
        
        # Get all images from S3
        print("Fetching file list from S3...")
        # Only get pngs as requested
        s3_files = get_s3_image_files(bucket_name, folders=['males', 'females'], extensions=('.png',))
        
        if not s3_files:
            print(f"No PNG images found in {bucket_name}/males or {bucket_name}/females")
            return

        print(f"Found {len(s3_files)} images total.")
        print(f"Batch size: {batch_size}")
        print(f"{'#'*80}\n")
        
        total_processed = 0
        total_start_time = time.time()
        
        # Process in batches
        num_batches = (len(s3_files) + batch_size - 1) // batch_size
        
        for i in range(0, len(s3_files), batch_size):
            batch_files = s3_files[i:i+batch_size]
            batch_idx = (i // batch_size) + 1
            
            print(f"\n{'='*80}")
            print(f"BATCH {batch_idx}/{num_batches} ({len(batch_files)} images)")
            print(f"{'='*80}")
            
            # Process this batch
            responses, batch_time = self.process_batch_multi_image(batch_files)
            
            # Save results individually as requested
            print(f"\n[3/3] Saving individual results...")
            for img_path, response in zip(batch_files, responses):
                # Parse filename from s3 path: s3://bucket/folder/1.png -> 1
                filename = Path(img_path).stem # "1"
                
                # Determine subfolder for output based on source folder (males/females)
                # s3://bucket/males/1.png
                parts = img_path.replace("s3://", "").split("/")
                if len(parts) > 2:
                     subfolder = parts[1] # males or females
                     output_dir = os.path.join(config.OUTPUT_FOLDER, subfolder)
                     create_output_folder(output_dir)
                else:
                     output_dir = config.OUTPUT_FOLDER
                
                # Format: 1_edit.txt
                save_edit_prompt(response, output_dir, f"{filename}_edit")
            
            total_processed += len(batch_files)
            
        total_processing_time = time.time() - total_start_time
        
        print(f"\n\n{'#'*80}")
        print("FINAL SUMMARY")
        print(f"{'#'*80}")
        print(f"Total images processed: {total_processed}")
        print(f"Total time: {total_processing_time:.2f}s")
        print(f"{'#'*80}\n")
        

def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description="Qwen VLM Batch Inference")
    parser.add_argument("--difficulty", type=str, choices=['easy', 'medium', 'hard'], default='medium', help="Sampler difficulty")
    parser.add_argument("--bucket", type=str, default="vton-pe", help="S3 Bucket Name")
    parser.add_argument("--batch_size", type=int, default=28, help="Batch size")
    parser.add_argument("--local", action="store_true", help="Use local images instead of S3")
    
    args = parser.parse_args()
    
    # Initialize processor (loads model once)
    processor = QwenBatchProcessor(difficulty=args.difficulty)
    
    if args.local:
        # Legacy local processing (cyclic)
        processor.process_all_images_cyclic(
            total_prompts=config.TOTAL_PROMPTS,
            batch_size=args.batch_size
        )
    else:
        # S3 processing
        processor.process_images_from_s3(
            bucket_name=args.bucket,
            batch_size=args.batch_size
        )
    
    print("\n✓ All processing complete!")
    print(f"Check outputs in: {config.OUTPUT_FOLDER}")


if __name__ == "__main__":
    main()