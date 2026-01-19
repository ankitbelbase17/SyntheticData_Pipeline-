import torch
from diffusers import Flux2KleinPipeline
from huggingface_hub import hf_hub_download
from safetensors.torch import load_file
from PIL import Image
import os

class ImageGenerator:
    def __init__(self, model_type="nvfp4"):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.dtype = torch.bfloat16
        self.pipe = None
        self.model_type = model_type.lower()
        
    def load_model(self):
        print("=" * 60)
        print(f"Setting up FLUX.2 Klein Model: {self.model_type}")
        print("=" * 60)
        
        if self.device == "cpu":
             print("Warning: CUDA not found. Running on CPU. This will be very slow.")

        if self.model_type == "nvfp4":
            print("Step 1: Downloading NVFP4 weights...")
            nvfp4_weights_path = hf_hub_download(
                repo_id="black-forest-labs/FLUX.2-klein-4b-nvfp4",
                filename="flux-2-klein-4b-nvfp4.safetensors",
                cache_dir="./weights_cache"
            )
            
            print("Step 2: Loading base pipeline structure...")
            self.pipe = Flux2KleinPipeline.from_pretrained(
                "black-forest-labs/FLUX.2-klein-4B",
                torch_dtype=self.dtype,
            )
            
            print("Step 3: Loading NVFP4 quantized weights...")
            nvfp4_state_dict = load_file(nvfp4_weights_path)
            self.pipe.transformer.load_state_dict(nvfp4_state_dict, strict=False)

        elif self.model_type == "4b":
            print("Loading Standard FLUX.2-klein-4B...")
            self.pipe = Flux2KleinPipeline.from_pretrained(
                "black-forest-labs/FLUX.2-klein-4B", 
                torch_dtype=self.dtype
            )

        elif self.model_type == "9b":
            print("Loading Standard FLUX.2-klein-9B...")
            self.pipe = Flux2KleinPipeline.from_pretrained(
                "black-forest-labs/FLUX.2-klein-9B", 
                torch_dtype=self.dtype
            )
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")
        
        print("Step 4: Moving model to device...")
        self.pipe.to(self.device)
        print("✓ Model ready!")
        
    def generate(self, prompt: str, height=1024, width=1024, steps=None, guidance=None, seed=None) -> Image.Image:
        # Defaults based on model type if not provided
        if steps is None:
            steps = 4 if self.model_type in ["nvfp4", "4b"] else 4 # Assuming 9B is also distilled for 4 steps, or user can override
        
        if guidance is None:
             guidance = 4.0 if self.model_type == "nvfp4" else 1.0

        generator = None
        if seed is not None:
            generator = torch.Generator(device=self.device).manual_seed(seed)
            
        image = self.pipe(
            prompt=prompt,
            height=height,
            width=width,
            guidance_scale=guidance,
            num_inference_steps=steps,
            generator=generator
        ).images[0]
        
        return image
