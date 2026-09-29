"""Preview and remove idle job artifacts within the server storage boundary."""

from pathlib import Path
import re
import shutil
import stat

from blendjob import JobServer


def is_redirect(path):
    """Detect symlinks and Windows junctions without following them."""
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def directory_bytes(directory):
    """Measure an ordinary directory, rejecting redirected descendants."""
    total = 0
    for path in directory.iterdir():
        if is_redirect(path):
            raise ValueError("Job directory contains a redirected path")
        total += directory_bytes(path) if path.is_dir() else path.stat().st_size
    return total


class AnyImageJobServer(JobServer):
    """Keep job file removal serialized with job submission."""

    def maintain_job_files(self, protected_paths, selected=None):
        with self.lock:
            if self.closed or self.active_job_id is not None or self._queued_job_count():
                raise RuntimeError("Job Server is busy or stopped")
            root = self.storage_root.resolve()
            directory = root / "jobs"
            result = {"jobs": [], "bytes": 0, "skipped": 0, "failed": []}
            if not directory.exists():
                return result
            if is_redirect(directory) or directory.resolve().parent != root:
                raise ValueError("Jobs directory must be a local storage subdirectory")
            protected = [Path(path).resolve() for path in protected_paths]
            for child in directory.iterdir():
                if not re.fullmatch(r"[0-9a-f]{32}", child.name):
                    continue
                if selected is not None and child.name not in selected:
                    continue
                try:
                    if is_redirect(child) or not child.is_dir() or child.resolve().parent != directory:
                        result["skipped"] += 1
                        continue
                    if any(path.is_relative_to(child) for path in protected):
                        result["skipped"] += 1
                        continue
                    size = directory_bytes(child)
                    if selected is not None:
                        shutil.rmtree(child)
                        self.jobs.pop(child.name, None)
                    result["jobs"].append(child.name)
                    result["bytes"] += size
                except ValueError:
                    result["skipped"] += 1
                except OSError as error:
                    result["failed"].append({"job": child.name, "error": str(error)})
            return result

    def create_app(self, instance_id, storage_root=None):
        from fastapi import HTTPException

        app = super().create_app(instance_id, storage_root)

        @app.post("/job-files/{action}")
        def job_files(action: str, payload: dict):
            protected = payload.get("protected_paths", [])
            selected = payload.get("jobs") if action == "clear" else None
            if (action not in {"preview", "clear"}
                    or not isinstance(protected, list) or not all(isinstance(p, str) and Path(p).is_absolute() for p in protected)
                    or (action == "clear" and (not isinstance(selected, list)
                        or not all(isinstance(p, str) and re.fullmatch(r"[0-9a-f]{32}", p) for p in selected)))):
                raise HTTPException(status_code=422, detail="Invalid job file request")
            try:
                return self.maintain_job_files(protected, None if selected is None else set(selected))
            except RuntimeError as error:
                raise HTTPException(status_code=409, detail=str(error))
            except (OSError, ValueError) as error:
                raise HTTPException(status_code=400, detail=str(error))

        return app
