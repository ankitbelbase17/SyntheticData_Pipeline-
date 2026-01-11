# Deployment Scripts

This directory contains setup and deployment scripts for the Zalando Gallery Scraper with AWS S3 integration.

## Contents

### `ec2_s3_setup.sh`
Complete automation script for setting up AWS EC2 instances with:
- System dependencies (Chrome, Python, development tools)
- Python virtual environment
- All required Python packages
- AWS S3 configuration (IAM roles or credentials)
- Systemd service setup
- Optional daily cron job scheduling

## EC2 Setup Guide

### Quick Start

```bash
# 1. Copy script to EC2
scp -i your-key.pem data_pipeline/deployment/ec2_s3_setup.sh ec2-user@your-ec2-ip:/home/ec2-user/

# 2. Run setup (requires sudo)
ssh -i your-key.pem ec2-user@your-ec2-ip
chmod +x ec2_s3_setup.sh
sudo ./ec2_s3_setup.sh

# 3. Configure AWS credentials
vim /home/ec2-user/zalando-scraper/.env

# 4. Run scraper
systemctl start zalando-scraper
# OR
cd /home/ec2-user/zalando-scraper
source venv/bin/activate
python data_pipeline/zalando_gallery_scraper_s3_ec2.py
```

### Prerequisites

- AWS EC2 instance (Amazon Linux 2 or Ubuntu)
- Root/sudo access
- Internet connectivity
- Optional: IAM role with S3 access permissions

### What Gets Installed

1. **System Packages:**
   - Python 3.9+
   - Google Chrome (stable)
   - Development tools (gcc, g++, make)
   - X11 libraries for headless rendering

2. **Python Packages:**
   - selenium (browser automation)
   - webdriver-manager (Chrome driver management)
   - Pillow (image processing)
   - requests (HTTP client)
   - boto3 (AWS S3 client)
   - python-dotenv (environment configuration)

3. **Services:**
   - Systemd service for automated scraping
   - Cron job for daily scheduling

### Configuration

After setup, edit `/home/ec2-user/zalando-scraper/.env`:

```env
# AWS S3 Configuration
AWS_S3_BUCKET=your-bucket-name
AWS_S3_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key

# Scraper Configuration
SCRAPER_OUTPUT_DIR=/tmp/vton_gallery_dataset
SCRAPER_MAX_PAGES=None
SCRAPER_MAX_ITEMS=None
SCRAPER_HEADLESS=true
SCRAPER_LOG_LEVEL=INFO
```

**Recommended:** Use IAM roles instead of credentials. Attach an IAM role to the EC2 instance with S3 access.

### Running the Scraper

#### Option 1: Manual (Development)
```bash
cd /home/ec2-user/zalando-scraper
source venv/bin/activate
python data_pipeline/zalando_gallery_scraper_s3_ec2.py
```

#### Option 2: Systemd Service (Production)
```bash
# Start
sudo systemctl start zalando-scraper

# Stop
sudo systemctl stop zalando-scraper

# View status
sudo systemctl status zalando-scraper

# View logs
sudo journalctl -u zalando-scraper -f
```

#### Option 3: Scheduled (Cron)
- Automatically runs daily at 2:00 AM
- Logs to `/home/ec2-user/zalando-scraper/logs/scraper_cron.log`

### Monitoring

```bash
# Check service status
systemctl status zalando-scraper

# Follow service logs
journalctl -u zalando-scraper -f

# Check cron logs
tail -f /home/ec2-user/zalando-scraper/logs/scraper_cron.log

# Check S3 uploads
aws s3 ls s3://your-bucket-name/products/ --recursive
```

### Troubleshooting

#### Chrome not found
```bash
google-chrome --version
sudo yum install google-chrome-stable  # Amazon Linux
sudo apt-get install google-chrome-stable  # Ubuntu
```

#### Python packages missing
```bash
source /home/ec2-user/zalando-scraper/venv/bin/activate
pip install -r requirements.txt
```

#### AWS S3 access denied
- Verify IAM role is attached: `curl http://169.254.169.254/latest/meta-data/iam/security-credentials/`
- Or set credentials in `.env` file
- Verify S3 bucket name is correct

#### Disk space issues
- Script auto-deletes local files after S3 upload
- Clear `/tmp/vton_gallery_dataset/` if needed
- Monitor: `df -h`

### Logs

- **Setup log:** `/var/log/zalando_scraper_setup.log`
- **Service logs:** `journalctl -u zalando-scraper`
- **Cron logs:** `/home/ec2-user/zalando-scraper/logs/scraper_cron.log`
- **Scraper logs:** `/home/ec2-user/zalando-scraper/logs/scraper.log`

### Security Best Practices

1. **IAM Roles (Recommended):**
   - Use IAM roles instead of storing credentials
   - Attach only necessary S3 permissions
   - Regularly rotate access keys

2. **Environment Variables:**
   - Use `.env` file (not tracked in git)
   - Restrict file permissions: `chmod 600 .env`
   - Never commit credentials

3. **EC2 Security:**
   - Use security groups to restrict access
   - Keep security groups narrow
   - Use VPC for isolation

4. **S3 Bucket:**
   - Enable versioning
   - Enable encryption (SSE-S3 or KMS)
   - Set bucket policies to prevent public access
   - Enable logging

### Maintenance

```bash
# Update Python packages
source /home/ec2-user/zalando-scraper/venv/bin/activate
pip install --upgrade selenium webdriver-manager boto3

# Update Chrome
sudo yum update -y google-chrome-stable

# Clean up old data
rm -rf /tmp/vton_gallery_dataset/*
```

### Uninstall

```bash
# Stop service
sudo systemctl stop zalando-scraper
sudo systemctl disable zalando-scraper

# Remove service file
sudo rm /etc/systemd/system/zalando-scraper.service
sudo systemctl daemon-reload

# Remove project directory
rm -rf /home/ec2-user/zalando-scraper

# Remove cron job
sudo crontab -u ec2-user -r
```
