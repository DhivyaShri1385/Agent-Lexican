import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Blueprint, jsonify, session

from backend.config import Settings
from backend.services.auth_service import AuthService


def create_admin_blueprint(auth_service: AuthService, settings: Settings) -> Blueprint:
    admin_bp = Blueprint("admin", __name__)

    def admin_required(handler):
        @wraps(handler)
        def wrapper(*args, **kwargs):
            user_pk = session.get("user_pk")
            if not user_pk:
                return jsonify({"error": "Authentication required."}), 401

            user = auth_service.get_user_by_pk(user_pk)
            if user is None or user.get("role") != "admin":
                return jsonify({"error": "Admin access required."}), 403

            return handler(*args, **kwargs)

        return wrapper

    def load_history_all() -> list[dict]:
        if not settings.history_file.exists():
            return []

        try:
            raw = settings.history_file.read_text(encoding="utf-8").strip()
            data = json.loads(raw) if raw else []
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    @admin_bp.get("/admin/users")
    @admin_required
    def list_users():
        users = auth_service.list_users(limit=500)
        return jsonify({"items": users})

    @admin_bp.get("/admin/analytics")
    @admin_required
    def analytics():
        history = load_history_all()
        user_counts = auth_service.user_counts()

        total_generations = len(history)
        recent_cutoff = datetime.now(timezone.utc) - timedelta(days=7)

        recent_7d = 0
        theme_counter = Counter()
        prompt_counter = Counter()

        for record in history:
            theme_counter.update([record.get("theme") or "unknown"])
            prompt_counter.update([record.get("prompt") or ""])

            ts = record.get("timestamp")
            if not ts:
                continue
            try:
                parsed = datetime.fromisoformat(ts)
                if parsed >= recent_cutoff:
                    recent_7d += 1
            except ValueError:
                continue

        top_themes = [{"theme": k, "count": v} for k, v in theme_counter.most_common(5)]
        top_prompts = [{"prompt": k, "count": v} for k, v in prompt_counter.most_common(5) if k]

        return jsonify(
            {
                "users": user_counts,
                "generation": {
                    "total_generations": total_generations,
                    "last_7_days": recent_7d,
                    "top_themes": top_themes,
                    "top_prompts": top_prompts,
                },
            }
        )

    return admin_bp
