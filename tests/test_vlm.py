import sys
import os
import time
import torch
from PIL import Image

# Add parent directory to path so we can import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.models import QwenVLM
from src.data.dataloader import get_dataloader
from src.utils.helpers import load_image_from_url

def test_vlm_latency_comparison():
    print("="*80)
    print("VLM EVALUATION LATENCY COMPARISON: SEQUENTIAL vs BATCH")
    print("="*80)
    
    # 1. Initialize Model
    print("Initializing QwenVLM...")
    t0 = time.time()
    vlm = QwenVLM(model_id="Qwen/Qwen3-VL-8B-Instruct", device="cuda")
    print(f"Model Init Time: {time.time() - t0:.2f}s")
    
    # 2. Prepare Data
    loader_single, _ = get_dataloader(difficulty="easy", gender="female")
    
    sample = next(iter(loader_single))
    p_url = sample['initialImage'][0]
    c_url = sample['clothImage'][0]
    
    try:
        p_img = load_image_from_url(p_url)
        c_img = load_image_from_url(c_url)
        try_on_img = p_img.copy() 
        print("Images prepared.")
    except Exception as e:
        print(f"Failed to prepare images: {e}")
        return

    BATCH_SIZE = 28
    history = [try_on_img] # Single item history for simplicity
    
    # Warmup
    print("\nWarming up (1 evaluation)...")
    _ = vlm.evaluate(p_img, c_img, history, iteration=1)
    
    # --- TEST A: Sequential Processing ---
    print(f"\n[TEST A] Sequential Processing (Looping {BATCH_SIZE} times)")
    print("Starting sequential loop...")
    t_start_seq = time.time()
    
    for i in range(BATCH_SIZE):
        # Pass single items
        _ = vlm.evaluate(p_img, c_img, history, iteration=1)
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
    # History for batch is list of lists of images
    histories_batch = [[try_on_img.copy()] for _ in range(BATCH_SIZE)]
    
    print("Starting batch evaluation...")
    t_start_batch = time.time()
    
    # Pass lists to trigger batch mode
    _ = vlm.evaluate(p_imgs_batch, c_imgs_batch, histories_batch, iteration=1)
    
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
    test_vlm_latency_comparison()
