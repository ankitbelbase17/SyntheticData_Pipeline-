# Data Pipeline Usage Guide

## Quick Start

### Running the Full Pipeline

```python
from data_pipeline.core.pipeline_orchestrator import SyntheticDataPipeline

# Create pipeline instance
pipeline = SyntheticDataPipeline()

# Run full pipeline (with scraping)
results = pipeline.run_full_pipeline(skip_scraping=False)

# Or skip scraping if images already exist
results = pipeline.run_full_pipeline(skip_scraping=True)
```

### Using Individual Modules

#### Web Scraping
```python
from data_pipeline.scrapers.robust_scraper import (
    weighted_sample_sites_hierarchical,
    selenium_crawl_images,
    SCRAPE_SITE_CATEGORIES
)

# Sample sites hierarchically
sampled_sites = weighted_sample_sites_hierarchical(SCRAPE_SITE_CATEGORIES, k=4)

# Crawl images using Selenium
selenium_crawl_images(sampled_sites, image_type="human", max_depth=3, max_images=100)
```

#### Keyword Sampling
```python
from data_pipeline.utils.keyword_sampler import sample_prompt_json, VTON_DICTIONARY

# Sample hierarchical keywords
prompt = sample_prompt_json()
print(prompt)  # Returns JSON with garment, fit, observed_elements, etc.
```

#### Vision-Language Processing
```python
from data_pipeline.models.qwen_vl_processor import QwenVLProcessor, process_and_save_edits

# Initialize processor
processor = QwenVLProcessor()

# Generate edit prompts from images
result = processor.generate_edit_prompt(
    person_image_path="path/to/person.jpg",
    clothing_images=["path/to/cloth.jpg"],
    context_prompt="Your context here"
)

# Or use the full pipeline function
result = process_and_save_edits(
    "path/to/person.jpg",
    ["path/to/cloth.jpg"],
    "context prompt",
    "output.json"
)
```

#### Image Editing
```python
from data_pipeline.models.edit_model_pipeline import process_vl_to_edits

# Process VL outputs and generate edited images
results = process_vl_to_edits(
    vl_analysis_dir="outputs/vl_analysis/",
    output_dir="outputs/edited_images/",
    max_images=10
)
```

#### Image Utilities
```python
from data_pipeline.utils.image_utils import (
    check_aspect_ratio,
    check_min_resolution,
    resize_image,
    save_json_metadata,
    create_dataset_index
)
from PIL import Image

# Validate image
img = Image.open("image.jpg")
if check_aspect_ratio(img) and check_min_resolution(img):
    # Resize and process
    resized = resize_image(img, target_size=(512, 512))
    resized.save("output.jpg")

# Create dataset index
index = create_dataset_index("images/", "index.json")
```

#### Prompt Conversion
```python
from data_pipeline.prompts.mllm_to_vlm_converter import (
    fill_json_placeholders_and_correct,
    mllm_generate_vlm_prompt
)
from data_pipeline.utils.keyword_sampler import sample_prompt_json

# Sample keywords
json_data = sample_prompt_json()

# Fill placeholders and correct implausible combinations
filled_json = fill_json_placeholders_and_correct(json_data)

# Generate VLM prompt
vlm_prompt = mllm_generate_vlm_prompt(filled_json)
```

## Configuration

### Environment Variables

Create a `.env` file in `data_pipeline/`:

```bash
# AWS S3 Configuration
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_S3_BUCKET=your_bucket_name
AWS_DEFAULT_REGION=us-east-1

# API Keys
HF_TOKEN=your_huggingface_token
OPENAI_API_KEY=your_openai_key
GEMINI_API_KEY=your_gemini_key
```

### Configuration File

Edit `data_pipeline/config.py` for:
- Model paths and parameters
- AWS S3 settings
- Output directory paths
- Default hyperparameters

## Module Dependencies

```
data_pipeline/
├── core/
│   └── pipeline_orchestrator.py
│       ├── scrapers/robust_scraper.py
│       ├── models/qwen_vl_processor.py
│       ├── models/edit_model_pipeline.py
│       ├── utils/keyword_sampler.py
│       └── utils/image_utils.py
│
├── models/
│   ├── qwen_vl_processor.py
│   │   └── (depends on transformers, torch, PIL)
│   └── edit_model_pipeline.py
│       └── (depends on diffusers, torch, PIL)
│
├── scrapers/
│   └── robust_scraper.py
│       ├── models/qwen_vl_processor.py
│       └── utils/keyword_sampler.py
│
├── prompts/
│   └── mllm_to_vlm_converter.py
│       └── utils/keyword_sampler.py
│
└── utils/
    ├── keyword_sampler.py
    │   └── keywords_dictionary.py
    └── image_utils.py
```

