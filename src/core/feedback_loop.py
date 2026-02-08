from .models import FluxGenerator, QwenVLM
import sys
import os
# Add parent directory to path so we can import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.helpers import save_image

class FeedbackSystem:
    def __init__(self, generator: FluxGenerator, evaluator: QwenVLM, config):
        self.generator = generator
        self.evaluator = evaluator
        self.config = config
        
    def run(self, person_name: str, cloth_name: str, person_img: object, cloth_img: object, initial_prompt: str):
        
        # Store initial inputs
        current_prompt = initial_prompt
        try_on_history = [] # List of images generated so far

        print(f"Starting feedback loop for {person_name} and {cloth_name}")

        for i in range(1, self.config.MAX_ITERATIONS + 1):
            print(f"--- Iteration {i} ---")
            
            # Generate Image using Flux
            try_on_img = self.generator.generate(person_img, cloth_img, current_prompt)
            try_on_history.append(try_on_img)
            
            # Evaluate using VLM with history
            eval_result = self.evaluator.evaluate(person_img, cloth_img, try_on_history, iteration=i)
            
            # Extract checks and scores
            feedback = eval_result.get("feedback", "No feedback provided")
            improved_prompt = eval_result.get("improved_prompt", current_prompt)
            scores = eval_result.get("constraint_scores", {})

            # Rule-Based Decision Logic
            status = "CONTINUE"
            
            # 1. Critical Failure Check
            if any(scores.get(k, 0) < self.config.CRITICAL_FAILURE_THRESHOLD for k in self.config.CRITICAL_CONSTRAINTS):
                 print(f"Critical failure detected in {self.config.CRITICAL_CONSTRAINTS}. ABORTING.")
                 status = "ABORT"
            
            # 2. Success Check 
            elif all(score >= self.config.SUCCESS_THRESHOLD for score in scores.values()):
                 print(f"All constraint scores are high (>= {self.config.SUCCESS_THRESHOLD}). SUCCESS.")
                 status = "SUCCESS"
            
            # 3. Continue Check
            else:
                 print("Scores are mixed. CONTINUING with improved prompt.")
                 status = "CONTINUE"

            print(f"Computed Status: {status}")
            print(f"Scores: {scores}")
            print(f"Feedback: {feedback}")

            output_filename = f"{os.path.splitext(person_name)[0]}_{os.path.splitext(cloth_name)[0]}_iter{i}.png"
            
            if status == "SUCCESS":
                save_dir = self.config.CORRECT_TRY_ON_DIR
                save_image(try_on_img, save_dir, output_filename)
                print("Try-on successful!")
                return 
            
            elif status == "CONTINUE":
                # Save as incorrect for this stage
                save_dir = self.config.INCORRECT_TRY_ON_DIRS.get(i, f"{self.config.OUTPUT_DIR}/unknown_iter")
                save_image(try_on_img, save_dir, output_filename)
                
                if i == self.config.MAX_ITERATIONS:
                    print("Max iterations reached. Stopping.")
                    return

                current_prompt = improved_prompt
                print(f"Retrying with improved prompt: {current_prompt}")
                
            elif status == "ABORT":
                save_dir = self.config.INCORRECT_TRY_ON_DIRS.get(i, f"{self.config.OUTPUT_DIR}/unknown_iter")
                save_image(try_on_img, save_dir, output_filename)
                print("ABORT received. Stopping feedback loop.")
                return

            else:
                 print(f"Unknown status '{status}'. Aborting.")
                 return
