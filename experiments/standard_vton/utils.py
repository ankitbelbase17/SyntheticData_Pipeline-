"""
Utility functions for VTON training and inference
"""

import os
import torch
import numpy as np
from PIL import Image
from typing import Optional, Union, List
import matplotlib.pyplot as plt
from datetime import datetime
import json


def save_checkpoint(
    model,
    optimizer,
    epoch: int,
    step: int,
    loss: float,
    save_dir: str,
    is_best: bool = False
):
    """
    Save model checkpoint
    Args:
        model: Model to save
        optimizer: Optimizer state
        epoch: Current epoch
        step: Current step
        loss: Current loss
        save_dir: Directory to save checkpoint
        is_best: Whether this is the best model so far
    """
    os.makedirs(save_dir, exist_ok=True)

    checkpoint = {
        'epoch': epoch,
        'step': step,
        'model_state_dict': model.state_dict(),
        'optimizer_state_dict': optimizer.state_dict(),
        'loss': loss,
    }

    # Save regular checkpoint
    checkpoint_path = os.path.join(save_dir, f'checkpoint_epoch_{epoch}_step_{step}.pt')
    torch.save(checkpoint, checkpoint_path)
    print(f"Checkpoint saved: {checkpoint_path}")

    # Save as latest
    latest_path = os.path.join(save_dir, 'checkpoint_latest.pt')
    torch.save(checkpoint, latest_path)

    # Save as best if applicable
    if is_best:
        best_path = os.path.join(save_dir, 'checkpoint_best.pt')
        torch.save(checkpoint, best_path)
        print(f"Best checkpoint saved: {best_path}")


def load_checkpoint(
    checkpoint_path: str,
    model,
    optimizer=None,
    device: str = 'cuda'
) -> dict:
    """
    Load model checkpoint
    Args:
        checkpoint_path: Path to checkpoint file
        model: Model to load weights into
        optimizer: Optional optimizer to load state
        device: Device to load checkpoint on
    Returns:
        Dictionary with checkpoint metadata
    """
    checkpoint = torch.load(checkpoint_path, map_location=device)

    model.load_state_dict(checkpoint['model_state_dict'])

    if optimizer is not None and 'optimizer_state_dict' in checkpoint:
        optimizer.load_state_dict(checkpoint['optimizer_state_dict'])

    print(f"Checkpoint loaded from {checkpoint_path}")
    print(f"  Epoch: {checkpoint.get('epoch', 'N/A')}")
    print(f"  Step: {checkpoint.get('step', 'N/A')}")
    print(f"  Loss: {checkpoint.get('loss', 'N/A')}")

    return checkpoint


def tensor_to_image(tensor: torch.Tensor) -> np.ndarray:
    """
    Convert tensor to numpy image
    Args:
        tensor: Tensor of shape (C, H, W) or (B, C, H, W) in range [-1, 1]
    Returns:
        numpy array in range [0, 255]
    """
    if tensor.dim() == 4:
        tensor = tensor[0]  # Take first image from batch

    # Denormalize from [-1, 1] to [0, 1]
    tensor = (tensor + 1) / 2
    tensor = torch.clamp(tensor, 0, 1)

    # Convert to numpy and transpose
    image = tensor.cpu().detach().numpy()
    image = np.transpose(image, (1, 2, 0))

    # Convert to [0, 255]
    image = (image * 255).astype(np.uint8)

    return image


def save_image(tensor: torch.Tensor, save_path: str):
    """
    Save tensor as image
    Args:
        tensor: Image tensor
        save_path: Path to save image
    """
    image = tensor_to_image(tensor)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    Image.fromarray(image).save(save_path)


def visualize_batch(
    person_masked: torch.Tensor,
    cloth: torch.Tensor,
    target: torch.Tensor,
    generated: Optional[torch.Tensor] = None,
    save_path: Optional[str] = None,
    num_samples: int = 4
):
    """
    Visualize a batch of images
    Args:
        person_masked: Masked person images
        cloth: Cloth images
        target: Ground truth images
        generated: Generated images (optional)
        save_path: Path to save visualization
        num_samples: Number of samples to visualize
    """
    num_samples = min(num_samples, person_masked.shape[0])
    num_cols = 4 if generated is not None else 3

    fig, axes = plt.subplots(num_samples, num_cols, figsize=(num_cols * 3, num_samples * 3))

    if num_samples == 1:
        axes = axes.reshape(1, -1)

    for i in range(num_samples):
        # Masked person
        axes[i, 0].imshow(tensor_to_image(person_masked[i]))
        axes[i, 0].set_title('Masked Person')
        axes[i, 0].axis('off')

        # Cloth
        axes[i, 1].imshow(tensor_to_image(cloth[i]))
        axes[i, 1].set_title('Cloth')
        axes[i, 1].axis('off')

        # Target
        axes[i, 2].imshow(tensor_to_image(target[i]))
        axes[i, 2].set_title('Ground Truth')
        axes[i, 2].axis('off')

        # Generated (if available)
        if generated is not None:
            axes[i, 3].imshow(tensor_to_image(generated[i]))
            axes[i, 3].set_title('Generated')
            axes[i, 3].axis('off')

    plt.tight_layout()

    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Visualization saved: {save_path}")

    plt.close()


