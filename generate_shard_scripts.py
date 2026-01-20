import os

def create_scripts():
    difficulties = ['easy', 'medium', 'hard']
    num_shards_male = 7
    num_shards_female = 7
    batch_size = 28
    for diff in difficulties:
        # Set epochs based on user request (3 for all)
        epochs = 3
            
        folder_name = f"{diff}_bash_scripts"
        os.makedirs(folder_name, exist_ok=True)
        print(f"\nGenerating {diff.upper()} Scripts in {folder_name}/... (Epochs: {epochs})")
        
        # --- Generate Male Scripts ---
        for i in range(num_shards_male):
            filename = f"{folder_name}/run_vlm_male_{i}.sh"
            content = (
                f"#!/bin/bash\n"
                f"# Auto-generated script for Male Shard {i}/{num_shards_male} ({diff})\n"
                f"python qwen_batch_inference.py \\\n"
                f"  --gender male \\\n"
                f"  --difficulty {diff} \\\n"
                f"  --batch_size {batch_size} \\\n"
                f"  --shard_id {i} \\\n"
                f"  --total_shards {num_shards_male} \\\n"
                f"  --epochs {epochs}\n"
            )
            
            with open(filename, "w") as f:
                f.write(content)
            print(f"  Created {filename}")

        # --- Generate Female Scripts ---
        for i in range(num_shards_female):
            filename = f"{folder_name}/run_vlm_female_{i}.sh"
            content = (
                f"#!/bin/bash\n"
                f"# Auto-generated script for Female Shard {i}/{num_shards_female} ({diff})\n"
                f"python qwen_batch_inference.py \\\n"
                f"  --gender female \\\n"
                f"  --difficulty {diff} \\\n"
                f"  --batch_size {batch_size} \\\n"
                f"  --shard_id {i} \\\n"
                f"  --total_shards {num_shards_female} \\\n"
                f"  --epochs {epochs}\n"
            )
            
            with open(filename, "w") as f:
                f.write(content)
            print(f"  Created {filename}")

if __name__ == "__main__":
    create_scripts()
