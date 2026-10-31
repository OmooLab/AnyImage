import bpy
from blendjob import JobRuntime
from .ai_preferences import storage_root


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


def prepare_models(runtime):
    from .server.model_catalog import DEFAULT_MODEL_KEYS

    runtime.submit("download_required_models", {
        "models": list(DEFAULT_MODEL_KEYS), "online": bpy.app.online_access,
    })


runtime = JobRuntime(
    "anyimage",
    storage_root=storage_root,
    environment=ENVIRONMENT,
    post_setup=prepare_models,
)


JobOperator = runtime.JobOperator
