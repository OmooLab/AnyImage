"""AnyImage Job Server without Blender dependencies."""

from blendjob import JobServer

server = JobServer("AnyImage Job Server")


def _run_model_job(handler, context, parameters):
    from .models.onnx_runtime import OnnxResourceError

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
    from .model_manager import ModelManager

    return ModelManager(job_server.storage_root / "models")


@server.job("download_model")
def download_model(context, parameters):
    manager = context.resource("model_manager")
    return manager.download(context, parameters["model"])


@server.job("download_required_models")
def download_required_models(context, parameters):
    manager = context.resource("model_manager")
    return manager.download_missing(context, parameters["models"], online=parameters.get("online", True))


@server.job("remove_background")
def remove_background(context, parameters):
    from .jobs.remove_background import run

    return _run_model_job(run, context, parameters)


@server.job("upscale_image")
def upscale_image(context, parameters):
    from .jobs.upscale import run

    return _run_model_job(run, context, parameters)


@server.job("generate_depth_plane_geometry")
def generate_depth_plane_geometry(context, parameters):
    from .jobs.depth_plane import run

    return _run_model_job(run, context, parameters)


@server.job("generate_cutout_artifacts")
def generate_cutout_artifacts(context, parameters):
    from .jobs.cutout import run

    return _run_model_job(run, context, parameters)


@server.job("generate_panorama_geometry")
def generate_panorama_geometry(context, parameters):
    from .jobs.panorama import run

    return _run_model_job(run, context, parameters)
