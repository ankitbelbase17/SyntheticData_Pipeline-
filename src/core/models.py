import torch
from PIL import Image
from typing import List, Dict, Any, Union
import json
import re

# Try to import config from parent
try:
    from config import config
except ImportError:
    from src.config import config


class FluxGenerator:
    """
    Wrapper for FLUX.2 Klein Model.
    Supports text-to-image and image-to-image multi-reference editing.
    Uses person and cloth images as reference for virtual try-on generation.
    """
    def __init__(self, model_id: str = "9b", device: str = "cuda"):
        self.device = device if torch.cuda.is_available() else "cpu"
        self.model_id = model_id.lower()
        self.dtype = torch.bfloat16
        self.pipe = None
        
        print(f"Initializing FluxGenerator with model: FLUX.2-klein-{self.model_id} on {self.device}")
        self._load_model()

    def _load_model(self):
        """Load the FLUX.2 Klein pipeline"""
        from huggingface_hub import login
        
        print("=" * 60)
        print(f"Loading FLUX.2 Klein Model: {self.model_id}")
        print("=" * 60)
        
        # Login to HuggingFace for gated models
        hf_token = config.HF_TOKEN
        if hf_token and hf_token != "your_hf_token":
            print("Authenticating with HuggingFace...")
            login(token=hf_token)
        else:
            print("Warning: No HF_TOKEN found. Gated models may fail to load.")
        
        if self.device == "cpu":
            print("Warning: CUDA not found. Running on CPU. This will be very slow.")

        # Use FLUX.2 Klein with Mistral3 encoder
        if self.model_id == "4b":
            print("Loading FLUX.2-klein-4B...")
            model_name = "black-forest-labs/FLUX.2-klein-4B"
        elif self.model_id == "9b":
            print("Loading FLUX.2-klein-9B...")
            model_name = "black-forest-labs/FLUX.2-klein-9B"
        else:
            print(f"Unknown model type '{self.model_id}', defaulting to 4B...")
            model_name = "black-forest-labs/FLUX.2-klein-4B"
        
        try:
            from diffusers import Flux2KleinPipeline
            
            print(f"Loading {model_name} with Flux2KleinPipeline...")
            self.pipe = Flux2KleinPipeline.from_pretrained(
                model_name,
                torch_dtype=self.dtype,
                token=hf_token
            )
            self.pipe.enable_model_cpu_offload()  # Saves VRAM
            print("Loaded Flux2KleinPipeline successfully")
            
        except Exception as e:
            print(f"Flux2KleinPipeline failed: {e}")
            print("Falling back to FLUX.1-dev...")
            
            from diffusers import FluxPipeline
            self.pipe = FluxPipeline.from_pretrained(
                "black-forest-labs/FLUX.1-dev",
                torch_dtype=self.dtype,
                token=hf_token
            )
            self.pipe.to(self.device)
        
        print(f"Pipeline type: {type(self.pipe).__name__}")
        print("✓ FluxGenerator ready!")

    def generate(self, person_image: Image.Image, cloth_image: Image.Image, prompt: str, 
                 height: int = 1024, width: int = 1024, steps: int = 4, 
                 guidance: float = 1.0, seed: int = None, 
                 strength: float = 0.75) -> Image.Image: # Keeping strength in signature for compatibility but ignoring it
        """
        Generates a try-on image using multi-reference editing.
        """
        # Ensure prompt is a string
        if isinstance(prompt, list):
            prompt = prompt[0] if prompt else ""
        prompt = str(prompt)
        
        print(f"Generating try-on image with prompt: {prompt[:100]}...")
        
        generator = None
        if seed is not None:
            generator = torch.Generator(device=self.device).manual_seed(seed)
        else:
            # Default seed 0 as requested if none provided
            generator = torch.Generator(device=self.device).manual_seed(0)
        
        # Helper to resize images to be divisible by 16 (for FLUX)
        def resize_for_flux(img, max_size=1024):
            img = img.copy()
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            w, h = img.size
            w = (w // 16) * 16
            h = (h // 16) * 16
            # Avoid resizing to 0
            w = max(16, w)
            h = max(16, h)
            return img.resize((w, h), Image.Resampling.LANCZOS)

        # Preprocess images
        p_img_resized = resize_for_flux(person_image, max(height, width))
        c_img_resized = resize_for_flux(cloth_image, max(height, width))
        
        # FLUX pipeline call
        try:
            print(f"Calling pipeline with [person, cloth] images. Steps={steps}, Guidance={guidance} (Klein settings)")
            
            # Pass list of images as per example, removing strength
            image = self.pipe(
                prompt=prompt,
                image=[p_img_resized, c_img_resized],  # Multiple reference images
                height=height,
                width=width,
                guidance_scale=guidance,
                num_inference_steps=steps,
                generator=generator
            ).images[0]
                
        except Exception as e:
            print(f"Generation error: {e}")
            # Fallback: return resized person image
            print("Falling back to returning person image...")
            image = person_image.copy().resize((width, height), Image.Resampling.LANCZOS)
        
        # Clear CUDA cache after generation
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        return image


class QwenVLM:
    """
    Wrapper for Qwen3-VL-32B-Instruct Model.
    Evaluates try-on images and provides feedback.
    """
    def __init__(self, model_id: str = "Qwen/Qwen3-VL-32B-Instruct", device: str = "cuda"):
        self.device = device if torch.cuda.is_available() else "cpu"
        self.model_id = model_id
        self.processor = None
        self.model = None
        
        print(f"Initializing QwenVLM with model: {model_id} on {self.device}")
        self._load_model()

    def _load_model(self):
        """Load the Qwen3-VL model and processor"""
        from transformers import AutoProcessor, AutoModel
        from huggingface_hub import login
        
        print("=" * 60)
        print(f"Loading Qwen VLM: {self.model_id}")
        print("=" * 60)
        
        # Login to HuggingFace for gated models
        hf_token = config.HF_TOKEN
        if hf_token and hf_token != "your_hf_token":
            print("Authenticating with HuggingFace...")
            login(token=hf_token)
        
        # Load processor
        print("Loading processor...")
        self.processor = AutoProcessor.from_pretrained(
            self.model_id,
            trust_remote_code=True,
            token=hf_token
        )
        
        # Load model - Qwen3-VL requires its own model class
        print("Loading model (this may take a while for 32B)...")
        
        # Try Qwen3VLForConditionalGeneration first (for Qwen3-VL)
        try:
            from transformers import Qwen3VLForConditionalGeneration
            print("Using Qwen3VLForConditionalGeneration...")
            self.model = Qwen3VLForConditionalGeneration.from_pretrained(
                self.model_id,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                device_map="auto" if self.device == "cuda" else None,
                trust_remote_code=True,
                token=hf_token
            )
        except (ImportError, AttributeError) as e:
            print(f"Qwen3VLForConditionalGeneration not available: {e}")
            # Fallback to AutoModel with trust_remote_code (loads correct class from hub)
            print("Using AutoModel with trust_remote_code...")
            self.model = AutoModel.from_pretrained(
                self.model_id,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                device_map="auto" if self.device == "cuda" else None,
                trust_remote_code=True,
                token=hf_token
            )
        
        if self.device == "cpu":
            self.model = self.model.to(self.device)
        
        self.model.eval()
        print(f"Model type: {type(self.model).__name__}")
        print("✓ QwenVLM ready!")

    def evaluate(self, 
                 person_image: Image.Image, 
                 cloth_image: Image.Image, 
                 try_on_images: List[Image.Image], 
                 iteration: int,
                 max_new_tokens: int = 1024,
                 temperature: float = 0.3) -> Dict[str, Any]:
        """
        Evaluates the try-on images and returns feedback in JSON format.
        
        Image format sent to VLM:
        - Iteration 1: person_image, cloth_image, incorrect_tryon_1
        - Iteration 2: person_image, cloth_image, incorrect_tryon_1, incorrect_tryon_2
        - Iteration N: person_image, cloth_image, incorrect_tryon_1, ..., incorrect_tryon_N
        
        Args:
            person_image: Original person image
            cloth_image: Original cloth image
            try_on_images: List of ALL generated try-on images (cumulative history)
            iteration: Current iteration number
            max_new_tokens: Max tokens to generate
            temperature: Sampling temperature (lower = more deterministic)
            
        Returns:
            Dictionary with feedback, improved_prompt, and constraint_scores
        """
        print(f"Evaluating iteration {iteration} with {len(try_on_images)} try-on images.")
        
        if not try_on_images:
            return self._default_error_response("No try-on image provided")
        
        # Construct the evaluation prompt
        system_prompt = self._get_system_prompt()
        user_prompt = self._construct_user_prompt(iteration, len(try_on_images))
        
        # Build images list: person, cloth, then ALL try-on images in order
        images = [person_image, cloth_image] + try_on_images
        
        # Build the message content with all images
        content = [
            {"type": "text", "text": system_prompt},
            {"type": "text", "text": "\n\nImage 1 - Original Person:"},
            {"type": "image", "image": person_image},
            {"type": "text", "text": "\n\nImage 2 - Original Cloth:"},
            {"type": "image", "image": cloth_image},
        ]
        
        # Add all try-on images with labels
        for idx, tryon_img in enumerate(try_on_images, start=1):
            img_num = idx + 2  # person=1, cloth=2, so tryons start at 3
            if idx == len(try_on_images):
                # Latest (current) try-on
                content.append({"type": "text", "text": f"\n\nImage {img_num} - Generated Try-On Iteration {idx} (LATEST - evaluate this):"})
            else:
                # Previous try-on
                content.append({"type": "text", "text": f"\n\nImage {img_num} - Generated Try-On Iteration {idx} (previous attempt):"})
            content.append({"type": "image", "image": tryon_img})
        
        content.append({"type": "text", "text": f"\n\n{user_prompt}"})
        
        messages = [{"role": "user", "content": content}]
        
        # Apply chat template
        text = self.processor.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        
        # Process inputs
        inputs = self.processor(
            text=[text],
            images=images,
            return_tensors="pt",
            padding=True,
            truncation=True
        ).to(self.device)
        
        # Generate response
        with torch.no_grad():
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=True if temperature > 0 else False,
                pad_token_id=self.processor.tokenizer.pad_token_id,
            )
        
        # Decode output
        generated_ids = output_ids[0][len(inputs.input_ids[0]):]
        response_text = self.processor.decode(
            generated_ids,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False
        )
        
        # Parse the JSON response
        result = self._parse_response(response_text)
        
        # Clear CUDA cache after evaluation
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        return result

    def _get_system_prompt(self) -> str:
        # Use system prompt from config if available, else fallback to generic
        try:
            prompt = config.VLM_SYSTEM_PROMPT
            if prompt and isinstance(prompt, str):
                return prompt
        except Exception:
            pass
        # Fallback generic prompt
        return (
            "You are an expert evaluator for virtual try-on systems. Your task is to determine if the generated try-on image shows the clothing being worn as it should be, with no unintended changes to the person, pose, or scene. This must work for any person or clothing type.\n\n"
            "You will receive:\n"
            "1. The original person image (any gender, pose, or background)\n"
            "2. The original clothing image (any garment type, color, or style)\n"
            "3. One or more generated try-on images (showing attempt history; the last image is the latest attempt)\n\n"
            "Your goal is to analyze the latest try-on image and answer:\n"
            "- Is the clothing correctly and realistically worn by the person, matching the original garment's structure, color, and style?\n"
            "- Are there any unintended changes to the person, pose, background, or scene?\n\n"
            "If the clothing is worn as intended and there are no unintended changes, return SUCCESS. Otherwise, return NOT_SUCCESS.\n\n"
            "Output a VALID JSON object:\n"
            "{\n"
            "    \"result\": \"SUCCESS\" or \"NOT_SUCCESS\",\n"
            "    \"explanation\": \"Detailed explanation of why it is or is not a success, including any issues or strengths.\",\n"
            "    \"improved_prompt\": \"A revised prompt focusing on fixing any issues, if needed.\"\n"
            "}\n\n"
            "CRITICAL: Return ONLY the JSON object. No markdown blocks, no extra text."
        )

    def _construct_user_prompt(self, iteration: int, num_tryons: int) -> str:
        # Images passed: [Person(1), Cloth(2), TryOn1(3), ..., TryOnN(N+2)]
        latest_image_index = num_tryons + 2
        
        if num_tryons == 1:
            return f"""This is Feedback Iteration {iteration}.
You have exactly 3 images:
- Image 1: The Original Person (Reference Body/Pose).
- Image 2: The Original Cloth (Reference Garment).
- Image 3: The Generated Try-On Result (To be evaluated).

TASK: Compare Image 3 against Image 1 and Image 2.
Does Image 3 successfully show the person from Image 1 wearing the cloth from Image 2?
Check for all hallucinations and strict criteria defined in the system prompt.
Output ONLY the JSON."""
        else:
            return f"""This is Feedback Iteration {iteration}.
You have {latest_image_index} images in total:
- Image 1: The Original Person.
- Image 2: The Original Cloth.
- Images 3 to {latest_image_index-1}: Previous failed attempts (History).
- Image {latest_image_index}: The LATEST Generated Try-On Result (Final).

TASK: Analyze the EVOLUTION of the try-on process.
1. Briefly look at the previous attempts (Images 3 to {latest_image_index-1}) and identify what was wrong in each step.
2. Then, CRITICALLY evaluate Image {latest_image_index} (the latest one).
3. Did the model learn from past mistakes? Does Image {latest_image_index} fix the specific errors seen in earlier versions?
4. Final Verdict: Based on this evolution, strictly judge Image {latest_image_index}.

Output ONLY the JSON."""

    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """Parse the VLM response into structured feedback (SUCCESS/NOT_SUCCESS only)"""
        # Try direct JSON parsing
        try:
            data = json.loads(response_text.strip())
        except json.JSONDecodeError:
            # Try extracting from markdown code block
            match = re.search(r"```(?:json)?(.*?)```", response_text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1).strip())
                except json.JSONDecodeError:
                    data = None
            else:
                # Try finding first { and last }
                start = response_text.find("{")
                end = response_text.rfind("}")
                if start != -1 and end != -1 and end > start:
                    try:
                        data = json.loads(response_text[start:end+1])
                    except json.JSONDecodeError:
                        data = None
                else:
                    data = None
        if data and "result" in data and "explanation" in data:
            return data
        # If all parsing fails, return error response
        print(f"Warning: Could not parse VLM response as JSON. Raw response: {response_text[:500]}")
        return {
            "result": "NOT_SUCCESS",
            "explanation": f"Error: Failed to parse response: {response_text[:200]}",
            "improved_prompt": "A photorealistic virtual try-on image showing the person wearing the exact cloth with accurate colors, patterns, and fit."
        }
