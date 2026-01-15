"""
Evaluation metrics for VTON model
Includes SSIM, PSNR, LPIPS, FID, and IS
"""

import torch
import torch.nn.functional as F
import numpy as np
from typing import Dict, Optional
from scipy import linalg


def psnr(img1: torch.Tensor, img2: torch.Tensor, max_val: float = 1.0) -> float:
    """
    Calculate Peak Signal-to-Noise Ratio (PSNR)
    Args:
        img1: First image tensor (B, C, H, W) in range [-1, 1] or [0, 1]
        img2: Second image tensor (B, C, H, W) in range [-1, 1] or [0, 1]
        max_val: Maximum pixel value
    Returns:
        PSNR value in dB
    """
    # Denormalize if in [-1, 1]
    if img1.min() < 0:
        img1 = (img1 + 1) / 2
        img2 = (img2 + 1) / 2

    mse = F.mse_loss(img1, img2)
    if mse == 0:
        return float('inf')

    psnr_val = 20 * torch.log10(max_val / torch.sqrt(mse))
    return psnr_val.item()


def ssim(
    img1: torch.Tensor,
    img2: torch.Tensor,
    window_size: int = 11,
    size_average: bool = True
) -> float:
    """
    Calculate Structural Similarity Index (SSIM)
    Args:
        img1: First image tensor (B, C, H, W) in range [-1, 1] or [0, 1]
        img2: Second image tensor (B, C, H, W) in range [-1, 1] or [0, 1]
        window_size: Size of the Gaussian window
        size_average: Whether to average over batch
    Returns:
        SSIM value
    """
    # Denormalize if in [-1, 1]
    if img1.min() < 0:
        img1 = (img1 + 1) / 2
        img2 = (img2 + 1) / 2

    # Create Gaussian window
    channel = img1.size(1)
    window = create_window(window_size, channel).to(img1.device)

    mu1 = F.conv2d(img1, window, padding=window_size // 2, groups=channel)
    mu2 = F.conv2d(img2, window, padding=window_size // 2, groups=channel)

    mu1_sq = mu1.pow(2)
    mu2_sq = mu2.pow(2)
    mu1_mu2 = mu1 * mu2

    sigma1_sq = F.conv2d(img1 * img1, window, padding=window_size // 2, groups=channel) - mu1_sq
    sigma2_sq = F.conv2d(img2 * img2, window, padding=window_size // 2, groups=channel) - mu2_sq
    sigma12 = F.conv2d(img1 * img2, window, padding=window_size // 2, groups=channel) - mu1_mu2

    C1 = 0.01 ** 2
    C2 = 0.03 ** 2

    ssim_map = ((2 * mu1_mu2 + C1) * (2 * sigma12 + C2)) / \
               ((mu1_sq + mu2_sq + C1) * (sigma1_sq + sigma2_sq + C2))

    if size_average:
        return ssim_map.mean().item()
    else:
        return ssim_map.mean(1).mean(1).mean(1)


def create_window(window_size: int, channel: int) -> torch.Tensor:
    """Create a Gaussian window for SSIM calculation"""
    def gaussian(window_size, sigma):
        gauss = torch.Tensor([
            np.exp(-(x - window_size // 2) ** 2 / float(2 * sigma ** 2))
            for x in range(window_size)
        ])
        return gauss / gauss.sum()

    _1D_window = gaussian(window_size, 1.5).unsqueeze(1)
    _2D_window = _1D_window.mm(_1D_window.t()).float().unsqueeze(0).unsqueeze(0)
    window = _2D_window.expand(channel, 1, window_size, window_size).contiguous()
    return window


def mae(img1: torch.Tensor, img2: torch.Tensor) -> float:
    """
    Calculate Mean Absolute Error (MAE)
    Args:
        img1: First image tensor
        img2: Second image tensor
    Returns:
        MAE value
    """
    return F.l1_loss(img1, img2).item()


def mse(img1: torch.Tensor, img2: torch.Tensor) -> float:
    """
    Calculate Mean Squared Error (MSE)
    Args:
        img1: First image tensor
        img2: Second image tensor
    Returns:
        MSE value
    """
    return F.mse_loss(img1, img2).item()


class LPIPSMetric:
    """
    LPIPS (Learned Perceptual Image Patch Similarity) metric
    Requires lpips package: pip install lpips
    """

    def __init__(self, net: str = 'alex', device: str = 'cuda'):
        """
        Args:
            net: Network to use ('alex', 'vgg', 'squeeze')
            device: Device to run on
        """
        try:
            import lpips
            self.lpips_fn = lpips.LPIPS(net=net).to(device)
            self.available = True
        except ImportError:
            print("Warning: lpips package not installed. LPIPS metric will not be available.")
            print("Install with: pip install lpips")
            self.available = False

    def __call__(self, img1: torch.Tensor, img2: torch.Tensor) -> float:
        """
        Calculate LPIPS distance
        Args:
            img1: First image tensor (B, C, H, W) in range [-1, 1]
            img2: Second image tensor (B, C, H, W) in range [-1, 1]
        Returns:
            LPIPS distance
        """
        if not self.available:
            return -1.0

        with torch.no_grad():
            lpips_val = self.lpips_fn(img1, img2)
        return lpips_val.mean().item()


class InceptionScore:
    """
    Inception Score (IS) metric
    Requires torchvision and scipy
    """

    def __init__(self, device: str = 'cuda', splits: int = 10):
        """
        Args:
            device: Device to run on
            splits: Number of splits for IS calculation
        """
        from torchvision.models import inception_v3

        self.device = device
        self.splits = splits
        self.inception_model = inception_v3(pretrained=True, transform_input=False).to(device)
        self.inception_model.eval()

    def __call__(self, images: torch.Tensor) -> tuple:
        """
        Calculate Inception Score
        Args:
            images: Batch of images (B, C, H, W) in range [-1, 1]
        Returns:
            (mean, std) of Inception Score
        """
        # Denormalize to [0, 1]
        images = (images + 1) / 2

        # Resize to 299x299 for Inception
        if images.shape[2] != 299 or images.shape[3] != 299:
            images = F.interpolate(images, size=(299, 299), mode='bilinear', align_corners=False)

        # Get predictions
        with torch.no_grad():
            preds = self.inception_model(images)

        # Calculate IS
        preds = F.softmax(preds, dim=1).cpu().numpy()

        split_scores = []
        for k in range(self.splits):
            part = preds[k * (len(preds) // self.splits): (k + 1) * (len(preds) // self.splits), :]
            py = np.mean(part, axis=0)
            scores = []
            for i in range(part.shape[0]):
                pyx = part[i, :]
                scores.append(np.sum(pyx * np.log(pyx / py)))
            split_scores.append(np.exp(np.mean(scores)))

        return np.mean(split_scores), np.std(split_scores)


class FIDMetric:
    """
    Frechet Inception Distance (FID) metric
    """

    def __init__(self, device: str = 'cuda'):
        """
        Args:
            device: Device to run on
        """
        from torchvision.models import inception_v3

        self.device = device
        self.inception_model = inception_v3(pretrained=True, transform_input=False).to(device)
        self.inception_model.eval()

        # Remove the final FC layer
        self.inception_model.fc = torch.nn.Identity()

    def get_features(self, images: torch.Tensor) -> np.ndarray:
        """
        Extract features from images
        Args:
            images: Batch of images (B, C, H, W) in range [-1, 1]
        Returns:
            Feature vectors
        """
        # Denormalize to [0, 1]
        images = (images + 1) / 2

        # Resize to 299x299
        if images.shape[2] != 299 or images.shape[3] != 299:
            images = F.interpolate(images, size=(299, 299), mode='bilinear', align_corners=False)

        with torch.no_grad():
            features = self.inception_model(images)

        return features.cpu().numpy()

    def calculate_fid(self, real_features: np.ndarray, fake_features: np.ndarray) -> float:
        """
        Calculate FID between real and fake features
        Args:
            real_features: Features from real images
            fake_features: Features from generated images
        Returns:
            FID score
        """
        mu1, sigma1 = real_features.mean(axis=0), np.cov(real_features, rowvar=False)
        mu2, sigma2 = fake_features.mean(axis=0), np.cov(fake_features, rowvar=False)

        # Calculate Frechet distance
        ssdiff = np.sum((mu1 - mu2) ** 2.0)
        covmean = linalg.sqrtm(sigma1.dot(sigma2))

        if np.iscomplexobj(covmean):
            covmean = covmean.real

        fid = ssdiff + np.trace(sigma1 + sigma2 - 2.0 * covmean)
        return float(fid)


def compute_metrics(
    generated: torch.Tensor,
    target: torch.Tensor,
    use_lpips: bool = True,
    device: Optional[str] = None
) -> Dict[str, float]:
    """
    Compute all available metrics
    Args:
        generated: Generated images (B, C, H, W)
        target: Target images (B, C, H, W)
        use_lpips: Whether to compute LPIPS (requires lpips package)
        device: Device to use
    Returns:
        Dictionary of metric values
    """
    if device is None:
        device = generated.device

    metrics = {}

    # Basic metrics
    metrics['psnr'] = psnr(generated, target)
    metrics['ssim'] = ssim(generated, target)
    metrics['mae'] = mae(generated, target)
    metrics['mse'] = mse(generated, target)

    # LPIPS (if available)
    if use_lpips:
        try:
            lpips_metric = LPIPSMetric(device=str(device))
            if lpips_metric.available:
                metrics['lpips'] = lpips_metric(generated, target)
        except Exception as e:
            print(f"Warning: Could not compute LPIPS: {e}")

    return metrics


def compute_batch_metrics(
    generated_images: list,
    target_images: list,
    compute_fid: bool = False,
    compute_is: bool = False,
    device: str = 'cuda'
) -> Dict[str, float]:
    """
    Compute metrics over a batch of images
    Args:
        generated_images: List of generated image tensors
        target_images: List of target image tensors
        compute_fid: Whether to compute FID
        compute_is: Whether to compute Inception Score
        device: Device to use
    Returns:
        Dictionary of aggregated metrics
    """
    all_metrics = []

    # Compute per-image metrics
    for gen, tgt in zip(generated_images, target_images):
        metrics = compute_metrics(gen.unsqueeze(0), tgt.unsqueeze(0), device=device)
        all_metrics.append(metrics)

    # Aggregate metrics
    avg_metrics = {}
    for key in all_metrics[0].keys():
        avg_metrics[f'avg_{key}'] = np.mean([m[key] for m in all_metrics])
        avg_metrics[f'std_{key}'] = np.std([m[key] for m in all_metrics])

    # Compute FID if requested
    if compute_fid:
        try:
            fid_metric = FIDMetric(device=device)
            real_features = fid_metric.get_features(torch.stack(target_images).to(device))
            fake_features = fid_metric.get_features(torch.stack(generated_images).to(device))
            avg_metrics['fid'] = fid_metric.calculate_fid(real_features, fake_features)
        except Exception as e:
            print(f"Warning: Could not compute FID: {e}")

    # Compute IS if requested
    if compute_is:
        try:
            is_metric = InceptionScore(device=device)
            is_mean, is_std = is_metric(torch.stack(generated_images).to(device))
            avg_metrics['is_mean'] = is_mean
            avg_metrics['is_std'] = is_std
        except Exception as e:
            print(f"Warning: Could not compute IS: {e}")

    return avg_metrics


if __name__ == "__main__":
    # Test metrics
    print("Testing metrics...")

    # Create dummy images
    img1 = torch.randn(2, 3, 256, 256)
    img2 = torch.randn(2, 3, 256, 256)

    # Compute metrics
    metrics = compute_metrics(img1, img2, use_lpips=False)

    print("\nMetrics:")
    for name, value in metrics.items():
        print(f"  {name}: {value:.4f}")
