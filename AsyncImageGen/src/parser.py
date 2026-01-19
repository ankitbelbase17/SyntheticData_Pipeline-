import json
from pathlib import Path
from typing import List, Generator, Dict, Any

def parse_prompts(jsonl_files: List[str]) -> Generator[Dict[str, Any], None, None]:
    """
    Parse JSONL files and yield prompt data.
    
    Args:
        jsonl_files: List of paths to the JSONL files to parse.
        
    Yields:
        Dictionary containing prompt data.
    """
    for file_path_str in jsonl_files:
        file_path = Path(file_path_str)
        if not file_path.exists():
            print(f"Warning: File '{file_path_str}' not found. Skipping.")
            continue
            
        print(f"Processing '{file_path_str}'...")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        
                        prompt_number = data.get("prompt_number")
                        if prompt_number is None:
                            print(f"Warning: 'prompt_number' missing in line {line_num} of {file_path_str}. Skipping.")
                            continue

                        yield data
                        
                    except json.JSONDecodeError as e:
                        print(f"Warning: Failed to parse line {line_num} in {file_path_str}: {e}")
                        continue
                        
        except Exception as e:
            print(f"Error reading file {file_path_str}: {e}")
