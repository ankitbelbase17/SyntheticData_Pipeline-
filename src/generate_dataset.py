import sys
import os
import boto3
from PIL import Image
import io

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import config
from src.core.models import FluxGenerator
from src.data.dataloader import get_dataloader
from src.utils.helpers import load_image_from_url

def generate_and_upload():
    print("="*60)
    print("MASS GENERATION SCRIPT")
    print("="*60)
    
    # Configuration
    TARGET_BUCKET = "test"
    TARGET_PREFIX = "_search"
    CATEGORIES = ["easy", "medium", "hard"]
    GENDERS = ["male", "female"]
    LIMIT_PER_CATEGORY = 100
    
    # Initialize S3 Client
    s3_client = boto3.client(
        's3',
        aws_access_key_id=config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
        region_name=config.AWS_REGION_NAME
    )
    
    # Ensure bucket exists
    try:
        s3_client.head_bucket(Bucket=TARGET_BUCKET)
        print(f"Bucket '{TARGET_BUCKET}' exists.")
    except Exception as e:
        print(f"Bucket '{TARGET_BUCKET}' not found or inaccessible. Attempting to create...")
        try:
            if config.AWS_REGION_NAME == 'us-east-1':
                s3_client.create_bucket(Bucket=TARGET_BUCKET)
            else:
                s3_client.create_bucket(
                    Bucket=TARGET_BUCKET,
                    CreateBucketConfiguration={'LocationConstraint': config.AWS_REGION_NAME}
                )
            print(f"Created bucket '{TARGET_BUCKET}'.")
        except Exception as create_error:
            print(f"Failed to create bucket: {create_error}")
            print("Trying to continue (maybe it exists but permissions issue)...")

    # Initialize Model
    print("Initializing FluxGenerator...")
    flux_gen = FluxGenerator(model_id="9b", device="cuda")
    
    # Prompt
    prompt = "Make the person in the first image wear the cloth from the second image. High quality, photorealistic."

    for diff in CATEGORIES:
        for gen in GENDERS:
            print(f"\nProcessing: {diff} - {gen}")
            
            try:
                loader, _ = get_dataloader(diff, gen)
            except Exception as e:
                print(f"Failed to load dataloader for {diff}/{gen}: {e}")
                continue
                
            count = 0
            
            for i, batch in enumerate(loader):
                if count >= LIMIT_PER_CATEGORY:
                    break
                
                try:
                    # Dataloader batch size is 1
                    try:
                        p_url = batch['initialImage'][0]
                        c_url = batch['clothImage'][0]
                        sample_id = batch['id'][0] # Integer ID from loader
                        # Use initial_person_image_name to get a robust ID if possible
                        # The dataloader item has 'initial_person_image_name'. 
                        # Let's use the filename stem as ID for saving.
                        orig_name = batch['initial_person_image_name'][0]
                        # Extract base name without extension
                        base_name = os.path.splitext(os.path.basename(orig_name))[0]
                        
                    except KeyError as e:
                        print(f"  Missing key in batch: {e}")
                        continue
                        
                    print(f"  Generating {count+1}/{LIMIT_PER_CATEGORY}: {base_name}...")
                    
                    # Load Images
                    p_img = load_image_from_url(p_url)
                    c_img = load_image_from_url(c_url)
                    
                    # Generate
                    # Using steps=4 as per current config/defaults
                    try_on_img = flux_gen.generate(p_img, c_img, prompt, steps=4)
                    
                    # Upload to S3
                    # Naming convention: {diff}/{gen}/{base_name}_tryon.png
                    s3_key = f"{TARGET_PREFIX}/{diff}/{gen}/{base_name}_tryon.png"
                    
                    # Save to memory buffer
                    img_byte_arr = io.BytesIO()
                    try_on_img.save(img_byte_arr, format='PNG')
                    img_byte_arr.seek(0)
                    
                    print(f"    Uploading to s3://{TARGET_BUCKET}/{s3_key} ...")
                    s3_client.put_object(
                        Bucket=TARGET_BUCKET,
                        Key=s3_key,
                        Body=img_byte_arr,
                        ContentType='image/png'
                    )
                    
                    count += 1
                    
                except Exception as e:
                    print(f"  Error processing sample {i}: {e}")
                    continue

    print("\nGeneration Complete.")

if __name__ == "__main__":
    generate_and_upload()
