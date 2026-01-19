"""
TRUE Batch Inference Script for Qwen3-VL-4B-Instruct
Processes different images in batches with sampled prompts
"""

import os
import time
import torch
from pathlib import Path
from itertools import cycle

# Import configuration and utilities
import config
from utils import (
    sample_keywords,
    create_output_folder,
    save_prompts,
    get_image_files
)
from qwen_inference import QwenVLBatchInference


class QwenBatchProcessor:
    def __init__(self):
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
        
        print("\n[3/3] Initialization complete!")
        print(f"✓ Keyword sampling: MEDIUM_DICT + HARD_DICT")
        print(f"✓ Min categories (medium): {config.MIN_CATEGORIES_FROM_MEDIUM}")
        print(f"✓ Min categories (hard): {config.MIN_CATEGORIES_FROM_HARD}")
        print("="*80)
    
    def process_batch_multi_image(self, image_paths, batch_size=None):
        """
        Process a batch with DIFFERENT images (one prompt per image)
        
        Args:
            image_paths: List of paths to different images for this batch
            batch_size: Number of images/prompts in this batch
            
        Returns:
            List of responses (one per image)
        """
        actual_batch_size = len(image_paths)
        
        print(f"\n[1/3] Generating {actual_batch_size} unique prompts with sampled keywords...")
        keyword_samples = sample_keywords(
            actual_batch_size,
            config.MIN_CATEGORIES_FROM_MEDIUM,
            config.MIN_CATEGORIES_FROM_HARD
        )
        
        # Create full prompts with system prompt prefix
        full_prompts = []
        for keywords in keyword_samples:
            if keywords:
                prompt = f"{config.SYSTEM_PROMPT}\n\nKeywords: {keywords}"
            else:
                prompt = config.SYSTEM_PROMPT
            full_prompts.append(prompt)
        
        print(f"✓ Generated {len(full_prompts)} prompts with diverse keyword combinations")
        
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
    
    def process_all_images_cyclic(self, total_prompts=None, batch_size=None):
        """
        Process images cyclically until reaching total_prompts.
        Each batch contains different images with sampled prompts.
        
        Args:
            total_prompts: Total number of prompts to generate (cycles through images)
            batch_size: Number of images/prompts per batch
        """
        total_prompts = total_prompts or config.TOTAL_PROMPTS
        batch_size = batch_size or config.BATCH_SIZE
        
        # Get all images
        image_files = get_image_files(config.IMAGE_FOLDER)
        
        if not image_files:
            print(f"No images found in {config.IMAGE_FOLDER}")
            return
        
        print(f"\n{'#'*80}")
        print(f"CYCLIC BATCH PROCESSING")
        print(f"{'#'*80}")
        print(f"Found {len(image_files)} image(s)")
        print(f"Target total prompts: {total_prompts}")
        print(f"Batch size: {batch_size}")
        print(f"Images will cycle: {image_files}")
        print(f"{'#'*80}\n")
        
        # Create cyclic iterator for images
        image_cycle = cycle(image_files)
        
        # Calculate number of batches
        num_batches = (total_prompts + batch_size - 1) // batch_size
        
        all_results = []
        total_start_time = time.time()
        prompts_generated = 0
        
        # Process batches
        for batch_idx in range(num_batches):
            # Calculate batch size for this iteration
            remaining_prompts = total_prompts - prompts_generated
            current_batch_size = min(batch_size, remaining_prompts)
            
            # Get next batch of images (cycling through)
            batch_images = [next(image_cycle) for _ in range(current_batch_size)]
            
            print(f"\n{'='*80}")
            print(f"BATCH {batch_idx + 1}/{num_batches} ({current_batch_size} images)")
            print(f"{'='*80}")
            print(f"Images in this batch:")
            for i, img in enumerate(batch_images, 1):
                print(f"  {i}. {Path(img).name}")
            print(f"{'='*80}\n")
            
            # Process this batch
            responses, batch_time = self.process_batch_multi_image(
                batch_images,
                current_batch_size
            )
            
            # Store results with image associations
            for img_path, response in zip(batch_images, responses):
                all_results.append({
                    'image_path': img_path,
                    'image_name': Path(img_path).stem,
                    'response': response
                })
            
            prompts_generated += current_batch_size
            
            print(f"\n[3/3] Batch {batch_idx + 1} complete!")
            print(f"Progress: {prompts_generated}/{total_prompts} prompts generated")
        
        total_processing_time = time.time() - total_start_time
        
        # Save all results
        print(f"\n{'='*80}")
        print("SAVING RESULTS")
        print(f"{'='*80}")
        
        # Group results by image
        from collections import defaultdict
        results_by_image = defaultdict(list)
        for result in all_results:
            results_by_image[result['image_name']].append(result['response'])
        
        # Save results for each image
        for image_name, responses in results_by_image.items():
            json_path, txt_path = save_prompts(
                responses,
                config.OUTPUT_FOLDER,
                image_name,
                batch_id=f"total_{len(responses)}"
            )
        
        # Also save combined results
        all_responses = [r['response'] for r in all_results]
        json_path, txt_path = save_prompts(
            all_responses,
            config.OUTPUT_FOLDER,
            "all_images_combined",
            batch_id=f"total_{len(all_responses)}"
        )
        
        # Final summary
        print(f"\n\n{'#'*80}")
        print("FINAL SUMMARY")
        print(f"{'#'*80}")
        print(f"Total images in pool: {len(image_files)}")
        print(f"Total prompts generated: {prompts_generated}")
        print(f"Total processing time: {total_processing_time:.2f}s")
        print(f"Average time per prompt: {total_processing_time/prompts_generated:.3f}s")
        print(f"Overall throughput: {prompts_generated/total_processing_time:.2f} prompts/second")
        print(f"\nPrompts per image:")
        for image_name, responses in results_by_image.items():
            print(f"  {image_name}: {len(responses)} prompts")
        print(f"{'#'*80}\n")
        
        return all_results


def main():
    """Main execution function"""
    # Initialize processor (loads model once)
    processor = QwenBatchProcessor()
    
    # Process images cyclically until reaching total prompts
    results = processor.process_all_images_cyclic(
        total_prompts=config.TOTAL_PROMPTS,
        batch_size=config.BATCH_SIZE
    )
    
    print("\n✓ All processing complete!")
    print(f"Check outputs in: {config.OUTPUT_FOLDER}")


if __name__ == "__main__":
    main()