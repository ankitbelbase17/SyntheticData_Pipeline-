#!/bin/bash
# Setup script for optimized Qwen VLM inference on Vast AI / cloud GPU rentals
# Run this BEFORE running the inference pipeline

echo "========================================"
echo "Setting up optimized environment"
echo "========================================"

# Check GPU
echo ""
echo "[1/4] Checking GPU..."
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv

# Check CUDA version
echo ""
echo "[2/4] Checking CUDA..."
nvcc --version 2>/dev/null || echo "nvcc not found, checking PyTorch CUDA..."
python3 -c "import torch; print(f'PyTorch CUDA: {torch.version.cuda}')"

# Install Flash Attention 2 (critical for performance)
echo ""
echo "[3/4] Installing Flash Attention 2..."
echo "This may take a few minutes..."

# First ensure we have the build dependencies
pip install packaging ninja

pip install -r requirements.txt

# Install flash-attn (--no-build-isolation is required)
pip install flash-attn --no-build-isolation

# Verify installation
echo ""
echo "[4/4] Verifying installation..."
python3 -c "
import torch
print(f'PyTorch: {torch.__version__}')
print(f'CUDA Available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'GPU: {torch.cuda.get_device_name(0)}')
    print(f'BF16 Support: {torch.cuda.is_bf16_supported()}')
    major, minor = torch.cuda.get_device_capability()
    print(f'Compute Capability: {major}.{minor}')
    if major >= 8:
        print('✓ GPU supports Flash Attention 2')

try:
    import flash_attn
    print(f'✓ Flash Attention: {flash_attn.__version__}')
except ImportError:
    print('✗ Flash Attention NOT installed')
    print('  Try: pip install flash-attn --no-build-isolation')

try:
    from transformers.utils import is_flash_attn_2_available
    if is_flash_attn_2_available():
        print('✓ Transformers can use Flash Attention 2')
    else:
        print('⚠ Transformers cannot use Flash Attention 2')
except:
    pass
"

echo ""
echo "========================================"
echo "Setup complete!"
echo "========================================"
echo ""
echo "To run optimized inference:"
echo "  python qwen_batch_inference_optimized.py --gender male --shard_id 0 --total_shards 7 --epochs 8"
echo ""
