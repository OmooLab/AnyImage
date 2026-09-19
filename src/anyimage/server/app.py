"""AnyImage Job Server without Blender dependencies."""

from blendjob import JobServer

from .jobs.cutout import run as _generate_cutout_artifacts
from .jobs.depth_plane import run as _generate_depth_plane_geometry
from .jobs.panorama import run as _generate_panorama_geometry
from .jobs.remove_background import run as _remove_background
from .jobs.upscale import run as _upscale_image
from .model_manager import ModelManager

server = JobServer("AnyImage Job Server")


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
    return _remove_background(context, parameters)


@server.job("upscale-image")
def upscale_image(context, parameters):
    return _upscale_image(context, parameters)


@server.job("generate-depth-plane-geometry")
def generate_depth_plane_geometry(context, parameters):
    return _generate_depth_plane_geometry(context, parameters)


@server.job("generate-cutout-artifacts")
def generate_cutout_artifacts(context, parameters):
    return _generate_cutout_artifacts(context, parameters)


@server.job("generate-panorama-geometry")
def generate_panorama_geometry(context, parameters):
    return _generate_panorama_geometry(context, parameters)
