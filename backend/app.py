import os
from pathlib import Path

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from backend.config import get_settings
from backend.routes.admin import create_admin_blueprint
from backend.routes.auth import create_auth_blueprint
from backend.routes.generate import create_generate_blueprint
from backend.services.auth_service import AuthService
from backend.services.email_service import EmailService
from backend.services.inference import InferenceService
from backend.services.job_service import JobService
from backend.utils.file_handler import ensure_output_files


def create_app() -> Flask:
    settings = get_settings()
    ensure_output_files(settings.output_dir, settings.history_file)

    app = Flask(__name__)
    app.secret_key = settings.secret_key
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = settings.app_env == "production"

    frontend_dir = settings.base_dir / "frontend"

    CORS(
        app,
        supports_credentials=True,
        resources={r"/api/*": {"origins": r".*"}},
    )

    inference_service = InferenceService(settings)
    job_service = JobService()
    auth_service = AuthService(settings.users_db_file)
    auth_service.bootstrap_admin(settings.admin_email)
    email_service = EmailService(settings)

    app.register_blueprint(create_auth_blueprint(auth_service, email_service, settings), url_prefix="/api")
    app.register_blueprint(create_admin_blueprint(auth_service, settings), url_prefix="/api")
    app.register_blueprint(create_generate_blueprint(inference_service, settings, job_service), url_prefix="/api")

    @app.get("/health")
    def health_check():
        return jsonify({"status": "ok", "device": settings.device, "theme": settings.theme})

    @app.get("/outputs/<path:filename>")
    def serve_output(filename: str):
        return send_from_directory(settings.output_dir, filename)

    @app.get("/")
    def serve_root():
        return send_from_directory(frontend_dir, "login.html")

    @app.get("/<path:filename>")
    def serve_frontend_file(filename: str):
        full_path = (frontend_dir / filename).resolve()
        if not str(full_path).startswith(str(frontend_dir.resolve())):
            return jsonify({"error": "Invalid path"}), 400

        if not full_path.exists() or not full_path.is_file():
            return jsonify({"error": "Not found"}), 404

        # Serve only frontend static assets/pages through this route.
        allowed_suffixes = {".html", ".css", ".js", ".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico"}
        if full_path.suffix.lower() not in allowed_suffixes and "assets" not in Path(filename).parts:
            return jsonify({"error": "Not found"}), 404

        return send_from_directory(frontend_dir, filename)

    return app


app = create_app()


if __name__ == "__main__":
    run_settings = get_settings()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=run_settings.app_env != "production")