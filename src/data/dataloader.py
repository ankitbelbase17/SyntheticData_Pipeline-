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
        self.samples = self._list_and_group_samples()

    def _list_and_group_samples(self) -> List[Dict[str, str]]:
        # List all objects in the directory
        paginator = self.s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=self.bucket, Prefix=self.prefix)

        all_keys = []
        for page in pages:
            if 'Contents' in page:
                for obj in page['Contents']:
                    key = obj['Key']
                    if key.endswith(('.jpg', '.png', '.jpeg', '.webp')):
                        all_keys.append(key)

        # Robust Grouping using Folder Structure and Base ID
        # Structure:
        # {diff}/{gender}/initial_image/ID_edit_person.png
        # {diff}/{gender}/cloth_image/ID_edit_cloth_XXXX.png
        # {diff}/{gender}/try_on_image/ID_... (result)
        
        grouped_by_id = {}
        
        # Regex to capture the base ID: 12345_partition_0_0
        id_pattern = re.compile(r'(\d+partition\d+_\d+)')

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
                continue # Skip unknown folders
            
            # Extract ID
            filename = key.split('/')[-1]
            match = id_pattern.search(filename)
            if match:
                base_id = match.group(1)
                
                if base_id not in grouped_by_id:
                    grouped_by_id[base_id] = {}
                
                grouped_by_id[base_id][file_type] = key

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
