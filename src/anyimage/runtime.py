from pathlib import Path

from blendjob import JobRuntime

from .preferences import configured_storage_root
from .server.model_catalog import DEFAULT_MODEL_KEYS


ENVIRONMENT = {
    "python": "3.12",
    "packages": [
        "numpy==2.4.2",
        "scipy==1.15.3",
        "pillow==12.1.1",

        "trimesh==4.11.2",
    ],
    "platform_packages": {
        "windows": ["onnxruntime-directml==1.24.4"],
        "default": ["onnxruntime==1.24.4"],
    },
}


def post_install(job_runtime):
    job_runtime.request(
        "download-required-models", {"models": list(DEFAULT_MODEL_KEYS)},
    )


runtime = JobRuntime(
    "server:server",
    entrypoint_root=Path(__file__).parent,
    storage_root=configured_storage_root,
    environment=ENVIRONMENT,
    post_install=post_install,
    namespace="anyimage",
)

JobOperatorBase = runtime.JobOperatorBase
