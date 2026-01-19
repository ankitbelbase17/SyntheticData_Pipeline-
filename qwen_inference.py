"""
Qwen3-VL-4B-Instruct TRUE Batch Inference Code for Lightning AI Studio
Processes multiple different images with different prompts in a single forward pass
"""

import torch
from transformers import AutoModelForVision2Seq, AutoProcessor
from PIL import Image
import requests
from io import BytesIO
from typing import List, Union


class QwenVLBatchInference:
    def __init__(self, model_name="Qwen/Qwen3-VL-4B-Instruct", device=None):
        """
        Initialize the Qwen3-VL model for batch inference
        
        Args:
            model_name: HuggingFace model identifier
            device: Device to run inference on (cuda/cpu). Auto-detects if None
        """
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Loading model on {self.device}...")
        
        # Load processor and model
        self.processor = AutoProcessor.from_pretrained(
            model_name,
            trust_remote_code=True
        )
        
        self.model = AutoModelForVision2Seq.from_pretrained(
            model_name,
            torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
            device_map="auto" if self.device == "cuda" else None,
            trust_remote_code=True
        )
        
        if self.device == "cpu":
            self.model = self.model.to(self.device)
        
        self.model.eval()  # Set to evaluation mode
        print("Model loaded successfully!")
    
    def load_image(self, image_source):
        """
        Load image from file path or URL
        
        Args:
            image_source: Path to local image or URL
            
        Returns:
            PIL Image object
        """
        if image_source.startswith(('http://', 'https://')):
            response = requests.get(image_source)
            img = Image.open(BytesIO(response.content))
        else:
            img = Image.open(image_source)
        
        return img.convert('RGB')
    
    def batch_inference_multi_image(
        self, 
        image_sources: List[str], 
        prompts: List[str], 
        max_new_tokens: int = 512, 
        temperature: float = 0.7
    ):
        """
        Run batch inference with DIFFERENT images and DIFFERENT prompts
        Each image gets its own prompt in a single forward pass
        
        Args:
            image_sources: List of paths to different images (one per prompt)
            prompts: List of text prompts (one per image)
            max_new_tokens: Maximum number of tokens to generate
            temperature: Sampling temperature (higher = more creative)
            
        Returns:
            List of generated text responses (one per image/prompt pair)
        """
        batch_size = len(image_sources)
        
        if len(prompts) != batch_size:
            raise ValueError(f"Number of images ({batch_size}) must match number of prompts ({len(prompts)})")
        
        print(f"Processing batch of {batch_size} different images...")
        
        # Load all images
        images = [self.load_image(img_src) for img_src in image_sources]
        
        # Prepare batch of messages (different image + different prompt for each)
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
        # Each sample gets its own image and text
        inputs = self.processor(
            text=texts,
            images=images,  # Different image for each sample
            return_tensors="pt",
            padding=True,  # Pad to same length for batching
            truncation=True
        ).to(self.device)
        
        # Generate responses in batch
        print(f"Running batch generation on {self.device}...")
        with torch.no_grad():
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=True if temperature > 0 else False,
                pad_token_id=self.processor.tokenizer.pad_token_id,
            )
        
        # Decode all outputs
        # Extract only the newly generated tokens (not the input)
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
    ):
        """
        Run batch inference - same image with multiple prompts
        (For backward compatibility)
        
        Args:
            image_source: Path to image or URL (same image for all prompts)
            prompts: List of text prompts to process in batch
            max_new_tokens: Maximum number of tokens to generate
            temperature: Sampling temperature (higher = more creative)
            
        Returns:
            List of generated text responses (one per prompt)
        """
        batch_size = len(prompts)
        print(f"Processing batch of {batch_size} prompts on same image...")
        
        # Load image once
        image = self.load_image(image_source)
        
        # Prepare batch of messages (same image, different prompts)
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
        # Each sample gets the same image but different text
        inputs = self.processor(
            text=texts,
            images=[image] * batch_size,  # Same image repeated
            return_tensors="pt",
            padding=True,  # Pad to same length for batching
            truncation=True
        ).to(self.device)
        
        # Generate responses in batch
        print(f"Running batch generation on {self.device}...")
        with torch.no_grad():
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=True if temperature > 0 else False,
                pad_token_id=self.processor.tokenizer.pad_token_id,
            )
        
        # Decode all outputs
        # Extract only the newly generated tokens (not the input)
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
    
    def single_inference(self, image_source, prompt, max_new_tokens=512, temperature=0.7):
        """
        Run inference on a single prompt (for backward compatibility)
        
        Args:
            image_source: Path to image or URL
            prompt: Text prompt/question about the image
            max_new_tokens: Maximum number of tokens to generate
            temperature: Sampling temperature
            
        Returns:
            Generated text response
        """
        responses = self.batch_inference(
            image_source, 
            [prompt], 
            max_new_tokens, 
            temperature
        )
        return responses[0]


# Example usage for testing
if __name__ == "__main__":
    # Initialize the model
    model = QwenVLBatchInference()
    
    # Example: Batch inference with different images
    image_paths = [
        "./data/images/image1.png",
        "./data/images/image2.png",
        "./data/images/image3.png",
        "./data/images/image4.png"
    ]
    
    batch_prompts = [
        "Describe this image in detail.",
        "What is the person wearing?",
        "What is the background like?",
        "Describe the lighting and pose."
    ]
    
    print(f"\n{'='*60}")
    print("Testing multi-image batch inference...")
    print(f"{'='*60}\n")
    
    import time
    start = time.time()
    responses = model.batch_inference_multi_image(
        image_sources=image_paths,
        prompts=batch_prompts,
        max_new_tokens=256,
        temperature=0.7
    )
    elapsed = time.time() - start
    
    print(f"\nBatch processing completed in {elapsed:.2f}s")
    print(f"Average time per image: {elapsed/len(batch_prompts):.3f}s\n")
    
    for i, (img, prompt, response) in enumerate(zip(image_paths, batch_prompts, responses), 1):
        print(f"--- Image {i}: {img} ---")
        print(f"Q: {prompt}")
        print(f"A: {response}\n")