"""
Qwen 2.5 VL Processor: Multi-image analysis and structured prompt generation for edit-based models.
Takes person image, clothing image(s), and context to generate strong editing prompts.
"""

import json
import base64
from pathlib import Path
from typing import List, Dict, Any
import torch
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
from PIL import Image

# Model configuration
MODEL_NAME = "Qwen/Qwen2-VL-7B-Instruct"  # or "Qwen/Qwen2.5-VL-7B-Instruct" if available

class QwenVLProcessor:
    def __init__(self, model_name: str = MODEL_NAME, device: str = "cuda" if torch.cuda.is_available() else "cpu"):
        """Initialize Qwen VL model."""
        self.device = device
        self.model = Qwen2VLForConditionalGeneration.from_pretrained(
            model_name,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            attn_implementation="flash_attention_2" if device == "cuda" else "eager"
        ).to(device)
        self.processor = AutoProcessor.from_pretrained(model_name)

    @staticmethod
    def encode_image_to_base64(image_path: str) -> str:
        """Encode image to base64 for processing."""
        with open(image_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')

    @staticmethod
    def load_image(image_path: str) -> Image.Image:
        """Load image from path."""
        return Image.open(image_path).convert('RGB')

    def generate_edit_prompt(
        self,
        person_image_path: str,
        clothing_images: List[str],
        context_prompt: str,
        keyword_dict: Dict[str, Any] = None,
        max_tokens: int = 512
    ) -> Dict[str, Any]:
        """
        Generate a structured prompt for edit-based models using Qwen VL.
        
        Args:
            person_image_path: Path to person/human image
            clothing_images: List of paths to clothing images
            context_prompt: Context/task description for Qwen VL
            keyword_dict: Sampled keywords dictionary from keyword_sampler.py
            max_tokens: Max tokens for model output
            
        Returns:
            Structured dict with editing instructions for edit-based models
        """
        
        # Load images
        person_img = self.load_image(person_image_path)
        clothing_imgs = [self.load_image(img_path) for img_path in clothing_images]
        
        # Build multi-image prompt for Qwen VL
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": person_img},
                    *[{"type": "image", "image": img} for img in clothing_imgs],
                    {
                        "type": "text",
                        "text": self._build_qwen_prompt(context_prompt, keyword_dict)
                    }
                ]
            }
        ]
        
        # Prepare inputs
        text = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.processor(
            text=text,
            images=[person_img] + clothing_imgs,
            padding=True,
            return_tensors="pt"
        ).to(self.device)
        
        # Generate response
        with torch.no_grad():
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=0.7,
                top_p=0.9
            )
        
        response = self.processor.decode(
            output_ids[0],
            skip_special_tokens=True
        )
        
        # Parse and structure response
        structured_output = self._parse_vl_response(response, person_image_path, clothing_images)
        
        return structured_output

    @staticmethod
    def _build_qwen_prompt(context_prompt: str, keyword_dict: Dict[str, Any] = None) -> str:
        """Build a structured prompt for Qwen VL."""
        base_prompt = f"""
Role: Vision-Language Model (Qwen 2.5 VL)
Task: Analyze person and clothing images to generate detailed editing instructions

Images Provided:
1. Person Image: Human in current outfit/pose
2. Clothing Image(s): Target garment(s) to try on

{context_prompt}

Analysis Requirements:
1. Describe the person: body shape, skin tone, pose, visible characteristics
2. Describe current clothing: type, fit, color, material, style
3. Describe target clothing: type, fit, color, material, style
4. Identify key transitions: fit changes, fabric drape, color harmony
5. Generate detailed editing instructions for virtual try-on

Output Format (STRICT JSON):
{{
    "person_analysis": {{
        "body_shape": "...",
        "skin_tone": "...",
        "pose": "...",
        "visible_characteristics": ["..."],
        "standing_position": "front|side|back",
        "arm_position": "..."
    }},
    "current_clothing": {{
        "type": "...",
        "fit": "...",
        "color": "...",
        "material": "...",
        "style": "..."
    }},
    "target_clothing": {{
        "type": "...",
        "fit": "...",
        "color": "...",
        "material": "...",
        "style": "..."
    }},
    "transition_notes": {{
        "fit_changes": "...",
        "fabric_drape": "...",
        "color_harmony": "...",
        "style_compatibility": "..."
    }},
    "edit_instructions": [
        "instruction 1",
        "instruction 2",
        "..."
    ],
    "edit_strength": "light|medium|strong",
    "confidence_score": 0.0-1.0,
    "feasibility": "high|medium|low"
}}

Ensure JSON is valid and all fields are populated.
"""
        return base_prompt

    @staticmethod
    def _parse_vl_response(response: str, person_image_path: str, clothing_images: List[str]) -> Dict[str, Any]:
        """Parse Qwen VL response and structure for edit-based models."""
        try:
            # Extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                json_str = response[json_start:json_end]
                parsed = json.loads(json_str)
            else:
                parsed = {"raw_response": response}
        except json.JSONDecodeError:
            parsed = {"raw_response": response}
        
        # Structure for edit-based models (InstructPix2Pix, etc.)
        structured_output = {
            "source": {
                "person_image": person_image_path,
                "clothing_images": clothing_images
            },
            "vl_analysis": parsed,
            "edit_prompt_for_model": _generate_edit_model_prompt(parsed),
            "metadata": {
                "model": "Qwen2.5-VL",
                "task": "virtual_try_on",
                "output_type": "structured_editing_instructions"
            }
        }
        
        return structured_output


