"""Shared image preview layout and overlay drawing."""


def preview_draw_bounds(region_size, aspect_ratio):
    region_width, region_height = (float(value) for value in region_size)
    available_width = min(region_width * 0.65, 640.0)
    available_height = min(region_height * 0.65, 640.0)
    if aspect_ratio >= available_width / available_height:
        width = available_width
        height = width / aspect_ratio
    else:
        height = available_height
        width = height * aspect_ratio
    return (
        (region_width - width) * 0.5,
        (region_height - height) * 0.5,
        width,
        height,
    )


def draw_preview_frame(bounds):
    import gpu
    from gpu_extras.batch import batch_for_shader

    left, bottom, width, height = bounds
    vertices = (
        (left, bottom),
        (left + width, bottom),
        (left + width, bottom + height),
        (left, bottom + height),
        (left, bottom),
    )
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    batch = batch_for_shader(shader, "LINE_STRIP", {"pos": vertices})
    gpu.state.blend_set("ALPHA")
    gpu.state.line_width_set(2.0)
    shader.bind()
    shader.uniform_float("color", (0.12, 0.52, 1.0, 1.0))
    batch.draw(shader)
    gpu.state.line_width_set(1.0)
    gpu.state.blend_set("NONE")


def draw_centered_text(text, center_x, baseline_y, size, color):
    import blf

    font_id = 0
    blf.size(font_id, size)
    width, _height = blf.dimensions(font_id, text)
    x = center_x - width * 0.5
    blf.position(font_id, x + 1.0, baseline_y - 1.0, 0.0)
    blf.color(font_id, 0.0, 0.0, 0.0, 0.9)
    blf.draw(font_id, text)
    blf.position(font_id, x, baseline_y, 0.0)
    blf.color(font_id, *color)
    blf.draw(font_id, text)


def preview_texture_draw_options(blender_version):
    if tuple(blender_version) >= (5, 0, 0):
        return {"is_scene_linear_with_rec709_srgb_target": True}
    return {}
