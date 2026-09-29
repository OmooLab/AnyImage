"""AnyImage Job Server without Blender dependencies."""

from .job_files import AnyImageJobServer

from .jobs.cutout import run as _generate_cutout_artifacts
from .jobs.depth_plane import run as _generate_depth_plane_geometry
from .jobs.panorama import run as _generate_panorama_geometry
from .jobs.remove_background import run as _remove_background
from .jobs.upscale import run as _upscale_image
from .model_manager import ModelManager
from .models.onnx_runtime import OnnxResourceError

server = AnyImageJobServer("AnyImage Job Server")


def _run_model_job(handler, context, parameters):
    try:
        return handler(context, parameters)
    except (OnnxResourceError, MemoryError) as error:
        context.resource("model_manager").clear()
        if isinstance(error, MemoryError):
            raise RuntimeError(
                "Model processing exceeded available system memory. "
                "Reduce Maximum AI Input Size or model resolution, then try again."
            ) from error
        raise


@server.resource("model_manager")
def create_model_manager(job_server):
    return ModelManager(job_server.storage_root / "models")


@server.job("download-model")
def download_model(context, parameters):
    manager = context.resource("model_manager")
    return manager.download(context, parameters["model"])


@server.job("download-required-models")
def download_required_models(context, parameters):
    manager = context.resource("model_manager")
    return manager.download_missing(context, parameters["models"])


@server.job("remove-background")
def remove_background(context, parameters):
    return _run_model_job(_remove_background, context, parameters)


@server.job("upscale-image")
def upscale_image(context, parameters):
    return _run_model_job(_upscale_image, context, parameters)


@server.job("generate-depth-plane-geometry")
def generate_depth_plane_geometry(context, parameters):
    return _run_model_job(_generate_depth_plane_geometry, context, parameters)


@server.job("generate-cutout-artifacts")
def generate_cutout_artifacts(context, parameters):
    return _run_model_job(_generate_cutout_artifacts, context, parameters)


@server.job("generate-panorama-geometry")
def generate_panorama_geometry(context, parameters):
    return _run_model_job(_generate_panorama_geometry, context, parameters)
