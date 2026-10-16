import secrets
from urllib.parse import urlencode

import requests
from flask import Blueprint, jsonify, redirect, request, session

from backend.config import Settings
from backend.services.auth_service import AuthService
from backend.services.email_service import EmailService


def create_auth_blueprint(auth_service: AuthService, email_service: EmailService, settings: Settings) -> Blueprint:
    auth_bp = Blueprint("auth", __name__)

    frontend_login_url = f"{settings.frontend_url.rstrip('/')}/login.html"

    def current_user():
        user_pk = session.get("user_pk")
        if not user_pk:
            return None
        return auth_service.get_user_by_pk(user_pk)

    @auth_bp.get("/auth/me")
    def me():
        user = current_user()
        if user is None:
            return jsonify({"authenticated": False}), 200
        return jsonify({"authenticated": True, "user": user}), 200

    @auth_bp.post("/auth/register")
    def register():
        payload = request.get_json(silent=True) or {}
        user_id = (payload.get("user_id") or "").strip()
        email = (payload.get("email") or "").strip()
        password = payload.get("password") or ""

        ok, message = auth_service.register_local_user(user_id, email, password)
        if not ok:
            return jsonify({"error": message}), 400

        auth_service.bootstrap_admin(settings.admin_email)

        return jsonify({"message": message}), 201

    @auth_bp.post("/auth/login")
    def login():
        payload = request.get_json(silent=True) or {}
        login_value = (payload.get("login") or "").strip()
        password = payload.get("password") or ""

        if not login_value or not password:
            return jsonify({"error": "Provide login and password."}), 400

        user = auth_service.authenticate_local_user(login_value, password)
        if user is None:
            return jsonify({"error": "Invalid credentials."}), 401

        session["user_pk"] = user["id"]
        session["user"] = {
            "id": user.get("id"),
            "user_id": user.get("user_id"),
            "email": user.get("email"),
            "role": user.get("role"),
        }
        return jsonify({"message": "Login successful.", "user": user}), 200

    @auth_bp.post("/auth/forgot-password")
    def forgot_password():
        payload = request.get_json(silent=True) or {}
        email = (payload.get("email") or "").strip().lower()

        # Always return success-shaped response to avoid account enumeration.
        response_payload = {"message": "If the email exists, a reset link was sent."}
        if not email:
            return jsonify(response_payload), 200

        user, token = auth_service.generate_password_reset_token(email, settings.reset_token_expiry_minutes)
        if user is None or token is None:
            return jsonify(response_payload), 200

        reset_link = f"{settings.frontend_url}/login.html?reset_token={token}"
        if email_service.is_configured:
            try:
                email_service.send_password_reset_email(email, reset_link)
            except Exception:
                if settings.app_env != "production":
                    response_payload["reset_token_preview"] = token
                return jsonify(response_payload), 200
        elif settings.app_env != "production":
            response_payload["reset_token_preview"] = token

        return jsonify(response_payload), 200

    @auth_bp.post("/auth/reset-password")
    def reset_password():
        payload = request.get_json(silent=True) or {}
        token = (payload.get("token") or "").strip()
        new_password = payload.get("new_password") or ""

        if not token or not new_password:
            return jsonify({"error": "Token and new password are required."}), 400

        token_data = auth_service.verify_password_reset_token(token)
        if token_data is None:
            return jsonify({"error": "Invalid or expired reset token."}), 400

        ok, message = auth_service.update_user_password(token_data["user"]["id"], new_password)
        if not ok:
            return jsonify({"error": message}), 400

        auth_service.consume_password_reset_token(token_data["token_id"])
        return jsonify({"message": message}), 200

    @auth_bp.post("/auth/logout")
    def logout():
        session.clear()
        return jsonify({"message": "Logged out."}), 200

    @auth_bp.get("/auth/github/login")
    def github_login():
        if not settings.github_client_id or not settings.github_client_secret:
            return jsonify({"error": "GitHub OAuth is not configured."}), 503

        state = secrets.token_urlsafe(24)
        session["github_oauth_state"] = state

        redirect_uri = f"{settings.backend_url}/api/auth/github/callback"
        params = {
            "client_id": settings.github_client_id,
            "redirect_uri": redirect_uri,
            "scope": "read:user user:email",
            "state": state,
        }
        auth_url = f"https://github.com/login/oauth/authorize?{urlencode(params)}"
        return redirect(auth_url)

    @auth_bp.get("/auth/github/callback")
    def github_callback():
        if not settings.github_client_id or not settings.github_client_secret:
            return redirect(f"{frontend_login_url}?auth_error=github_not_configured")

        state = request.args.get("state", "")
        code = request.args.get("code", "")
        expected_state = session.pop("github_oauth_state", None)

        if not expected_state or state != expected_state:
            return redirect(f"{frontend_login_url}?auth_error=invalid_state")

        if not code:
            return redirect(f"{frontend_login_url}?auth_error=missing_code")

        token_response = requests.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
                "redirect_uri": f"{settings.backend_url}/api/auth/github/callback",
            },
            timeout=30,
        )

        token_json = token_response.json()
        access_token = token_json.get("access_token")
        if not access_token:
            return redirect(f"{frontend_login_url}?auth_error=token_exchange_failed")

        user_response = requests.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
            timeout=30,
        )
        github_user = user_response.json()

        github_id = str(github_user.get("id", "")).strip()
        github_login_name = str(github_user.get("login", "")).strip()
        email = github_user.get("email")

        if not github_id or not github_login_name:
            return redirect(f"{frontend_login_url}?auth_error=github_user_fetch_failed")

        user = auth_service.upsert_github_user(
            github_id=github_id,
            github_username=github_login_name,
            email=email,
        )
        session["user_pk"] = user["id"]
        session["user"] = {
            "id": user.get("id"),
            "user_id": user.get("user_id"),
            "email": user.get("email"),
            "role": user.get("role"),
        }

        return redirect(f"{frontend_login_url}?auth=github_success")

    return auth_bp
