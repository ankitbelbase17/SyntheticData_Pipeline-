# Use official Python image with CUDA support (if GPU needed)
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for Selenium, Chrome, and image processing
RUN apt-get update && \
    apt-get install -y \
    wget gnupg2 curl git build-essential \
    libsm6 libxext6 libxrender-dev \
    libgomp1 && \
    wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt ./

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy all application code
COPY . .

# Create necessary directories
RUN mkdir -p images/human images/cloth outputs/vl_analysis outputs/edited_images outputs/dataset_index

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV QWEN_VL_DEVICE=cpu

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Default command
CMD ["python", "pipeline_orchestrator.py"]
