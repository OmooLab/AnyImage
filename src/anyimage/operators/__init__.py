from .remove_background import CLASSES as BACKGROUND_CLASSES
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
from .color_match import CLASSES as COLOR_MATCH_CLASSES
from .bake_mesh import CLASSES as MESH_CLASSES
from .job_files import ClearJobFiles


CLASSES = (
    *MESH_CLASSES,
    *COLOR_MATCH_CLASSES,
    *PANORAMA_CLASSES,
    *PLANE_CLASSES,
    *CUTOUT_CLASSES,
    SetupAIEnvironment,
    OpenAIEnvironmentSettings,
    DownloadModel,
    DownloadRequiredModels,
    ClearModels,
    ClearJobFiles,
    *FRAME_CLASSES,
    EditImageAlpha,
    *RECTIFY_CLASSES,
    *BACKGROUND_CLASSES,
    UpscaleImage,
)
