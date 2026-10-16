from pathlib import Path
from typing import Any

import torch
from diffusers import DPMSolverMultistepScheduler, StableDiffusionPipeline

from backend.config import Settings
from backend.utils.file_handler import append_history, build_output_path, ensure_output_files
from backend.utils.helpers import utc_timestamp


class InferenceService:
	def __init__(self, settings: Settings):
		self.settings = settings
		self.pipe: StableDiffusionPipeline | None = None
		ensure_output_files(self.settings.output_dir, self.settings.history_file)

	def _load_pipeline(self) -> StableDiffusionPipeline:
		if self.pipe is not None:
			return self.pipe

		torch_dtype = torch.float16 if self.settings.device == "cuda" else torch.float32
		pipe = StableDiffusionPipeline.from_pretrained(
			self.settings.model_id,
			torch_dtype=torch_dtype,
			safety_checker=None,
			requires_safety_checker=False,
			low_cpu_mem_usage=False,
		)
		pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config)
		pipe = pipe.to(self.settings.device)

		if self.settings.device == "cpu":
			pipe.enable_attention_slicing()
			pipe.enable_vae_slicing()

		if self.settings.lora_weights_dir.exists():
			try:
				pipe.load_lora_weights(str(self.settings.lora_weights_dir))
				pipe.fuse_lora()
			except Exception:
				# If LoRA weights are missing/invalid, keep base model available.
				pass

		self.pipe = pipe
		return pipe

	def generate_image(
		self,
		prompt: str,
		negative_prompt: str = "",
		num_inference_steps: int | None = None,
		guidance_scale: float | None = None,
		width: int | None = None,
		height: int | None = None,
		seed: int | None = None,
		generated_by_user_id: str | None = None,
		generated_by_email: str | None = None,
	) -> dict[str, Any]:
		try:
			pipe = self._load_pipeline()
		except Exception:
			self.pipe = None
			raise

		resolved_steps = num_inference_steps or self.settings.default_steps
		resolved_guidance = guidance_scale or self.settings.default_guidance_scale
		resolved_width = width or self.settings.default_width
		resolved_height = height or self.settings.default_height

		generator = None
		if seed is not None:
			generator = torch.Generator(device=self.settings.device).manual_seed(seed)

		output_path = build_output_path(self.settings.output_dir, prompt)

		result = pipe(
			prompt=prompt,
			negative_prompt=negative_prompt or None,
			num_inference_steps=resolved_steps,
			guidance_scale=resolved_guidance,
			width=resolved_width,
			height=resolved_height,
			generator=generator,
		)

		image = result.images[0]
		image.save(output_path)

		output_name = output_path.name
		served_url = f"/outputs/{output_name}"
		record = {
			"timestamp": utc_timestamp(),
			"prompt": prompt,
			"negative_prompt": negative_prompt,
			"steps": resolved_steps,
			"guidance_scale": resolved_guidance,
			"seed": seed,
			"theme": self.settings.theme,
			"generated_by_user_id": generated_by_user_id,
			"generated_by_email": generated_by_email,
			"image_path": output_name,
			"image_url": served_url,
		}
		append_history(self.settings.history_file, record)

		return {
			"image_path": output_name,
			"image_url": served_url,
			"seed": seed,
			"theme": self.settings.theme,
		}


def resolve_image_path(base_dir: Path, relative_path: str) -> Path:
	return (base_dir / relative_path).resolve()
