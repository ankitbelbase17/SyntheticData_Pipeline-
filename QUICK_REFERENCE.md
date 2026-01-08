# Quick Reference Card: Qwen 2.5 VL + InstructPix2Pix Pipeline

## 🚀 Quick Start

### Option 1: Full Automated Pipeline (Recommended)
```bash
python pipeline_orchestrator.py
```
Runs: Scraping → VL Analysis → Image Editing → Indexing

### Option 2: Step-by-Step
```python
# Step 1: Scrape images
python -c "from robust_scraper import robust_scraper; robust_scraper()"

# Step 2: VL Analysis
python -c "from qwen_vl_processor import process_and_save_edits; ..."

# Step 3: Edit images
python -c "from edit_model_pipeline import process_vl_to_edits; ..."
```

---

## 📋 File Reference

| File | Purpose | Type |
|------|---------|------|
| `pipeline_orchestrator.py` | Main entry point | 🎯 Start here |
| `qwen_vl_processor.py` | Multi-image VL analysis | Core |
| `edit_model_pipeline.py` | Image editing with InstructPix2Pix | Core |
| `robust_scraper.py` | Web scraping (updated) | Core |
| `keyword_sampler.py` | Context keyword sampling | Support |
| `config.py` | Configuration (updated) | Config |
| `model.py` | Model loaders (updated) | Support |
| `utils.py` | Utilities (updated) | Support |

---

## 🔧 Configuration

Edit `config.py`:
```python
HF_TOKEN = "your_huggingface_token"
QWEN_VL_MODEL = "Qwen/Qwen2-VL-7B-Instruct"
EDIT_MODEL = "timbrooks/instruct-pix2pix"
EDIT_NUM_INFERENCE_STEPS = 50
```

---

## 📊 Data Flow

```
Images (human + cloth)
    ↓
Qwen VL Analysis
    ↓
Structured JSON + Edit Prompts
    ↓
InstructPix2Pix Editing
    ↓
Synthetic Try-On Images
    ↓
Dataset Index
```

---

## 🎯 Key Classes

### QwenVLProcessor
```python
from qwen_vl_processor import QwenVLProcessor

processor = QwenVLProcessor()
result = processor.generate_edit_prompt(
    person_image_path="images/human/person.jpg",
    clothing_images=["images/cloth/shirt.jpg"],
    context_prompt="Virtual try-on task...",
    keyword_dict={"garment": "t-shirt", ...}
)
# Output: Structured JSON with "edit_prompt_for_model"
```

### EditModelPipeline
```python
from edit_model_pipeline import EditModelPipeline

editor = EditModelPipeline(model_name="timbrooks/instruct-pix2pix")
edited_img = editor.generate_edited_image(
    source_image_path="images/human/person.jpg",
    edit_prompt="Replace clothing with blue t-shirt...",
    output_path="outputs/edited_images/result.png"
)
```

### SyntheticDataPipeline
```python
from pipeline_orchestrator import SyntheticDataPipeline

pipeline = SyntheticDataPipeline()
results = pipeline.run_full_pipeline(skip_scraping=False)
# Outputs: Structured results with status for each stage
```

---

## 📂 Output Directories

```
outputs/
├── vl_analysis/
│   └── vl_analysis_*.json          # Structured analysis + prompts
├── edited_images/
│   ├── edited_*.png                # Synthetic try-on images
│   └── processing_results.json     # Batch results summary
└── dataset_index/
    ├── edited_images_index.json    # Image inventory
    └── pipeline_results.json       # Full pipeline summary
```

---

## 🔍 Example Outputs

### VL Analysis JSON Structure
```json
{
    "vl_analysis": {
        "person_analysis": {
            "body_shape": "mesomorph",
            "skin_tone": "warm medium",
            "pose": "standing"
        },
        "target_clothing": {
            "type": "t-shirt",
            "fit": "slim",
            "color": "blue"
        },
        "edit_instructions": [
            "Remove current shirt",
            "Apply navy blue slim-fit t-shirt",
            "Ensure natural fabric drape",
            "Maintain consistent lighting"
        ]
    },
    "edit_prompt_for_model": "Replace the clothing in the image with a blue slim-fit t-shirt..."
}
```

