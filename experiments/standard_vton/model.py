"""
Standard VTON Model Architecture
Uses Stable Diffusion 1.5 as backbone with trainable attention weights only.
Concatenates VAE latents of masked person image and cloth for conditioning.
"""

import torch
import torch.nn as nn
from typing import Dict, Optional, Tuple
from diffusers import AutoencoderKL, UNet2DConditionModel, DDPMScheduler
from transformers import CLIPTextModel, CLIPTokenizer


class StandardVTONModel(nn.Module):
    """
    Standard VTON model that:
    1. Encodes masked person image and cloth image to VAE latents
    2. Concatenates latents as conditioning
    3. Uses UNet with self-attention only (trainable attention weights)
    4. Generates ground truth person image with cloth
    """

    def __init__(
        self,
        pretrained_model_name: str = "runwayml/stable-diffusion-v1-5",
        freeze_weights: bool = True,
        train_attention_only: bool = True
    ):
        super().__init__()

        # Load pretrained Stable Diffusion 1.5 components
        self.vae = AutoencoderKL.from_pretrained(
            pretrained_model_name,
            subfolder="vae"
        )

        self.unet = UNet2DConditionModel.from_pretrained(
            pretrained_model_name,
            subfolder="unet"
        )

        self.text_encoder = CLIPTextModel.from_pretrained(
            pretrained_model_name,
            subfolder="text_encoder"
        )

        self.tokenizer = CLIPTokenizer.from_pretrained(
            pretrained_model_name,
            subfolder="tokenizer"
        )

        # Noise scheduler for training
        self.noise_scheduler = DDPMScheduler.from_pretrained(
            pretrained_model_name,
            subfolder="scheduler"
        )

        # Freeze all weights initially
        if freeze_weights:
            self._freeze_all_weights()

        # Only train attention weights
        if train_attention_only:
            self._unfreeze_attention_weights()

        # Modify UNet input channels to accept concatenated latents
        # Original: 4 channels (latent), New: 8 channels (4 + 4 for masked person + cloth)
        self._modify_unet_input_channels()

        self.latent_channels = 4

    def _freeze_all_weights(self):
        """Freeze all model weights"""
        for param in self.vae.parameters():
            param.requires_grad = False

        for param in self.unet.parameters():
            param.requires_grad = False

        for param in self.text_encoder.parameters():
            param.requires_grad = False

    def _unfreeze_attention_weights(self):
        """Unfreeze only self-attention weights in UNet"""
        for name, param in self.unet.named_parameters():
            # Unfreeze attention layers (query, key, value, output projections)
            if 'attn1' in name or 'self_attn' in name:
                # attn1 is self-attention in diffusers UNet
                if any(x in name for x in ['to_q', 'to_k', 'to_v', 'to_out']):
                    param.requires_grad = True
                    print(f"Unfrozen: {name}")

    def _modify_unet_input_channels(self):
        """Modify UNet to accept concatenated latents (8 channels instead of 4)"""
        # Get the original first convolution layer
        original_conv = self.unet.conv_in

        # Create new convolution with 8 input channels
        new_conv = nn.Conv2d(
            in_channels=8,  # 4 (masked person latent) + 4 (cloth latent)
            out_channels=original_conv.out_channels,
            kernel_size=original_conv.kernel_size,
            stride=original_conv.stride,
            padding=original_conv.padding
        )

        # Initialize new conv weights
        with torch.no_grad():
            # Copy original weights for first 4 channels
            new_conv.weight[:, :4, :, :] = original_conv.weight.clone()
            # Initialize weights for additional 4 channels
            new_conv.weight[:, 4:, :, :] = original_conv.weight.clone()
            new_conv.bias = original_conv.bias.clone()

        # Replace the conv layer
        self.unet.conv_in = new_conv

    def encode_images(self, images: torch.Tensor) -> torch.Tensor:
        """
        Encode images to VAE latents
        Args:
            images: Tensor of shape (B, 3, H, W) in range [-1, 1]
        Returns:
            latents: Tensor of shape (B, 4, H/8, W/8)
        """
        with torch.no_grad():
            latents = self.vae.encode(images).latent_dist.sample()
            latents = latents * self.vae.config.scaling_factor
        return latents

    def decode_latents(self, latents: torch.Tensor) -> torch.Tensor:
        """
        Decode latents to images
        Args:
            latents: Tensor of shape (B, 4, H/8, W/8)
        Returns:
            images: Tensor of shape (B, 3, H, W) in range [-1, 1]
        """
        latents = latents / self.vae.config.scaling_factor
        with torch.no_grad():
            images = self.vae.decode(latents).sample
        return images

    def get_text_embeddings(self, prompts: list[str]) -> torch.Tensor:
        """
        Get text embeddings from prompts
        Args:
            prompts: List of text prompts
        Returns:
            text_embeddings: Tensor of shape (B, 77, 768)
        """
        text_inputs = self.tokenizer(
            prompts,
            padding="max_length",
            max_length=self.tokenizer.model_max_length,
            truncation=True,
            return_tensors="pt"
        )

        with torch.no_grad():
            text_embeddings = self.text_encoder(
                text_inputs.input_ids.to(self.text_encoder.device)
            )[0]

        return text_embeddings

    def forward(
        self,
        masked_person_image: torch.Tensor,
        cloth_image: torch.Tensor,
        target_image: torch.Tensor,
        prompts: Optional[list[str]] = None,
        timesteps: Optional[torch.Tensor] = None
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass for training
        Args:
            masked_person_image: Masked person image (B, 3, H, W)
            cloth_image: Cloth image (B, 3, H, W)
            target_image: Ground truth person with cloth (B, 3, H, W)
            prompts: Text prompts for conditioning (optional)
            timesteps: Specific timesteps to use (optional)
        Returns:
            Dictionary containing loss and predictions
        """
        batch_size = masked_person_image.shape[0]
        device = masked_person_image.device

        # Encode images to latents
        masked_person_latents = self.encode_images(masked_person_image)
        cloth_latents = self.encode_images(cloth_image)
        target_latents = self.encode_images(target_image)

        # Concatenate latents for conditioning
        conditioning_latents = torch.cat([masked_person_latents, cloth_latents], dim=1)

        # Sample noise
        noise = torch.randn_like(target_latents)

        # Sample random timesteps
        if timesteps is None:
            timesteps = torch.randint(
                0,
                self.noise_scheduler.config.num_train_timesteps,
                (batch_size,),
                device=device
            ).long()

        # Add noise to target latents
        noisy_latents = self.noise_scheduler.add_noise(
            target_latents,
            noise,
            timesteps
        )

        # Concatenate noisy latents with conditioning
        unet_input = torch.cat([noisy_latents, conditioning_latents[:, :4, :, :]], dim=1)

        # Get text embeddings if prompts provided
        if prompts is not None:
            encoder_hidden_states = self.get_text_embeddings(prompts)
        else:
            # Use unconditional (empty) prompts
            encoder_hidden_states = self.get_text_embeddings([""] * batch_size)

        # Predict noise with UNet
        noise_pred = self.unet(
            unet_input,
            timesteps,
            encoder_hidden_states=encoder_hidden_states
        ).sample

        # Calculate loss (MSE between predicted and actual noise)
        loss = nn.functional.mse_loss(noise_pred, noise)

        return {
            "loss": loss,
            "noise_pred": noise_pred,
            "noise": noise,
            "conditioning_latents": conditioning_latents,
            "target_latents": target_latents
        }

    @torch.no_grad()
    def generate(
        self,
        masked_person_image: torch.Tensor,
        cloth_image: torch.Tensor,
        prompts: Optional[list[str]] = None,
        num_inference_steps: int = 50,
        guidance_scale: float = 7.5
    ) -> torch.Tensor:
        """
        Generate try-on result
        Args:
            masked_person_image: Masked person image (B, 3, H, W)
            cloth_image: Cloth image (B, 3, H, W)
            prompts: Text prompts for conditioning (optional)
            num_inference_steps: Number of denoising steps
            guidance_scale: Classifier-free guidance scale
        Returns:
            generated_images: Generated person with cloth (B, 3, H, W)
        """
        batch_size = masked_person_image.shape[0]
        device = masked_person_image.device

        # Encode conditioning images
        masked_person_latents = self.encode_images(masked_person_image)
        cloth_latents = self.encode_images(cloth_image)

        # Concatenate latents
        conditioning_latents = torch.cat([masked_person_latents, cloth_latents], dim=1)

        # Initialize with random noise
        latents = torch.randn(
            (batch_size, 4, masked_person_latents.shape[2], masked_person_latents.shape[3]),
            device=device
        )

        # Set timesteps
        self.noise_scheduler.set_timesteps(num_inference_steps)

        # Get text embeddings
        if prompts is not None:
            text_embeddings = self.get_text_embeddings(prompts)
        else:
            text_embeddings = self.get_text_embeddings([""] * batch_size)

        # Get unconditional embeddings for classifier-free guidance
        uncond_embeddings = self.get_text_embeddings([""] * batch_size)

        # Denoising loop
        for t in self.noise_scheduler.timesteps:
            # Expand latents for classifier-free guidance
            latent_model_input = torch.cat([latents] * 2)
            latent_model_input = self.noise_scheduler.scale_model_input(latent_model_input, t)

            # Concatenate with conditioning
            unet_input = torch.cat([
                latent_model_input,
                conditioning_latents[:, :4, :, :].repeat(2, 1, 1, 1)
            ], dim=1)

            # Predict noise
            noise_pred = self.unet(
                unet_input,
                t,
                encoder_hidden_states=torch.cat([uncond_embeddings, text_embeddings])
            ).sample

            # Perform guidance
            noise_pred_uncond, noise_pred_text = noise_pred.chunk(2)
            noise_pred = noise_pred_uncond + guidance_scale * (noise_pred_text - noise_pred_uncond)

            # Compute previous latents
            latents = self.noise_scheduler.step(noise_pred, t, latents).prev_sample

        # Decode latents to images
        generated_images = self.decode_latents(latents)

        return generated_images

    def get_trainable_parameters(self):
        """Get trainable parameters"""
        return [p for p in self.parameters() if p.requires_grad]

    def print_trainable_parameters(self):
        """Print trainable parameter statistics"""
        trainable_params = 0
        all_params = 0

        for name, param in self.named_parameters():
            all_params += param.numel()
            if param.requires_grad:
                trainable_params += param.numel()
                print(f"Trainable: {name} - {param.numel()} parameters")

        print(f"\nTrainable params: {trainable_params:,} || "
              f"All params: {all_params:,} || "
              f"Trainable %: {100 * trainable_params / all_params:.2f}%")
