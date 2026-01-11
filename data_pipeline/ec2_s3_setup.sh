#!/bin/bash

################################################################################
# Zalando Gallery Scraper - EC2 Setup Script
# Sets up EC2 instance for running zalando_gallery_scraper_s3_ec2.py
# Installs all dependencies, configures Chrome, Python, and AWS S3 access
################################################################################

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="/home/ec2-user/zalando-scraper"
VENV_DIR="$PROJECT_DIR/venv"
LOG_FILE="/var/log/zalando_scraper_setup.log"

################################################################################
# Helper Functions
################################################################################

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi
}

detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
    else
        log_error "Cannot detect OS"
        exit 1
    fi
}

################################################################################
# System Setup
################################################################################

setup_system() {
    log_info "Detecting OS..."
    detect_os
    
    case "$OS" in
        amzn|amzn2)
            log_info "Detected Amazon Linux 2"
            update_system_amazon
            install_chrome_amazon
            ;;
        ubuntu)
            log_info "Detected Ubuntu"
            update_system_ubuntu
            install_chrome_ubuntu
            ;;
        *)
            log_error "Unsupported OS: $OS"
            exit 1
            ;;
    esac
}

update_system_amazon() {
    log_info "Updating Amazon Linux system packages..."
    yum update -y >> "$LOG_FILE" 2>&1
    yum install -y \
        python3 python3-pip python3-devel \
        gcc g++ make \
        git wget curl \
        unzip \
        xvfb x11-utils \
        fontconfig dejavu-fonts \
        ca-certificates \
        >> "$LOG_FILE" 2>&1
    log_success "System updated"
}

update_system_ubuntu() {
    log_info "Updating Ubuntu system packages..."
    apt-get update >> "$LOG_FILE" 2>&1
    apt-get upgrade -y >> "$LOG_FILE" 2>&1
    apt-get install -y \
        python3 python3-pip python3-venv python3-dev \
        build-essential \
        git wget curl \
        unzip \
        xvfb x11-utils \
        fonts-dejavu fonts-liberation \
        ca-certificates \
        libglib2.0-0 libxext6 libxrender-dev \
        >> "$LOG_FILE" 2>&1
    log_success "System updated"
}

install_chrome_amazon() {
    log_info "Installing Google Chrome on Amazon Linux..."
    
    # Add Google Chrome repository
    cat > /etc/yum.repos.d/google-chrome.repo << EOF
[google-chrome]
name=google-chrome
baseurl=http://dl.google.com/linux/chrome/rpm/stable/x86_64
enabled=1
gpgcheck=1
gpgkey=https://dl-ssl.google.com/linux/linux_signing_key.pub
EOF
    
    yum install -y google-chrome-stable >> "$LOG_FILE" 2>&1
    log_success "Google Chrome installed"
}

install_chrome_ubuntu() {
    log_info "Installing Google Chrome on Ubuntu..."
    
    # Add Google Chrome repository
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" | tee /etc/apt/sources.list.d/google-chrome.list >> "$LOG_FILE"
    
    curl https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor | tee /usr/share/keyrings/google-chrome-keyring.gpg >> "$LOG_FILE" 2>&1
    
    apt-get update >> "$LOG_FILE" 2>&1
    apt-get install -y google-chrome-stable >> "$LOG_FILE" 2>&1
    log_success "Google Chrome installed"
}

################################################################################
# Python Setup
################################################################################

setup_python() {
    log_info "Setting up Python virtual environment..."
    
    # Create project directory
    mkdir -p "$PROJECT_DIR"
    cd "$PROJECT_DIR"
    
    # Create virtual environment
    python3 -m venv "$VENV_DIR" >> "$LOG_FILE" 2>&1
    
    # Activate virtual environment
    source "$VENV_DIR/bin/activate"
    
    # Upgrade pip
    pip install --upgrade pip setuptools wheel >> "$LOG_FILE" 2>&1
    
    log_success "Python virtual environment created at $VENV_DIR"
}

install_python_dependencies() {
    log_info "Installing Python dependencies..."
    
    source "$VENV_DIR/bin/activate"
    
    # Core dependencies
    pip install --no-cache-dir \
        selenium>=4.0 \
        webdriver-manager \
        Pillow \
        requests \
        boto3 \
        botocore \
        python-dotenv \
        >> "$LOG_FILE" 2>&1
    
    log_success "Python dependencies installed"
}

