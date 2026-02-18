#!/bin/bash
# ============================================================
#  setup.sh — Dependency installer for Qwen3-VL-32B-Instruct
#  Run once before executing qwen3vl_32b.py
# ============================================================

set -e  # Exit immediately on any error

echo "=========================================="
echo "  Qwen3-VL-32B Inference Setup"
echo "=========================================="

# ── 1. System-level packages (CUDA toolkit assumed present) ─
echo "[1/6] Upgrading pip..."
pip install --upgrade pip

# ── 2. Core ML stack ──────────────────────────────────────
echo "[2/6] Installing PyTorch (cu121 build)..."
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# ── 3. Transformers (dev build required for Qwen3-VL) ─────
echo "[3/6] Installing Transformers from GitHub (Qwen3-VL support)..."
pip install git+https://github.com/huggingface/transformers

# ── 4. HuggingFace ecosystem ──────────────────────────────
echo "[4/6] Installing HuggingFace ecosystem..."
pip install \
    accelerate \
    huggingface_hub \
    tokenizers \
    safetensors

# ── 5. Qwen-VL utilities (image/video pre-processing) ─────
echo "[5/6] Installing Qwen-VL utility dependencies..."
pip install \
    qwen-vl-utils \
    datasets \
    Pillow \
    requests \
    numpy

# ── 6. Flash Attention 2 ──────────────────────────────────────────────────
# Requires: CUDA 12.x, PyTorch 2.5, Python 3.12, BF16 GPU (A100/H100/4090)
# Installs via direct wheel download to avoid [Errno 18] cross-device link error
# that occurs when pip tries to move the wheel across filesystem mount boundaries.
echo "[6/6] Installing Flash Attention 2 (direct wheel download)..."

FA_WHL="flash_attn-2.8.3+cu12torch2.5cxx11abiFALSE-cp312-cp312-linux_x86_64.whl"
FA_URL="https://github.com/Dao-AILab/flash-attention/releases/download/v2.8.3/${FA_WHL}"
FA_LOCAL="/tmp/${FA_WHL}"

echo "  Downloading wheel to /tmp ..."
wget -q --show-progress -O "${FA_LOCAL}" "${FA_URL}"

echo "  Installing from local wheel ..."
pip install "${FA_LOCAL}"

echo "  Cleaning up..."
rm -f "${FA_LOCAL}"

echo ""
echo "=========================================="
echo "  All dependencies installed successfully!"
echo "  Run:  python qwen3vl_32b.py --input sampled_keywords_7000.json"
echo "=========================================="
