"""
Qwen3-VL-4B-Instruct OPTIMIZED Batch Inference Code
Fixes for slow performance on Vast AI / cloud GPU rentals

Key Optimizations:
1. Flash Attention 2 - Major speedup on A100/H100
2. BFloat16 - Better performance than Float16 on Ampere+ GPUs
3. CUDA optimizations (TF32, cuDNN benchmark)
4. Optional torch.compile for further speedups
5. Better memory management
"""

import os
import torch
from transformers import AutoModelForVision2Seq, AutoProcessor, BitsAndBytesConfig
from PIL import Image
import requests
from io import BytesIO
from typing import List, Union, Optional
import config


def setup_cuda_optimizations():
    """
    Enable CUDA optimizations for maximum performance on A100/H100
    Call this BEFORE loading the model
    """
    if torch.cuda.is_available():
        # Enable TF32 for matrix multiplications (significant speedup on Ampere+)
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        
        # Enable cuDNN autotuner to find the best algorithm
        torch.backends.cudnn.benchmark = True
        torch.backends.cudnn.enabled = True
        
        # Set memory allocator settings for better performance
        # Reduces fragmentation and speeds up allocations
        os.environ.setdefault('PYTORCH_CUDA_ALLOC_CONF', 'expandable_segments:True')
        
        print("✓ CUDA optimizations enabled (TF32, cuDNN benchmark)")
        print(f"  GPU: {torch.cuda.get_device_name(0)}")
        print(f"  CUDA Version: {torch.version.cuda}")
        print(f"  PyTorch Version: {torch.__version__}")


def check_flash_attention_available():
    """Check if Flash Attention 2 is available"""
    try:
        from transformers.utils import is_flash_attn_2_available
        available = is_flash_attn_2_available()
        if available:
            print("✓ Flash Attention 2 is available")
        else:
            print("⚠ Flash Attention 2 NOT available - install with: pip install flash-attn --no-build-isolation")
        return available
    except ImportError:
        print("⚠ Could not check Flash Attention availability")
        return False