def _generate_edit_model_prompt(vl_analysis: Dict[str, Any]) -> str:
    """
    Generate a concise, high-quality prompt for edit-based models (InstructPix2Pix, etc.).
    Based on Qwen VL analysis.
    """
    if "edit_instructions" in vl_analysis:
        instructions = vl_analysis["edit_instructions"]
    else:
        instructions = []
    
    person_desc = vl_analysis.get("person_analysis", {})
    target_clothing = vl_analysis.get("target_clothing", {})
    transition = vl_analysis.get("transition_notes", {})
    
    prompt = f"""Replace the clothing in the image with {target_clothing.get('type', 'the target garment')} 
that is {target_clothing.get('fit', 'well-fitted')} and {target_clothing.get('color', 'appropriately colored')}.
The person has {person_desc.get('body_shape', 'a human')} body shape and is in {person_desc.get('pose', 'standing')} pose.
Ensure {transition.get('fabric_drape', 'natural fabric drape')} and {transition.get('color_harmony', 'color harmony')}.
"""
    
    if instructions:
        prompt += "\nDetailed instructions:\n"
        prompt += "\n".join(f"- {instr}" for instr in instructions[:5])  # Limit to 5 instructions
    
    return prompt.strip()


def process_and_save_edits(
    person_image_path: str,
    clothing_images: List[str],
    context_prompt: str,
    output_json_path: str,
    keyword_dict: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Full pipeline: Process images with Qwen VL and save structured output.
    
    Args:
        person_image_path: Path to person image
        clothing_images: List of clothing image paths
        context_prompt: Context for VL model
        output_json_path: Path to save output JSON
        keyword_dict: Optional sampled keywords dictionary
        
    Returns:
        Structured output dictionary
    """
    processor = QwenVLProcessor()
    
    # Generate edit prompt
    result = processor.generate_edit_prompt(
        person_image_path,
        clothing_images,
        context_prompt,
        keyword_dict
    )
    
    # Save to JSON
    output_dir = Path(output_json_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(output_json_path, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"[Qwen VL] Saved structured output to {output_json_path}")
    
    return result


# Example usage:
if __name__ == "__main__":
    # Example context prompt
    context = """
    Perform virtual try-on: Replace current clothing with target garment.
    Focus on realism: fabric drape, fit, color harmony, lighting consistency.
    Ensure seamless integration with person's body and pose.
    """
    
    # Example paths (replace with actual)
    person_img = "images/human/person_001.jpg"
    clothing_imgs = ["images/cloth/shirt_001.jpg", "images/cloth/pants_001.jpg"]
    output_json = "outputs/vl_analysis/result_001.json"
    
    # Process
    result = process_and_save_edits(
        person_img,
        clothing_imgs,
        context,
        output_json
    )
    
    print("Generated Edit Prompt:")
    print(result["edit_prompt_for_model"])
