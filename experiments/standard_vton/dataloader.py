"""
Dataloader for VTON Dataset
Handles loading of person images, cloth images, and masks
"""

import os
import torch
from torch.utils.data import Dataset, DataLoader
from PIL import Image
import torchvision.transforms as transforms
from typing import Dict, Optional, Tuple, List
import json


class VTONDataset(Dataset):
    """
    Dataset for Virtual Try-On
    Expected directory structure:
        data_root/
            person/          # Original person images
            person_masked/   # Person images with cloth region masked
            cloth/           # Cloth images
            pairs.json       # Pairing information
    """

    def __init__(
        self,
        data_root: str,
        image_size: Tuple[int, int] = (512, 512),
        mode: str = "train",
        cloth_type: Optional[str] = None
    ):
        """
        Args:
            data_root: Root directory of the dataset
            image_size: Target image size (height, width)
            mode: 'train' or 'test'
            cloth_type: Filter by cloth type (e.g., 'upper', 'lower', 'dress')
        """
        self.data_root = data_root
        self.image_size = image_size
        self.mode = mode
        self.cloth_type = cloth_type

        # Define directories
        self.person_dir = os.path.join(data_root, "person")
        self.person_masked_dir = os.path.join(data_root, "person_masked")
        self.cloth_dir = os.path.join(data_root, "cloth")

        # Load pairing information
        pairs_file = os.path.join(data_root, f"pairs_{mode}.json")
        if os.path.exists(pairs_file):
            with open(pairs_file, 'r') as f:
                self.pairs = json.load(f)
        else:
            # If no pairs file, create default pairs
            self.pairs = self._create_default_pairs()

        # Filter by cloth type if specified
        if cloth_type:
            self.pairs = [p for p in self.pairs if p.get('cloth_type') == cloth_type]

        # Define transforms
        self.image_transform = transforms.Compose([
            transforms.Resize(image_size),
            transforms.ToTensor(),
            transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5])  # Normalize to [-1, 1]
        ])

    def _create_default_pairs(self) -> List[Dict]:
        """Create default pairing if pairs.json doesn't exist"""
        pairs = []

        # Get all person images
        person_files = sorted([f for f in os.listdir(self.person_dir)
                              if f.endswith(('.jpg', '.png', '.jpeg'))])

        # Get all cloth images
        cloth_files = sorted([f for f in os.listdir(self.cloth_dir)
                             if f.endswith(('.jpg', '.png', '.jpeg'))])

        # Create pairs (each person with each cloth)
        for person_file in person_files:
            for cloth_file in cloth_files:
                pairs.append({
                    'person': person_file,
                    'person_masked': person_file,  # Assume same filename
                    'cloth': cloth_file,
                    'cloth_type': 'upper'  # Default type
                })

        return pairs

    def __len__(self) -> int:
        return len(self.pairs)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        """
        Returns:
            Dictionary containing:
                - person_image: Ground truth person image
                - person_masked: Person with cloth region masked
                - cloth_image: Cloth image
                - person_name: Person image filename
                - cloth_name: Cloth image filename
        """
        pair = self.pairs[idx]

        # Load images
        person_path = os.path.join(self.person_dir, pair['person'])
        person_masked_path = os.path.join(self.person_masked_dir, pair['person_masked'])
        cloth_path = os.path.join(self.cloth_dir, pair['cloth'])

        # Load and transform images
        person_image = self._load_image(person_path)
        person_masked = self._load_image(person_masked_path)
        cloth_image = self._load_image(cloth_path)

        return {
            'person_image': person_image,
            'person_masked': person_masked,
            'cloth_image': cloth_image,
            'person_name': pair['person'],
            'cloth_name': pair['cloth']
        }

    def _load_image(self, path: str) -> torch.Tensor:
        """Load and transform an image"""
        try:
            image = Image.open(path).convert('RGB')
            return self.image_transform(image)
        except Exception as e:
            print(f"Error loading image {path}: {e}")
            # Return a black image as fallback
            return torch.zeros(3, self.image_size[0], self.image_size[1])


