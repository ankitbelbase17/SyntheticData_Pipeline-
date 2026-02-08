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
        self.FLUX_MODEL_ID = "flux-2-klein-9b"
        self.QWEN_MODEL_ID = "Qwen/Qwen-VL-Chat"
        self.DEVICE = "cuda"
        
        # Feedback Loop
        self.MAX_ITERATIONS = 4
        self.CRITICAL_CONSTRAINTS = ["body_integrity", "identity_preservation", "pose_alignment"]
        self.SUCCESS_THRESHOLD = 8
        self.CRITICAL_FAILURE_THRESHOLD = 4

        # AWS S3 Credentials
        self.AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "your_access_key")
        self.AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "your_secret_key")
        self.AWS_REGION_NAME = os.getenv("AWS_REGION_NAME", "us-east-1")
        self.S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "your_bucket_name")
        self.HF_TOKEN = os.getenv("HF_TOKEN", "your_hf_token")
        self.DIFFICULTY = "easy"
        self.GENDER = "lower_body"

config = Config()
