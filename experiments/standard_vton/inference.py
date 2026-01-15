"""
Inference script for Standard VTON model
"""

import os
import argparse
import torch
from PIL import Image
import torchvision.transforms as transforms
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

from model import StandardVTONModel
from dataloader import get_dataloader
from utils import (
    load_checkpoint,
    save_image,
    visualize_batch,
    get_device,
    tensor_to_image
)
from metrics import compute_metrics


def parse_args():
    parser = argparse.ArgumentParser(description='Inference with Standard VTON Model')

    # Model parameters
    parser.add_argument('--checkpoint', type=str, required=True,
                       help='Path to model checkpoint')
    parser.add_argument('--pretrained_model', type=str,
                       default='runwayml/stable-diffusion-v1-5',
                       help='Pretrained Stable Diffusion model')

    # Input parameters
    parser.add_argument('--mode', type=str, default='dataset',
                       choices=['dataset', 'single'],
                       help='Inference mode: dataset or single image pair')
    parser.add_argument('--data_root', type=str, default=None,
                       help='Root directory of dataset (for dataset mode)')
    parser.add_argument('--dataset_type', type=str, default='vton',
                       choices=['vton', 'viton-hd'],
                       help='Dataset type')
    parser.add_argument('--person_masked', type=str, default=None,
                       help='Path to masked person image (for single mode)')
    parser.add_argument('--cloth', type=str, default=None,
                       help='Path to cloth image (for single mode)')
    parser.add_argument('--person_gt', type=str, default=None,
                       help='Path to ground truth person image (optional, for metrics)')

    # Generation parameters
    parser.add_argument('--image_size', type=int, nargs=2, default=[512, 512],
                       help='Image size (height, width)')
    parser.add_argument('--num_inference_steps', type=int, default=50,
                       help='Number of denoising steps')
    parser.add_argument('--guidance_scale', type=float, default=7.5,
                       help='Classifier-free guidance scale')
    parser.add_argument('--batch_size', type=int, default=1,
                       help='Batch size for dataset mode')

    # Output parameters
    parser.add_argument('--output_dir', type=str, default='./outputs/inference',
                       help='Output directory')
    parser.add_argument('--save_visualization', action='store_true',
                       help='Save visualization grid')
    parser.add_argument('--compute_metrics', action='store_true',
                       help='Compute evaluation metrics')

    # Other parameters
    parser.add_argument('--num_workers', type=int, default=4,
                       help='Number of data loading workers')
    parser.add_argument('--gpu_id', type=int, default=None,
                       help='GPU ID to use')

    return parser.parse_args()


def load_single_image(image_path: str, image_size: tuple) -> torch.Tensor:
    """
    Load and preprocess a single image
    Args:
        image_path: Path to image
        image_size: Target size (height, width)
    Returns:
        Preprocessed image tensor
    """
    transform = transforms.Compose([
        transforms.Resize(image_size),
        transforms.ToTensor(),
        transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5])
    ])

    image = Image.open(image_path).convert('RGB')
    return transform(image).unsqueeze(0)


def inference_single(
    model,
    person_masked_path: str,
    cloth_path: str,
    person_gt_path: str,
    args,
    device
):
    """
    Run inference on a single image pair
    """
    print("Running inference on single image pair...")

    # Load images
    person_masked = load_single_image(person_masked_path, tuple(args.image_size)).to(device)
    cloth_image = load_single_image(cloth_path, tuple(args.image_size)).to(device)

    # Generate
    model.eval()
    with torch.no_grad():
        generated = model.generate(
            masked_person_image=person_masked,
            cloth_image=cloth_image,
            prompts=None,
            num_inference_steps=args.num_inference_steps,
            guidance_scale=args.guidance_scale
        )

    # Save results
    os.makedirs(args.output_dir, exist_ok=True)

    # Save generated image
    output_path = os.path.join(args.output_dir, 'generated.png')
    save_image(generated[0], output_path)
    print(f"Generated image saved: {output_path}")

    # Save visualization if requested
    if args.save_visualization:
        if person_gt_path:
            person_gt = load_single_image(person_gt_path, tuple(args.image_size)).to(device)
        else:
            person_gt = person_masked

        visualize_batch(
            person_masked=person_masked,
            cloth=cloth_image,
            target=person_gt,
            generated=generated,
            save_path=os.path.join(args.output_dir, 'visualization.png'),
            num_samples=1
        )
        print(f"Visualization saved: {os.path.join(args.output_dir, 'visualization.png')}")

    # Compute metrics if ground truth available
    if args.compute_metrics and person_gt_path:
        person_gt = load_single_image(person_gt_path, tuple(args.image_size)).to(device)
        metrics = compute_metrics(generated, person_gt)

        print("\nMetrics:")
        for metric_name, value in metrics.items():
            print(f"  {metric_name}: {value:.4f}")

        # Save metrics
        import json
        metrics_path = os.path.join(args.output_dir, 'metrics.json')
        with open(metrics_path, 'w') as f:
            json.dump(metrics, f, indent=2)


