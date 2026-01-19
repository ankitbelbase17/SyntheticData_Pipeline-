# Async Image Generation & S3 Upload

This project generates images using the FLUX.2-klein-4b-nvfp4 model and uploads them to S3 asynchronously.

## Setup

1.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Environment Variables:**
    Create a `.env` file in this directory (or set environment variables):
    ```ini
    S3_BUCKET_NAME=your-bucket-name
    S3_REGION=us-east-1
    S3_PREFIX=generated_images
    ```
    Ensure you have AWS credentials configured (e.g., in `~/.aws/credentials` or via `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`).

3.  **Prepare Input:**
    Place your `prompts_combined_1.jsonl` (and others) in this directory.

## Running

**Run the full pipeline (Requires GPU):**
```bash
# Default (nvfp4)
python main.py

# Specify model variant
python main.py --model 4b
python main.py --model 9b
```

**Run a mock simulation (No GPU, No S3 Upload):**
```bash
python mock_run.py
```
This simulates the generation and upload process to verify the logic.

## Project Structure
- `src/`: Source code
  - `generator.py`: Handles FLUX model loading and inference.
  - `s3_uploader.py`: Handles async S3 uploads using `aioboto3`.
  - `parser.py`: Parses JSONL files.
  - `config.py`: Configuration settings.
- `main.py`: Main entry point.
