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
        import time
        current_prompt = initial_prompt
        try_on_history = []
        print(f"Starting feedback loop for {person_name} and {cloth_name}")
        
        total_gen_time = 0
        total_eval_time = 0
        total_io_time = 0
        
        for i in range(1, self.config.MAX_ITERATIONS + 1):
            print(f"--- Iteration {i} ---")
            iter_start = time.time()
            
            # Measure Generation Latency
            t0 = time.time()
            try_on_img = self.generator.generate(person_img, cloth_img, current_prompt)
            gen_time = time.time() - t0
            total_gen_time += gen_time
            print(f"  [Latency] Flux Generation: {gen_time:.4f}s")
            
            try_on_history.append(try_on_img)
            
            # Measure Evaluation Latency
            t0 = time.time()
            eval_result = self.evaluator.evaluate(person_img, cloth_img, try_on_history, iteration=i)
            eval_time = time.time() - t0
            total_eval_time += eval_time
            print(f"  [Latency] VLM Evaluation:  {eval_time:.4f}s")

            # VLM now returns 'result' (SUCCESS/NOT_SUCCESS), 'explanation', 'improved_prompt'
            result = eval_result.get("result", "NOT_SUCCESS")
            explanation = eval_result.get("explanation", "No explanation provided")
            improved_prompt = eval_result.get("improved_prompt", current_prompt)
            print(f"VLM result: {result}")
            print(f"Explanation: {explanation}")
            
            # Simple naming convention: {sample_id}_tryon_iter{i}.png
            output_filename = f"{sample_id}_tryon_iter{i}.png"
            
            # Measure IO Latency
            t0 = time.time()
            if result == "SUCCESS":
                save_dir = self.config.CORRECT_TRY_ON_DIR
                save_image(try_on_img, save_dir, output_filename)
                print("Try-on successful! Saved to correct_try_on.")
                io_time = time.time() - t0
                total_io_time += io_time
                print(f"  [Latency] Disk Save:       {io_time:.4f}s")
                print(f"  [Latency] Disk Save:       {io_time:.4f}s")
                return {
                    "status": "SUCCESS",
                    "iteration": i,
                    "image": try_on_img,
                    "filename": output_filename,
                    "local_path": os.path.join(save_dir, output_filename)
                }
            else:
                # Save as incorrect for this stage
                save_dir = self.config.INCORRECT_TRY_ON_DIRS.get(i, f"{self.config.OUTPUT_DIR}/unknown_iter")
                save_image(try_on_img, save_dir, output_filename)
                io_time = time.time() - t0
                total_io_time += io_time
                print(f"  [Latency] Disk Save:       {io_time:.4f}s")
                
                if i == self.config.MAX_ITERATIONS:
                    print("Max iterations reached. Stopping.")
                    print(f"\n[Summary] Total Generation: {total_gen_time:.2f}s | Total Eval: {total_eval_time:.2f}s | Total IO: {total_io_time:.2f}s")
                    print(f"\n[Summary] Total Generation: {total_gen_time:.2f}s | Total Eval: {total_eval_time:.2f}s | Total IO: {total_io_time:.2f}s")
                    # Return the last attempt as failure
                    # Since we save incorrect attempts, we can return the last filepath
                    last_save_dir = save_dir
                    return {
                        "status": "NOT_SUCCESS",
                        "iteration": i,
                        "image": try_on_img,
                        "filename": output_filename,
                        "local_path": os.path.join(last_save_dir, output_filename)
                    }
                current_prompt = improved_prompt
                print(f"Retrying with improved prompt: {current_prompt}")
            
            iter_total = time.time() - iter_start
            print(f"  [Latency] Iteration Total: {iter_total:.4f}s")