def inference_dataset(model, dataloader, args, device):
    """
    Run inference on entire dataset
    """
    print(f"Running inference on dataset ({len(dataloader.dataset)} samples)...")

    # Create output directories
    os.makedirs(os.path.join(args.output_dir, 'generated'), exist_ok=True)
    if args.save_visualization:
        os.makedirs(os.path.join(args.output_dir, 'visualizations'), exist_ok=True)

    model.eval()

    all_metrics = []
    pbar = tqdm(dataloader, desc='Inference')

    for batch_idx, batch in enumerate(pbar):
        # Move to device
        person_masked = batch['person_masked'].to(device)
        cloth_image = batch['cloth_image'].to(device)
        target_image = batch['person_image'].to(device)

        # Generate
        with torch.no_grad():
            generated = model.generate(
                masked_person_image=person_masked,
                cloth_image=cloth_image,
                prompts=None,
                num_inference_steps=args.num_inference_steps,
                guidance_scale=args.guidance_scale
            )

        # Save generated images
        for i in range(generated.shape[0]):
            person_name = batch['person_names'][i]
            cloth_name = batch['cloth_names'][i]

            # Create output filename
            output_filename = f"{os.path.splitext(person_name)[0]}_{os.path.splitext(cloth_name)[0]}.png"
            output_path = os.path.join(args.output_dir, 'generated', output_filename)

            save_image(generated[i], output_path)

        # Save visualization
        if args.save_visualization and batch_idx < 10:  # Save first 10 batches
            vis_path = os.path.join(
                args.output_dir,
                'visualizations',
                f'batch_{batch_idx}.png'
            )
            visualize_batch(
                person_masked=person_masked,
                cloth=cloth_image,
                target=target_image,
                generated=generated,
                save_path=vis_path,
                num_samples=min(4, person_masked.shape[0])
            )

        # Compute metrics
        if args.compute_metrics:
            batch_metrics = compute_metrics(generated, target_image)
            all_metrics.append(batch_metrics)

            # Update progress bar
            pbar.set_postfix({k: f"{v:.4f}" for k, v in batch_metrics.items()})

    print(f"\nInference completed. Results saved to: {args.output_dir}")

    # Aggregate and save metrics
    if args.compute_metrics and all_metrics:
        avg_metrics = {}
        for key in all_metrics[0].keys():
            avg_metrics[key] = sum(m[key] for m in all_metrics) / len(all_metrics)

        print("\nAverage Metrics:")
        for metric_name, value in avg_metrics.items():
            print(f"  {metric_name}: {value:.4f}")

        # Save metrics
        import json
        metrics_path = os.path.join(args.output_dir, 'metrics.json')
        with open(metrics_path, 'w') as f:
            json.dump({
                'average': avg_metrics,
                'per_batch': all_metrics
            }, f, indent=2)

        print(f"Metrics saved: {metrics_path}")


def main():
    args = parse_args()

    # Setup device
    device = get_device(args.gpu_id)
    print(f"Using device: {device}")

    # Load model
    print("Loading model...")
    model = StandardVTONModel(
        pretrained_model_name=args.pretrained_model,
        freeze_weights=True,
        train_attention_only=True
    ).to(device)

    # Load checkpoint
    load_checkpoint(
        checkpoint_path=args.checkpoint,
        model=model,
        device=device
    )

    print("Model loaded successfully!")

    # Run inference
    if args.mode == 'single':
        if not args.person_masked or not args.cloth:
            raise ValueError("For single mode, --person_masked and --cloth are required")

        inference_single(
            model=model,
            person_masked_path=args.person_masked,
            cloth_path=args.cloth,
            person_gt_path=args.person_gt,
            args=args,
            device=device
        )

    elif args.mode == 'dataset':
        if not args.data_root:
            raise ValueError("For dataset mode, --data_root is required")

        # Create dataloader
        dataloader = get_dataloader(
            data_root=args.data_root,
            batch_size=args.batch_size,
            image_size=tuple(args.image_size),
            mode='test',
            num_workers=args.num_workers,
            dataset_type=args.dataset_type,
            shuffle=False
        )

        inference_dataset(
            model=model,
            dataloader=dataloader,
            args=args,
            device=device
        )


if __name__ == '__main__':
    main()
