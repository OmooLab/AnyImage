"""Keep cleanup bounded, reference-aware and serialized with active jobs."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from server.job_files import AnyImageJobServer


@pytest.fixture
def server(tmp_path):
    instance = AnyImageJobServer("Test", storage_root=tmp_path)
    yield instance
    instance.close()


def create_job(server, name="a" * 32):
    directory = server.storage_root / "jobs" / name
    directory.mkdir(parents=True)
    (directory / "depth.exr").write_bytes(b"depth")
    server.jobs[name] = SimpleNamespace(_snapshot=lambda: {"state": "succeeded"})
    return directory


def test_preview_clear_and_history_preserve_resources(server):
    job = create_job(server)
    model = server.storage_root / "model.onnx"
    model.write_bytes(b"model")
    log = server.storage_root / "server.log"
    log.write_text("log")
    resource = Mock()
    server.resources["model_manager"] = resource
    preview = server.maintain_job_files([])
    assert preview["jobs"] == [job.name] and preview["bytes"] == 5
    assert job.exists() and job.name in server.jobs
    result = server.maintain_job_files([], set(preview["jobs"]))
    assert result["jobs"] == [job.name] and not job.exists()
    assert job.name not in server.jobs
    assert model.read_bytes() == b"model" and log.read_text() == "log"
    resource.clear.assert_not_called()


@pytest.mark.parametrize("state", ["active", "queued"])
def test_busy_server_refuses_preview_and_clear(server, state):
    job = create_job(server)
    if state == "active":
        server.active_job_id = job.name
    else:
        server.jobs[job.name] = SimpleNamespace(_snapshot=lambda: {"state": "queued"})
    for selected in (None, {job.name}):
        with pytest.raises(RuntimeError, match="busy"):
            server.maintain_job_files([], selected)
    assert job.exists()


def test_new_jobs_and_new_references_are_rechecked(server):
    job = create_job(server)
    selected = set(server.maintain_job_files([])["jobs"])
    new = create_job(server, "b" * 32)
    result = server.maintain_job_files([str(job / "depth.exr")], selected)
    assert result["skipped"] == 1 and not result["jobs"]
    assert job.exists() and new.exists()
    server.maintain_job_files([], selected)
    assert new.exists()


def test_failed_delete_keeps_history_and_reports_partial_progress(server, monkeypatch):
    from server import job_files

    job = create_job(server)
    monkeypatch.setattr(job_files.shutil, "rmtree", Mock(side_effect=PermissionError("locked")))
    result = server.maintain_job_files([], {job.name})
    assert result["failed"][0]["job"] == job.name
    assert job.name in server.jobs and job.exists()


@pytest.mark.parametrize("location", ["root", "job", "nested"])
def test_redirected_paths_are_never_deleted(server, monkeypatch, location):
    from server import job_files

    job = create_job(server)
    redirected = {"root": job.parent, "job": job, "nested": job / "depth.exr"}[location]
    monkeypatch.setattr(job_files, "is_redirect", lambda path: path == redirected)
    if location == "root":
        with pytest.raises(ValueError, match="local storage"):
            server.maintain_job_files([], {job.name})
    else:
        assert server.maintain_job_files([], {job.name})["skipped"] == 1
    assert (job / "depth.exr").read_bytes() == b"depth"


def test_only_uuid_job_directories_are_candidates(server):
    root = server.storage_root / "jobs"
    (root / "user-files").mkdir(parents=True)
    (root / ("a" * 32)).write_text("not a directory")
    assert server.maintain_job_files([])["jobs"] == []
    assert (root / "user-files").exists()


def test_http_route_validates_requests_and_busy_state(server, monkeypatch):
    import sys
    from blendjob import JobServer

    class HTTPException(Exception):
        def __init__(self, status_code, detail):
            super().__init__(detail)
            self.status_code = status_code

    routes = {}

    def post(path):
        def register(endpoint):
            routes[path] = endpoint
            return endpoint
        return register

    monkeypatch.setitem(sys.modules, "fastapi", SimpleNamespace(HTTPException=HTTPException))
    monkeypatch.setattr(JobServer, "create_app", lambda *args: SimpleNamespace(post=post))

    server.create_app("test")
    route = routes["/job-files/{action}"]
    for action, payload in (("clear", {}), ("clear", {"jobs": ["../models"]}),
                            ("preview", {"protected_paths": ["relative"]}), ("unknown", {})):
        with pytest.raises(HTTPException) as caught:
            route(action, payload)
        assert caught.value.status_code == 422
    job = create_job(server)
    assert route("preview", {})["jobs"] == [job.name]
    server.active_job_id = job.name
    with pytest.raises(HTTPException) as caught:
        route("clear", {"jobs": [job.name]})
    assert caught.value.status_code == 409
