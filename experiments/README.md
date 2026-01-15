# Experiments Directory

This directory contains experimental implementations for Virtual Try-On (VTON) models.

## Overview

The `experiments` directory contains two VTON approaches:

1. **Standard VTON** - Baseline implementation
2. **Our Approach** - Advanced/novel implementation (coming soon)

## Virtual Try-On (VTON) with Stable Diffusion 1.5

An end-to-end virtual try-on implementation using Stable Diffusion 1.5 as the backbone:

- **Dataset Composition**:
  - Masked person image (person with cloth region masked)
  - Cloth image (standalone garment)
  - Person image with cloth (ground truth)

- **Task**: End-to-end virtual try-on synthesis
- **Model**: Stable Diffusion 1.5 (pretrained backbone)
- **Training**: Only self-attention weights are trainable

## Directory Structure

```
experiments/
├── README.md                 # This file
├── config.py                 # Global experiment configuration
├── standard_vton/            # Baseline VTON implementation
│   ├── model.py              # StandardVTONModel architecture
│   ├── dataloader.py         # Dataset loaders
│   ├── train.py              # Training script
│   ├── inference.py          # Inference script
│   ├── utils.py              # Utility functions
│   ├── metrics.py            # Evaluation metrics
│   ├── config.py             # Training configuration
│   ├── requirements.txt      # Dependencies
│   ├── quick_start.sh        # Quick start script
│   └── README.md             # Detailed documentation
└── our_approach/             # Advanced VTON (to be implemented)
    └── README.md             # Placeholder
```

## Standard VTON

The standard approach uses:
- **Pretrained VAE** for encoding images to latent space
- **Concatenated latents** (masked person + cloth) as conditioning
- **Pretrained UNet** with modified input channels (8 instead of 4)
- **Trainable attention weights** only (~5-10% of parameters)

See [standard_vton/README.md](standard_vton/README.md) for detailed documentation.

## Quick Start

### Installation

```bash
cd experiments/standard_vton
pip install -r requirements.txt
```

### Training

```bash
python train.py \
  --data_root ./data/vton_dataset \
  --output_dir ./outputs/standard_vton \
  --batch_size 4 \
  --num_epochs 100
```

### Inference

```bash
python inference.py \
  --checkpoint ./outputs/standard_vton/checkpoints/checkpoint_best.pt \
  --mode single \
  --person_masked ./examples/person_masked.jpg \
  --cloth ./examples/cloth.jpg \
  --output_dir ./outputs/inference
```

## Configuration

See individual subdirectories for specific configurations:
- `standard_vton/config.py` - Standard VTON configuration
- `config.py` - Global experiment settings

## Status

- **Standard VTON**: ✅ Complete and ready to use
- **Our Approach**: 🚧 Coming soon

## Notes

- All experimental code is isolated from the main data pipeline
- Results and models are tracked separately
- Each approach has its own dependencies and configuration
- Supports both custom datasets and VITON-HD format
