# Standard VTON - Virtual Try-On Model

A baseline virtual try-on model using Stable Diffusion 1.5 as the backbone with trainable attention weights only.

## Overview

This implementation follows a standard approach for virtual try-on:
1. **VAE Encoding**: Encodes masked person image and cloth image to latent space
2. **Latent Concatenation**: Concatenates VAE latents as conditioning
3. **UNet Generation**: Uses pretrained SD 1.5 UNet with self-attention layers
4. **Trainable Weights**: Only attention weights (Q, K, V, output projections) are trainable

## Architecture

- **Backbone**: Stable Diffusion 1.5 (runwayml/stable-diffusion-v1-5)
- **VAE**: Pretrained VAE encoder/decoder (frozen)
- **UNet**: Pretrained UNet with modified input channels (8 instead of 4)
- **Trainable Parameters**: Self-attention weights only (~5-10% of total parameters)

## Project Structure

```
standard_vton/
├── model.py           # StandardVTONModel architecture
├── dataloader.py      # Dataset loaders (VTON, VITON-HD)
├── train.py           # Training script
├── inference.py       # Inference script
├── utils.py           # Utility functions
├── metrics.py         # Evaluation metrics
├── __init__.py        # Package initialization
└── README.md          # This file
```

## Installation

### Requirements

```bash
pip install torch torchvision
pip install diffusers transformers accelerate
pip install pillow numpy scipy matplotlib
pip install tensorboard tqdm
pip install lpips  # Optional, for LPIPS metric
```

### Dataset Preparation

#### Option 1: Custom VTON Dataset

Create the following directory structure:

```
data/vton_dataset/
├── person/              # Original person images
├── person_masked/       # Person images with cloth region masked
├── cloth/               # Cloth images
├── pairs_train.json     # Training pairs
└── pairs_test.json      # Test pairs
```

The `pairs.json` format:
```json
[
  {
    "person": "person_001.jpg",
    "person_masked": "person_001.jpg",
    "cloth": "cloth_001.jpg",
    "cloth_type": "upper"
  },
  ...
]
```

#### Option 2: VITON-HD Dataset

Download VITON-HD dataset and organize as:

```
data/viton-hd/
├── train/
│   ├── image/              # Person images
│   ├── image-parse-v3/     # Segmentation masks
│   ├── cloth/              # Cloth images
│   └── train_pairs.txt     # Pairing information
└── test/
    └── ...
```

## Training

### Basic Training

```bash
python train.py \
  --data_root ./data/vton_dataset \
  --dataset_type vton \
  --output_dir ./outputs/standard_vton \
  --batch_size 4 \
  --num_epochs 100 \
  --lr 1e-4 \
  --train_attention_only
```

### Advanced Training Options

```bash
python train.py \
  --data_root ./data/viton-hd \
  --dataset_type viton-hd \
  --image_size 512 512 \
  --batch_size 8 \
  --num_epochs 200 \
  --lr 1e-4 \
  --weight_decay 0.01 \
  --warmup_epochs 5 \
  --gradient_accumulation_steps 2 \
  --output_dir ./outputs/experiment_1 \
  --log_interval 10 \
  --save_interval 1000 \
  --vis_interval 500 \
  --num_workers 8 \
  --gpu_id 0
```

### Resume Training

```bash
python train.py \
  --data_root ./data/vton_dataset \
  --resume ./outputs/standard_vton/checkpoints/checkpoint_latest.pt \
  --output_dir ./outputs/standard_vton
```

## Inference

### Single Image Pair

```bash
python inference.py \
  --checkpoint ./outputs/standard_vton/checkpoints/checkpoint_best.pt \
  --mode single \
  --person_masked ./examples/person_masked.jpg \
  --cloth ./examples/cloth.jpg \
  --person_gt ./examples/person_gt.jpg \
  --output_dir ./outputs/inference \
  --num_inference_steps 50 \
  --guidance_scale 7.5 \
  --save_visualization \
  --compute_metrics
```

### Dataset Inference

```bash
python inference.py \
  --checkpoint ./outputs/standard_vton/checkpoints/checkpoint_best.pt \
  --mode dataset \
  --data_root ./data/vton_dataset \
  --dataset_type vton \
  --output_dir ./outputs/inference \
  --batch_size 4 \
  --num_inference_steps 50 \
  --save_visualization \
  --compute_metrics
```

## Evaluation Metrics

The following metrics are computed:

- **PSNR**: Peak Signal-to-Noise Ratio
- **SSIM**: Structural Similarity Index
- **MAE**: Mean Absolute Error
- **MSE**: Mean Squared Error
- **LPIPS**: Learned Perceptual Image Patch Similarity (requires `lpips` package)
- **FID**: Frechet Inception Distance (optional)
- **IS**: Inception Score (optional)

## Model Details

### Input

- **Masked Person Image**: RGB image with cloth region masked (512x512)
- **Cloth Image**: RGB image of the cloth to try on (512x512)

### Output

- **Generated Image**: Person wearing the cloth (512x512)

### Training Strategy

1. **Freeze all weights** except self-attention layers
2. **Modify UNet input** to accept concatenated latents (8 channels)
3. **Train with diffusion objective** (noise prediction)
4. **Use classifier-free guidance** during inference

### Trainable Parameters

Only self-attention weights are trainable:
- Query (to_q) projections
- Key (to_k) projections
- Value (to_v) projections
- Output (to_out) projections

This typically results in **~5-10%** of total parameters being trainable.

## Output Structure

```
outputs/standard_vton/
├── checkpoints/
│   ├── checkpoint_epoch_X_step_Y.pt
│   ├── checkpoint_latest.pt
│   └── checkpoint_best.pt
├── logs/
│   ├── train.log
│   ├── metrics.json
│   └── tensorboard/
├── samples/
│   └── epoch_X_step_Y.png
└── config.json
```

## Configuration

All training configurations are saved in `config.json`:

```json
{
  "data_root": "./data/vton_dataset",
  "dataset_type": "vton",
  "image_size": [512, 512],
  "pretrained_model": "runwayml/stable-diffusion-v1-5",
  "batch_size": 4,
  "num_epochs": 100,
  "lr": 0.0001,
  ...
}
```

## Monitoring Training

### TensorBoard

```bash
tensorboard --logdir ./outputs/standard_vton/logs
```

### Training Logs

Check `./outputs/standard_vton/logs/train.log` for detailed training logs.

### Visualizations

Sample visualizations are saved periodically in `./outputs/standard_vton/samples/`

## Tips for Better Performance

1. **Data Quality**: Ensure high-quality paired data with accurate masks
2. **Batch Size**: Use larger batch sizes for more stable training
3. **Learning Rate**: Start with 1e-4 and adjust based on loss curves
4. **Warmup**: Use warmup epochs to stabilize early training
5. **Inference Steps**: Use 50+ steps for higher quality results
6. **Guidance Scale**: Adjust between 5-10 for quality vs diversity trade-off

## Known Limitations

- Only self-attention is trainable (limited capacity for learning)
- Requires well-aligned and masked person images
- Performance depends heavily on mask quality
- May struggle with complex poses or occlusions

## Citation

If you use this code, please cite:

```bibtex
@misc{standard-vton-2025,
  title={Standard VTON: Baseline Virtual Try-On with Stable Diffusion},
  author={Your Name},
  year={2025}
}
```

## License

This project is licensed under the MIT License.

## Acknowledgements

- Stable Diffusion by Stability AI
- Diffusers library by Hugging Face
- VITON-HD dataset
