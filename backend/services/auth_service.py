import sqlite3
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from werkzeug.security import check_password_hash, generate_password_hash


class AuthService:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT UNIQUE,
                    email TEXT UNIQUE,
                    password_hash TEXT,
                    github_id TEXT UNIQUE,
                    github_username TEXT,
                    role TEXT NOT NULL DEFAULT 'user',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token_hash TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    used INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
                """
            )

            user_columns = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
            if "role" not in user_columns:
                conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")

    def _row_to_user(self, row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None

        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "email": row["email"],
            "github_username": row["github_username"],
            "role": row["role"],
        }

    def bootstrap_admin(self, admin_email: str) -> None:
        normalized = (admin_email or "").strip().lower()
        if not normalized:
            return

        with self._connect() as conn:
            conn.execute("UPDATE users SET role = 'admin' WHERE lower(email) = ?", (normalized,))

    def get_user_by_pk(self, user_pk: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, user_id, email, github_username, role FROM users WHERE id = ?",
                (user_pk,),
            ).fetchone()
        return self._row_to_user(row)

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        normalized_email = (email or "").strip().lower()
        if not normalized_email:
            return None

        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, user_id, email, github_username, role FROM users WHERE lower(email) = ?",
                (normalized_email,),
            ).fetchone()
        return self._row_to_user(row)

    def register_local_user(self, user_id: str, email: str, password: str) -> tuple[bool, str]:
        normalized_user_id = user_id.strip().lower()
        normalized_email = email.strip().lower()

        if not normalized_user_id and not normalized_email:
            return False, "Provide either a user ID or email."

        if len(password) < 6:
            return False, "Password must be at least 6 characters."

        password_hash = generate_password_hash(password)

        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO users (user_id, email, password_hash) VALUES (?, ?, ?)",
                    (
                        normalized_user_id or None,
                        normalized_email or None,
                        password_hash,
                    ),
                )
        except sqlite3.IntegrityError:
            return False, "User ID or email already exists."

        return True, "Registration successful."

    def authenticate_local_user(self, login: str, password: str) -> dict[str, Any] | None:
        normalized_login = login.strip().lower()

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, user_id, email, github_username, role, password_hash
                FROM users
                WHERE user_id = ? OR email = ?
                """,
                (normalized_login, normalized_login),
            ).fetchone()

        if row is None or not row["password_hash"]:
            return None

        if not check_password_hash(row["password_hash"], password):
            return None

        return self._row_to_user(row)

    def upsert_github_user(self, github_id: str, github_username: str, email: str | None) -> dict[str, Any]:
        normalized_username = (github_username or "").strip().lower()
        normalized_email = (email or "").strip().lower() or None

        with self._connect() as conn:
            existing = conn.execute(
                "SELECT id, user_id, email, github_username, role FROM users WHERE github_id = ?",
                (github_id,),
            ).fetchone()

            if existing is not None:
                conn.execute(
                    "UPDATE users SET github_username = ?, email = COALESCE(email, ?) WHERE github_id = ?",
                    (normalized_username, normalized_email, github_id),
                )
                row = conn.execute(
                    "SELECT id, user_id, email, github_username, role FROM users WHERE github_id = ?",
                    (github_id,),
                ).fetchone()
                user = self._row_to_user(row)
                if user is None:
                    raise RuntimeError("Failed to refresh GitHub user row.")
                return user

            conn.execute(
                "INSERT INTO users (user_id, email, github_id, github_username) VALUES (?, ?, ?, ?)",
                (normalized_username or None, normalized_email, github_id, normalized_username),
            )
            row = conn.execute(
                "SELECT id, user_id, email, github_username, role FROM users WHERE github_id = ?",
                (github_id,),
            ).fetchone()

        user = self._row_to_user(row)
        if user is None:
            raise RuntimeError("Failed to create GitHub user.")
        return user

    def list_users(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, user_id, email, github_username, role, created_at
                FROM users
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            {
                "id": row["id"],
                "user_id": row["user_id"],
                "email": row["email"],
                "github_username": row["github_username"],
                "role": row["role"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def user_counts(self) -> dict[str, int]:
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
            local = conn.execute("SELECT COUNT(*) AS n FROM users WHERE password_hash IS NOT NULL").fetchone()["n"]
            github = conn.execute("SELECT COUNT(*) AS n FROM users WHERE github_id IS NOT NULL").fetchone()["n"]
            admins = conn.execute("SELECT COUNT(*) AS n FROM users WHERE role = 'admin'").fetchone()["n"]
        return {
            "total_users": int(total),
            "local_users": int(local),
            "github_users": int(github),
            "admin_users": int(admins),
        }

    def generate_password_reset_token(self, email: str, expiry_minutes: int) -> tuple[dict[str, Any] | None, str | None]:
        user = self.get_user_by_email(email)
        if user is None:
            return None, None

        raw_token = secrets.token_urlsafe(32)
        token_hash = generate_password_hash(raw_token)
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes)).isoformat()

        with self._connect() as conn:
            conn.execute("UPDATE password_reset_tokens SET used = 1 WHERE user_id = ? AND used = 0", (user["id"],))
            conn.execute(
                """
                INSERT INTO password_reset_tokens (user_id, token_hash, expires_at, used)
                VALUES (?, ?, ?, 0)
                """,
                (user["id"], token_hash, expires_at),
            )

        return user, raw_token

    def verify_password_reset_token(self, raw_token: str) -> dict[str, Any] | None:
        now = datetime.now(timezone.utc)

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT prt.id AS token_id, prt.token_hash, prt.expires_at, prt.used,
                       u.id, u.user_id, u.email, u.github_username, u.role
                FROM password_reset_tokens prt
                JOIN users u ON u.id = prt.user_id
                WHERE prt.used = 0
                ORDER BY prt.id DESC
                """
            ).fetchall()

        for row in rows:
            expires = datetime.fromisoformat(row["expires_at"])
            if expires < now:
                continue
            if check_password_hash(row["token_hash"], raw_token):
                return {
                    "token_id": row["token_id"],
                    "user": {
                        "id": row["id"],
                        "user_id": row["user_id"],
                        "email": row["email"],
                        "github_username": row["github_username"],
                        "role": row["role"],
                    },
                }

        return None

    def consume_password_reset_token(self, token_id: int) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE password_reset_tokens SET used = 1 WHERE id = ?", (token_id,))

    def update_user_password(self, user_pk: int, new_password: str) -> tuple[bool, str]:
        if len(new_password) < 6:
            return False, "Password must be at least 6 characters."

        password_hash = generate_password_hash(new_password)
        with self._connect() as conn:
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_pk))
        return True, "Password updated successfully."
