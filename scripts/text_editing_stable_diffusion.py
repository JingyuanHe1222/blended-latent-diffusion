import argparse
import numpy as np
from PIL import Image
import cv2

from diffusers import DDIMScheduler, StableDiffusionPipeline
import torch


class BlendedLatnetDiffusion:
    def __init__(self):
        self.parse_args()
        self.load_models()

    def parse_args(self):
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--prompt", type=str, required=True, help="The target text prompt"
        )
        parser.add_argument(
            "--init_image", type=str, required=True, help="The path to the input image"
        )
        parser.add_argument(
            "--mask", type=str, required=True, help="The path to the input mask"
        )
        parser.add_argument(
            "--model_path",
            type=str,
            default="stabilityai/stable-diffusion-2-1-base",
            help="The path to the HuggingFace model",
        )
        parser.add_argument(
            "--batch_size", type=int, default=4, help="The number of images to generate"
        )
        parser.add_argument(
            "--blending_start_percentage",
            type=float,
            default=0.25,
            help="The diffusion steps percentage to jump",
        )
        parser.add_argument("--device", type=str, default="cuda")
        parser.add_argument(
            "--output_path",
            type=str,
            default="outputs/res.jpg",
            help="The destination output path",
        )
        parser.add_argument("--morph", type=str, default=False)

        self.args = parser.parse_args()

    def load_models(self):
        pipe = StableDiffusionPipeline.from_pretrained(
            self.args.model_path, torch_dtype=torch.float16
        )
        self.vae = pipe.vae.to(self.args.device)
        self.tokenizer = pipe.tokenizer
        self.text_encoder = pipe.text_encoder.to(self.args.device)
        self.unet = pipe.unet.to(self.args.device)
        self.scheduler = DDIMScheduler(
            beta_start=0.00085,
            beta_end=0.012,
            beta_schedule="scaled_linear",
            clip_sample=False,
            set_alpha_to_one=False,
        )

    @torch.no_grad()
    def edit_image(
        self,
        image_path,
        mask_path,
        prompts,
        height=512,
        width=512,
        num_inference_steps=50,
        guidance_scale=7.5,
        generator=torch.manual_seed(42),
        blending_percentage=0.25,
    ):
        batch_size = len(prompts)

        image = Image.open(image_path)
        image = image.resize((height, width), Image.BILINEAR)
        image = np.array(image)[:, :, :3]
        source_latents = self._image2latent(image) # the souce image latents

        text_input = self.tokenizer(
            prompts,
            padding="max_length",
            max_length=self.tokenizer.model_max_length,
            truncation=True,
            return_tensors="pt",
        )
        text_embeddings = self.text_encoder(text_input.input_ids.to("cuda"))[0] # encode prompt -> desired subject

        max_length = text_input.input_ids.shape[-1]
        uncond_input = self.tokenizer(
            [""] * batch_size,
            padding="max_length",
            max_length=max_length,
            return_tensors="pt",
        )
        uncond_embeddings = self.text_encoder(uncond_input.input_ids.to("cuda"))[0] # blank
        text_embeddings = torch.cat([uncond_embeddings, text_embeddings])

        latents = torch.randn(
            (batch_size, self.unet.in_channels, height // 8, width // 8),
            generator=generator,
        )
        latents = latents.to("cuda").half()

        self.scheduler.set_timesteps(num_inference_steps)
        
        # morph dilation samples
        total = self.scheduler.timesteps[int(len(self.scheduler.timesteps) * blending_percentage) :].size(0)
        threshold = total // 2 # threshold
        print("dilation step threshold", threshold)
        dilation_init = 5
        print("dilation init", dilation_init)
        
        for i, t in enumerate(self.scheduler.timesteps[
            int(len(self.scheduler.timesteps) * blending_percentage) :
        ]):
            # expand the latents if we are doing classifier-free guidance to avoid doing two forward passes.
            latent_model_input = torch.cat([latents] * 2)

            latent_model_input = self.scheduler.scale_model_input(
                latent_model_input, timestep=t
            )

            # predict the noise residual -> should add the multimoadl embeddings of text and images
            with torch.no_grad():
                noise_pred = self.unet(
                    latent_model_input, t, encoder_hidden_states=text_embeddings
                ).sample

            # perform guidance
            noise_pred_uncond, noise_pred_text = noise_pred.chunk(2)
            noise_pred = noise_pred_uncond + guidance_scale * (
                noise_pred_text - noise_pred_uncond
            )

            # compute the previous noisy sample x_t -> x_t-1
            latents = self.scheduler.step(noise_pred, t, latents).prev_sample
            
            
            latent_mask, org_mask = self._read_mask(mask_path)

            # moprh transform
            if self.args.morph == True:
                print(self.args.morph)
                print("use morph")
                np_mask = latent_mask.squeeze().cpu().numpy()
                latent_mask = self.morph_dilation(np_mask, i, threshold, dilation_init)

            # Blending
            noise_source_latents = self.scheduler.add_noise(
                source_latents, torch.randn_like(latents), t
            )
            latents = latents * latent_mask + noise_source_latents * (1 - latent_mask)

        latents = 1 / 0.18215 * latents

        with torch.no_grad():
            image = self.vae.decode(latents).sample

        image = (image / 2 + 0.5).clamp(0, 1)
        image = image.detach().cpu().permute(0, 2, 3, 1).numpy()
        images = (image * 255).round().astype("uint8")

        return images
    
    
    def morph_dilation(self, mask, i, threshold, dilation_init):
            closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((1, 1),np.uint8), iterations=1) 
            latent_mask = closed

            if i < threshold: # first denosing steps only
                kernel_size = 2
                kernel = np.ones((kernel_size, kernel_size),np.uint8)
                latent_mask = cv2.erode(closed.astype(np.uint8),kernel,iterations = 1)
            else: 
                print("dilate: ")
                # dialated for previous steps -> larger kernel
                kernel_size = int(dilation_init*i/threshold)
                print("kernel size", kernel_size)
                kernel = np.ones((kernel_size, kernel_size),np.uint8)
                latent_mask = cv2.dilate(closed.astype(np.uint8),kernel,iterations = 1)
            latent_mask = torch.from_numpy(latent_mask)
            latent_mask = latent_mask[None, None, :, :].to("cuda")
            return latent_mask

        
    @torch.no_grad()
    def _image2latent(self, image):
        image = torch.from_numpy(image).float() / 127.5 - 1
        image = image.permute(2, 0, 1).unsqueeze(0).to("cuda")
        image = image.half()
        latents = self.vae.encode(image)["latent_dist"].mean
        latents = latents * 0.18215

        return latents

    def _read_mask(self, mask_path: str, dest_size=(64, 64)):
        org_mask = Image.open(mask_path).convert("L")
        mask = org_mask.resize(dest_size, Image.NEAREST)
        mask = np.array(mask)
        if np.max(mask) > 1: 
            mask = np.array(mask) / 255
        mask[mask < 0.5] = 0
        mask[mask >= 0.5] = 1
        mask = mask[np.newaxis, np.newaxis, ...]
        mask = torch.from_numpy(mask).half().to(self.args.device)

        return mask, org_mask


if __name__ == "__main__":
    bld = BlendedLatnetDiffusion()
    results = bld.edit_image(
        bld.args.init_image,
        bld.args.mask,
        prompts=[bld.args.prompt] * bld.args.batch_size,
        blending_percentage=bld.args.blending_start_percentage,
    )
    results_flat = np.concatenate(results, axis=1)
    Image.fromarray(results_flat).save(bld.args.output_path)
