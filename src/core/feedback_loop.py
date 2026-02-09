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
        
    def run(self, person_name: str, cloth_name: str, person_img: object, cloth_img: object, initial_prompt: str, sample_id: int):
        current_prompt = initial_prompt
        try_on_history = []
        print(f"Starting feedback loop for {person_name} and {cloth_name}")
        for i in range(1, self.config.MAX_ITERATIONS + 1):
            print(f"--- Iteration {i} ---")
            try_on_img = self.generator.generate(person_img, cloth_img, current_prompt)
            try_on_history.append(try_on_img)
            eval_result = self.evaluator.evaluate(person_img, cloth_img, try_on_history, iteration=i)
            # VLM now returns 'result' (SUCCESS/NOT_SUCCESS), 'explanation', 'improved_prompt'
            result = eval_result.get("result", "NOT_SUCCESS")
            explanation = eval_result.get("explanation", "No explanation provided")
            improved_prompt = eval_result.get("improved_prompt", current_prompt)
            print(f"VLM result: {result}")
            print(f"Explanation: {explanation}")
            
            # Simple naming convention: {sample_id}_tryon_iter{i}.png
            output_filename = f"{sample_id}_tryon_iter{i}.png"
            
            if result == "SUCCESS":
                save_dir = self.config.CORRECT_TRY_ON_DIR
                save_image(try_on_img, save_dir, output_filename)
                print("Try-on successful! Saved to correct_try_on.")
                return
            else:
                # Save as incorrect for this stage
                save_dir = self.config.INCORRECT_TRY_ON_DIRS.get(i, f"{self.config.OUTPUT_DIR}/unknown_iter")
                save_image(try_on_img, save_dir, output_filename)
                if i == self.config.MAX_ITERATIONS:
                    print("Max iterations reached. Stopping.")
                    return
                current_prompt = improved_prompt
                print(f"Retrying with improved prompt: {current_prompt}")
