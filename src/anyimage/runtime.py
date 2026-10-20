from pathlib import Path

from blendjob import JobRuntime
from .preferences import storage_root
from .server.model_catalog import DEFAULT_MODEL_KEYS


ENVIRONMENT = {
    "python": "3.12",
    "packages": [
        "numpy==2.4.2",
        "scipy==1.17.1",
        "pillow==12.1.1",

        "trimesh==4.11.2",
    ],
    "platform_packages": {
        "windows": ["onnxruntime-directml==1.24.4"],
        "default": ["onnxruntime==1.24.4"],
    },
}


def prepare_models(setup):
    setup.request(
        "download-required-models", {"models": list(DEFAULT_MODEL_KEYS), "online": setup.online},
    )


runtime = JobRuntime(
    "server:server",
    entrypoint_root=Path(__file__).parent,
    storage_root=storage_root,
    environment=ENVIRONMENT,
    post_setup=prepare_models,
    namespace="anyimage",
)

JobOperatorBase = runtime.JobOperatorBase
