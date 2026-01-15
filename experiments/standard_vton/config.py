"""
Configuration file for Standard VTON training
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class DataConfig:
    """Data configuration"""
    data_root: str = "./data/vton_dataset"
    dataset_type: str = "vton"  # 'vton' or 'viton-hd'
    image_size: List[int] = field(default_factory=lambda: [512, 512])
    num_workers: int = 4


@dataclass
class ModelConfig:
    """Model configuration"""
    pretrained_model: str = "runwayml/stable-diffusion-v1-5"
    train_attention_only: bool = True
    freeze_weights: bool = True


@dataclass
class TrainingConfig:
    """Training configuration"""
    batch_size: int = 4
    num_epochs: int = 100
    lr: float = 1e-4
    weight_decay: float = 0.01
    warmup_epochs: int = 5
    gradient_accumulation_steps: int = 1
    max_grad_norm: float = 1.0
    seed: int = 42


@dataclass
class LoggingConfig:
    """Logging configuration"""
    output_dir: str = "./outputs/standard_vton"
    log_interval: int = 10
    save_interval: int = 1000
    vis_interval: int = 500


@dataclass
class InferenceConfig:
    """Inference configuration"""
    num_inference_steps: int = 50
    guidance_scale: float = 7.5
    compute_metrics: bool = True
    save_visualization: bool = True


@dataclass
class VTONConfig:
    """Complete VTON configuration"""
    data: DataConfig = field(default_factory=DataConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    training: TrainingConfig = field(default_factory=TrainingConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    inference: InferenceConfig = field(default_factory=InferenceConfig)

    def to_dict(self):
        """Convert config to dictionary"""
        return {
            'data': {
                'data_root': self.data.data_root,
                'dataset_type': self.data.dataset_type,
                'image_size': self.data.image_size,
                'num_workers': self.data.num_workers
            },
            'model': {
                'pretrained_model': self.model.pretrained_model,
                'train_attention_only': self.model.train_attention_only,
                'freeze_weights': self.model.freeze_weights
            },
            'training': {
                'batch_size': self.training.batch_size,
                'num_epochs': self.training.num_epochs,
                'lr': self.training.lr,
                'weight_decay': self.training.weight_decay,
                'warmup_epochs': self.training.warmup_epochs,
                'gradient_accumulation_steps': self.training.gradient_accumulation_steps,
                'max_grad_norm': self.training.max_grad_norm,
                'seed': self.training.seed
            },
            'logging': {
                'output_dir': self.logging.output_dir,
                'log_interval': self.logging.log_interval,
                'save_interval': self.logging.save_interval,
                'vis_interval': self.logging.vis_interval
            },
            'inference': {
                'num_inference_steps': self.inference.num_inference_steps,
                'guidance_scale': self.inference.guidance_scale,
                'compute_metrics': self.inference.compute_metrics,
                'save_visualization': self.inference.save_visualization
            }
        }


def get_default_config() -> VTONConfig:
    """Get default configuration"""
    return VTONConfig()


def get_viton_hd_config() -> VTONConfig:
    """Get VITON-HD specific configuration"""
    config = VTONConfig()
    config.data.dataset_type = "viton-hd"
    config.data.data_root = "./data/viton-hd"
    config.data.image_size = [512, 512]
    config.training.batch_size = 8
    config.training.num_epochs = 200
    return config


if __name__ == "__main__":
    # Example usage
    config = get_default_config()
    print("Default Configuration:")
    print(config.to_dict())

    print("\nVITON-HD Configuration:")
    viton_config = get_viton_hd_config()
    print(viton_config.to_dict())