### Pipeline Results
```json
{
    "scraping": {"status": "success", "sites_sampled": [...]},
    "vl_analysis": {"status": "success", "pairs_processed": 15},
    "editing": {"status": "success", "successful_edits": 12},
    "dataset_index": {"status": "success", "edited_images": 12}
}
```

---

## ⚙️ Performance Tips

| Setting | Purpose | Recommended |
|---------|---------|------------|
| `EDIT_NUM_INFERENCE_STEPS` | Image quality | 50 (quality-speed tradeoff) |
| `EDIT_IMAGE_GUIDANCE_SCALE` | Fidelity to source | 1.5 (default) |
| `EDIT_GUIDANCE_SCALE` | Fidelity to text | 7.5 (default) |
| `batch_size` | Memory efficiency | 1-5 (depends on GPU) |
| `max_depth` (scraper) | Crawling depth | 2-3 (avoid excessive crawling) |

---

## 🐛 Troubleshooting

### Out of Memory
```python
# In config.py
BATCH_SIZE = 1
EDIT_NUM_INFERENCE_STEPS = 25  # Reduce quality
```

### Poor Edit Quality
```python
# In config.py
EDIT_NUM_INFERENCE_STEPS = 100  # Increase quality
EDIT_GUIDANCE_SCALE = 10.0      # More faithful to text
```

### Slow VL Analysis
```python
# Use smaller model
QWEN_VL_MODEL = "Qwen/Qwen-VL-Chat"  # 5B instead of 7B
```

---

## 📚 Documentation

- **QWEN_VL_INTEGRATION_README.md** → Overview & setup
- **IMPLEMENTATION_GUIDE.md** → Technical details
- **MODIFICATIONS_SUMMARY.md** → Change inventory

---

## ✅ Verification Checklist

- [ ] HuggingFace token configured in `config.py`
- [ ] GPU available (`nvidia-smi` or check PyTorch)
- [ ] Dependencies installed (`transformers`, `diffusers`, `torch`)
- [ ] Sample images in `images/human/` and `images/cloth/`
- [ ] `outputs/` directory exists or will be created
- [ ] Run: `python pipeline_orchestrator.py`

---

## 🎓 Use Cases

1. **Generate Try-On Dataset**
   ```bash
   python pipeline_orchestrator.py
   ```
   Uses scraped images + VL analysis + editing to create synthetic dataset

2. **Analyze Specific Pair**
   ```python
   from qwen_vl_processor import process_and_save_edits
   result = process_and_save_edits(
       "custom_person.jpg", ["custom_shirt.jpg"],
       "My context", "output.json"
   )
   ```

3. **Batch Edit Images**
   ```python
   from edit_model_pipeline import process_vl_to_edits
   results = process_vl_to_edits(
       vl_analysis_dir="my_vl_outputs/",
       max_images=100
   )
   ```

---

## 🔗 Integration Points

```python
# Scraper + VL
robust_scraper() 
  → process_and_save_edits()        # VL analysis
  
# VL + Edit Model
vl_output.json
  → process_vl_to_edits()            # Image editing
  
# All Stages + Orchestrator
SyntheticDataPipeline()
  → _run_scraping()                 # Stage 1
  → _run_vl_analysis()              # Stage 2
  → _run_editing()                  # Stage 3
  → _create_dataset_index()         # Stage 4
```

---

## 📞 Support

- Check **MODIFICATIONS_SUMMARY.md** for what was added
- Check **IMPLEMENTATION_GUIDE.md** for technical details
- Check **QWEN_VL_INTEGRATION_README.md** for usage examples
- Check **Troubleshooting** section above for common issues

---

**Version:** 1.0  
**Last Updated:** January 8, 2026  
**Status:** ✅ Production Ready
