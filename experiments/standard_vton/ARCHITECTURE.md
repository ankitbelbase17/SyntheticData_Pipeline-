# Standard VTON Architecture Documentation

## Overview

The Standard VTON model is a baseline virtual try-on implementation that leverages Stable Diffusion 1.5 as a pretrained backbone. The key innovation is training only the self-attention weights while keeping all other parameters frozen.

## Architecture Components

### 1. VAE (Variational Autoencoder)

**Purpose**: Encode images to latent space and decode back to image space

**Configuration**:
- Pretrained from SD 1.5
- Frozen (no training)
- Input: RGB images (3, H, W) normalized to [-1, 1]
- Output: Latent representations (4, H/8, W/8)
- Scaling factor: 0.18215

**Usage**:
```python
# Encoding
latents = vae.encode(images).latent_dist.sample()
latents = latents * 0.18215

# Decoding
images = vae.decode(latents / 0.18215).sample
```

### 2. UNet

**Purpose**: Denoise latent representations conditioned on person and cloth

**Configuration**:
- Pretrained from SD 1.5
- Modified input channels: 8 (4 noisy + 4 conditioning)
- Only attention weights trainable
- Classifier-free guidance support

**Architecture Details**:
```
Input: (B, 8, H/8, W/8)
  ├─ 4 channels: Noisy latent
  └─ 4 channels: Masked person latent (conditioning)

UNet Blocks:
  ├─ Down Blocks (with self-attention)
  ├─ Mid Block (with self-attention)
  └─ Up Blocks (with self-attention)

Output: (B, 4, H/8, W/8) - Predicted noise
```

**Trainable Components**:
Only self-attention layers (attn1):
- `to_q`: Query projection
- `to_k`: Key projection
- `to_v`: Value projection
- `to_out`: Output projection

### 3. Text Encoder (CLIP)

**Purpose**: Encode text prompts for conditioning (optional)

**Configuration**:
- Pretrained CLIP text encoder
- Frozen (no training)
- Max sequence length: 77 tokens
- Output dimension: 768

**Usage**:
```python
text_embeddings = text_encoder(token_ids)[0]  # (B, 77, 768)
```

### 4. Noise Scheduler (DDPM)

**Purpose**: Add/remove noise during training and inference

**Configuration**:
- DDPM scheduler from SD 1.5
- Training timesteps: 1000
- Beta schedule: scaled_linear
- Prediction type: epsilon (noise prediction)

## Data Flow

### Training Pipeline

```
1. Input Processing:
   Masked Person Image (B, 3, 512, 512)  ─┐
                                           ├─> VAE Encoder
   Cloth Image (B, 3, 512, 512)          ─┘
                                           ↓
   Person Latent (B, 4, 64, 64)          ─┐
                                           ├─> Concatenate
   Cloth Latent (B, 4, 64, 64)           ─┘
                                           ↓
   Conditioning Latent (B, 8, 64, 64)

2. Target Processing:
   Target Image (B, 3, 512, 512)         ─> VAE Encoder
                                           ↓
   Target Latent (B, 4, 64, 64)
                                           ↓
   Add Noise (random timestep)
                                           ↓
   Noisy Latent (B, 4, 64, 64)

3. UNet Forward:
   Noisy Latent (B, 4, 64, 64)           ─┐
                                           ├─> Concatenate
   Conditioning[:, :4] (B, 4, 64, 64)    ─┘
                                           ↓
   UNet Input (B, 8, 64, 64)             ─> UNet
                                           ↓
   Predicted Noise (B, 4, 64, 64)

4. Loss Calculation:
   MSE(Predicted Noise, Actual Noise)
```

### Inference Pipeline

```
1. Input Processing:
   Masked Person Image ─> VAE Encoder ─> Person Latent
   Cloth Image         ─> VAE Encoder ─> Cloth Latent
                                       ↓
   Concatenate ─> Conditioning Latent (B, 8, 64, 64)

2. Initialize:
   Random Noise ─> Initial Latent (B, 4, 64, 64)

3. Iterative Denoising (50 steps):
   For t in [T, T-1, ..., 1]:
     ├─ Concatenate: Latent + Conditioning
     ├─ UNet Prediction (with CFG)
     └─ Update Latent (remove predicted noise)

4. Decode:
   Final Latent ─> VAE Decoder ─> Generated Image
```

