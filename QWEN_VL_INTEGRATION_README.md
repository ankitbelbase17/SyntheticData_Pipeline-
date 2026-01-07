# Synthetic Data Pipeline with Qwen 2.5 VL & Edit-Based Models

Complete end-to-end pipeline for synthetic virtual try-on dataset creation combining:
- **Robust Web Scraping** (Selenium + Hierarchical Site Crawling)
- **Qwen 2.5 VL** (Multi-image analysis & prompt generation)
- **InstructPix2Pix** (Instruction-guided image editing)

## Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  STEP 1: SCRAPING                                               │
│  ├─ Hierarchical Site Categories (ecommerce, marketplace, etc) │
│  ├─ Probabilistic Site Sampling                                │
│  ├─ Selenium Crawler (Deep crawling with pagination)           │
│  └─ Output: images/human/, images/cloth/                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  STEP 2: VL ANALYSIS (Qwen 2.5 VL)                              │
│  ├─ Multi-image input (person + clothing)                      │
│  ├─ Structured analysis (body, pose, garment, transitions)     │
│  ├─ Strong prompt generation for edit models                   │
│  └─ Output: outputs/vl_analysis/ (JSON with edit prompts)      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  STEP 3: EDITING (InstructPix2Pix)                              │
│  ├─ Take VL prompts + person image                             │
│  ├─ Generate edited images (virtual try-on)                    │
│  └─ Output: outputs/edited_images/                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  STEP 4: INDEXING & ORGANIZATION                               │
│  └─ Output: outputs/dataset_index/ + metadata                  │
└─────────────────────────────────────────────────────────────────┘
```

## Key Features

### 1. Hierarchical Site Management
Sites organized by category with probabilities:
- **ecommerce** (0.45): Amazon, Zalando, ASOS, etc.
- **marketplace** (0.15): Depop, Vinted, Facebook Marketplace
- **stock_photo** (0.15): Getty Images, Unsplash, Pexels, Pixabay
- **social_media** (0.10): Instagram, Pinterest, Flickr, Reddit
- **fashion_blog_magazine** (0.10): Vogue, Harper's Bazaar, GQ, Elle
- **creative_commons** (0.05): Wikimedia, Flickr CC

### 2. Qwen 2.5 VL Multi-Image Analysis
Takes person + clothing images and generates:
```json
{
    "person_analysis": {
        "body_shape": "...",
        "skin_tone": "...",
        "pose": "...",
        "visible_characteristics": ["..."],
        "standing_position": "front|side|back"
    },
    "current_clothing": {...},
    "target_clothing": {...},
    "transition_notes": {...},
    "edit_instructions": ["instruction 1", "instruction 2", ...],
    "edit_strength": "light|medium|strong",
    "confidence_score": 0.0-1.0
}
```

### 3. Edit-Based Prompt Generation
Converts VL analysis into strong prompts for InstructPix2Pix:
```
"Replace the clothing in the image with [target_garment] that is [fit] and [color].
The person has a [body_shape] body shape and is in [pose] pose.
Ensure [fabric_drape] and [color_harmony]. [Additional instructions...]"
```

### 4. Diversities Covered
- **Garment attributes**: type, material, color, pattern, surface detail
- **Fit & silhouette**: overall fit, length, neckline, waist
- **Observed elements**: age group, gender, body shape, skin tone
- **Body characteristics**: prosthetic limb, wheelchair, tattoo, hijab, etc.
- **Scene context**: background, lighting, image quality
- **Style & aesthetic**: casual, formal, business, streetwear, etc.

## Installation

```bash
# Clone repository
git clone <repo_url>
cd SyntheticData_Pipeline

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install deep learning packages
pip install torch torchvision transformers diffusers pillow selenium

