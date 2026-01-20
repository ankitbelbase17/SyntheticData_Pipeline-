import os

def create_scripts():
    os.makedirs("scripts", exist_ok=True)
    
    # Configuration
    num_shards_male = 7
    num_shards_female = 7
    batch_size = 28
    
    # Generate Male Scripts
    print("Generating Male Scripts...")
    for i in range(num_shards_male):
        filename = f"scripts/run_vlm_male_{i}.sh"
        content = (
            f"#!/bin/bash\n"
            f"# Auto-generated script for Male Shard {i}/{num_shards_male}\n"
            f"python qwen_batch_inference.py \\\n"
            f"  --gender male \\\n"
            f"  --difficulty medium \\\n"
            f"  --batch_size {batch_size} \\\n"
            f"  --shard_id {i} \\\n"
            f"  --total_shards {num_shards_male}\n"
        )
        
        with open(filename, "w") as f:
            f.write(content)
        print(f"  Created {filename}")

    # Generate Female Scripts
    print("\nGenerating Female Scripts...")
    for i in range(num_shards_female):
        filename = f"scripts/run_vlm_female_{i}.sh"
        content = (
            f"#!/bin/bash\n"
            f"# Auto-generated script for Female Shard {i}/{num_shards_female}\n"
            f"python qwen_batch_inference.py \\\n"
            f"  --gender female \\\n"
            f"  --difficulty medium \\\n"
            f"  --batch_size {batch_size} \\\n"
            f"  --shard_id {i} \\\n"
            f"  --total_shards {num_shards_female}\n"
        )
        
        with open(filename, "w") as f:
            f.write(content)
        print(f"  Created {filename}")

if __name__ == "__main__":
    create_scripts()