## Training Strategy

### Phase 1: Attention-Only Training

**Trainable Parameters** (~5-10% of total):
- Self-attention query, key, value projections
- Self-attention output projections

**Frozen Parameters** (~90-95% of total):
- VAE encoder/decoder
- UNet convolutional layers
- UNet normalization layers
- Cross-attention layers
- Text encoder

### Loss Function

**Diffusion Loss** (MSE):
```
L = MSE(ε_pred, ε_target)

where:
- ε_pred: Predicted noise from UNet
- ε_target: Actual noise added to target latent
```

### Optimization

**Optimizer**: AdamW
- Learning rate: 1e-4
- Weight decay: 0.01
- Betas: (0.9, 0.999)

**Learning Rate Schedule**:
1. Linear warmup (5 epochs): 0.1 * lr → lr
2. Cosine annealing: lr → 1e-6

**Gradient Clipping**: Max norm = 1.0

## Inference Strategy

### Classifier-Free Guidance (CFG)

**Purpose**: Improve sample quality by balancing conditional and unconditional predictions

**Method**:
```python
# Predict with both conditional and unconditional embeddings
noise_pred_uncond = UNet(latent, t, uncond_embeddings)
noise_pred_cond = UNet(latent, t, text_embeddings)

# Combine predictions
noise_pred = noise_pred_uncond + guidance_scale * (noise_pred_cond - noise_pred_uncond)
```

**Guidance Scale**:
- Lower (1-5): More diverse, less faithful
- Medium (5-10): Balanced
- Higher (10+): More faithful, less diverse
- Recommended: 7.5

### Number of Inference Steps

**Trade-off**: Quality vs Speed

- 20 steps: Fast, decent quality
- 50 steps: Balanced (recommended)
- 100 steps: High quality, slow

## Model Size

**Total Parameters**: ~860M
- VAE: ~83M
- UNet: ~860M
- Text Encoder: ~123M

**Trainable Parameters**: ~43-86M (5-10%)
- Self-attention layers only

**Memory Requirements**:
- Training (batch=4, 512x512): ~16-20GB VRAM
- Inference (512x512): ~8-10GB VRAM

## Key Design Decisions

### 1. Why Train Only Attention?

**Rationale**:
- Attention layers learn semantic correspondences
- Most relevant for cloth-to-person transfer
- Efficient: Only 5-10% of parameters
- Preserves pretrained knowledge

### 2. Why Concatenate Latents?

**Rationale**:
- Direct conditioning on both person and cloth
- Spatial alignment in latent space
- Leverages UNet's spatial processing
- Simple and effective

### 3. Why Stable Diffusion 1.5?

**Rationale**:
- Strong pretrained knowledge
- Well-tested architecture
- Good image quality
- Reasonable computational cost

## Limitations

1. **Limited Capacity**: Only attention weights trainable
2. **Mask Quality**: Requires accurate person masks
3. **Pose Variation**: May struggle with extreme poses
4. **Occlusions**: Cannot handle complex occlusions well
5. **Resolution**: Limited to 512x512 (can be extended)

## Extensions

### Potential Improvements

1. **Train More Layers**: Cross-attention, normalization layers
2. **Better Conditioning**: Add pose keypoints, semantic maps
3. **Multi-Scale**: Process at multiple resolutions
4. **Adversarial Loss**: Add discriminator for realism
5. **Perceptual Loss**: Add LPIPS or VGG loss

### Higher Resolution

To train at 1024x1024:
1. Use SD 2.0 or SDXL backbone
2. Increase VRAM (24GB+ recommended)
3. Adjust batch size and learning rate
4. Use gradient checkpointing

## References

- Stable Diffusion: https://github.com/CompVis/stable-diffusion
- Diffusers: https://github.com/huggingface/diffusers
- VITON-HD: https://github.com/shadow2496/VITON-HD
