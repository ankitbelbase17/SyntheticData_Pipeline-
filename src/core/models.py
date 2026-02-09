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
        import torch
        
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
            # User specifically requested Flux2KleinPipeline for 9B model
            from diffusers import Flux2KleinPipeline
            
            print(f"Loading {model_name} with Flux2KleinPipeline...")
            self.pipe = Flux2KleinPipeline.from_pretrained(
                model_name,
                torch_dtype=self.dtype,
                token=hf_token
            )
            self.pipe.to(self.device)
            print("Loaded Flux2KleinPipeline successfully")
            
        except ImportError:
            print("Flux2KleinPipeline not found in diffusers. Please ensure you have the latest diffusers (git+https://github.com/huggingface/diffusers.git).")
            print("Falling back to FluxPipeline (Note: 'image' argument might not work)...")
            try:
                from diffusers import FluxPipeline
                self.pipe = FluxPipeline.from_pretrained(
                    model_name,
                    torch_dtype=self.dtype,
                    token=hf_token
                )
                self.pipe.to(self.device)
            except Exception as e:
                print(f"Failed to load fallback FluxPipeline: {e}")
                
        except Exception as e:
            print(f"Failed to load Flux2KleinPipeline: {e}")
            print("Falling back to standard FluxPipeline...")
            
            try:
                from diffusers import FluxPipeline
                self.pipe = FluxPipeline.from_pretrained(
                    "black-forest-labs/FLUX.1-dev",
                    torch_dtype=self.dtype,
                    token=hf_token
                )
                self.pipe.to(self.device)
            except Exception as e2:
                print(f"CRITICAL: Could not load any Flux model: {e2}")
        
        print(f"Pipeline type: {type(self.pipe).__name__}")
        print("✓ FluxGenerator ready!")

    def generate(self, person_image: Union[Image.Image, List[Image.Image]], 
                 cloth_image: Union[Image.Image, List[Image.Image]], 
                 prompt: Union[str, List[str]], 
                 height: int = 1024, width: int = 1024, steps: int = 4, 
                 guidance: float = 1.0, seed: int = None, 
                 strength: float = 0.75) -> Union[Image.Image, List[Image.Image]]:
        """
        Generates try-on images. Supports both single samples and batches.
        """
        # Determine if batch mode
        is_batch = isinstance(person_image, list)
        
        # Normalize inputs
        prompts = prompt if isinstance(prompt, list) else [prompt]
        p_imgs = person_image if isinstance(person_image, list) else [person_image]
        c_imgs = cloth_image if isinstance(cloth_image, list) else [cloth_image]
        
        # Replicate prompt if single prompt provided for batch
        if len(prompts) == 1 and len(p_imgs) > 1:
            prompts = prompts * len(p_imgs)
            
        print(f"Generating {'batch of ' + str(len(p_imgs)) if is_batch else 'single'} try-on image(s)...")

        generator = None
        if seed is not None:
             # Create list of generators for batch if needed, or single
            generator = torch.Generator(device=self.device).manual_seed(seed)
        else:
            generator = torch.Generator(device=self.device).manual_seed(0)
        
        def resize_for_flux(img, max_size=1024):
            img = img.copy()
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            w, h = img.size
            w = (w // 16) * 16
            h = (h // 16) * 16
            return img.resize((max(16, w), max(16, h)), Image.Resampling.LANCZOS)

        p_imgs_resized = [resize_for_flux(img, max(height, width)) for img in p_imgs]
        c_imgs_resized = [resize_for_flux(img, max(height, width)) for img in c_imgs]
        
        # Prepare inputs as expected by pipeline
        # Common structure for multi-image pipelines in batch:
        # image = [[p1, c1], [p2, c2], ...] failed with "got list".
        # Try flattened list: [p1, c1, p2, c2, ...] if pipeline consumes N images per prompt?
        # Or maybe it expects [p_batch, c_batch] ?? (List of 2 lists, each length B)?
        # Let's try flattening first as [p1, c1, p2, c2...] or [p1, p2..., c1, c2...]
        # Given single sample is [p, c], linear consumption implies [p1, c1, p2, c2].
        
        output_images = []
        try:
            if is_batch:
                 # Strategy 1: Flattened list [p1, c1, p2, c2, ...]
                 batch_inputs_flat = [img for p, c in zip(p_imgs_resized, c_imgs_resized) for img in (p, c)]
                 
                 print(f"Calling pipeline with Batch Size={len(p_imgs)} (Flat images list len={len(batch_inputs_flat)})...")
                 output_images = self.pipe(
                    prompt=prompts,
                    image=batch_inputs_flat, 
                    height=height,
                    width=width,
                    guidance_scale=guidance,
                    num_inference_steps=steps,
                    generator=generator
                ).images
            else:
                # Single sample case (pass simple list [p, c])
                batch_inputs = [[p, c] for p, c in zip(p_imgs_resized, c_imgs_resized)]
                output_images = self.pipe(
                    prompt=prompts[0],
                    image=batch_inputs[0],
                    height=height,
                    width=width,
                    guidance_scale=guidance,
                    num_inference_steps=steps,
                    generator=generator
                ).images

        except Exception as e:
            print(f"Batch Generation error: {e}")
            
            # If flat list failed, try Strategy 2: List of Batches [ [p1, p2...], [c1, c2...] ]
            try:
                print("Retrying with List of Batches [Batch_P, Batch_C]...")
                batch_inputs_cols = [p_imgs_resized, c_imgs_resized]
                output_images = self.pipe(
                    prompt=prompts,
                    image=batch_inputs_cols, 
                    height=height,
                    width=width,
                    guidance_scale=guidance,
                    num_inference_steps=steps,
                    generator=generator
                ).images
                
            except Exception as e2:
                print(f"Batch Strategy 2 failed: {e2}")
                print("Falling back to sequential loop...")
                batch_inputs = [[p, c] for p, c in zip(p_imgs_resized, c_imgs_resized)]
                output_images = []
                for i, p_txt in enumerate(prompts):
                     try:
                         # For single sample fallback, pass [p, c]
                         res = self.pipe(
                            prompt=p_txt,
                            image=batch_inputs[i],
                            height=height,
                            width=width,
                            guidance_scale=guidance,
                            num_inference_steps=steps,
                            generator=generator
                        ).images[0]
                         output_images.append(res)
                     except Exception as inner_e:
                         print(f"  Error on sample {i}: {inner_e}")
                         output_images.append(p_imgs[i].copy())
        
        # Clear CUDA cache if needed
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
        
        if is_batch:
            return output_images
        else:
            return output_images[0]


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
                 person_image: Union[Image.Image, List[Image.Image]], 
                 cloth_image: Union[Image.Image, List[Image.Image]], 
                 try_on_images: Union[List[Image.Image], List[List[Image.Image]]], 
                 iteration: int,
                 max_new_tokens: int = 1024,
                 temperature: float = 0.3) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Evaluates try-on images. Supports both single samples and batches.
        For batch, try_on_images should be a List of Lists of Images (one history per sample).
        """
        # Determine if batch mode
        is_batch = isinstance(person_image, list)
        
        if is_batch:
            # Normalize inputs
            p_imgs = person_image
            c_imgs = cloth_image
            # try_on_images must be List[List[Image]]
            histories = try_on_images
            batch_size = len(p_imgs)
            print(f"Evaluating VLM batch of {batch_size} samples (Iteration {iteration})...")
        else:
            # Single sample normalized to list format
            p_imgs = [person_image]
            c_imgs = [cloth_image]
            histories = [try_on_images]
            batch_size = 1
            print(f"Evaluating iteration {iteration} for single sample.")

        if not histories or any(not h for h in histories):
             # Handle empty history case
             if is_batch:
                 return [self._default_error_response("No try-on image provided") for _ in range(batch_size)]
             else:
                 return self._default_error_response("No try-on image provided")

        # Move model to GPU for inference
        print("Moving VLM to GPU...")
        self.model.to(self.device)
        
        texts = []
        image_inputs = [] 
        
        for i in range(batch_size):
            p_img = p_imgs[i]
            c_img = c_imgs[i]
            history = histories[i]
            
            system_prompt = self._get_system_prompt()
            user_prompt = self._construct_user_prompt(iteration, len(history))
            
            # Content definition
            content = [
                {"type": "text", "text": system_prompt},
                {"type": "text", "text": "\n\nImage 1 - Original Person:"},
                {"type": "image", "image": p_img},
                {"type": "text", "text": "\n\nImage 2 - Original Cloth:"},
                {"type": "image", "image": c_img},
            ]
            
            # Track images for this sample
            current_sample_images = [p_img, c_img]
            
            for idx, tryon_img in enumerate(history, start=1):
                img_num = idx + 2
                label = "(LATEST - evaluate this)" if idx == len(history) else "(previous attempt)"
                content.append({"type": "text", "text": f"\n\nImage {img_num} - Generated Try-On Iteration {idx} {label}:"})
                content.append({"type": "image", "image": tryon_img})
                current_sample_images.append(tryon_img)
            
            content.append({"type": "text", "text": f"\n\n{user_prompt}"})
            
            # Apply chat template
            text = self.processor.apply_chat_template(
                [{"role": "user", "content": content}],
                tokenize=False,
                add_generation_prompt=True
            )
            texts.append(text)
            image_inputs.append(current_sample_images)

        # Process batch inputs
        # For Qwen2-VL, passing list of texts and list of lists of images works for batching
        inputs = self.processor(
            text=texts,
            images=image_inputs,
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
        generated_ids = output_ids[:, inputs.input_ids.shape[1]:]
        
        response_texts = self.processor.batch_decode(
            generated_ids,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False
        )
        
        # Move model back to CPU
        print("Moving VLM back to CPU...")
        self.model.cpu()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            
        # Parse results
        results = [self._parse_response(r) for r in response_texts]
        
        if is_batch:
            return results
        else:
            return results[0]

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
    
    def _default_error_response(self, error_msg: str) -> Dict[str, Any]:
        return {
            "result": "NOT_SUCCESS",
            "explanation": error_msg,
            "improved_prompt": ""
        }
