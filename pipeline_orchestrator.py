"""
Pipeline Orchestrator: Full end-to-end pipeline orchestration.
Coordinates scraping, VL analysis, and edit-based model generation.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

from scraper.robust_scraper import robust_scraper, weighted_sample_sites_hierarchical, SCRAPE_SITE_CATEGORIES, selenium_crawl_images
from keyword_sampler import sample_keywords_hierarchical, VTON_DICTIONARY
from qwen_vl_processor import process_and_save_edits
from edit_model_pipeline import process_vl_to_edits
from utils import create_dataset_index, save_json_metadata

class SyntheticDataPipeline:
    """Orchestrate the full synthetic dataset creation pipeline."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize pipeline with configuration."""
        self.config = config or self._default_config()
        self.results = {
            "scraping": {},
            "vl_analysis": {},
            "editing": {},
            "dataset_index": {}
        }
    
    @staticmethod
    def _default_config() -> Dict[str, Any]:
        """Default pipeline configuration."""
        return {
            "scraping": {
                "max_images_per_site": 50,
                "max_depth": 3,
                "image_types": ["human", "cloth"]
            },
            "vl_analysis": {
                "max_pairs": 20,
                "batch_size": 5
            },
            "editing": {
                "model_name": "timbrooks/instruct-pix2pix",
                "num_inference_steps": 50,
                "max_edits": 20
            },
            "output_dirs": {
                "images": "images/",
                "vl_analysis": "outputs/vl_analysis/",
                "edited": "outputs/edited_images/",
                "index": "outputs/dataset_index/"
            }
        }
    
    def run_full_pipeline(self, skip_scraping: bool = False) -> Dict[str, Any]:
        """
        Run the complete pipeline: scraping -> VL analysis -> editing.
        
        Args:
            skip_scraping: If True, use existing images. If False, scrape new images.
            
        Returns:
            Results dictionary with all pipeline outputs
        """
        logger.info("=" * 80)
        logger.info("SYNTHETIC DATA PIPELINE: Starting full pipeline")
        logger.info("=" * 80)
        
        # Step 1: Scraping
        if not skip_scraping:
            logger.info("\n[Step 1] SCRAPING: Collecting human and clothing images...")
            self._run_scraping()
        else:
            logger.info("\n[Step 1] SCRAPING: Skipped (using existing images)")
        
        # Step 2: VL Analysis with Qwen
        logger.info("\n[Step 2] VL ANALYSIS: Analyzing image pairs with Qwen 2.5 VL...")
        self._run_vl_analysis()
        
        # Step 3: Edit-based Generation
        logger.info("\n[Step 3] EDITING: Generating edited images with InstructPix2Pix...")
        self._run_editing()
        
        # Step 4: Dataset Indexing
        logger.info("\n[Step 4] INDEXING: Creating dataset index...")
        self._create_dataset_index()
        
        logger.info("\n" + "=" * 80)
        logger.info("PIPELINE COMPLETE")
        logger.info("=" * 80)
        self._print_summary()
        
        return self.results
    
    def _run_scraping(self):
        """Execute scraping stage."""
        try:
            logger.info("Sampling sites from hierarchical categories...")
            sampled_sites = weighted_sample_sites_hierarchical(SCRAPE_SITE_CATEGORIES, k=4)
            logger.info(f"Sampled sites: {sampled_sites}")
            
            logger.info("Starting Selenium crawlers for image collection...")
            for image_type in self.config["scraping"]["image_types"]:
                logger.info(f"Scraping {image_type} images...")
                selenium_crawl_images(
                    sampled_sites,
                    image_type=image_type,
                    max_depth=self.config["scraping"]["max_depth"],
                    max_images=self.config["scraping"]["max_images_per_site"]
                )
            
            self.results["scraping"]["status"] = "success"
            self.results["scraping"]["sites_sampled"] = sampled_sites
            logger.info("Scraping completed successfully")
        except Exception as e:
            logger.error(f"Scraping failed: {e}")
            self.results["scraping"]["status"] = "failed"
            self.results["scraping"]["error"] = str(e)
    
    def _run_vl_analysis(self):
        """Execute VL analysis stage."""
        try:
            images_dir = self.config["output_dirs"]["images"]
            vl_dir = self.config["output_dirs"]["vl_analysis"]
            
            human_images = list(Path(f"{images_dir}/human/").glob("*.jpg"))[:self.config["vl_analysis"]["max_pairs"]]
            cloth_images = list(Path(f"{images_dir}/cloth/").glob("*.jpg"))
            
            if not human_images or not cloth_images:
                logger.warning("Not enough images for VL analysis")
                self.results["vl_analysis"]["status"] = "skipped"
                return
            
            logger.info(f"Found {len(human_images)} human images and {len(cloth_images)} cloth images")
            
            processed = 0
            for idx, human_img in enumerate(human_images):
                for jdx, cloth_img in enumerate(cloth_images[:2]):
                    if processed >= self.config["vl_analysis"]["batch_size"]:
                        break
                    
                    try:
                        keyword_dict = sample_keywords_hierarchical(VTON_DICTIONARY)
                        
                        context_prompt = f"""
                        Virtual Try-On Synthesis:
                        - Target garment: {keyword_dict.get('garment', 'top')}
                        - Fit: {keyword_dict.get('fit', 'regular')}
                        - Color: {keyword_dict.get('color', 'blue')}
                        - Body shape: {keyword_dict.get('body_shape', 'average')}
                        Generate realistic editing instructions for try-on synthesis.
                        """
                        
                        output_json = os.path.join(vl_dir, f"vl_analysis_{idx}_{jdx}.json")
                        
                        process_and_save_edits(
                            str(human_img),
                            [str(cloth_img)],
                            context_prompt,
                            output_json,
                            keyword_dict
                        )
                        
                        processed += 1
                        logger.info(f"VL processed {processed} pairs")
                    except Exception as e:
                        logger.error(f"VL analysis failed for pair ({idx},{jdx}): {e}")
            
            self.results["vl_analysis"]["status"] = "success"
            self.results["vl_analysis"]["pairs_processed"] = processed
            logger.info(f"VL analysis completed: {processed} pairs processed")
        except Exception as e:
            logger.error(f"VL analysis failed: {e}")
            self.results["vl_analysis"]["status"] = "failed"
            self.results["vl_analysis"]["error"] = str(e)
    
    def _run_editing(self):
        """Execute editing stage."""
        try:
            vl_dir = self.config["output_dirs"]["vl_analysis"]
            edited_dir = self.config["output_dirs"]["edited"]
            
            logger.info(f"Processing VL outputs from {vl_dir}...")
            results = process_vl_to_edits(
                vl_analysis_dir=vl_dir,
                output_dir=edited_dir,
                max_images=self.config["editing"]["max_edits"],
                model_name=self.config["editing"]["model_name"]
            )
            
            successful = sum(1 for r in results if r.get("status") == "success")
            failed = sum(1 for r in results if r.get("status") == "failed")
            
            self.results["editing"]["status"] = "success"
            self.results["editing"]["successful_edits"] = successful
            self.results["editing"]["failed_edits"] = failed
            logger.info(f"Editing completed: {successful} successful, {failed} failed")
        except Exception as e:
            logger.error(f"Editing failed: {e}")
            self.results["editing"]["status"] = "failed"
            self.results["editing"]["error"] = str(e)
    
    def _create_dataset_index(self):
        """Create dataset index for organized access."""
        try:
            index_dir = self.config["output_dirs"]["index"]
            os.makedirs(index_dir, exist_ok=True)
            
            # Index edited images
            edited_dir = self.config["output_dirs"]["edited"]
            if Path(edited_dir).exists():
                index = create_dataset_index(edited_dir, os.path.join(index_dir, "edited_images_index.json"))
                self.results["dataset_index"]["edited_images"] = index["total_count"]
                logger.info(f"Created index for {index['total_count']} edited images")
            
            # Save pipeline results
            results_file = os.path.join(index_dir, "pipeline_results.json")
            save_json_metadata(self.results, results_file)
            
            self.results["dataset_index"]["status"] = "success"
            logger.info(f"Dataset index saved to {index_dir}")
        except Exception as e:
            logger.error(f"Indexing failed: {e}")
            self.results["dataset_index"]["status"] = "failed"
            self.results["dataset_index"]["error"] = str(e)
    
    def _print_summary(self):
        """Print pipeline execution summary."""
        logger.info("\nPIPELINE SUMMARY:")
        logger.info(f"  Scraping: {self.results['scraping'].get('status', 'N/A')}")
        logger.info(f"  VL Analysis: {self.results['vl_analysis'].get('status', 'N/A')} "
                   f"({self.results['vl_analysis'].get('pairs_processed', 0)} pairs)")
        logger.info(f"  Editing: {self.results['editing'].get('status', 'N/A')} "
                   f"({self.results['editing'].get('successful_edits', 0)} edits)")
        logger.info(f"  Dataset Index: {self.results['dataset_index'].get('status', 'N/A')} "
                   f"({self.results['dataset_index'].get('edited_images', 0)} images)")
        logger.info("\nOutput directories:")
        for dir_type, dir_path in self.config["output_dirs"].items():
            logger.info(f"  {dir_type}: {dir_path}")


# Example usage:
if __name__ == "__main__":
    # Create pipeline instance
    pipeline = SyntheticDataPipeline()
    
    # Run full pipeline (with scraping)
    results = pipeline.run_full_pipeline(skip_scraping=False)
    
    # Or skip scraping if images already exist
    # results = pipeline.run_full_pipeline(skip_scraping=True)
    
    print("\n[Done] Synthetic dataset creation pipeline completed!")
    print(f"Results: {json.dumps(results, indent=2)}")
