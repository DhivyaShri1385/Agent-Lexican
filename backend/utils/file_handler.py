import json
import threading
from pathlib import Path
from typing import Any

from .helpers import slugify_prompt, utc_timestamp

_history_lock = threading.Lock()


def ensure_output_files(output_dir: Path, history_file: Path) -> None:
	output_dir.mkdir(parents=True, exist_ok=True)

	if not history_file.exists():
		history_file.parent.mkdir(parents=True, exist_ok=True)
		history_file.write_text("[]", encoding="utf-8")


def build_output_path(output_dir: Path, prompt: str) -> Path:
	timestamp = utc_timestamp().replace(":", "-")
	filename = f"{timestamp}-{slugify_prompt(prompt)}.png"
	return output_dir / filename


def read_history(history_file: Path, limit: int = 30) -> list[dict[str, Any]]:
	if not history_file.exists():
		return []

	raw = history_file.read_text(encoding="utf-8").strip()
	if not raw:
		return []

	try:
		records = json.loads(raw)
		if not isinstance(records, list):
			return []
		return records[-limit:][::-1]
	except json.JSONDecodeError:
		return []


def append_history(history_file: Path, record: dict[str, Any], max_items: int = 300) -> None:
	with _history_lock:
		records = []
		if history_file.exists():
			try:
				content = history_file.read_text(encoding="utf-8").strip()
				records = json.loads(content) if content else []
				if not isinstance(records, list):
					records = []
			except json.JSONDecodeError:
				records = []

		records.append(record)
		records = records[-max_items:]
		history_file.write_text(json.dumps(records, indent=2), encoding="utf-8")
