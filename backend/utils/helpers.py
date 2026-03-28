import re
from datetime import datetime, timezone


def utc_timestamp() -> str:
	return datetime.now(timezone.utc).isoformat()


def slugify_prompt(prompt: str, max_len: int = 40) -> str:
	text = prompt.strip().lower()
	text = re.sub(r"[^a-z0-9\s-]", "", text)
	text = re.sub(r"\s+", "-", text).strip("-")
	if not text:
		text = "generated-image"
	return text[:max_len]


def validate_prompt(prompt: str) -> tuple[bool, str]:
	if not isinstance(prompt, str):
		return False, "Prompt must be a text string."

	normalized = prompt.strip()
	if not normalized:
		return False, "Prompt cannot be empty."

	if len(normalized) < 5:
		return False, "Prompt is too short. Use at least 5 characters."

	if len(normalized) > 300:
		return False, "Prompt is too long. Keep it under 300 characters."

	return True, ""
