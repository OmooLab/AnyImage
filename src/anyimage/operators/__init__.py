from .remove_background import RemoveImageBackground, RunBackgroundRemoval
from .cutout_tool import CLASSES as CUTOUT_CLASSES
from .frame_tool import CLASSES as FRAME_CLASSES
from .mask_tool import EditImageAlpha
from .rectify_tool import CLASSES as RECTIFY_CLASSES
from .convert_to_plane import CLASSES as PLANE_CLASSES
from .ai_setup import (
    ClearModels,
    DownloadModel,
    DownloadRequiredModels,
    OpenAIEnvironmentSettings,
    SetupAIEnvironment,
)
from .upscale import UpscaleImage
from .convert_to_panorama import CLASSES as PANORAMA_CLASSES


CLASSES = (
    *PANORAMA_CLASSES,
    *PLANE_CLASSES,
    *CUTOUT_CLASSES,
    SetupAIEnvironment,
    OpenAIEnvironmentSettings,
    DownloadModel,
    DownloadRequiredModels,
    RunBackgroundRemoval,
    ClearModels,
    *FRAME_CLASSES,
    EditImageAlpha,
    *RECTIFY_CLASSES,
    RemoveImageBackground,
    UpscaleImage,
)
