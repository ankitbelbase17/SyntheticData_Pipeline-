"""
Training script for Standard VTON model
"""

import os
import argparse
import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR, LinearLR
from torch.utils.tensorboard import SummaryWriter
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

from model import StandardVTONModel
from dataloader import get_dataloader
from utils import (
    save_checkpoint,
    load_checkpoint,
    visualize_batch,
    AverageMeter,
    Logger,
    count_parameters,
    setup_directories,
    get_lr,
    set_seed,
    get_device,
    save_config
)


def parse_args():
    parser = argparse.ArgumentParser(description='Train Standard VTON Model')

    # Data parameters
    parser.add_argument('--data_root', type=str, required=True,
                       help='Root directory of dataset')
    parser.add_argument('--dataset_type', type=str, default='vton',
                       choices=['vton', 'viton-hd'],
                       help='Dataset type')
    parser.add_argument('--image_size', type=int, nargs=2, default=[512, 512],
                       help='Image size (height, width)')

    # Model parameters
    parser.add_argument('--pretrained_model', type=str,
                       default='runwayml/stable-diffusion-v1-5',
                       help='Pretrained Stable Diffusion model')
    parser.add_argument('--train_attention_only', action='store_true',
                       help='Train only attention weights')

    # Training parameters
    parser.add_argument('--batch_size', type=int, default=4,
                       help='Batch size')
    parser.add_argument('--num_epochs', type=int, default=100,
                       help='Number of training epochs')
    parser.add_argument('--lr', type=float, default=1e-4,
                       help='Learning rate')
    parser.add_argument('--weight_decay', type=float, default=0.01,
                       help='Weight decay')
    parser.add_argument('--warmup_epochs', type=int, default=5,
                       help='Number of warmup epochs')
    parser.add_argument('--gradient_accumulation_steps', type=int, default=1,
                       help='Gradient accumulation steps')
    parser.add_argument('--max_grad_norm', type=float, default=1.0,
                       help='Max gradient norm for clipping')

    # Logging and saving
    parser.add_argument('--output_dir', type=str, default='./outputs/standard_vton',
                       help='Output directory')
    parser.add_argument('--log_interval', type=int, default=10,
                       help='Logging interval (steps)')
    parser.add_argument('--save_interval', type=int, default=1000,
                       help='Checkpoint saving interval (steps)')
    parser.add_argument('--vis_interval', type=int, default=500,
                       help='Visualization interval (steps)')
    parser.add_argument('--resume', type=str, default=None,
                       help='Resume from checkpoint')

    # Other parameters
    parser.add_argument('--num_workers', type=int, default=4,
                       help='Number of data loading workers')
    parser.add_argument('--seed', type=int, default=42,
                       help='Random seed')
    parser.add_argument('--gpu_id', type=int, default=None,
                       help='GPU ID to use')

    return parser.parse_args()


def train_epoch(
    model,
    dataloader,
    optimizer,
    scheduler,
    epoch,
    args,
    device,
    logger,
    writer,
    global_step
):
    """Train for one epoch"""
    model.train()

    loss_meter = AverageMeter('Loss')
    pbar = tqdm(dataloader, desc=f'Epoch {epoch}')

    for step, batch in enumerate(pbar):
        # Move to device
        person_masked = batch['person_masked'].to(device)
        cloth_image = batch['cloth_image'].to(device)
        target_image = batch['person_image'].to(device)

        # Forward pass
        outputs = model(
            masked_person_image=person_masked,
            cloth_image=cloth_image,
            target_image=target_image,
            prompts=None  # Can add prompts if needed
        )

        loss = outputs['loss']

        # Gradient accumulation
        loss = loss / args.gradient_accumulation_steps
        loss.backward()

        # Update weights
        if (step + 1) % args.gradient_accumulation_steps == 0:
            # Gradient clipping
            if args.max_grad_norm > 0:
                torch.nn.utils.clip_grad_norm_(
                    model.get_trainable_parameters(),
                    args.max_grad_norm
                )

            optimizer.step()
            optimizer.zero_grad()

            if scheduler is not None:
                scheduler.step()

            global_step += 1

            # Update loss meter
            loss_meter.update(loss.item() * args.gradient_accumulation_steps)

            # Update progress bar
            pbar.set_postfix({
                'loss': loss_meter.avg,
                'lr': get_lr(optimizer)
            })

            # Logging
            if global_step % args.log_interval == 0:
                logger.log_metrics(
                    epoch=epoch,
                    step=global_step,
                    metrics={
                        'loss': loss_meter.avg,
                        'lr': get_lr(optimizer)
                    }
                )

                writer.add_scalar('train/loss', loss_meter.avg, global_step)
                writer.add_scalar('train/lr', get_lr(optimizer), global_step)

            # Save checkpoint
            if global_step % args.save_interval == 0:
                save_checkpoint(
                    model=model,
                    optimizer=optimizer,
                    epoch=epoch,
                    step=global_step,
                    loss=loss_meter.avg,
                    save_dir=os.path.join(args.output_dir, 'checkpoints')
                )

            # Visualization
            if global_step % args.vis_interval == 0:
                model.eval()
                with torch.no_grad():
                    generated = model.generate(
                        masked_person_image=person_masked[:4],
                        cloth_image=cloth_image[:4],
                        num_inference_steps=20
                    )

                    visualize_batch(
                        person_masked=person_masked[:4],
                        cloth=cloth_image[:4],
                        target=target_image[:4],
                        generated=generated,
                        save_path=os.path.join(
                            args.output_dir,
                            'samples',
                            f'epoch_{epoch}_step_{global_step}.png'
                        )
                    )
                model.train()

    return global_step


