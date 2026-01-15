"""
Standard VTON - Virtual Try-On Model
Baseline approach using Stable Diffusion 1.5 with trainable attention weights
"""

from .model import StandardVTONModel
from .dataloader import VTONDataset, VITONHDDataset, get_dataloader
from .metrics import compute_metrics, compute_batch_metrics

__version__ = "1.0.0"
__all__ = [
    'StandardVTONModel',
    'VTONDataset',
    'VITONHDDataset',
    'get_dataloader',
    'compute_metrics',
    'compute_batch_metrics'
]
