# Experiments Directory

This directory contains experimental implementations for the Synthetic Data Pipeline.

## Overview

The `experiments` directory is dedicated to advanced research and prototyping, currently focused on:

### Virtual Try-On (VTON) with Stable Diffusion 1.5

An end-to-end virtual try-on implementation inspired by the CATVTON paper, but using a different training paradigm:

- **Dataset Composition**: 
  - Person image in Clothing 1
  - Image of Clothing 2 (standalone)
  - Person image in Clothing 2 (ground truth)

- **Task**: End-to-end virtual try-on synthesis
- **Model**: Stable Diffusion 1.5 (fine-tuned)
- **Approach**: Direct image-to-image translation without explicit masking-based segmentation

## Directory Structure

```
experiments/
├── README.md                 # This file
├── config.py                 # Experiment-specific configuration
└── (code to be added)
```

## Configuration

See `config.py` for experiment-specific settings including:
- Model paths and checkpoints
- Training parameters
- Dataset paths
- Hardware configuration

## Status

Currently in setup phase. Code implementation pending.

## Notes

- All experimental code is isolated from the main data pipeline
- Results and models are tracked separately
- This allows for safe experimentation without affecting production pipelines
