import boto3
from torch.utils.data import Dataset, DataLoader
try:
    from config import config
except ImportError:
    from src.config import config
from typing import List, Dict, Optional
import re

class S3VTONDataset(Dataset):
    def __init__(self, difficulty: str, gender: str, s3_client):
        self.s3_client = s3_client
        self.bucket = config.S3_BUCKET_NAME
        self.difficulty = difficulty
        self.gender = gender
        self.prefix = f"{difficulty}/{gender}/"
        
        print(f"[DEBUG] S3 Bucket: {self.bucket}")
        print(f"[DEBUG] S3 Prefix: {self.prefix}")
        
        self.samples = self._list_and_group_samples()

    def _list_and_group_samples(self) -> List[Dict[str, str]]:
        # List all objects in the directory
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket, Prefix=self.prefix)
        except Exception as e:
            print(f"[ERROR] Failed to list S3 objects: {e}")
            print("[DEBUG] Check if AWS credentials are properly set:")
            print(f"  - AWS_ACCESS_KEY_ID set: {bool(config.AWS_ACCESS_KEY_ID and config.AWS_ACCESS_KEY_ID != 'your_access_key')}")
            print(f"  - AWS_SECRET_ACCESS_KEY set: {bool(config.AWS_SECRET_ACCESS_KEY and config.AWS_SECRET_ACCESS_KEY != 'your_secret_key')}")
            print(f"  - S3_BUCKET_NAME: {config.S3_BUCKET_NAME}")
            return []

        all_keys = []
        for page in pages:
            if 'Contents' in page:
                for obj in page['Contents']:
                    key = obj['Key']
                    if key.endswith(('.jpg', '.png', '.jpeg', '.webp')):
                        all_keys.append(key)
        
        print(f"[DEBUG] Found {len(all_keys)} image files in S3 with prefix '{self.prefix}'")
        
        if len(all_keys) == 0:
            print("[DEBUG] No images found. Trying to list root of bucket to verify access...")
            try:
                response = self.s3_client.list_objects_v2(Bucket=self.bucket, MaxKeys=10)
                if 'Contents' in response:
                    print("[DEBUG] Sample keys in bucket root:")
                    for obj in response['Contents'][:5]:
                        print(f"  - {obj['Key']}")
                else:
                    print("[DEBUG] Bucket appears to be empty or inaccessible")
            except Exception as e:
                print(f"[ERROR] Cannot access bucket: {e}")
            return []
        
        # Show first few keys for debugging
        print(f"[DEBUG] First 3 keys found:")
        for k in all_keys[:3]:
            print(f"  - {k}")

        # Robust Grouping using Folder Structure and Base ID
        # Structure:
        # {diff}/{gender}/initial_image/ID_edit_person.png
        # {diff}/{gender}/cloth_image/ID_edit_cloth_XXXX.png
        # {diff}/{gender}/try_on_image/ID_... (result)
        
        grouped_by_id = {}
        
        # Regex to capture the base ID: 12345_partition_0_0 or 12345partition0_0
        # Made more flexible to handle variations
        id_pattern = re.compile(r'(\d+_?partition_?\d+_\d+)')
        
        # Fallback: use filename without extension as ID if pattern doesn't match
        unmatched_count = 0
        skipped_folders = set()

        for key in all_keys:
            # Determine type based on folder
            folder_part = key.replace(self.prefix, "")
            
            file_type = None
            if "initial_image" in folder_part:
                file_type = "initial_person_image_name"
            elif "cloth_image" in folder_part:
                file_type = "cloth_image_name"
            elif "try_on_image" in folder_part:
                file_type = "clothed_person_image_name"
            else:
                # Track skipped folders for debugging
                folder_name = folder_part.split('/')[0] if '/' in folder_part else folder_part
                skipped_folders.add(folder_name)
                continue # Skip unknown folders
            
            # Extract ID
            filename = key.split('/')[-1]
            match = id_pattern.search(filename)
            if match:
                base_id = match.group(1)
            else:
                # Fallback: use filename without extension as ID
                base_id = filename.rsplit('.', 1)[0]
                unmatched_count += 1
                
            if base_id not in grouped_by_id:
                grouped_by_id[base_id] = {}
            
            grouped_by_id[base_id][file_type] = key
        
        if unmatched_count > 0:
            print(f"[DEBUG] {unmatched_count} files didn't match ID pattern, using filename as fallback")
        if skipped_folders:
            print(f"[DEBUG] Skipped folders (not matching expected structure): {skipped_folders}")

        final_samples = []
        for base_id, parts in grouped_by_id.items():
            # Only require initial feedback loop inputs: person and cloth
            if 'initial_person_image_name' in parts and 'cloth_image_name' in parts:
                sample = {
                    "initial_person_image_name": parts['initial_person_image_name'],
                    "cloth_image_name": parts['cloth_image_name'],
                }
                # Optional: include clothed person if available (but not required)
                if 'clothed_person_image_name' in parts:
                    sample["clothed_person_image_name"] = parts['clothed_person_image_name']
                
                final_samples.append(sample)
        
        print(f"[DEBUG] Grouped {len(grouped_by_id)} unique IDs, {len(final_samples)} complete samples (with both person and cloth)")
        
        if len(all_keys) > 0 and len(final_samples) == 0:
            print("[DEBUG] Files found but no samples matched. Possible issues:")
            print("  1. Folder structure doesn't match expected: {diff}/{gender}/initial_image/, cloth_image/, try_on_image/")
            print("  2. Filename pattern doesn't match regex: (\\d+partition\\d+_\\d+)")
            print("[DEBUG] Checking folder structure in found keys...")
            folders_found = set()
            for key in all_keys[:20]:
                parts = key.replace(self.prefix, "").split('/')
                if len(parts) > 1:
                    folders_found.add(parts[0])
            print(f"[DEBUG] Subfolders found: {folders_found}")
        
        # Sort by initial image name for consistency
        final_samples.sort(key=lambda x: x['initial_person_image_name'])
        
        return final_samples

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        if idx >= len(self.samples):
            raise IndexError("Index out of bounds")
            
        sample = self.samples[idx]
        
        # Generate presigned URLs
        def get_url(key):
            try:
                return self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': self.bucket, 'Key': key},
                    ExpiresIn=3600
                )
            except Exception as e:
                print(f"Error generating url for {key}: {e}")
                return ""

        item = {
            "id": idx,
            "difficulty": self.difficulty,
            "gender": self.gender,
            "initial_person_image_name": sample['initial_person_image_name'],
            "initialImage": get_url(sample['initial_person_image_name']),
            "cloth_image_name": sample['cloth_image_name'],
            "clothImage": get_url(sample['cloth_image_name']),
        }
        
        # Include result image if it exists in sample, otherwise handle gracefully
        if "clothed_person_image_name" in sample:
            item["clothed_person_image_name"] = sample['clothed_person_image_name']
            item["resultImage"] = get_url(sample['clothed_person_image_name'])
        else:
            # Provide None or omit - strict adherence to user request "only initial ... provided"
            # leaving it out is safest based on prompt
            pass

        return item

def get_dataloader(difficulty: str, gender: str):
    # Validate credentials before connecting
    if not config.AWS_ACCESS_KEY_ID or config.AWS_ACCESS_KEY_ID == "your_access_key":
        print("[ERROR] AWS_ACCESS_KEY_ID not set. Please set the environment variable.")
    if not config.AWS_SECRET_ACCESS_KEY or config.AWS_SECRET_ACCESS_KEY == "your_secret_key":
        print("[ERROR] AWS_SECRET_ACCESS_KEY not set. Please set the environment variable.")
    if not config.S3_BUCKET_NAME or config.S3_BUCKET_NAME == "your_bucket_name":
        print("[ERROR] S3_BUCKET_NAME not set. Please set the environment variable.")
    
    print(f"[DEBUG] Connecting to S3 with region: {config.AWS_REGION_NAME}")
    
    # Setup S3 Client
    s3 = boto3.client(
        's3',
        aws_access_key_id=config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
        region_name=config.AWS_REGION_NAME
    )
    
    dataset = S3VTONDataset(difficulty, gender, s3)
    
    # "batch size is 1 and no shuffle"
    loader = DataLoader(dataset, batch_size=1, shuffle=False)
    return loader, dataset
