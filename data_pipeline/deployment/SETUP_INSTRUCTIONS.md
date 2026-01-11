# EC2 S3 Setup - Complete Instructions

## Overview

This document provides step-by-step instructions for deploying the Zalando Gallery Scraper to AWS EC2 with automated S3 uploads.

## Prerequisites

1. **AWS Account** with:
   - EC2 instance (Amazon Linux 2 or Ubuntu)
   - S3 bucket created
   - IAM role with S3 permissions (or access keys)

2. **Local Machine** with:
   - SSH key pair (.pem file)
   - SSH client configured
   - Git (optional, for cloning repository)

3. **Network Access**:
   - EC2 security group allows SSH (port 22)
   - EC2 can access internet (for Chrome, Python packages)

## Step 1: Create S3 Bucket

```bash
# Option 1: AWS Console
# 1. Go to S3 dashboard
# 2. Click "Create bucket"
# 3. Enter bucket name (e.g., zalando-gallery-scraper)
# 4. Select region (e.g., us-east-1)
# 5. Click "Create"

# Option 2: AWS CLI
aws s3 mb s3://zalando-gallery-scraper --region us-east-1
```

## Step 2: Create IAM Role (Recommended)

```bash
# Option 1: AWS Console
# 1. Go to IAM dashboard
# 2. Click "Roles" > "Create role"
# 3. Select "EC2" as trusted entity
# 4. Search for "AmazonS3FullAccess" (or custom policy)
# 5. Name: "EC2-Zalando-Scraper"
# 6. Create role

# Option 2: AWS CLI
aws iam create-role \
  --role-name EC2-Zalando-Scraper \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "ec2.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

aws iam attach-role-policy \
  --role-name EC2-Zalando-Scraper \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
```

## Step 3: Launch EC2 Instance

```bash
# Option 1: AWS Console
# 1. Go to EC2 dashboard
# 2. Click "Launch instances"
# 3. Select "Amazon Linux 2" or "Ubuntu Server"
# 4. Instance type: t3.medium or t3.large (for Chrome/Selenium)
# 5. Under "Advanced details", set IAM instance profile to "EC2-Zalando-Scraper"
# 6. Configure storage: 20 GB minimum
# 7. Configure security group (allow SSH from your IP)
# 8. Review and launch
# 9. Select/create key pair

# Option 2: AWS CLI
aws ec2 run-instances \
  --image-id ami-0c02fb55956c7d316 \
  --instance-type t3.medium \
  --key-name your-key-pair \
  --iam-instance-profile Name=EC2-Zalando-Scraper \
  --security-groups default \
  --region us-east-1
```

## Step 4: Connect to EC2

```bash
# Get public IP from AWS console or:
aws ec2 describe-instances --filters "Name=instance-state-name,Values=running" --query 'Reservations[].Instances[].PublicIpAddress' --output text

# SSH into instance
ssh -i /path/to/your-key.pem ec2-user@your-ec2-public-ip
# or for Ubuntu:
ssh -i /path/to/your-key.pem ubuntu@your-ec2-public-ip
```

## Step 5: Setup Project

```bash
# On EC2 instance:

# Option A: Clone from repository
git clone https://github.com/your-repo/SyntheticData_Pipeline.git
cd SyntheticData_Pipeline

# Option B: Download setup script
wget https://raw.githubusercontent.com/your-repo/SyntheticData_Pipeline/main/data_pipeline/deployment/ec2_s3_setup.sh
chmod +x ec2_s3_setup.sh

# Run setup
sudo ./ec2_s3_setup.sh
```

## Step 6: Configure S3

```bash
# Edit configuration file
vim /home/ec2-user/zalando-scraper/.env

# Update with your S3 details:
AWS_S3_BUCKET=your-bucket-name
AWS_S3_REGION=us-east-1
# AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are optional if using IAM role
```

## Step 7: Verify Installation

```bash
# Check Chrome
google-chrome --version

# Check Python packages
source /home/ec2-user/zalando-scraper/venv/bin/activate
python -c "import selenium, boto3; print('OK')"

# Test S3 access
aws s3 ls your-bucket-name

# Test scraper (limited run)
python /home/ec2-user/zalando-scraper/data_pipeline/zalando_gallery_scraper_s3_ec2.py
```

## Step 8: Run Scraper

