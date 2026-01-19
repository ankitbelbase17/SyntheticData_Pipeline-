"""
Quick test script to verify TRUE batch processing works
Tests with small batch first, then scales up
"""

import time
import torch
from qwen_inference import QwenVLBatchInference

def test_batch_inference():
    """Test batch inference with increasing batch sizes"""
    
    print("="*80)
    print("BATCH INFERENCE TEST")
    print("="*80)
    
    # Initialize model
    print("\nLoading model...")
    model = QwenVLBatchInference()
    
    # Test image
    image_path = "./data/images/zalando1.webp"
    
    # Test with different batch sizes
    test_sizes = [1, 4, 16, 32, 64, 128]
    
    results = []
    
    for batch_size in test_sizes:
        print(f"\n{'='*60}")
        print(f"Testing batch size: {batch_size}")
        print(f"{'='*60}")
        
        # Create dummy prompts
        prompts = [f"Describe this image. Focus on detail {i}." for i in range(batch_size)]
        
        # Run batch inference
        start_time = time.time()
        responses = model.batch_inference(
            image_source=image_path,
            prompts=prompts,
            max_new_tokens=256,
            temperature=0.7
        )
        elapsed = time.time() - start_time
        
        # Calculate metrics
        avg_time = elapsed / batch_size
        throughput = batch_size / elapsed
        
        result = {
            'batch_size': batch_size,
            'total_time': elapsed,
            'avg_time': avg_time,
            'throughput': throughput,
            'responses_count': len(responses)
        }
        results.append(result)
        
        print(f"✓ Processed {batch_size} prompts in {elapsed:.2f}s")
        print(f"  Amortized time per prompt: {avg_time:.3f}s")
        print(f"  Throughput: {throughput:.2f} prompts/second")
        print(f"  GPU Memory: {torch.cuda.max_memory_allocated() / 1e9:.2f} GB")
        
        # Show first response as sample
        if batch_size <= 4:
            print(f"\n  Sample response 1: {responses[0][:100]}...")
    
    # Summary comparison
    print(f"\n\n{'='*80}")
    print("PERFORMANCE SUMMARY")
    print(f"{'='*80}")
    print(f"{'Batch Size':<12} {'Total Time':<12} {'Avg/Prompt':<15} {'Throughput':<15}")
    print("-" * 80)
    
    for r in results:
        print(f"{r['batch_size']:<12} {r['total_time']:<12.2f} "
              f"{r['avg_time']:<15.3f} {r['throughput']:<15.2f}")
    
    print(f"\n{'='*80}")
    print(f"Peak GPU Memory: {torch.cuda.max_memory_allocated() / 1e9:.2f} GB")
    print(f"{'='*80}\n")
    
    return results


if __name__ == "__main__":
    test_batch_inference()