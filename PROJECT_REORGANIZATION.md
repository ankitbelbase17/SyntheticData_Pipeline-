# Project Reorganization Summary

## Directory Structure Changes

### New Root Structure

```
SyntheticData_Pipeline-/
├── data_pipeline/              # Main data collection and preprocessing
│   ├── config.py               # Configuration with AWS S3 settings
│   ├── .env.example            # Environment variables template
│   ├── zalando_gallery_scraper_s3.py  # Zalando scraper with S3 support
│   ├── README.md               # Data pipeline documentation
│   └── vton_gallery_dataset/   # Local output (temporary cache)
│
├── experiments/                # Research and experimentation
│   ├── config.py               # Experiment-specific configuration
│   ├── README.md               # Experiments documentation
│   └── (code to be added later)
│
├── scraper/                    # Original scraper code
├── bash_scripts/               # Bash execution scripts
├── docker-compose.yml          # Docker orchestration
├── deployment.yaml             # Kubernetes deployment
└── README.md                   # Main project README
```

## Key Changes

### 1. Data Pipeline Organization

**New Location**: `data_pipeline/`

**Contents**:
- `config.py`: Comprehensive configuration with AWS S3 support
- `zalando_gallery_scraper_s3.py`: Modified Zalando scraper with S3 integration
- `.env.example`: Template for environment variables
- `README.md`: Complete setup and usage guide

### 2. AWS S3 Integration

**Modified File**: `data_pipeline/zalando_gallery_scraper_s3.py`

**Key Features**:
- Automatic S3 upload of images and metadata
- Local caching for faster processing
- Progress tracking with resume capability
- Comprehensive error handling and logging
- Support for IAM user credentials

**S3 Structure**:
```
s3://your-bucket/
├── products/{product_id}/{image_00.jpg}
├── metadata/{product_id}.json
└── ...
```

### 3. Configuration System

**New File**: `data_pipeline/config.py`

**Includes**:
- AWS S3 credentials (from environment variables)
- API keys (HuggingFace, OpenAI, Gemini)
- Model configurations
- Scraper settings
- Local directory paths
- Logging configuration

**Environment Variables** (in `.env` or system):
```
AWS_S3_BUCKET=your-bucket
AWS_S3_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
HF_TOKEN=your_token
OPENAI_API_KEY=your_key
```

### 4. Experiments Directory

**New Location**: `experiments/`

**Current Contents**:
- `config.py`: Stable Diffusion 1.5 VTON training configuration
- `README.md`: Overview and status

**Future**: Will contain Stable Diffusion 1.5 implementation for end-to-end VTON with:
- Person image in Clothing 1 (anchor)
- Clothing 2 image (target garment)
- Person image in Clothing 2 (ground truth)

## Configuration Files

### `data_pipeline/config.py`

**AWS S3 Section**:
```python
AWS_S3_BUCKET = os.getenv('AWS_S3_BUCKET', 'your-bucket')
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', None)
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', None)
```

**Scraper Section**:
```python
ZALANDO_USE_S3 = True  # Enable S3 uploads
ZALANDO_SCRAPER_HEADLESS = False  # Visible browser
ZALANDO_SCRAPER_MAX_PAGES = 0  # All pages
```

### `data_pipeline/.env.example`

Template with all required variables:
```
AWS_S3_BUCKET=your-synthetic-data-bucket
AWS_S3_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
HF_TOKEN=hf_...
OPENAI_API_KEY=sk-...
```

### `experiments/config.py`

**Stable Diffusion 1.5 Training**:
```python
SD15_MODEL_ID = "runwayml/stable-diffusion-v1-5"
TRAINING_EPOCHS = 50
TRAINING_BATCH_SIZE = 4
TRAINING_LEARNING_RATE = 1e-4
```

**Dataset Format**:
```python
DATA_FORMAT = {
    "anchor": "person_in_clothing1",
    "target_garment": "clothing2",
    "target": "person_in_clothing2"
}
```

## Usage Instructions

### 1. Setup AWS Credentials

```bash
# Option 1: Using .env file
cp data_pipeline/.env.example data_pipeline/.env
# Edit data_pipeline/.env with your credentials

# Option 2: Using environment variables
export AWS_ACCESS_KEY_ID="your_key"
export AWS_SECRET_ACCESS_KEY="your_secret"
export AWS_S3_BUCKET="your-bucket"
```

### 2. Verify S3 Access

```bash
python -c "
import sys
sys.path.insert(0, 'data_pipeline')
from config import AWS_S3_BUCKET
import boto3
s3 = boto3.client('s3')
s3.head_bucket(Bucket=AWS_S3_BUCKET)
print(f'✓ S3 access verified: {AWS_S3_BUCKET}')
"
```

### 3. Run Zalando Scraper

```bash
cd data_pipeline
python zalando_gallery_scraper_s3.py
```

**Output**:
- Local: `vton_gallery_dataset/`
- S3: `s3://your-bucket/products/` and `s3://your-bucket/metadata/`

## Key Configuration Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `AWS_S3_BUCKET` | `your-synthetic-data-bucket` | S3 bucket name |
| `AWS_S3_REGION` | `us-east-1` | AWS region |
| `ZALANDO_USE_S3` | `True` | Enable S3 uploads |
| `ZALANDO_SCRAPER_HEADLESS` | `False` | Browser visibility |
| `ZALANDO_SCRAPER_MAX_PAGES` | `0` | Pages to scrape (0=all) |
| `ZALANDO_SCRAPER_MAX_ITEMS` | `0` | Items to scrape (0=all) |

## AWS IAM Permissions Required

```json
{
  "Effect": "Allow",
  "Action": [
    "s3:PutObject",
    "s3:GetObject",
    "s3:ListBucket",
    "s3:HeadBucket"
  ],
  "Resource": [
    "arn:aws:s3:::your-synthetic-data-bucket",
    "arn:aws:s3:::your-synthetic-data-bucket/*"
  ]
}
```

## Files Modified/Created

### Created Files
- `data_pipeline/` (directory)
- `data_pipeline/config.py`
- `data_pipeline/zalando_gallery_scraper_s3.py`
- `data_pipeline/.env.example`
- `data_pipeline/README.md`
- `experiments/` (directory)
- `experiments/config.py`
- `experiments/README.md`

### Future Work

In `experiments/` (when code is provided):
- Stable Diffusion 1.5 training implementation
- VTON dataset preparation
- Model fine-tuning pipeline
- Evaluation metrics

## Security Notes

1. **Never commit `.env` file** - only commit `.env.example`
2. **Use IAM users**, not root AWS account
3. **Rotate credentials** regularly
4. **Enable S3 encryption** for sensitive data
5. **Use S3 versioning** for data backup

## Next Steps

1. ✅ Configure AWS credentials in `data_pipeline/.env`
2. ✅ Run Zalando scraper in test mode
3. ✅ Verify S3 uploads are working
4. ⏳ Provide code for `experiments/` directory
5. ⏳ Implement Stable Diffusion 1.5 training

## Contact & Support

For issues or questions:
- Check `data_pipeline/README.md` for troubleshooting
- Review configuration examples in `.env.example`
- Check AWS IAM permissions if S3 access fails