# Download models (optional, will download on first use)
python -c "from qwen_vl_processor import QwenVLProcessor; QwenVLProcessor()"
```

## Configuration

Edit `config.py` to set:
```python
HF_TOKEN = "your_huggingface_token"
QWEN_VL_MODEL = "Qwen/Qwen2-VL-7B-Instruct"
EDIT_MODEL = "timbrooks/instruct-pix2pix"
```

## Usage

### Option 1: Full Pipeline (Recommended)
```bash
python pipeline_orchestrator.py
```

This runs:
1. Scraping (hierarchical site sampling + Selenium crawling)
2. Qwen VL analysis (multi-image prompts)
3. InstructPix2Pix editing (synthetic image generation)
4. Dataset indexing

### Option 2: Individual Steps

**Scraping:**
```python
from robust_scraper import robust_scraper
robust_scraper()
```

**VL Analysis:**
```python
from qwen_vl_processor import process_and_save_edits
result = process_and_save_edits(
    person_image_path="images/human/person.jpg",
    clothing_images=["images/cloth/shirt.jpg"],
    context_prompt="Virtual try-on task...",
    output_json_path="outputs/vl_analysis/result.json"
)
```

**Editing:**
```python
from edit_model_pipeline import process_vl_to_edits
results = process_vl_to_edits(
    vl_analysis_dir="outputs/vl_analysis/",
    output_dir="outputs/edited_images/",
    max_images=10
)
```

## Output Structure

```
SyntheticData_Pipeline/
├── images/
│   ├── human/              # Scraped person images
│   └── cloth/              # Scraped clothing images
├── outputs/
│   ├── vl_analysis/        # Qwen VL analysis JSONs (with edit prompts)
│   ├── edited_images/      # InstructPix2Pix generated images
│   └── dataset_index/      # Dataset metadata and indexing
├── config.py               # Configuration & API keys
├── model.py                # Model loading utilities
├── utils.py                # Image utilities
├── keyword_sampler.py      # Hierarchical keyword sampling
├── robust_scraper.py       # Selenium crawler with site hierarchy
├── qwen_vl_processor.py    # Qwen VL multi-image analysis
├── edit_model_pipeline.py  # InstructPix2Pix pipeline
└── pipeline_orchestrator.py # Full pipeline orchestration
```

## Key Files

| File | Purpose |
|------|---------|
| `pipeline_orchestrator.py` | Main entry point; orchestrates full pipeline |
| `robust_scraper.py` | Scrapes images with hierarchical site management |
| `qwen_vl_processor.py` | Analyzes person+clothing with Qwen VL; generates strong edit prompts |
| `edit_model_pipeline.py` | Applies InstructPix2Pix for image editing |
| `keyword_sampler.py` | Hierarchical sampling of garment, pose, scene, etc. |
| `model.py` | Centralized model loading utilities |
| `utils.py` | Image processing and metadata utilities |
| `config.py` | Configuration, API keys, model names |

## Qwen VL Integration Details

### Input
- **Person image**: Current outfit, pose, body visible
- **Clothing image(s)**: Target garment(s)
- **Context prompt**: Task description with sampled keywords

### Processing
1. Load images with Qwen processor
2. Build multi-image prompt with structured task description
3. Generate with model (temperature=0.7, top_p=0.9)
4. Parse JSON response

### Output (Structured JSON)
```json
{
    "source": {
        "person_image": "...",
        "clothing_images": ["..."]
    },
    "vl_analysis": {
        "person_analysis": {...},
        "current_clothing": {...},
        "target_clothing": {...},
        "transition_notes": {...},
        "edit_instructions": [...],
        "edit_strength": "medium",
        "confidence_score": 0.85
    },
    "edit_prompt_for_model": "Replace the clothing in the image with [strong, detailed prompt]...",
    "metadata": {
        "model": "Qwen2.5-VL",
        "task": "virtual_try_on"
    }
}
```

## Edit-Based Model Integration

### InstructPix2Pix Parameters
- **num_inference_steps**: 50 (higher = better quality, slower)
- **image_guidance_scale**: 1.5 (strength of source image conditioning)
- **guidance_scale**: 7.5 (strength of text guidance)

### Prompt Example
```
"Replace the clothing in the image with a blue cotton t-shirt that is regular-fitting. 
The person has a mesomorph body shape and is standing in a front-facing pose. 
Ensure natural fabric drape and color harmony with warm tones. 
Add subtle shadows at garment folds. Maintain consistent lighting with the background."
```

## Performance Tips

1. **GPU Memory**: For Qwen VL (7B) + InstructPix2Pix, use GPU with ≥16GB VRAM
2. **Batch Processing**: Process VL pairs in batches (default 5-10)
3. **Max Depth Crawling**: Limit to depth 3-4 to avoid excessive crawling
4. **Rate Limiting**: Selenium includes minimal delays; adjust in `robust_scraper.py` if needed

## Testing

```bash
python test/test.py
```

Tests cover:
- Keyword sampling
- Image aspect ratio checking
- Basic utility functions

## Future Enhancements

- [ ] Additional specialized models (pose transfer, body reshaping, relighting)
- [ ] Parallel processing for multi-GPU setups
- [ ] API integration (real-time Qwen VL API instead of local model)
- [ ] More site categories and domain-specific scrapers
- [ ] Advanced VL correction rules for implausible combinations
- [ ] Evaluation metrics for synthetic dataset quality

## Troubleshooting

### Memory Issues
```python
# Reduce batch size in config.py
BATCH_SIZE = 2  # Instead of 5
```

### Model Download Issues
```bash
# Manually download with HF CLI
huggingface-cli download Qwen/Qwen2-VL-7B-Instruct
```

### Scraping Failures
- Check site accessibility (some sites block scraping)
- Increase delays: `time.sleep(2)` in `selenium_crawl_images()`
- Use VPN if geo-restricted

## References

- [Qwen VL Documentation](https://huggingface.co/Qwen/Qwen2-VL-7B-Instruct)
- [InstructPix2Pix Paper](https://arxiv.org/abs/2211.09800)
- [Diffusers Library](https://huggingface.co/docs/diffusers)
- [Selenium WebDriver](https://www.selenium.dev/)

## License

This project is provided as-is. Ensure compliance with terms of service for all scraped websites and models used.

## Contact & Support

For issues, questions, or contributions, please open an issue or contact the maintainers.
