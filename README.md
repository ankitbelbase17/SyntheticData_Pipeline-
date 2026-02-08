# Closed-Loop Feedback Try-On System

This project implements a closed-loop feedback system for virtual try-on using **Flux 2 Klein 9B** for generation and **Qwen 3 VL 32B** for evaluation.

## System Overview

1.  **Data Source**: Fetches paired Person and Cloth images from an AWS S3 bucket.
2.  **Generation**: Flux model generates a try-on image.
3.  **Evaluation**: Qwen VLM analyzes the result against the inputs and provides feedback based on 7 hierarchical constraints.
4.  **Feedback Loop**:
    - If successful, saves to `output/correct_try_on`.
    - If failed, saves to `output/incorrect_try_on_X` and generates a new prompt.
    - Repeats up to 4 iterations.

## Directory Structure

```
local_data_pipeline/
├── src/
│   ├── config.py           # Configuration (Paths, Models, AWS Credentials)
│   ├── main.py             # Entry point & Execution Loop
│   ├── core/
│   │   ├── models.py       # Flux and Qwen Wrappers (Mock/Real)
│   │   └── feedback_loop.py# Core Loop Logic
│   ├── data/
│   │   └── dataloader.py   # S3 Data Loading Logic
│   └── utils/
│       └── helpers.py      # Helper functions (Image saving, JSON parsing)
├── input/                  # Local dummy input (if needed)
├── output/                 # Results Sorted by Iteration/Quality
└── requirements.txt
```

## Setup & configuration

### 1. Install Requirements
```bash
pip install -r requirements.txt
```

### 2. Configure Credentials
You must set the following environment variables for S3 access and Model access:

- `AWS_ACCESS_KEY_ID`: Your AWS Access Key.
- `AWS_SECRET_ACCESS_KEY`: Your AWS Secret Key.
- `AWS_REGION_NAME`: AWS Region (e.g., `us-east-1`).
- `S3_BUCKET_NAME`: The name of your S3 bucket containing the dataset.
- `HF_TOKEN`: Hugging Face Token (for accessing gated models).

Alternatively, you can edit defaults in `src/config.py`.

### 3. Model Integration
**Important**: The default `src/core/models.py` contains **placeholder/mock implementations** to allow testing the loop logic without heavy GPU requirements.

**To use the REAL models:**
1.  Open `src/core/models.py`.
2.  Uncomment the real initialization code in `__init__` for `FluxGenerator` and `QwenVLM`.
3.  Uncomment the actual inference lines in `generate()` and `evaluate()`.
4.  Ensure you have a GPU with sufficient VRAM (approx 24GB+ recommended for these models).

## Running the Pipeline

Run the main script to start processing samples from S3:

```bash
python src/main.py
```

**Features:**
- **Batch Processing**: Processes up to 100 samples from the S3 bucket.
- **Latency Measurement**: Tracks and reports the average time taken for the feedback loop (generation + evaluation), excluding download times.
- **Robustness**: Skips invalid images or failed downloads automatically.
