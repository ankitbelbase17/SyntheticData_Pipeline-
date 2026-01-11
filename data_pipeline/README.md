# Data Pipeline

This directory contains the main data collection and preprocessing pipeline for the Synthetic Data for Virtual Try-On project.

## Overview

The data pipeline includes:
- **Web Scraping**: Zalando product gallery scraper
- **Image Processing**: Quality checks and resizing
- **Cloud Storage**: AWS S3 integration for scalable storage
- **Metadata Management**: JSON-based dataset indexing

## Features

- **Zalando Gallery Scraper**: Extracts only main product gallery images (ignoring color variants)
- **AWS S3 Support**: Automatic upload of images and metadata to S3
- **Progress Tracking**: Resume scraping from checkpoint
- **Quality Validation**: Image dimension and aspect ratio checks
- **Logging**: Comprehensive logging for debugging and monitoring

## Directory Structure

```
data_pipeline/
├── config.py                     # Main configuration with S3 settings
├── .env.example                  # Environment variables template
├── zalando_gallery_scraper_s3.py # Zalando scraper with S3 support
├── README.md                     # This file
└── vton_gallery_dataset/         # Local output (temporary cache)
    ├── products/                 # Downloaded product images
    ├── metadata/                 # JSON metadata files
    └── progress/                 # Scraping progress tracking
```

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Required packages:
- `boto3` - AWS SDK for Python
- `undetected-chromedriver` - Stealth Chrome automation
- `selenium` - Web browser automation
- `pillow` - Image processing
- `python-dotenv` - Environment variable management
- `requests` - HTTP requests

### 2. Configure AWS Credentials

#### Option A: Using .env file (Development)

1. Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

2. Fill in your AWS IAM user credentials:
```
AWS_ACCESS_KEY_ID=AKIA1234567890ABCDEF
AWS_SECRET_ACCESS_KEY=abcdefg1234567890ABCDEFGHIJKLMNOPQRST+/
AWS_S3_BUCKET=your-synthetic-data-bucket
AWS_S3_REGION=us-east-1
```

#### Option B: Using AWS CLI Configuration (Production)

```bash
aws configure
```

This creates `~/.aws/credentials` with your credentials.

#### Option C: Using Environment Variables

```bash
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"
export AWS_S3_BUCKET="your-bucket-name"
export AWS_S3_REGION="us-east-1"
```

### 3. Create S3 Bucket

If you don't have a bucket yet, create one:

```bash
aws s3 mb s3://your-synthetic-data-bucket --region us-east-1
```

### 4. Verify AWS Access

Test your S3 connection:

```bash
python -c "
from config import AWS_S3_BUCKET, AWS_S3_REGION
import boto3
s3 = boto3.client('s3', region_name=AWS_S3_REGION)
s3.head_bucket(Bucket=AWS_S3_BUCKET)
print(f'✓ Access to S3 bucket: {AWS_S3_BUCKET}')
"
```

## Usage

### Run Zalando Scraper (with S3)

```bash
python zalando_gallery_scraper_s3.py
```

### Configuration Options

Edit `config.py` or set environment variables:

```python
# Maximum pages to scrape
ZALANDO_SCRAPER_MAX_PAGES = 0  # 0 = all pages

# Maximum items to scrape
ZALANDO_SCRAPER_MAX_ITEMS = 0  # 0 = no limit

# Run in headless mode
ZALANDO_SCRAPER_HEADLESS = False  # Set True for background execution

# Use S3 for storage
ZALANDO_USE_S3 = True  # Set False for local-only mode
```

### Test Mode (Limited Scraping)

To test with a small dataset (5 items, 2 pages), the scraper is configured in test mode by default. Change `max_pages=2, max_items=5` to `max_pages=None, max_items=None` for production scraping.

### Resume from Checkpoint

The scraper automatically saves progress. To resume:

```bash
python zalando_gallery_scraper_s3.py
```

It will skip previously scraped URLs and continue from where it left off.

## Output Structure

### S3 Bucket Organization

```
s3://your-synthetic-data-bucket/
├── products/
│   ├── product-id-1/
│   │   ├── image_00.jpg
│   │   ├── image_01.jpg
│   │   └── image_02.jpg
│   ├── product-id-2/
│   │   └── image_00.jpg
│   └── ...
├── metadata/
│   ├── product-id-1.json
│   ├── product-id-2.json
│   └── ...
└── ...
```

### Metadata Format

```json
{
  "item_id": 0,
  "product_id": "product-id-1",
  "source": "zalando_gallery",
  "title": "Product Title",
  "url": "https://www.zalando.co.uk/...",
  "product_directory": "/local/path/to/products/product-id-1",
  "images": [
    {
      "filename": "image_00.jpg",
      "url": "https://...",
      "size": "512x512",
      "index": 0,
      "s3_key": "products/product-id-1/image_00.jpg"
    },
    ...
  ],
  "total_images": 3,
  "scraped_at": "2026-01-11T10:30:45.123456",
  "storage": "s3"
}
```

## AWS IAM User Permissions

Ensure your IAM user has the following S3 permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
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
  ]
}
```

## Troubleshooting

### "Access denied to S3 bucket"
- Verify IAM credentials are correct
- Check bucket name spelling
- Ensure IAM user has S3 permissions

### "SSL: CERTIFICATE_VERIFY_FAILED"
- This is typically a Chrome/Selenium issue
- Try: `pip install --upgrade undetected-chromedriver`
- Or set environment variable: `PYTHONHTTPSVERIFY=0`

### Images not uploading to S3
- Check AWS credentials
- Verify bucket exists and is accessible
- Check network connectivity
- Review logs for detailed error messages

### Scraper too slow
- Increase `ZALANDO_SCRAPER_DELAY_MIN/MAX` to reduce delays
- Set `ZALANDO_SCRAPER_HEADLESS=True`
- Use multiple scraper instances with different URL ranges

## Performance Tips

1. **Use Headless Mode**: Set `ZALANDO_SCRAPER_HEADLESS=True` for 2-3x speedup
2. **Adjust Delays**: Reduce `ZALANDO_SCRAPER_DELAY_MIN/MAX` but don't go below 1 second
3. **Parallel Downloads**: Increase `NUM_DOWNLOAD_WORKERS` if network allows
4. **S3 Upload**: Happens in background; doesn't block image processing

## Security

- **Never commit `.env` with real credentials**
- Use AWS IAM users (not root account)
- Rotate access keys regularly
- Use S3 bucket versioning and lifecycle policies
- Enable S3 bucket encryption

## Next Steps

1. Configure AWS credentials (.env file)
2. Create S3 bucket
3. Run scraper in test mode
4. Monitor logs and S3 uploads
5. Scale to full production scraping

## Additional Resources

- [AWS S3 Documentation](https://docs.aws.amazon.com/s3/)
- [Boto3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
- [IAM User Security Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