################################################################################
# AWS S3 Configuration
################################################################################

configure_aws_s3() {
    log_info "Configuring AWS S3 access..."
    
    # Check if using IAM role (preferred for EC2)
    if curl -s http://169.254.169.254/latest/meta-data/iam/security-credentials/ >> "$LOG_FILE" 2>&1; then
        log_success "IAM role detected - will use for S3 access (no credentials needed)"
        return
    fi
    
    log_warning "No IAM role detected"
    log_info "You have two options:"
    log_info "1. Attach IAM role to EC2 instance (RECOMMENDED)"
    log_info "2. Set AWS credentials as environment variables:"
    log_info "   export AWS_ACCESS_KEY_ID='your_access_key'"
    log_info "   export AWS_SECRET_ACCESS_KEY='your_secret_key'"
}

create_env_file() {
    log_info "Creating .env configuration file..."
    
    local env_file="$PROJECT_DIR/.env"
    
    # Check if .env already exists
    if [ -f "$env_file" ]; then
        log_warning ".env already exists at $env_file"
        return
    fi
    
    cat > "$env_file" << 'EOF'
# AWS S3 Configuration
AWS_S3_BUCKET=your-bucket-name
AWS_S3_REGION=us-east-1
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=

# Scraper Configuration
SCRAPER_OUTPUT_DIR=/tmp/vton_gallery_dataset
SCRAPER_MAX_PAGES=None
SCRAPER_MAX_ITEMS=None
SCRAPER_HEADLESS=true
SCRAPER_LOG_LEVEL=INFO
EOF
    
    chmod 600 "$env_file"
    log_success "Configuration file created at $env_file"
    log_warning "IMPORTANT: Edit $env_file and set your AWS_S3_BUCKET and AWS_S3_REGION"
}

################################################################################
# Project Setup
################################################################################

setup_project_directory() {
    log_info "Setting up project directories..."
    
    mkdir -p "$PROJECT_DIR"/{logs,data,results}
    mkdir -p /tmp/vton_gallery_dataset/{products,metadata,progress}
    chmod 777 /tmp/vton_gallery_dataset
    
    log_success "Project directories created"
}

copy_project_files() {
    log_info "Copying project files..."
    
    # Copy Python files from current script directory
    if [ -d "$SCRIPT_DIR/data_pipeline" ]; then
        cp -r "$SCRIPT_DIR/data_pipeline" "$PROJECT_DIR/" >> "$LOG_FILE" 2>&1
        cp "$SCRIPT_DIR/config.py" "$PROJECT_DIR/" >> "$LOG_FILE" 2>&1
        log_success "Project files copied"
    else
        log_warning "data_pipeline directory not found at $SCRIPT_DIR"
        log_info "Make sure to manually copy your project files to $PROJECT_DIR"
    fi
}

################################################################################
# Service Setup (Optional)
################################################################################

setup_systemd_service() {
    log_info "Setting up systemd service (optional)..."
    
    cat > /etc/systemd/system/zalando-scraper.service << EOF
[Unit]
Description=Zalando Gallery Scraper with S3 Upload
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$VENV_DIR/bin"
ExecStart=$VENV_DIR/bin/python $PROJECT_DIR/data_pipeline/zalando_gallery_scraper_s3_ec2.py
Restart=on-failure
RestartSec=10
StandardOutput=append:$PROJECT_DIR/logs/scraper.log
StandardError=append:$PROJECT_DIR/logs/scraper.log

[Install]
WantedBy=multi-user.target
EOF
    
    chmod 644 /etc/systemd/system/zalando-scraper.service
    systemctl daemon-reload
    
    log_success "Systemd service created"
    log_info "To start service: systemctl start zalando-scraper"
    log_info "To enable on boot: systemctl enable zalando-scraper"
    log_info "To view logs: systemctl status zalando-scraper"
}

