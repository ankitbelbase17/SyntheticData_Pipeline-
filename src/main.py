import os
import sys
import time

# Add parent directory to path so we can import from src
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.models import FluxGenerator, QwenVLM
from core.feedback_loop import FeedbackSystem
from data.dataloader import get_dataloader
from utils.helpers import ensure_directories_exist, load_image_from_url
from config import config
from PIL import Image, ImageDraw

def create_dummy_data():
    """
    Creates dummy person and cloth images for testing if they don't exist.
    """
    p_dir = config.PERSON_DIR
    c_dir = config.CLOTH_DIR
    
    os.makedirs(p_dir, exist_ok=True)
    os.makedirs(c_dir, exist_ok=True)
    
    if not os.listdir(p_dir):
        print("Creating dummy person image...")
        img = Image.new('RGB', (512, 512), color='blue')
        d = ImageDraw.Draw(img)
        d.text((10,10), "Person", fill=(255,255,0))
        img.save(os.path.join(p_dir, "person_01.jpg"))

    if not os.listdir(c_dir):
        print("Creating dummy cloth image...")
        img = Image.new('RGB', (512, 512), color='red')
        d = ImageDraw.Draw(img)
        d.text((10,10), "Cloth", fill=(255,255,0))
        img.save(os.path.join(c_dir, "cloth_01.jpg"))

def main():
    ensure_directories_exist(config.BASE_DIR)
    create_dummy_data() # For testing purposes

    # Initialize models
    flux_gen = FluxGenerator(model_id=config.FLUX_MODEL_ID, device=config.DEVICE)
    qwen_vlm = QwenVLM(model_id=config.QWEN_MODEL_ID, device=config.DEVICE)
    
    # Initialize Feedback System
    feedback_system = FeedbackSystem(flux_gen, qwen_vlm, config)
    
    # Load Data
    # Use S3 dataloader
    data_loader, dataset = get_dataloader(config.DIFFICULTY, config.GENDER)
    
    print(f"Loaded {len(dataset)} samples from S3.")
    
    total_latency = 0
    count = 0
    MAX_SAMPLES = 100
    
    for batch in data_loader:
        if count >= MAX_SAMPLES:
            print(f"Reached maximum of {MAX_SAMPLES} samples.")
            break

        # Batch size is 1, extract items
        p_name = batch['initial_person_image_name'][0]
        c_name = batch['cloth_image_name'][0]
        p_url = batch['initialImage'][0]
        c_url = batch['clothImage'][0]
        
        print(f"Processing sample {count + 1}/{MAX_SAMPLES}: {p_name} + {c_name}")
        
        # Download images (Latency excluded)
        try:
            p_img = load_image_from_url(p_url)
            c_img = load_image_from_url(c_url)
        except Exception as e:
            print(f"Error downloading images: {e}")
            continue
            
        # Default prompt
        prompt = "A photorealistic image of a person wearing the provided cloth, high quality, 8k"
        
        # Start timing (excluding dataloading/downloading)
        start_time = time.time()
        
        feedback_system.run(p_name, c_name, p_img, c_img, prompt)
        
        end_time = time.time()
        latency = end_time - start_time
        total_latency += latency
        count += 1
        
        print(f"Sample {count} latency: {latency:.2f} seconds")

    if count > 0:
        avg_latency = total_latency / count
        print(f"\nProcessing complete.")
        print(f"Total samples processed: {count}")
        print(f"Total time (excluding dataloading): {total_latency:.2f} seconds")
        print(f"Average latency per image: {avg_latency:.2f} seconds")
    else:
        print("\nNo samples were processed.")

if __name__ == "__main__":
    main()
