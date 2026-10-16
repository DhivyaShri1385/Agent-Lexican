from functools import wraps

from flask import Blueprint, jsonify, request, session

from backend.config import Settings
from backend.services.inference import InferenceService
from backend.services.job_service import JobService
from backend.utils.file_handler import read_history
from backend.utils.helpers import validate_prompt


def create_generate_blueprint(service: InferenceService, settings: Settings, job_service: JobService) -> Blueprint:
	generate_bp = Blueprint("generate", __name__)

	def login_required(handler):
		@wraps(handler)
		def wrapper(*args, **kwargs):
			if not session.get("user_pk"):
				return jsonify({"error": "Authentication required."}), 401
			return handler(*args, **kwargs)

		return wrapper

	@generate_bp.get("/theme")
	def get_theme():
		return jsonify(
			{
				"theme": settings.theme,
				"model_id": settings.model_id,
				"default_steps": settings.default_steps,
				"default_guidance_scale": settings.default_guidance_scale,
			}
		)

	@generate_bp.get("/history")
	@login_required
	def get_history():
		history = read_history(settings.history_file)
		return jsonify({"items": history})

	@generate_bp.post("/generate")
	@login_required
	def generate_image():
		payload = request.get_json(silent=True) or {}
		prompt = payload.get("prompt", "")
		negative_prompt = payload.get("negative_prompt", "")
		steps = int(payload.get("steps", settings.default_steps))
		guidance_scale = float(payload.get("guidance_scale", settings.default_guidance_scale))
		width = int(payload.get("width", settings.default_width))
		height = int(payload.get("height", settings.default_height))
		seed = payload.get("seed")

		is_valid, message = validate_prompt(prompt)
		if not is_valid:
			return jsonify({"error": message}), 400

		steps = max(4, min(60, steps))
		guidance_scale = max(1.0, min(20.0, guidance_scale))
		width = max(256, min(1024, width))
		height = max(256, min(1024, height))

		if seed in (None, ""):
			parsed_seed = None
		else:
			try:
				parsed_seed = int(seed)
			except ValueError:
				return jsonify({"error": "Seed must be a valid integer."}), 400

		try:
			current_user = session.get("user")
			if current_user is None:
				# Backward-compatible fallback for existing session style.
				current_user = {"id": session.get("user_pk")}

			result = service.generate_image(
				prompt=prompt.strip(),
				negative_prompt=negative_prompt.strip(),
				num_inference_steps=steps,
				guidance_scale=guidance_scale,
				width=width,
				height=height,
				seed=parsed_seed,
				generated_by_user_id=(current_user or {}).get("user_id"),
				generated_by_email=(current_user or {}).get("email"),
			)
			return jsonify(result)
		except Exception as exc:
			return jsonify({"error": f"Image generation failed: {exc}"}), 500

	@generate_bp.post("/generate-async")
	@login_required
	def generate_image_async():
		payload = request.get_json(silent=True) or {}
		prompt = payload.get("prompt", "")
		negative_prompt = payload.get("negative_prompt", "")
		steps = int(payload.get("steps", settings.default_steps))
		guidance_scale = float(payload.get("guidance_scale", settings.default_guidance_scale))
		width = int(payload.get("width", settings.default_width))
		height = int(payload.get("height", settings.default_height))
		seed = payload.get("seed")

		is_valid, message = validate_prompt(prompt)
		if not is_valid:
			return jsonify({"error": message}), 400

		steps = max(4, min(60, steps))
		guidance_scale = max(1.0, min(20.0, guidance_scale))
		width = max(256, min(1024, width))
		height = max(256, min(1024, height))

		if seed in (None, ""):
			parsed_seed = None
		else:
			try:
				parsed_seed = int(seed)
			except ValueError:
				return jsonify({"error": "Seed must be a valid integer."}), 400

		current_user = session.get("user") or {}
		job = job_service.create_job(
			{
				"prompt": prompt,
				"user_id": current_user.get("user_id"),
				"email": current_user.get("email"),
			}
		)

		def _task():
			job_service.update_job(job["job_id"], status="running", progress=45, message="Generating image")
			result = service.generate_image(
				prompt=prompt.strip(),
				negative_prompt=negative_prompt.strip(),
				num_inference_steps=steps,
				guidance_scale=guidance_scale,
				width=width,
				height=height,
				seed=parsed_seed,
				generated_by_user_id=current_user.get("user_id"),
				generated_by_email=current_user.get("email"),
			)
			job_service.update_job(job["job_id"], status="running", progress=90, message="Finalizing output")
			return result

		job_service.run_async(job["job_id"], _task)
		return jsonify({"job_id": job["job_id"], "status": "queued"}), 202

	@generate_bp.get("/jobs/<job_id>")
	@login_required
	def get_job_status(job_id: str):
		job = job_service.get_job(job_id)
		if job is None:
			return jsonify({"error": "Job not found."}), 404
		return jsonify(job), 200

	return generate_bp
