# config.py - Experiments Configuration
# Experiment-specific settings for VTON tasks and model training

# ============================================================================
# STABLE DIFFUSION 1.5 VTON CONFIGURATION
# ============================================================================

# Model Configuration
SD15_MODEL_ID = "runwayml/stable-diffusion-v1-5"
SD15_DEVICE = "cuda"  # "cuda" or "cpu"
SD15_PRECISION = "fp16"  # "fp16" or "fp32"
SD15_ENABLE_ATTENTION_SLICING = True

# LoRA Fine-tuning Configuration
LORA_RANK = 8
LORA_ALPHA = 16
LORA_DROPOUT = 0.1
LORA_TARGET_MODULES = ["to_k", "to_v", "to_q", "to_out.0"]

# Training Configuration
TRAINING_EPOCHS = 50
TRAINING_BATCH_SIZE = 4
TRAINING_GRADIENT_ACCUMULATION_STEPS = 1
TRAINING_LEARNING_RATE = 1e-4
TRAINING_WEIGHT_DECAY = 0.01
TRAINING_WARMUP_STEPS = 500
TRAINING_MAX_STEPS = 10000

# Dataset Configuration
DATASET_NAME = "vton_sd15_end2end"
DATASET_TRAIN_SPLIT = "train"
DATASET_VAL_SPLIT = "val"
DATASET_TEST_SPLIT = "test"

# Image Processing
IMAGE_SIZE = 512
IMAGE_AUGMENTATION_PROB = 0.5
IMAGE_NORMALIZE_MEAN = [0.5, 0.5, 0.5]
IMAGE_NORMALIZE_STD = [0.5, 0.5, 0.5]

# Data Composition (End-to-End VTON)
# Each training sample consists of:
# 1. Person image in Clothing 1 (anchor)
# 2. Clothing 2 image (target garment)
# 3. Person image in Clothing 2 (ground truth target)
DATA_FORMAT = {
    "anchor": "person_in_clothing1",
    "target_garment": "clothing2",
    "target": "person_in_clothing2"
}

# Inference Configuration
INFERENCE_NUM_INFERENCE_STEPS = 50
INFERENCE_GUIDANCE_SCALE = 7.5
INFERENCE_SCHEDULER = "DPMSolverMultistepScheduler"

# Output Configuration
OUTPUT_BASE_DIR = "./experiments/outputs"
CHECKPOINTS_DIR = "./experiments/outputs/checkpoints"
RESULTS_DIR = "./experiments/outputs/results"
LOGS_DIR = "./experiments/outputs/logs"
METRICS_DIR = "./experiments/outputs/metrics"

# Validation Configuration
VALIDATION_FREQUENCY = 500  # Validate every N steps
VALIDATION_NUM_SAMPLES = 10
VALIDATION_METRICS = ["lpips", "ssim", "fid", "inception_score"]

# Checkpoint Configuration
SAVE_CHECKPOINT_EVERY = 1000
KEEP_LAST_N_CHECKPOINTS = 5

# Callback and Monitoring
USE_TENSORBOARD = True
USE_WANDB = False
WANDB_PROJECT_NAME = "sd15-vton"
LOG_FREQUENCY = 100

# Hardware Configuration
NUM_WORKERS = 4
PIN_MEMORY = True
MIXED_PRECISION = "fp16"
GRADIENT_CHECKPOINTING = True

# Random Seed
RANDOM_SEED = 42
