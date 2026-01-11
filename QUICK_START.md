# Quick Start Guide - AWS S3 Integration

## 30-Second Setup

### 1. Add AWS Credentials

```bash
# Copy environment template
cp data_pipeline/.env.example data_pipeline/.env

# Edit with your IAM credentials (use a text editor)
# Set these values:
# AWS_ACCESS_KEY_ID=AKIA1234567890ABCDEF
# AWS_SECRET_ACCESS_KEY=abcdefg1234567890ABC...
# AWS_S3_BUCKET=your-synthetic-data-bucket
# AWS_S3_REGION=us-east-1
```

### 2. Install Dependencies

```bash
pip install boto3 selenium pillow python-dotenv undetected-chromedriver requests
```

### 3. Run Scraper

```bash
cd data_pipeline
python zalando_gallery_scraper_s3.py
```

## Minimal Configuration (.env)

```
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_S3_BUCKET=your-bucket-name
AWS_S3_REGION=us-east-1
```

## Data Flow

```
Zalando Website
    ↓
Local Download (temporary)
    ↓
Image Processing & Validation
    ↓
AWS S3 Upload
    ↓
Metadata JSON to S3
    ↓
Progress Checkpoint (local)
```

## Output Locations

**Local** (temporary cache):
```
data_pipeline/vton_gallery_dataset/
├── products/
├── metadata/
└── progress/
```

**S3** (permanent storage):
```
s3://your-bucket/
├── products/{product_id}/{image_00.jpg}
└── metadata/{product_id}.json
```

## Configuration Options

**In `data_pipeline/config.py`** or **in `.env`**:

```python
# Scraping scope
ZALANDO_SCRAPER_MAX_PAGES = 0  # 0 = all pages
ZALANDO_SCRAPER_MAX_ITEMS = 0  # 0 = no limit

# Browser
ZALANDO_SCRAPER_HEADLESS = False  # True for background

# Storage
ZALANDO_USE_S3 = True  # Save to S3

# Request delays (seconds)
ZALANDO_SCRAPER_DELAY_MIN = 2
ZALANDO_SCRAPER_DELAY_MAX = 4
```

## Verify Setup

```bash
python -c "
import sys
sys.path.insert(0, 'data_pipeline')
from config import AWS_S3_BUCKET, AWS_ACCESS_KEY_ID
import boto3

if not AWS_ACCESS_KEY_ID:
    print('✗ AWS credentials not configured')
else:
    try:
        s3 = boto3.client('s3')
        s3.head_bucket(Bucket=AWS_S3_BUCKET)
        print(f'✓ AWS S3 configured: {AWS_S3_BUCKET}')
    except Exception as e:
        print(f'✗ S3 connection failed: {e}')
"
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: boto3` | `pip install boto3` |
| `Access denied to S3` | Check IAM credentials and bucket name |
| `Scraper hangs` | Set `ZALANDO_SCRAPER_HEADLESS=False` to see browser |
| `SSL error` | Usually temporary; try again or check network |

## Directory Structure

```
SyntheticData_Pipeline-/
├── data_pipeline/              ← Main directory
│   ├── config.py              ← Configuration
│   ├── .env                   ← Your credentials (edit this)
│   ├── .env.example           ← Template (don't edit)
│   ├── zalando_gallery_scraper_s3.py  ← Main script
│   ├── README.md              ← Full documentation
│   └── vton_gallery_dataset/  ← Local output
│
├── experiments/               ← Experiment code (future)
│   ├── config.py
│   └── README.md
│
└── PROJECT_REORGANIZATION.md  ← Detailed changes
```

## Production Tips

1. **Set `ZALANDO_SCRAPER_HEADLESS=True`** for 2-3x speedup
2. **Use smaller delay values** (1-2 seconds minimum)
3. **Monitor S3 bucket size** - set `ZALANDO_SCRAPER_MAX_ITEMS` if needed
4. **Run on EC2/Server** for 24/7 scraping
5. **Enable S3 bucket lifecycle** for cost optimization

## Need Help?

1. Check `data_pipeline/README.md` for detailed guide
2. Review `.env.example` for all available options
3. Check logs in `data_pipeline/` for errors
4. Verify S3 bucket exists and credentials are correct

## Environment Variables Reference

| Variable | Type | Default | Example |
|----------|------|---------|---------|
| `AWS_S3_BUCKET` | str | - | `my-vton-bucket` |
| `AWS_S3_REGION` | str | `us-east-1` | `eu-west-1` |
| `AWS_ACCESS_KEY_ID` | str | - | `AKIA...` |
| `AWS_SECRET_ACCESS_KEY` | str | - | `abcd...` |
| `ZALANDO_USE_S3` | bool | `True` | `False` |
| `ZALANDO_SCRAPER_HEADLESS` | bool | `False` | `True` |
| `ZALANDO_SCRAPER_MAX_PAGES` | int | `0` | `10` |
| `ZALANDO_SCRAPER_MAX_ITEMS` | int | `0` | `100` |

## Get Started Now

```bash
# 1. Setup
cp data_pipeline/.env.example data_pipeline/.env
# (Edit .env with your AWS credentials)

# 2. Test
python -c "import boto3; print('✓ Ready')"

# 3. Run
cd data_pipeline && python zalando_gallery_scraper_s3.py
```

Done! 🚀
