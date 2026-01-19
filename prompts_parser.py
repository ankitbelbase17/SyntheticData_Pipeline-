#!/usr/bin/env python3
"""
Parser for prompts JSONL files.
Reads all prompts from the specified JSONL files and saves each to individual .txt files.
"""

import json
from pathlib import Path
from typing import List


def parse_and_save_prompts(jsonl_files: List[str], output_dir: str = "prompts"):
    """
    Parse JSONL files and save each prompt to individual .txt files.
    
    Args:
        jsonl_files: List of paths to the JSONL files to parse.
        output_dir: Directory to save the prompt files (default: prompts)
    """
    output_path = Path(output_dir)
    
    # Create output directory if it doesn't exist
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Clear existing files in the output directory
    print(f"Clearing existing .txt files in '{output_dir}'...")
    for existing_file in output_path.glob("*.txt"):
        try:
            existing_file.unlink()
        except OSError as e:
            print(f"Error deleting {existing_file}: {e}")
    
    total_prompts_saved = 0
    
    for file_path_str in jsonl_files:
        file_path = Path(file_path_str)
        if not file_path.exists():
            print(f"Error: File '{file_path_str}' not found.")
            continue
            
        print(f"Processing '{file_path_str}'...")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:  # Skip empty lines
                        continue
                    
                    try:
                        data = json.loads(line)
                        
                        # Extract relevant fields
                        prompt_number = data.get("prompt_number")
                        prompt = data.get("prompt", "")
                        dress_name = data.get("dress_name", "N/A")
                        setting = data.get("setting", "N/A")
                        
                        if prompt_number is None:
                            print(f"Warning: 'prompt_number' missing in line {line_num} of {file_path_str}. Skipping.")
                            continue

                        # Create formatted content for the file
                        file_content = f"""Prompt Number: {prompt_number}
Dress Name: {dress_name}
Setting: {setting}

{prompt}"""
                        
                        # Save to file using prompt_number as filename
                        output_file = output_path / f"{prompt_number}.txt"
                        with open(output_file, 'w', encoding='utf-8') as out_f:
                            out_f.write(file_content)
                        
                        total_prompts_saved += 1
                        
                        # Print progress
                        if total_prompts_saved % 1000 == 0:
                            print(f"Saved {total_prompts_saved} prompts so far...")
                        
                    except json.JSONDecodeError as e:
                        print(f"Warning: Failed to parse line {line_num} in {file_path_str}: {e}")
                        continue
                        
        except Exception as e:
            print(f"Error reading file {file_path_str}: {e}")

    print(f"\n{'='*80}")
    print(f"✓ Successfully saved a total of {total_prompts_saved} prompts to '{output_dir}/' directory")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    files_to_process = ["prompts_combined_1.jsonl", "prompts_combined_2.jsonl"]
    parse_and_save_prompts(files_to_process)
