import os
from dataclasses import dataclass
from pathlib import Path

import torch


@dataclass
class Settings:
	base_dir: Path
	app_env: str
	model_id: str
	lora_weights_dir: Path
	output_dir: Path
	history_file: Path
	theme: str
	device: str
	default_steps: int
	default_guidance_scale: float
	default_width: int
	default_height: int
	secret_key: str
	users_db_file: Path
	frontend_url: str
	backend_url: str
	github_client_id: str
	github_client_secret: str
	admin_email: str
	reset_token_expiry_minutes: int
	smtp_host: str
	smtp_port: int
	smtp_username: str
	smtp_password: str
	smtp_use_tls: bool
	mail_from: str


def get_settings() -> Settings:
	backend_dir = Path(__file__).resolve().parent
	project_root = backend_dir.parent
	app_env = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")).strip().lower()

	explicit_model = os.getenv("MODEL_ID")
	lora_weights_dir = Path(os.getenv("LORA_WEIGHTS_DIR", str(project_root / "model" / "lora")))
	output_dir = Path(os.getenv("OUTPUT_DIR", str(project_root / "outputs")))
	history_file = Path(os.getenv("HISTORY_FILE", str(output_dir / "history.json")))
	users_db_file = Path(os.getenv("USERS_DB_FILE", str(output_dir / "users.db")))
	theme = os.getenv("PROJECT_THEME", "futuristic robots")
	frontend_url = os.getenv("FRONTEND_URL", "http://127.0.0.1:5500")
	backend_url = os.getenv("BACKEND_URL", "http://127.0.0.1:5000")
	github_client_id = os.getenv("GITHUB_CLIENT_ID", "")
	github_client_secret = os.getenv("GITHUB_CLIENT_SECRET", "")
	secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
	admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
	reset_token_expiry_minutes = int(os.getenv("RESET_TOKEN_EXPIRY_MINUTES", "30"))

	smtp_host = os.getenv("SMTP_HOST", "").strip()
	smtp_port = int(os.getenv("SMTP_PORT", "587"))
	smtp_username = os.getenv("SMTP_USERNAME", "").strip()
	smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
	smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").strip().lower() in {"1", "true", "yes"}
	mail_from = os.getenv("MAIL_FROM", smtp_username or "no-reply@example.com").strip()

	if os.getenv("DEVICE"):
		device = os.getenv("DEVICE", "cpu")
	else:
		device = "cuda" if torch.cuda.is_available() else "cpu"

	if explicit_model:
		model_id = explicit_model
	else:
		# On CPU, use a smaller default model so generation returns in practical time.
		model_id = "segmind/tiny-sd" if device == "cpu" else "runwayml/stable-diffusion-v1-5"

	default_steps = int(os.getenv("DEFAULT_STEPS", "12" if device == "cpu" else "30"))
	default_guidance_scale = float(os.getenv("DEFAULT_GUIDANCE_SCALE", "6.5" if device == "cpu" else "7.5"))
	default_width = int(os.getenv("DEFAULT_WIDTH", "384" if device == "cpu" else "512"))
	default_height = int(os.getenv("DEFAULT_HEIGHT", "384" if device == "cpu" else "512"))

	return Settings(
		base_dir=project_root,
		app_env=app_env,
		model_id=model_id,
		lora_weights_dir=lora_weights_dir,
		output_dir=output_dir,
		history_file=history_file,
		theme=theme,
		device=device,
		default_steps=default_steps,
		default_guidance_scale=default_guidance_scale,
		default_width=default_width,
		default_height=default_height,
		secret_key=secret_key,
		users_db_file=users_db_file,
		frontend_url=frontend_url,
		backend_url=backend_url,
		github_client_id=github_client_id,
		github_client_secret=github_client_secret,
		admin_email=admin_email,
		reset_token_expiry_minutes=reset_token_expiry_minutes,
		smtp_host=smtp_host,
		smtp_port=smtp_port,
		smtp_username=smtp_username,
		smtp_password=smtp_password,
		smtp_use_tls=smtp_use_tls,
		mail_from=mail_from,
	)