setup_cron_job() {
    log_info "Setting up cron job (optional)..."
    
    cat > /tmp/zalando_scraper_cron << 'EOF'
# Zalando Scraper - Run daily at 2 AM
0 2 * * * ec2-user cd /home/ec2-user/zalando-scraper && /home/ec2-user/zalando-scraper/venv/bin/python data_pipeline/zalando_gallery_scraper_s3_ec2.py >> logs/scraper_cron.log 2>&1
EOF
    
    crontab -u ec2-user /tmp/zalando_scraper_cron 2>/dev/null || \
        log_warning "Could not set up cron job - run manually if needed"
    
    rm -f /tmp/zalando_scraper_cron
    log_success "Cron job configured"
}

################################################################################
# Verification
################################################################################

verify_installation() {
    log_info "Verifying installation..."
    
    source "$VENV_DIR/bin/activate"
    
    # Check Chrome
    if which google-chrome > /dev/null 2>&1; then
        CHROME_VERSION=$(google-chrome --version)
        log_success "✓ Chrome installed: $CHROME_VERSION"
    else
        log_error "✗ Chrome not found"
        return 1
    fi
    
    # Check Python
    if python3 --version >> "$LOG_FILE" 2>&1; then
        log_success "✓ Python $(python3 --version 2>&1 | awk '{print $2}')"
    else
        log_error "✗ Python not working"
        return 1
    fi
    
    # Check key Python packages
    python3 << 'PYEOF'
import sys
packages = ['selenium', 'webdriver_manager', 'PIL', 'requests', 'boto3']
missing = []
for pkg in packages:
    try:
        __import__(pkg)
    except ImportError:
        missing.append(pkg)
if missing:
    print(f"Missing packages: {', '.join(missing)}")
    sys.exit(1)
PYEOF
    
    if [ $? -eq 0 ]; then
        log_success "✓ All Python packages installed"
    else
        log_error "✗ Some Python packages missing"
        return 1
    fi
    
    # Check AWS connectivity
    if python3 -c "import boto3; boto3.client('s3')" >> "$LOG_FILE" 2>&1; then
        log_success "✓ AWS/boto3 working"
    else
        log_warning "⚠ AWS connectivity check inconclusive (may be IAM role)"
    fi
    
    return 0
}

################################################################################
# Main Execution
################################################################################

main() {
    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║   Zalando Gallery Scraper - EC2 S3 Setup                   ║"
    echo "║   Chrome Headless Mode + AWS S3 Integration                ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    log_info "Setup log: $LOG_FILE"
    
    # Create log directory
    mkdir -p "$(dirname "$LOG_FILE")"
    touch "$LOG_FILE"
    
    # Check prerequisites
    check_root
    
    # Execute setup steps
    setup_system
    setup_python
    install_python_dependencies
    setup_project_directory
    copy_project_files
    configure_aws_s3
    create_env_file
    setup_systemd_service
    setup_cron_job
    
    # Verify installation
    if verify_installation; then
        log_success "Installation completed successfully!"
    else
        log_error "Installation verification failed"
        exit 1
    fi
    
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║         Setup Complete - Next Steps                         ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}1. Configure AWS S3:${NC}"
    echo "   - Edit: $PROJECT_DIR/.env"
    echo "   - Set AWS_S3_BUCKET and AWS_S3_REGION"
    echo "   - OR attach IAM role to EC2 instance (RECOMMENDED)"
    echo ""
    echo -e "${YELLOW}2. Copy project files:${NC}"
    echo "   - Project directory: $PROJECT_DIR"
    echo "   - Virtual environment: $VENV_DIR"
    echo ""
    echo -e "${YELLOW}3. Run the scraper:${NC}"
    echo "   - Manual: source $VENV_DIR/bin/activate && python $PROJECT_DIR/data_pipeline/zalando_gallery_scraper_s3_ec2.py"
    echo "   - Service: systemctl start zalando-scraper"
    echo "   - Cron: Already configured to run daily at 2 AM"
    echo ""
    echo -e "${YELLOW}4. Monitor logs:${NC}"
    echo "   - Setup log: $LOG_FILE"
    echo "   - Service logs: journalctl -u zalando-scraper -f"
    echo "   - Cron logs: $PROJECT_DIR/logs/scraper_cron.log"
    echo ""
    echo -e "${BLUE}Documentation:${NC}"
    echo "   - Scraper: $PROJECT_DIR/data_pipeline/zalando_gallery_scraper_s3_ec2.py"
    echo "   - Config: $PROJECT_DIR/config.py"
    echo ""
}

# Run main setup
main "$@"
