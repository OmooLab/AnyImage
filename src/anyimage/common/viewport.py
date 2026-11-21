"""View3D projection, image tool context, and overlay drawing."""

import math

import bpy

from . import polygon as polygon_geometry
from .image import image_empty_bounds, is_image_empty
from .selection import ImageEditWarning

MIN_PATH_DISTANCE = 2.0


def redraw_area(context):
    area = getattr(context, "area", None)
    tag_redraw = getattr(area, "tag_redraw", None)
    if tag_redraw is not None:
        tag_redraw()


def image_edit_keymap(operator_id, *events):
    return (
        *((operator_id, {"type": "LEFTMOUSE", "value": value}, None) for value in events),
        ("view3d.select", {"type": "LEFTMOUSE", "value": "CLICK"},
         {"properties": [("deselect_all", True)]}),
        ("view3d.select", {"type": "LEFTMOUSE", "value": "CLICK", "shift": True},
         {"properties": [("toggle", True)]}),
    )


def simplify_screen_path(path):
    pixels = []
    for point in path:
        point = (float(point[0]), float(point[1]))
        if not pixels or math.dist(point, pixels[-1]) >= MIN_PATH_DISTANCE:
            pixels.append(point)
    return pixels


def screen_path_to_image_pixels(
    path,
    view_region,
    view3d,
    matrix_world,
    local_bounds,
    image_size,
    *,
    simplify=True,
):
    from bpy_extras import view3d_utils

    inverse = matrix_world.inverted()
    inverse_direction = inverse.to_3x3()
    x_min, x_max, y_min, y_max = local_bounds
    image_width, image_height = image_size
    local_width = x_max - x_min
    local_height = y_max - y_min
    pixels = []
    screen_points = simplify_screen_path(path) if simplify else path
    for point in screen_points:
        ray_origin = inverse @ view3d_utils.region_2d_to_origin_3d(
            view_region,
            view3d,
            point,
        )
        ray_direction = inverse_direction @ view3d_utils.region_2d_to_vector_3d(
            view_region,
            view3d,
            point,
        )
        if abs(ray_direction.z) <= 1e-10:
            raise ValueError("The Image Empty is edge-on to the current view")
        distance = -ray_origin.z / ray_direction.z
        local = ray_origin + ray_direction * distance
        pixels.append(
            (
                (local.x - x_min) * image_width / local_width,
                (y_max - local.y) * image_height / local_height,
            )
        )
    return pixels


def drawing_in_region(area_pointer, region_pointer):
    area = getattr(bpy.context, "area", None)
    region = getattr(bpy.context, "region", None)
    return (
        area is not None
        and region is not None
        and area.as_pointer() == area_pointer
        and region.as_pointer() == region_pointer
    )


def report_image_edit_exception(operator, error):
    level = "WARNING" if isinstance(error, ImageEditWarning) else "ERROR"
    operator.report({level}, str(error))


def image_edit_poll(context):
    return context.area is not None and context.area.type == "VIEW_3D"


def clicked_image_source(context, event):
    """Hit-test the selected image rectangle without changing object selection."""
    source = context.active_object
    if not is_image_empty(source) or source not in context.selected_objects:
        return None
    point = (event.mouse_region_x, event.mouse_region_y)
    try:
        (x, y), = screen_path_to_image_pixels(
            [point], context.region, context.region_data, source.matrix_world,
            image_empty_bounds(source), (1, 1),
        )
    except ValueError:
        return None
    return source if 0 <= x <= 1 and 0 <= y <= 1 else None


def active_image_edit_source(context):
    """Return the selected active Image Empty used by image edit tools."""
    source_object = context.active_object
    if (
        not is_image_empty(source_object)
        or source_object not in context.selected_objects
    ):
        raise ImageEditWarning(
            "Select an active Image Empty to use an Image tool"
        )
    return source_object


def active_view3d_tool_id(context):
    tools = getattr(getattr(context, "workspace", None), "tools", None)
    from_mode = getattr(tools, "from_space_view3d_mode", None)
    if not callable(from_mode):
        return None
    try:
        tool = from_mode(getattr(context, "mode", "OBJECT"), create=False)
    except (RuntimeError, TypeError):
        return None
    return getattr(tool, "idname", None)


def draw_dashed_line(
    vertices,
    color=(1.0, 1.0, 1.0, 0.9),
    segments=None,
):
    import gpu
    from gpu_extras.batch import batch_for_shader

    if segments is None:
        segments = polygon_geometry.dashed_line_segments(vertices)
    if not segments:
        return
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    batch = batch_for_shader(shader, "LINES", {"pos": segments})
    gpu.state.blend_set("ALPHA")
    gpu.state.line_width_set(1.0)
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)
    gpu.state.blend_set("NONE")


def draw_polygon_fill(
    vertices,
    triangles=None,
    color=(1.0, 1.0, 1.0, 0.16),
):
    import gpu
    from gpu_extras.batch import batch_for_shader

    if triangles is None:
        triangles = polygon_geometry.triangulated_polygon_vertices(vertices)
    if not triangles:
        return
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    batch = batch_for_shader(shader, "TRIS", {"pos": triangles})
    gpu.state.blend_set("ALPHA")
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)
    gpu.state.blend_set("NONE")


def rectangle_screen_path(start, end):
    x0, y0 = start
    x1, y1 = end
    if abs(x1 - x0) < 2.0 or abs(y1 - y0) < 2.0:
        return ()
    left, right = sorted((float(x0), float(x1)))
    bottom, top = sorted((float(y0), float(y1)))
    return ((left, top), (right, top), (right, bottom), (left, bottom))


def draw_polygon_outline(vertices, color):
    import gpu
    from gpu_extras.batch import batch_for_shader

    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    batch = batch_for_shader(
        shader,
        "LINE_STRIP",
        {"pos": (*vertices, vertices[0])},
    )
    gpu.state.blend_set("ALPHA")
    gpu.state.line_width_set(1.0)
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)
    gpu.state.blend_set("NONE")
