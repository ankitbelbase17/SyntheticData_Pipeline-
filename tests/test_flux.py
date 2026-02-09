import sys
import os
import time
import torch
from PIL import Image

# Add parent directory to path so we can import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.models import FluxGenerator
from src.data.dataloader import get_dataloader
from src.utils.helpers import load_image_from_url

def test_flux_latency_comparison():
    print("="*80)
    print("FLUX GENERATOR LATENCY COMPARISON: SEQUENTIAL vs BATCH")
    print("="*80)
    
    # 1. Initialize Model
    print("Initializing FluxGenerator...")
    t0 = time.time()
    flux_gen = FluxGenerator(model_id="9b", device="cuda")
    print(f"Model Init Time: {time.time() - t0:.2f}s")
    
    # 2. Prepare Data
    loader_single, _ = get_dataloader(difficulty="easy", gender="female")
    sample = next(iter(loader_single))
    p_url = sample['initialImage'][0]
    c_url = sample['clothImage'][0]
    
    try:
        p_img = load_image_from_url(p_url)
        c_img = load_image_from_url(c_url)
        print("Images prepared.")
    except Exception as e:
        print(f"Failed to prepare images: {e}")
        return

    BATCH_SIZE = 28
    prompt = "Make the person in the first image wear the cloth from the second image. High quality."
    
    # Warmup
    print("\nWarming up (1 generation)...")
    _ = flux_gen.generate(p_img, c_img, prompt, steps=4)
    
    # --- TEST A: Sequential Processing ---
    print(f"\n[TEST A] Sequential Processing (Looping {BATCH_SIZE} times)")
    print("Starting sequential loop...")
    t_start_seq = time.time()
    
    for i in range(BATCH_SIZE):
        # Pass single items
        _ = flux_gen.generate(p_img, c_img, prompt, steps=4)
        print(f".", end="", flush=True)
        
    t_end_seq = time.time()
    total_seq_time = t_end_seq - t_start_seq
    avg_seq_time = total_seq_time / BATCH_SIZE
    print(f"\nTotal Sequential Time: {total_seq_time:.4f}s")
    print(f"Average Per-Sample Latency (Sequential): {avg_seq_time:.4f}s")

    # --- TEST B: True Batch Processing ---
    print(f"\n[TEST B] True Batch Processing (Single Batch of {BATCH_SIZE})")
    
    # Prepare lists
    p_imgs_batch = [p_img.copy() for _ in range(BATCH_SIZE)]
    c_imgs_batch = [c_img.copy() for _ in range(BATCH_SIZE)]
    prompts_batch = [prompt] * BATCH_SIZE
    
    print("Starting batch generation...")
    t_start_batch = time.time()
    
    # Pass lists to trigger batch mode
    _ = flux_gen.generate(p_imgs_batch, c_imgs_batch, prompts_batch, steps=4)
    
    t_end_batch = time.time()
    total_batch_time = t_end_batch - t_start_batch
    avg_batch_time = total_batch_time / BATCH_SIZE
    print(f"Total Batch Time: {total_batch_time:.4f}s")
    print(f"Average Per-Sample Latency (Batch): {avg_batch_time:.4f}s")
    
    # --- Comparison ---
    print("\n" + "="*80)
    print("RESULTS SUMMARY")
    print("="*80)
    print(f"Batch Size: {BATCH_SIZE}")
    print(f"Sequential Total: {total_seq_time:.2f}s  | Per Sample: {avg_seq_time:.4f}s")
    print(f"Batch Total:      {total_batch_time:.2f}s  | Per Sample: {avg_batch_time:.4f}s")
    
    if avg_seq_time > 0:
        speedup = avg_seq_time / avg_batch_time
        print(f"Speedup Factor: {speedup:.2f}x")
    
    print("="*80)

if __name__ == "__main__":
    test_flux_latency_comparison()