### Manual Run
```bash
cd /home/ec2-user/zalando-scraper
source venv/bin/activate
python data_pipeline/zalando_gallery_scraper_s3_ec2.py
```

### As Service
```bash
# Start
sudo systemctl start zalando-scraper

# View status
sudo systemctl status zalando-scraper

# View logs
sudo journalctl -u zalando-scraper -f

# Enable on boot
sudo systemctl enable zalando-scraper
```

### Scheduled (Daily at 2 AM)
```bash
# Check cron
sudo crontab -u ec2-user -l

# View cron logs
tail -f /home/ec2-user/zalando-scraper/logs/scraper_cron.log
```

## Step 9: Monitor & Maintain

```bash
# Check S3 bucket for uploads
aws s3 ls s3://your-bucket-name/ --recursive --human-readable

# Monitor scraper logs
sudo journalctl -u zalando-scraper -f

# Check disk usage
df -h

# Check memory usage
free -h

# View instance details
aws ec2 describe-instances --instance-ids i-xxxxxxxxx --query 'Reservations[].Instances[0]'
```

## Configuration Options

### Scraper Parameters

Edit in `zalando_gallery_scraper_s3_ec2.py`:

```python
# In main() function:
scraper.scrape_sale_page(
    sale_url,
    max_pages=2,      # None for all pages
    max_items=10      # None for unlimited
)
```

### Different URLs

```python
# Women's Dresses
sale_url = "https://www.zalando.co.uk/womens-dresses-sale/"

# Men's Shirts
sale_url = "https://www.zalando.co.uk/mens-shirts-sale/"

# All Sale Items
sale_url = "https://www.zalando.co.uk/sale/"
```

### Chrome Options

Edit in `init_driver()`:

```python
chrome_options.add_argument('--window-size=1920,1080')  # Change resolution
chrome_options.add_argument('--disable-gpu')  # Already set for EC2
chrome_options.add_argument('--headless=new')  # Modern headless mode
```

## Troubleshooting

### Issue: "Chrome not found"
```bash
sudo yum update -y
sudo yum install google-chrome-stable
google-chrome --version
```

### Issue: "Cannot connect to S3"
```bash
# Check IAM role
curl http://169.254.169.254/latest/meta-data/iam/security-credentials/

# Or set credentials in .env
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret

# Test connection
aws s3 ls your-bucket-name
```

### Issue: "Disk space full"
```bash
# Check usage
df -h

# Clear temp directory
sudo rm -rf /tmp/vton_gallery_dataset/*

# Delete old logs
sudo rm -rf /home/ec2-user/zalando-scraper/logs/scraper.log.*
```

### Issue: "Service not starting"
```bash
# Check service status
sudo systemctl status zalando-scraper

# View service logs
sudo journalctl -u zalando-scraper -n 50

# Check service file
cat /etc/systemd/system/zalando-scraper.service

# Restart service
sudo systemctl restart zalando-scraper
```

## Cost Optimization

1. **Instance Type**: Use t3.medium or t3.small with burstable performance
2. **Spot Instances**: 70% savings, suitable for batch jobs
3. **Scheduled Start/Stop**: Stop instance when not needed
4. **S3 Lifecycle**: Archive old data to Glacier

```bash
# Stop instance
aws ec2 stop-instances --instance-ids i-xxxxxxxxx

# Start instance
aws ec2 start-instances --instance-ids i-xxxxxxxxx
```

## Security Checklist

- [ ] IAM role attached to EC2 instance
- [ ] S3 bucket has encryption enabled
- [ ] Security group restricts SSH access
- [ ] .env file is not committed to git
- [ ] .env file permissions: `chmod 600`
- [ ] Regular backups of S3 data
- [ ] CloudWatch monitoring enabled
- [ ] EC2 instance in private subnet (optional)

## Next Steps

1. **Automate**: Use Lambda or EventBridge for scheduled runs
2. **Monitor**: Set up CloudWatch alarms for failures
3. **Scale**: Use Auto Scaling or multiple instances
4. **Analyze**: Process scraped data with Lambda/Glue
5. **Backup**: Enable S3 versioning and replication

## Support

- **Logs**: `/var/log/zalando_scraper_setup.log`
- **Documentation**: See `README.md` in this directory
- **Scraper Code**: `data_pipeline/zalando_gallery_scraper_s3_ec2.py`
