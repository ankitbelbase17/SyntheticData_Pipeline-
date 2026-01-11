"""
Edit-Based Model Pipeline: Uses Qwen VL structured prompts to generate edited images.
Supports InstructPix2Pix, Blip-Diffusion, and other instruction-guided edit models.
"""

import json
import torch
from pathlib import Path
from typing import Dict, List, Any
from PIL import Image
import os

# InstructPix2Pix for instruction-guided image editing
try:
    from diffusers import StableDiffusionInstructPix2PixPipeline
except ImportError:
    print("[Warning] diffusers not installed. Install with: pip install diffusers")

class EditModelPipeline:
    def __init__(self, model_name: str = "timbrooks/instruct-pix2pix", device: str = None):
        """Initialize edit-based model (InstructPix2Pix or similar)."""
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        
        self.device = device
        self.model_name = model_name
        self.pipeline = StableDiffusionInstructPix2PixPipeline.from_pretrained(
            model_name,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            safety_checker=None
        ).to(device)
    
    def generate_edited_image(
        self,
        source_image_path: str,
        edit_prompt: str,
        num_inference_steps: int = 50,
        image_guidance_scale: float = 1.5,
        guidance_scale: float = 7.5,
        output_path: str = None
    ) -> Image.Image:
        """
        Generate edited image using InstructPix2Pix.
        
        Args:
            source_image_path: Path to source image
            edit_prompt: Editing instruction from Qwen VL
            num_inference_steps: Diffusion steps
            image_guidance_scale: Image conditioning strength
            guidance_scale: Prompt guidance strength
            output_path: Optional path to save edited image
            
        Returns:
            Edited PIL Image
        """
        # Load source image
        source_img = Image.open(source_image_path).convert('RGB')
        
        # Generate edited image
        with torch.autocast(self.device):
            edited_img = self.pipeline(
                prompt=edit_prompt,
                image=source_img,
                num_inference_steps=num_inference_steps,
                image_guidance_scale=image_guidance_scale,
                guidance_scale=guidance_scale,
                generator=torch.Generator(device=self.device).manual_seed(42)
            ).images[0]
        
        # Save if output path provided
        if output_path:
            output_dir = Path(output_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)
            edited_img.save(output_path)
            print(f"[EditModel] Saved edited image to {output_path}")
        
        return edited_img
    
    def batch_generate_edits(
        self,
        vl_analysis_dir: str,
        source_images_dir: str,
        output_dir: str,
        max_images: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Batch process Qwen VL outputs to generate edited images.
        
        Args:
            vl_analysis_dir: Directory with VL analysis JSON files
            source_images_dir: Directory with source images
            output_dir: Directory to save edited images
            max_images: Max images to process
            
        Returns:
            List of results with paths to edited images
        """
        results = []
        processed = 0
        
        vl_files = sorted(Path(vl_analysis_dir).glob("vl_analysis_*.json"))
        
        for vl_file in vl_files:
            if processed >= max_images:
                break
            
            try:
                with open(vl_file, 'r') as f:
                    vl_data = json.load(f)
                
                # Extract data
                person_image = vl_data.get("source", {}).get("person_image", "")
                edit_prompt = vl_data.get("edit_prompt_for_model", "")
                
                if not person_image or not edit_prompt:
                    continue
                
                # Generate edited image
                output_filename = f"edited_{Path(vl_file).stem}.png"
                output_path = os.path.join(output_dir, output_filename)
                
                edited_img = self.generate_edited_image(
                    person_image,
                    edit_prompt,
                    output_path=output_path
                )
                
                results.append({
                    "vl_analysis_file": str(vl_file),
                    "source_image": person_image,
                    "edit_prompt": edit_prompt,
                    "edited_image": output_path,
                    "status": "success"
                })
                
                processed += 1
                print(f"[EditModel] Processed {processed}/{max_images}")
                
            except Exception as e:
                print(f"[EditModel] Error processing {vl_file}: {e}")
                results.append({
                    "vl_analysis_file": str(vl_file),
                    "status": "failed",
                    "error": str(e)
                })
        
        return results


def process_vl_to_edits(
    vl_analysis_dir: str = "outputs/vl_analysis/",
    source_images_dir: str = "images/human/",
    output_dir: str = "outputs/edited_images/",
    max_images: int = 10,
    model_name: str = "timbrooks/instruct-pix2pix"
) -> List[Dict[str, Any]]:
    """
    Full pipeline: Load Qwen VL outputs and generate edited images.
    
    Args:
        vl_analysis_dir: Directory with VL analysis JSONs
        source_images_dir: Directory with source images
        output_dir: Directory to save edited images
        max_images: Max images to process
        model_name: Edit model to use
        
    Returns:
        List of processing results
    """
    print("[EditModel] Initializing edit-based model pipeline...")
    editor = EditModelPipeline(model_name=model_name)
    
    print(f"[EditModel] Processing VL outputs from {vl_analysis_dir}...")
    results = editor.batch_generate_edits(
        vl_analysis_dir,
        source_images_dir,
        output_dir,
        max_images=max_images
    )
    
    # Save results summary
    results_file = os.path.join(output_dir, "processing_results.json")
    os.makedirs(output_dir, exist_ok=True)
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"[EditModel] Saved results summary to {results_file}")
    
    return results


# Example usage:
if __name__ == "__main__":
    # Example: Process VL outputs and generate edits
    results = process_vl_to_edits(
        vl_analysis_dir="outputs/vl_analysis/",
        output_dir="outputs/edited_images/",
        max_images=5
    )
    
    print("\n[EditModel] Summary:")
    successful = sum(1 for r in results if r.get("status") == "success")
    failed = sum(1 for r in results if r.get("status") == "failed")
    print(f"Successful edits: {successful}")
    print(f"Failed edits: {failed}")