class AverageMeter:
    """Computes and stores the average and current value"""

    def __init__(self, name: str):
        self.name = name
        self.reset()

    def reset(self):
        self.val = 0
        self.avg = 0
        self.sum = 0
        self.count = 0

    def update(self, val: float, n: int = 1):
        self.val = val
        self.sum += val * n
        self.count += n
        self.avg = self.sum / self.count

    def __str__(self):
        return f'{self.name}: {self.val:.4f} (avg: {self.avg:.4f})'


class Logger:
    """Simple logger for training"""

    def __init__(self, log_dir: str, log_file: str = 'train.log'):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)

        self.log_file = os.path.join(log_dir, log_file)
        self.metrics = []

    def log(self, message: str, print_msg: bool = True):
        """Log a message"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_message = f'[{timestamp}] {message}'

        if print_msg:
            print(log_message)

        with open(self.log_file, 'a') as f:
            f.write(log_message + '\n')

    def log_metrics(self, epoch: int, step: int, metrics: dict):
        """Log training metrics"""
        metric_entry = {
            'epoch': epoch,
            'step': step,
            'timestamp': datetime.now().isoformat(),
            **metrics
        }

        self.metrics.append(metric_entry)

        # Save metrics to JSON
        metrics_file = os.path.join(self.log_dir, 'metrics.json')
        with open(metrics_file, 'w') as f:
            json.dump(self.metrics, f, indent=2)

        # Log message
        metrics_str = ', '.join([f'{k}: {v:.4f}' if isinstance(v, float) else f'{k}: {v}'
                                for k, v in metrics.items()])
        self.log(f'Epoch {epoch}, Step {step} - {metrics_str}')


def count_parameters(model) -> tuple:
    """
    Count model parameters
    Returns:
        (total_params, trainable_params)
    """
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    return total_params, trainable_params


def setup_directories(base_dir: str) -> dict:
    """
    Setup directory structure for training
    Args:
        base_dir: Base directory for the experiment
    Returns:
        Dictionary with directory paths
    """
    dirs = {
        'checkpoints': os.path.join(base_dir, 'checkpoints'),
        'logs': os.path.join(base_dir, 'logs'),
        'samples': os.path.join(base_dir, 'samples'),
        'results': os.path.join(base_dir, 'results')
    }

    for dir_path in dirs.values():
        os.makedirs(dir_path, exist_ok=True)

    return dirs


def get_lr(optimizer) -> float:
    """Get current learning rate from optimizer"""
    for param_group in optimizer.param_groups:
        return param_group['lr']


def set_seed(seed: int = 42):
    """
    Set random seed for reproducibility
    Args:
        seed: Random seed
    """
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    np.random.seed(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def create_mask_from_segmentation(
    segmentation: torch.Tensor,
    cloth_labels: List[int]
) -> torch.Tensor:
    """
    Create binary mask for cloth region from segmentation
    Args:
        segmentation: Segmentation map (H, W) with class labels
        cloth_labels: List of label indices for cloth regions
    Returns:
        Binary mask (1, H, W)
    """
    mask = torch.zeros_like(segmentation)
    for label in cloth_labels:
        mask = torch.logical_or(mask, segmentation == label)

    return mask.float().unsqueeze(0)


def denormalize(tensor: torch.Tensor) -> torch.Tensor:
    """
    Denormalize tensor from [-1, 1] to [0, 1]
    Args:
        tensor: Normalized tensor
    Returns:
        Denormalized tensor
    """
    return (tensor + 1) / 2


def normalize(tensor: torch.Tensor) -> torch.Tensor:
    """
    Normalize tensor from [0, 1] to [-1, 1]
    Args:
        tensor: Tensor in range [0, 1]
    Returns:
        Normalized tensor
    """
    return (tensor * 2) - 1


def get_device(gpu_id: Optional[int] = None) -> torch.device:
    """
    Get torch device
    Args:
        gpu_id: GPU ID to use (None for auto-select)
    Returns:
        torch.device
    """
    if torch.cuda.is_available():
        if gpu_id is not None:
            return torch.device(f'cuda:{gpu_id}')
        else:
            return torch.device('cuda')
    else:
        return torch.device('cpu')


def save_config(config: dict, save_path: str):
    """
    Save configuration to JSON file
    Args:
        config: Configuration dictionary
        save_path: Path to save config
    """
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with open(save_path, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"Configuration saved: {save_path}")


def load_config(config_path: str) -> dict:
    """
    Load configuration from JSON file
    Args:
        config_path: Path to config file
    Returns:
        Configuration dictionary
    """
    with open(config_path, 'r') as f:
        config = json.load(f)
    return config
