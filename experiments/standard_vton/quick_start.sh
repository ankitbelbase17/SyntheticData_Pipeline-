#!/bin/bash

# Quick Start Script for Standard VTON Training

echo "==================================="
echo "Standard VTON - Quick Start"
echo "==================================="

# Check if data directory exists
if [ ! -d "./data/vton_dataset" ]; then
    echo "Error: Data directory not found at ./data/vton_dataset"
    echo "Please prepare your dataset first."
    exit 1
fi

# Install requirements
echo "Installing requirements..."
pip install -r requirements.txt

# Create output directory
mkdir -p outputs/standard_vton

# Start training with default configuration
echo "Starting training..."
python train.py \
    --data_root ./data/vton_dataset \
    --dataset_type vton \
    --output_dir ./outputs/standard_vton \
    --batch_size 4 \
    --num_epochs 100 \
    --lr 1e-4 \
    --train_attention_only \
    --log_interval 10 \
    --save_interval 1000 \
    --vis_interval 500

echo "Training completed!"
