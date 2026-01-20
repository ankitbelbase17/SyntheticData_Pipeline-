#!/bin/bash
# Example optimized script - Male Shard 0/7 (medium)
# Uses the optimized inference pipeline with Flash Attention 2

# First time only: Run setup to install flash-attn
# bash setup_optimized.sh

python qwen_batch_inference_optimized.py \
  --gender male \
  --difficulty medium \
  --batch_size 28 \
  --shard_id 0 \
  --total_shards 7 \
  --epochs 8
