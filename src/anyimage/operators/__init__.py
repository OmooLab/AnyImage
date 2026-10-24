from .cutout_tool import CLASSES as CUTOUT_CLASSES
from .frame_tool import CLASSES as FRAME_CLASSES
from .mask_tool import EditImageAlpha
from .rectify_tool import CLASSES as RECTIFY_CLASSES
from .convert_to_plane import CLASSES as PLANE_CLASSES
from .color_match import CLASSES as COLOR_MATCH_CLASSES
from .bake_mesh import CLASSES as MESH_CLASSES


CLASSES = (
    *MESH_CLASSES,
    *COLOR_MATCH_CLASSES,
    *PLANE_CLASSES,
    *CUTOUT_CLASSES,
    *FRAME_CLASSES,
    EditImageAlpha,
    *RECTIFY_CLASSES,
)