## Key Classes & Functions

### Pipeline Orchestration
- `SyntheticDataPipeline`: Main orchestrator class
  - `run_full_pipeline(skip_scraping=False)`: Execute full workflow
  - `_run_scraping()`: Stage 1 - Image collection
  - `_run_vl_analysis()`: Stage 2 - VL analysis
  - `_run_editing()`: Stage 3 - Image editing
  - `_create_dataset_index()`: Stage 4 - Indexing

### Web Scraping
- `weighted_sample_sites_hierarchical()`: Hierarchical site sampling
- `selenium_crawl_images()`: Selenium-based image crawling
- `SCRAPE_SITE_CATEGORIES`: Site hierarchy dictionary
- `CLOTHES_DIVERSITY`: Clothing type hierarchy

### Vision-Language Processing
- `QwenVLProcessor`: Qwen 2.5 VL processor class
  - `generate_edit_prompt()`: Generate edit instructions
  - `_build_qwen_prompt()`: Build structured prompt
  - `_parse_vl_response()`: Parse model response

### Image Editing
- `EditModelPipeline`: InstructPix2Pix wrapper
  - `generate_edited_image()`: Edit single image
  - `batch_generate_edits()`: Process multiple VL outputs
- `process_vl_to_edits()`: Full VL-to-edits pipeline

### Utilities
- `check_aspect_ratio()`: Validate image dimensions
- `check_min_resolution()`: Check minimum resolution
- `resize_image()`: Resize with high quality
- `save_json_metadata()`: Save analysis as JSON
- `create_dataset_index()`: Index image datasets

### Keyword Sampling
- `sample_prompt_json()`: Sample complete prompt JSON
- `sample_component_keywords()`: Sample single component
- `weighted_choice()`: Weighted random selection
- `VTON_DICTIONARY`: Complete attribute dictionary

## Output Directories

After running the pipeline, outputs are organized as:

```
outputs/
├── vl_analysis/
│   ├── vl_analysis_0_0.json
│   ├── vl_analysis_0_1.json
│   └── ...
├── edited_images/
│   ├── edited_vl_analysis_0_0.png
│   ├── edited_vl_analysis_0_1.png
│   └── ...
└── dataset_index/
    ├── edited_images_index.json
    └── pipeline_results.json

images/
├── human/
│   ├── image_001.jpg
│   ├── image_002.jpg
│   └── ...
└── cloth/
    ├── item_001.jpg
    ├── item_002.jpg
    └── ...
```

## Testing

Run tests from `data_pipeline/tests/`:

```bash
# Test scrapers
python -m pytest data_pipeline/tests/test_scraper_*.py

# Test accessibility
python data_pipeline/tests/test_website_accessibility.py
```

## Docker Integration

Build and run with Docker Compose:

```bash
docker-compose up -d

# Or with specific service
docker-compose up data_pipeline
```

See root-level `docker-compose.yml` for full configuration.

## Troubleshooting

### Import Errors
Ensure you're importing from the correct module path:
```python
# ✅ Correct
from data_pipeline.utils.keyword_sampler import sample_prompt_json

# ❌ Wrong
from keyword_sampler import sample_prompt_json
```

### Missing Dependencies
Install all requirements:
```bash
pip install -r requirements.txt
```

### S3 Connection Issues
Verify AWS credentials in `.env`:
```bash
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_S3_BUCKET=...
```

### GPU Memory Issues
Reduce batch sizes in `config.py`:
```python
BATCH_SIZE = 2  # Reduce from default
NUM_INFERENCE_STEPS = 30  # Reduce from 50
```

## Performance Tips

1. **Scraping**: Use multiple workers for parallel image download
2. **VL Analysis**: Cache model on first load to avoid repeated initialization
3. **Editing**: Use CPU for batch generation if GPU VRAM is limited
4. **Storage**: Enable S3 uploads to offload storage requirements

## License & Attribution

See root-level `README.md` for project information and dependencies.
