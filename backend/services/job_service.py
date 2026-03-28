import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable


class JobService:
    def __init__(self, max_jobs: int = 500):
        self.max_jobs = max_jobs
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _prune_if_needed(self) -> None:
        if len(self._jobs) <= self.max_jobs:
            return

        ordered = sorted(self._jobs.items(), key=lambda item: item[1].get("created_at", ""))
        overflow = max(0, len(ordered) - self.max_jobs)
        for idx in range(overflow):
            self._jobs.pop(ordered[idx][0], None)

    def create_job(self, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        job_id = str(uuid.uuid4())
        record = {
            "job_id": job_id,
            "status": "queued",
            "progress": 0,
            "message": "Queued",
            "result": None,
            "error": None,
            "metadata": metadata or {},
            "created_at": self._now(),
            "updated_at": self._now(),
        }

        with self._lock:
            self._jobs[job_id] = record
            self._prune_if_needed()

        return record.copy()

    def update_job(
        self,
        job_id: str,
        *,
        status: str | None = None,
        progress: int | None = None,
        message: str | None = None,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> dict[str, Any] | None:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return None

            if status is not None:
                record["status"] = status
            if progress is not None:
                record["progress"] = max(0, min(100, int(progress)))
            if message is not None:
                record["message"] = message
            if result is not None:
                record["result"] = result
            if error is not None:
                record["error"] = error
            record["updated_at"] = self._now()
            return record.copy()

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return None
            return record.copy()

    def run_async(self, job_id: str, task: Callable[[], dict[str, Any]]) -> None:
        def _target() -> None:
            self.update_job(job_id, status="running", progress=5, message="Preparing model")
            try:
                time.sleep(0.1)
                self.update_job(job_id, status="running", progress=20, message="Loading pipeline")
                result = task()
                self.update_job(
                    job_id,
                    status="completed",
                    progress=100,
                    message="Generation complete",
                    result=result,
                )
            except Exception as exc:
                self.update_job(
                    job_id,
                    status="failed",
                    progress=100,
                    message="Generation failed",
                    error=str(exc),
                )

        thread = threading.Thread(target=_target, daemon=True)
        thread.start()
