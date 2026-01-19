import argparse
import asyncio
import os
from src.parser import parse_prompts
from src.generator import ImageGenerator
from src.s3_uploader import AsyncUploader
from src.config import S3_PREFIX

async def main(model_type="nvfp4"):
    # 1. Setup
    jsonl_files = ["prompts_combined_1.jsonl", "prompts_combined_2.jsonl"] # Ensure these exist or path is correct
    
    # Initialize Generator (Sync, Heavy Resource)
    generator = ImageGenerator(model_type=model_type)
    generator.load_model()
    
    # Initialize Uploader
    uploader = AsyncUploader()
    
    upload_tasks = []
    
    # 2. Processing Loop
    print("Starting generation loop...")
    
    # We use a set to keep track of active tasks to avoid potential memory issues if queue grows too large,
    # though with image gen being slow, upload should keep up.
    
    for prompt_data in parse_prompts(jsonl_files):
        prompt_number = prompt_data.get("prompt_number")
        prompt_text = prompt_data.get("prompt", "")
        dress_name = prompt_data.get("dress_name", "N/A")
        setting = prompt_data.get("setting", "N/A")
        
        print(f"\nGeneratng Prompt {prompt_number}...")
        
        # synchronous generation (blocks the main thread).
        # We run it in a thread to allow the asyncio event loop (S3 uploads) to progress.
        try:
            image = await asyncio.to_thread(generator.generate, prompt_text)
        except Exception as e:
            print(f"Failed to generate for prompt {prompt_number}: {e}")
            continue
            
        # Prepare text content
        text_content = f"""Prompt Number: {prompt_number}
Dress Name: {dress_name}
Setting: {setting}

{prompt_text}"""

        # Determine S3 Path structure: Bucket/S3_PREFIX/prompt_number/
        # Files: prompt_number.png, prompt_number.txt
        s3_key_prefix = f"{S3_PREFIX}/{prompt_number}" # e.g. generated_images/1
        
        # Fire off async upload
        # We create a task and don't await it immediately, so we can start next generation
        task = asyncio.create_task(
            uploader.upload_data(image, text_content, s3_key_prefix, str(prompt_number))
        )
        upload_tasks.append(task)
        
        # Clean up finished tasks to check for errors/free memory references
        # This is a simple way to not let the list grow infinitely if thousands of images
        upload_tasks = [t for t in upload_tasks if not t.done()]
        
    
    # 3. Wait for remaining uploads
    if upload_tasks:
        print(f"\nWaiting for {len(upload_tasks)} pending uploads...")
        await asyncio.gather(*upload_tasks)
    
    print("\nAll done!")

if __name__ == "__main__":
    # Ensure raw files are available or paths are correct relative to where you run this.
    # We assume jsonl files are in the current working directory.
    
    parser = argparse.ArgumentParser(description="Async Image Generation Pipeline")
    parser.add_argument("--model", type=str, default="nvfp4", choices=["nvfp4", "4b", "9b"], help="Model variant to use (nvfp4, 4b, 9b)")
    
    args = parser.parse_args()
    
    asyncio.run(main(model_type=args.model))