class VITONHDDataset(VTONDataset):
    """
    Dataset loader for VITON-HD dataset format
    Expected structure:
        data_root/
            train/
                image/              # Person images
                image-parse-v3/     # Segmentation masks
                cloth/              # Cloth images
                train_pairs.txt     # Pairing information
            test/
                ...
    """

    def __init__(
        self,
        data_root: str,
        image_size: Tuple[int, int] = (512, 512),
        mode: str = "train"
    ):
        self.data_root = data_root
        self.image_size = image_size
        self.mode = mode

        # Define directories
        mode_dir = os.path.join(data_root, mode)
        self.person_dir = os.path.join(mode_dir, "image")
        self.cloth_dir = os.path.join(mode_dir, "cloth")
        self.mask_dir = os.path.join(mode_dir, "image-parse-v3")

        # Load pairs
        pairs_file = os.path.join(mode_dir, f"{mode}_pairs.txt")
        self.pairs = self._load_pairs(pairs_file)

        # Define transforms
        self.image_transform = transforms.Compose([
            transforms.Resize(image_size),
            transforms.ToTensor(),
            transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5])
        ])

        self.mask_transform = transforms.Compose([
            transforms.Resize(image_size, interpolation=transforms.InterpolationMode.NEAREST),
            transforms.ToTensor()
        ])

    def _load_pairs(self, pairs_file: str) -> List[Tuple[str, str]]:
        """Load pairs from txt file"""
        pairs = []
        if os.path.exists(pairs_file):
            with open(pairs_file, 'r') as f:
                for line in f:
                    person_name, cloth_name = line.strip().split()
                    pairs.append((person_name, cloth_name))
        return pairs

    def __len__(self) -> int:
        return len(self.pairs)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        person_name, cloth_name = self.pairs[idx]

        # Load person image
        person_path = os.path.join(self.person_dir, person_name)
        person_image = Image.open(person_path).convert('RGB')
        person_image = self.image_transform(person_image)

        # Load cloth image
        cloth_path = os.path.join(self.cloth_dir, cloth_name)
        cloth_image = Image.open(cloth_path).convert('RGB')
        cloth_image = self.image_transform(cloth_image)

        # Load mask and create masked person
        mask_name = person_name.replace('.jpg', '.png')
        mask_path = os.path.join(self.mask_dir, mask_name)

        if os.path.exists(mask_path):
            mask = Image.open(mask_path).convert('L')
            mask = self.mask_transform(mask)

            # Create masked person (mask out cloth region)
            person_masked = person_image * (1 - mask)
        else:
            # If no mask, use original image
            person_masked = person_image
            print(f"Warning: No mask found for {person_name}")

        return {
            'person_image': person_image,
            'person_masked': person_masked,
            'cloth_image': cloth_image,
            'person_name': person_name,
            'cloth_name': cloth_name
        }


def get_dataloader(
    data_root: str,
    batch_size: int = 4,
    image_size: Tuple[int, int] = (512, 512),
    mode: str = "train",
    num_workers: int = 4,
    dataset_type: str = "vton",
    shuffle: Optional[bool] = None
) -> DataLoader:
    """
    Create dataloader for VTON dataset
    Args:
        data_root: Root directory of dataset
        batch_size: Batch size
        image_size: Image size (height, width)
        mode: 'train' or 'test'
        num_workers: Number of workers for data loading
        dataset_type: 'vton' or 'viton-hd'
        shuffle: Whether to shuffle data (default: True for train, False for test)
    Returns:
        DataLoader
    """
    if shuffle is None:
        shuffle = (mode == "train")

    if dataset_type == "viton-hd":
        dataset = VITONHDDataset(
            data_root=data_root,
            image_size=image_size,
            mode=mode
        )
    else:
        dataset = VTONDataset(
            data_root=data_root,
            image_size=image_size,
            mode=mode
        )

    dataloader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        pin_memory=True,
        drop_last=(mode == "train")
    )

    return dataloader


def collate_fn(batch: List[Dict]) -> Dict[str, torch.Tensor]:
    """
    Custom collate function for VTON dataset
    """
    person_images = torch.stack([item['person_image'] for item in batch])
    person_masked = torch.stack([item['person_masked'] for item in batch])
    cloth_images = torch.stack([item['cloth_image'] for item in batch])

    person_names = [item['person_name'] for item in batch]
    cloth_names = [item['cloth_name'] for item in batch]

    return {
        'person_image': person_images,
        'person_masked': person_masked,
        'cloth_image': cloth_images,
        'person_names': person_names,
        'cloth_names': cloth_names
    }


if __name__ == "__main__":
    # Test dataloader
    print("Testing VTON Dataloader...")

    # Create dummy dataset
    data_root = "./data/vton_dataset"

    try:
        dataloader = get_dataloader(
            data_root=data_root,
            batch_size=2,
            mode="train",
            num_workers=0
        )

        print(f"Dataset size: {len(dataloader.dataset)}")

        # Test loading one batch
        for batch in dataloader:
            print(f"Person image shape: {batch['person_image'].shape}")
            print(f"Masked person shape: {batch['person_masked'].shape}")
            print(f"Cloth image shape: {batch['cloth_image'].shape}")
            print(f"Person names: {batch['person_names']}")
            print(f"Cloth names: {batch['cloth_names']}")
            break

    except Exception as e:
        print(f"Error: {e}")
        print("Note: Create the dataset directory structure to test properly")