def main():
    args = parse_args()

    # Set seed
    set_seed(args.seed)

    # Setup device
    device = get_device(args.gpu_id)
    print(f"Using device: {device}")

    # Setup directories
    dirs = setup_directories(args.output_dir)

    # Save configuration
    save_config(vars(args), os.path.join(args.output_dir, 'config.json'))

    # Initialize logger
    logger = Logger(log_dir=dirs['logs'])
    logger.log(f"Starting training with config: {vars(args)}")

    # Initialize tensorboard
    writer = SummaryWriter(log_dir=dirs['logs'])

    # Create dataloaders
    logger.log("Creating dataloaders...")
    train_dataloader = get_dataloader(
        data_root=args.data_root,
        batch_size=args.batch_size,
        image_size=tuple(args.image_size),
        mode='train',
        num_workers=args.num_workers,
        dataset_type=args.dataset_type,
        shuffle=True
    )
    logger.log(f"Training dataset size: {len(train_dataloader.dataset)}")

    # Create model
    logger.log("Creating model...")
    model = StandardVTONModel(
        pretrained_model_name=args.pretrained_model,
        freeze_weights=True,
        train_attention_only=args.train_attention_only
    ).to(device)

    # Print model info
    total_params, trainable_params = count_parameters(model)
    logger.log(f"Total parameters: {total_params:,}")
    logger.log(f"Trainable parameters: {trainable_params:,}")
    logger.log(f"Trainable %: {100 * trainable_params / total_params:.2f}%")

    # Print trainable parameters
    model.print_trainable_parameters()

    # Create optimizer
    optimizer = AdamW(
        model.get_trainable_parameters(),
        lr=args.lr,
        weight_decay=args.weight_decay
    )

    # Create learning rate scheduler
    total_steps = len(train_dataloader) * args.num_epochs
    warmup_steps = len(train_dataloader) * args.warmup_epochs

    warmup_scheduler = LinearLR(
        optimizer,
        start_factor=0.1,
        total_iters=warmup_steps
    )

    cosine_scheduler = CosineAnnealingLR(
        optimizer,
        T_max=total_steps - warmup_steps,
        eta_min=1e-6
    )

    # Combine schedulers
    from torch.optim.lr_scheduler import SequentialLR
    scheduler = SequentialLR(
        optimizer,
        schedulers=[warmup_scheduler, cosine_scheduler],
        milestones=[warmup_steps]
    )

    # Resume from checkpoint if specified
    start_epoch = 0
    global_step = 0

    if args.resume:
        logger.log(f"Resuming from checkpoint: {args.resume}")
        checkpoint = load_checkpoint(
            checkpoint_path=args.resume,
            model=model,
            optimizer=optimizer,
            device=device
        )
        start_epoch = checkpoint.get('epoch', 0)
        global_step = checkpoint.get('step', 0)

    # Training loop
    logger.log("Starting training...")

    for epoch in range(start_epoch, args.num_epochs):
        logger.log(f"\n{'='*50}")
        logger.log(f"Epoch {epoch + 1}/{args.num_epochs}")
        logger.log(f"{'='*50}")

        global_step = train_epoch(
            model=model,
            dataloader=train_dataloader,
            optimizer=optimizer,
            scheduler=scheduler,
            epoch=epoch,
            args=args,
            device=device,
            logger=logger,
            writer=writer,
            global_step=global_step
        )

        # Save checkpoint at end of epoch
        save_checkpoint(
            model=model,
            optimizer=optimizer,
            epoch=epoch + 1,
            step=global_step,
            loss=0.0,  # Use validation loss if available
            save_dir=os.path.join(args.output_dir, 'checkpoints')
        )

    logger.log("\nTraining completed!")
    writer.close()


if __name__ == '__main__':
    main()
