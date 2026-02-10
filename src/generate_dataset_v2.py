import sys
import os
import boto3
from PIL import Image
import io
import time

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import config
from src.core.models import FluxGenerator, QwenVLM
from src.core.feedback_loop import FeedbackSystem
from src.data.dataloader import get_dataloader
from src.utils.helpers import load_image_from_url

def generate_dataset_with_feedback():
    print("="*80)
    print("DATASET GENERATION WITH FULL FEEDBACK LOOP")
    print("="*80)
    
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
    except Exception:
        try:
            if config.AWS_REGION_NAME == 'us-east-1':
                s3_client.create_bucket(Bucket=TARGET_BUCKET)
            else:
                s3_client.create_bucket(
                    Bucket=TARGET_BUCKET,
                    CreateBucketConfiguration={'LocationConstraint': config.AWS_REGION_NAME}
                )
            print(f"Created bucket '{TARGET_BUCKET}'.")
        except Exception as e:
            print(f"Bucket issue: {e}")

    # Initialize Models
    print("Initializing Models (Flux + QwenVLM)...")
    flux_gen = FluxGenerator(model_id="9b", device="cuda")
    vlm_eval = QwenVLM(model_id=config.QWEN_MODEL_ID, device="cuda")
    
    # Initialize Feedback System
    feedback_system = FeedbackSystem(flux_gen, vlm_eval, config)
    
    # Default Prompt
    default_prompt = "Make the person in the first image wear the cloth from the second image. High quality, photorealistic, no unintended changes."

    def upload_image_to_s3(img_obj_or_path, s3_key):
        """Uploads PIL Image or file path to S3"""
        try:
            if isinstance(img_obj_or_path, str):
                # File path
                with open(img_obj_or_path, "rb") as f:
                    s3_client.upload_fileobj(f, TARGET_BUCKET, s3_key)
            else:
                # PIL Image
                buf = io.BytesIO()
                img_obj_or_path.save(buf, format='PNG')
                buf.seek(0)
                s3_client.put_object(Bucket=TARGET_BUCKET, Key=s3_key, Body=buf, ContentType='image/png')
            print(f"    Uploaded: s3://{TARGET_BUCKET}/{s3_key}")
            return True
        except Exception as e:
            print(f"    Upload Failed: {e}")
            return False

    for diff in CATEGORIES:
        for gen in GENDERS:
            cat_start = time.time()
            print(f"\nProcessing Category: {diff} - {gen}")
            
            try:
                loader, _ = get_dataloader(diff, gen)
            except Exception as e:
                print(f"Failed to load dataloader: {e}")
                continue
                
            count = 0
            
            for i, batch in enumerate(loader):
                if count >= LIMIT_PER_CATEGORY:
                    break
                
                try:
                    # Parse Batch
                    p_url = batch['initialImage'][0]
                    c_url = batch['clothImage'][0]
                    # Robust ID from filename
                    orig_name = batch['initial_person_image_name'][0]
                    base_name = os.path.splitext(os.path.basename(orig_name))[0]
                    
                    # Also need cloth base name for structured input saving
                    cloth_name_orig = batch['cloth_image_name'][0]
                    cloth_base = os.path.basename(cloth_name_orig)
                    person_base = os.path.basename(orig_name)
                    
                    print(f"\nSample {count+1}/{LIMIT_PER_CATEGORY}: {base_name}")
                    
                    # Load Images
                    p_img = load_image_from_url(p_url)
                    c_img = load_image_from_url(c_url)
                    
                    if not p_img or not c_img:
                        print("    Skipping - failed to load images")
                        continue

                    # 1. Upload Inputs to S3 (Mirroring structure)
                    # Structure: {prefix}/{diff}/{gen}/input/person/...
                    input_p_key = f"{TARGET_PREFIX}/{diff}/{gen}/input/person/{person_base}"
                    input_c_key = f"{TARGET_PREFIX}/{diff}/{gen}/input/cloth/{cloth_base}"
                    
                    upload_image_to_s3(p_img, input_p_key)
                    upload_image_to_s3(c_img, input_c_key)
                    
                    # 2. Run Feedback Loop
                    # This saves local files in config.OUTPUT_DIR structure
                    result_feedback = feedback_system.run(
                        person_name=base_name,
                        cloth_name=cloth_base,
                        person_img=p_img,
                        cloth_img=c_img,
                        initial_prompt=default_prompt,
                        sample_id=base_name # Pass base_name as ID for consistent naming
                    )
                    
                    if not result_feedback:
                        print("    Feedback loop failed to return result.")
                        continue
                        
                    # 3. Upload Output to S3
                    # Map local result to S3 structure
                    # Result has: 'status', 'iteration', 'local_path', 'filename'
                    status = result_feedback.get('status')
                    iteration = result_feedback.get('iteration')
                    local_path = result_feedback.get('local_path')
                    filename = result_feedback.get('filename')
                    
                    if status == "SUCCESS":
                        s3_out_dir = "correct_try_on"
                    else:
                        s3_out_dir = f"incorrect_try_on_{iteration}"
                    
                    # S3 Output Key: {prefix}/{diff}/{gen}/output/{correct/incorrect}/{filename}
                    s3_out_key = f"{TARGET_PREFIX}/{diff}/{gen}/output/{s3_out_dir}/{filename}"
                    
                    if local_path and os.path.exists(local_path):
                        upload_image_to_s3(local_path, s3_out_key)
                    else:
                        # Fallback: upload image object locally
                        if result_feedback.get('image'):
                            upload_image_to_s3(result_feedback['image'], s3_out_key)
                    
                    count += 1
                    
                except Exception as e:
                    print(f"  Error processing sample {i}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            print(f"Category {diff}-{gen} complete. Time: {time.time()-cat_start:.2f}s")

    print("\nDataset Generation Complete.")

if __name__ == "__main__":
    generate_dataset_with_feedback()