class QwenVLBatchInferenceOptimized:
    """
    Optimized Qwen VL inference with:
    - Flash Attention 2 support
    - BFloat16 precision (better for A100/H100)
    - CUDA optimizations
    - Optional torch.compile
    """
    
    def __init__(
        self, 
        model_name: str = "Qwen/Qwen3-VL-4B-Instruct", 
        device: Optional[str] = None,
        use_flash_attention: bool = True,
        use_compile: bool = False,
        use_bettertransformer: bool = False
    ):
        """
        Initialize the Qwen3-VL model with optimizations
        
        Args:
            model_name: HuggingFace model identifier
            device: Device to run inference on (cuda/cpu). Auto-detects if None
            use_flash_attention: Enable Flash Attention 2 (requires flash-attn package)
            use_compile: Use torch.compile() for additional speedup (may increase first-run time)
            use_bettertransformer: Use BetterTransformer optimization (alternative to flash attn)
        """
        # Setup CUDA optimizations FIRST
        setup_cuda_optimizations()
        
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        print(f"\nLoading model on {self.device}...")
        
        # Determine attention implementation
        attn_implementation = None
        flash_available = check_flash_attention_available()
        
        if use_flash_attention and flash_available:
            attn_implementation = "flash_attention_2"
            print("✓ Using Flash Attention 2")
        elif use_flash_attention and not flash_available:
            print("⚠ Flash Attention requested but not available, using default SDPA")
            attn_implementation = "sdpa"  # Scaled Dot Product Attention (PyTorch native)
        else:
            attn_implementation = "sdpa"
            print("✓ Using SDPA (Scaled Dot Product Attention)")
        
        # Determine dtype - BFloat16 is better on A100/H100
        if self.device == "cuda":
            # Check if GPU supports BFloat16 (Ampere and newer)
            if torch.cuda.is_bf16_supported():
                torch_dtype = torch.bfloat16
                print("✓ Using BFloat16 precision (optimal for A100/H100)")
            else:
                torch_dtype = torch.float16
                print("✓ Using Float16 precision")
        else:
            torch_dtype = torch.float32
            print("✓ Using Float32 precision (CPU)")
        
        # Load processor
        self.processor = AutoProcessor.from_pretrained(
            model_name,
            trust_remote_code=True
        )
        
        # Load model with optimizations
        model_kwargs = {
            "torch_dtype": torch_dtype,
            "trust_remote_code=True",
            "low_cpu_mem_usage": True,  # Reduce CPU memory during loading
        }
        
        if self.device == "cuda":
            model_kwargs["device_map"] = "auto"
            if attn_implementation:
                model_kwargs["attn_implementation"] = attn_implementation
        
        # Fix the kwargs - trust_remote_code should not be a string
        self.model = AutoModelForVision2Seq.from_pretrained(
            model_name,
            torch_dtype=torch_dtype,
            device_map="auto" if self.device == "cuda" else None,
            trust_remote_code=True,
            low_cpu_mem_usage=True,
            attn_implementation=attn_implementation if self.device == "cuda" else None,
        )
        
        if self.device == "cpu":
            self.model = self.model.to(self.device)
        
        # Optional: Apply torch.compile for additional speedup
        # Note: First inference will be slower due to compilation
        if use_compile and self.device == "cuda":
            try:
                print("Applying torch.compile() optimization...")
                self.model = torch.compile(self.model, mode="reduce-overhead")
                print("✓ torch.compile() applied")
            except Exception as e:
                print(f"⚠ torch.compile() failed: {e}")
        
        # Optional: BetterTransformer (alternative to flash attention)
        if use_bettertransformer and not use_flash_attention:
            try:
                from optimum.bettertransformer import BetterTransformer
                self.model = BetterTransformer.transform(self.model)
                print("✓ BetterTransformer applied")
            except ImportError:
                print("⚠ BetterTransformer not available (install optimum)")
            except Exception as e:
                print(f"⚠ BetterTransformer failed: {e}")
        
        self.model.eval()
        
        # Warmup GPU with a dummy forward pass
        if self.device == "cuda":
            self._warmup()
        
        print("✓ Model loaded successfully!")
        self._print_memory_stats()
    
    def _warmup(self):
        """Warmup the GPU with a small forward pass to initialize CUDA kernels"""
        print("Warming up GPU...")
        try:
            # Create a small dummy image
            dummy_image = Image.new('RGB', (224, 224), color='white')
            dummy_messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": dummy_image},
                        {"type": "text", "text": "Hi"}
                    ]
                }
            ]
            
            text = self.processor.apply_chat_template(
                dummy_messages,
                tokenize=False,
                add_generation_prompt=True
            )
            
            inputs = self.processor(
                text=[text],
                images=[dummy_image],
                return_tensors="pt",
                padding=True
            ).to(self.device)
            
            with torch.no_grad():
                _ = self.model.generate(
                    **inputs,
                    max_new_tokens=1,
                    do_sample=False
                )
            
            # Clear cache after warmup
            torch.cuda.empty_cache()
            print("✓ GPU warmup complete")
        except Exception as e:
            print(f"⚠ Warmup failed (non-critical): {e}")
    
    def _print_memory_stats(self):
        """Print GPU memory statistics"""
        if torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated() / 1024**3
            reserved = torch.cuda.memory_reserved() / 1024**3
            total = torch.cuda.get_device_properties(0).total_memory / 1024**3
            print(f"  GPU Memory: {allocated:.2f}GB allocated, {reserved:.2f}GB reserved, {total:.2f}GB total")
    
    def load_image(self, image_source: str) -> Image.Image:
        """
        Load image from file path or URL (http/s, s3)
        
        Args:
            image_source: Path to local image or URL
            
        Returns:
            PIL Image object
        """
        if image_source.startswith(('http://', 'https://')):
            response = requests.get(image_source, timeout=30)
            img = Image.open(BytesIO(response.content))
        elif image_source.startswith('s3://'):
            try:
                import boto3
                parts = image_source.replace("s3://", "").split("/", 1)
                bucket = parts[0]
                key = parts[1]
                
                s3 = boto3.client(
                    's3',
                    aws_access_key_id=config.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
                    region_name=config.AWS_REGION_NAME
                )
                response = s3.get_object(Bucket=bucket, Key=key)
                img = Image.open(BytesIO(response['Body'].read()))
            except Exception as e:
                print(f"Error loading from S3: {e}")
                raise
        else:
            img = Image.open(image_source)
        
        return img.convert('RGB')
    
    @torch.inference_mode()  # Slightly faster than torch.no_grad()
    def batch_inference_multi_image(
        self, 
        image_sources: List[Union[str, Image.Image]], 
        prompts: List[str], 
        max_new_tokens: int = 512, 
        temperature: float = 0.7
    ) -> List[str]:
        """
        Run batch inference with DIFFERENT images and DIFFERENT prompts
        Each image gets its own prompt in a single forward pass
        
        Args:
            image_sources: List of paths (str) OR PIL Image objects
            prompts: List of text prompts (one per image)
            max_new_tokens: Maximum number of tokens to generate
            temperature: Sampling temperature (higher = more creative)
            
        Returns:
            List of generated text responses (one per image/prompt pair)
        """
        batch_size = len(image_sources)
        
        if len(prompts) != batch_size:
            raise ValueError(f"Number of images ({batch_size}) must match number of prompts ({len(prompts)})")
        
        # Load all images if they are strings
        images = []
        for img_src in image_sources:
            if isinstance(img_src, str):
                images.append(self.load_image(img_src))
            else:
                images.append(img_src)
        
        # Prepare batch of messages
        messages_batch = []
        for image, prompt in zip(images, prompts):
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": image},
                        {"type": "text", "text": prompt}
                    ]
                }
            ]
            messages_batch.append(messages)
        
        # Apply chat template to all messages
        texts = [
            self.processor.apply_chat_template(
                messages, 
                tokenize=False, 
                add_generation_prompt=True
            )
            for messages in messages_batch
        ]
        
        # Process inputs in batch
        inputs = self.processor(
            text=texts,
            images=images,
            return_tensors="pt",
            padding=True,
            truncation=True
        ).to(self.device)
        
        # Generate responses in batch
        output_ids = self.model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            do_sample=True if temperature > 0 else False,
            pad_token_id=self.processor.tokenizer.pad_token_id,
            # Performance optimizations for generation
            use_cache=True,  # Enable KV cache
        )
        
        # Decode all outputs
        generated_ids = [
            output_ids[i][len(inputs.input_ids[i]):] 
            for i in range(len(output_ids))
        ]
        
        responses = self.processor.batch_decode(
            generated_ids, 
            skip_special_tokens=True, 
            clean_up_tokenization_spaces=False
        )
        
        return responses
    
    def batch_inference(
        self, 
        image_source: str, 
        prompts: List[str], 
        max_new_tokens: int = 512, 
        temperature: float = 0.7
    ) -> List[str]:
        """
        Run batch inference - same image with multiple prompts
        (For backward compatibility)
        """
        batch_size = len(prompts)
        image = self.load_image(image_source)
        
        messages_batch = []
        for prompt in prompts:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": image},
                        {"type": "text", "text": prompt}
                    ]
                }
            ]
            messages_batch.append(messages)
        
        texts = [
            self.processor.apply_chat_template(
                messages, 
                tokenize=False, 
                add_generation_prompt=True
            )
            for messages in messages_batch
        ]
        
        inputs = self.processor(
            text=texts,
            images=[image] * batch_size,
            return_tensors="pt",
            padding=True,
            truncation=True
        ).to(self.device)
        
        with torch.inference_mode():
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=True if temperature > 0 else False,
                pad_token_id=self.processor.tokenizer.pad_token_id,
                use_cache=True,
            )
        
        generated_ids = [
            output_ids[i][len(inputs.input_ids[i]):] 
            for i in range(len(output_ids))
        ]
        
        responses = self.processor.batch_decode(
            generated_ids, 
            skip_special_tokens=True, 
            clean_up_tokenization_spaces=False
        )
        
        return responses
    
    def single_inference(self, image_source: str, prompt: str, max_new_tokens: int = 512, temperature: float = 0.7) -> str:
        """Run inference on a single prompt"""
        responses = self.batch_inference(image_source, [prompt], max_new_tokens, temperature)
        return responses[0]


# Convenience alias to match original class name pattern
QwenVLBatchInference = QwenVLBatchInferenceOptimized


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Testing Optimized Qwen VL Batch Inference")
    print("="*60 + "\n")
    
    # Initialize with optimizations
    model = QwenVLBatchInferenceOptimized(
        use_flash_attention=True,
        use_compile=False  # Set True for additional speedup (slower first run)
    )
    
    # Simple test
    print("\nReady for inference!")
