import os

# Configuration for the Closed-Loop Feedback Try-On System

class Config:
    def __init__(self):
        # Paths
        self.BASE_DIR = "."
        self.INPUT_DIR = "input"
        self.OUTPUT_DIR = "output"
        
        self.PERSON_DIR = f"{self.INPUT_DIR}/person"
        self.CLOTH_DIR = f"{self.INPUT_DIR}/cloth"
        
        self.CORRECT_TRY_ON_DIR = f"{self.OUTPUT_DIR}/correct_try_on"
        self.INCORRECT_TRY_ON_DIRS = {
            1: f"{self.OUTPUT_DIR}/incorrect_try_on_1",
            2: f"{self.OUTPUT_DIR}/incorrect_try_on_2",
            3: f"{self.OUTPUT_DIR}/incorrect_try_on_3",
            4: f"{self.OUTPUT_DIR}/incorrect_try_on_4",
        }
        
        # Models
        # FLUX options: "4b" or "9b" (for FLUX.2-klein-4B or FLUX.2-klein-9B)
        # Note: Using 4B to save GPU memory when running with VLM
        self.FLUX_MODEL_ID = "9b"
        # Qwen VLM for evaluation
        # Options: "Qwen/Qwen3-VL-8B-Instruct" (16GB) or "Qwen/Qwen3-VL-32B-Instruct" (65GB)
        # Using 8B to fit both models in GPU memory
        self.QWEN_MODEL_ID = "Qwen/Qwen3-VL-8B-Instruct"
        self.DEVICE = "cuda"
        
        # Feedback Loop
        self.MAX_ITERATIONS = 4
        # Critical constraints - cloth and try-on focused
        self.CRITICAL_CONSTRAINTS = ["cloth_structural_integrity", "cloth_texture_fidelity"]
        self.SUCCESS_THRESHOLD = 8
        self.CRITICAL_FAILURE_THRESHOLD = 4

        # AWS S3 Credentials
        self.AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "your_access_key")
        self.AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "your_secret_key")
        self.AWS_REGION_NAME = os.getenv("AWS_REGION_NAME", "ap-south-1")  # Mumbai region
        self.S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "your_bucket_name")
        self.HF_TOKEN = os.getenv("HF_TOKEN", "your_hf_token")
        self.DIFFICULTY = "easy"
        self.GENDER = "female"  # Options: "female" or "male" (matches S3 folder structure)

        # VLM System Prompt (robust default, can be overridden)
        self.VLM_SYSTEM_PROMPT = (
            """
You are the strictest possible Quality Assurance expert for virtual try-on systems. Your job is to identify even the most subtle hallucinations and failures. You must catch any deviation from the original garment.

You will receive:
1. The original person image
2. The original clothing image
3. The generated try-on result

STRICT EVALUATION CRITERIA:

1. **Garment Integrity & Layering Logic**:
   - The generated cloth MUST match the original exactly in texture, material, length, implementation, and regional style.
   - **Layering**: If the try-on item is an outer layer (jacket, coat) or inner layer (shirt), it must be worn LOGICALLY over/under existing clothes if applicable, or replace them entirely if conflicting.
     - FAIL if a jacket is "merged" into the shirt texture.
     - FAIL if inner-wear is drawn on top of outer-wear.

2. **Complex Mismatches (e.g., Saree -> Shirt)**:
   - When the target cloth (e.g., Shirt) is drastically different from the person's initial attire (e.g., Saree/Dress), the system MUST successfully replace the old garment with the new one while maintaining the person's identity and body structure.
   - FAIL if "ghost" remnants of the old garment (e.g., Saree pleats) are left behind or blended into the new outfit (e.g., Shirt).
   - FAIL if the person's body shape is distorted to fit the previous garment's silhouette instead of the new one.

3. **Hallucination & Generalization Check**:
   - FAIL if a full-body regional garment (e.g., Saree, Kimono) is split into separate upper/lower pieces.
   - FAIL if the model generalizes the material (e.g., making pants the same material as the shirt when only the shirt was provided).
   - FAIL if the texture is merely "etched" onto the skin or existing clothes instead of being a 3D garment.
   - FAIL if unrelated parts of the outfit (e.g., shoes, pants when trying on a top) are randomly changed to match the new cloth's texture.

4. **Fit and Realism**:
   - The cloth must drape naturally. It should not look like a flat texture map.
   - There should be no "bleeding" of cloth color onto the skin or background.

If ANY of these issues are present, even slightly, return NOT_SUCCESS. Only return SUCCESS for a perfect, hallucination-free try-on.

Output a VALID JSON object:
{
    "result": "SUCCESS" or "NOT_SUCCESS",
    "explanation": "Extremely detailed description of the failure, specifically mentioning if it was a hallucination, layering error, remnant of old clothes, or generalization issue.",
    "improved_prompt": "A corrected prompt that explicitly addresses the specific failure observed (e.g. 'Completely remove the Saree and replace it with the Shirt', 'Ensure the jacket is worn over the shirt, not merged')."
}

CRITICAL: Return ONLY the JSON object.
"""
        )

config = Config()
