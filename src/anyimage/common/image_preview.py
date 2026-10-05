"""Shared image preview layout and overlay drawing."""

from functools import lru_cache

import numpy as np

from .color_space import linear_rgb_to_srgb


def create_preview_texture(linear_rgba):
    """Upload top-down straight linear Rec.709 RGBA for fixed sRGB display."""
    import gpu

    rgba = np.asarray(linear_rgba, dtype=np.float32).copy()
    rgba[..., :3] = np.clip(linear_rgb_to_srgb(rgba[..., :3]), 0.0, 1.0)
    height, width = rgba.shape[:2]
    pixels = np.ascontiguousarray(np.flipud(rgba)).ravel()
    return gpu.types.GPUTexture(
        (width, height), format="RGBA32F",
        data=gpu.types.Buffer("FLOAT", pixels.size, pixels),
    )


@lru_cache(maxsize=1)
def _preview_shader():
    """Convert encoded display colors to the active framebuffer's space."""
    import gpu

    interface = gpu.types.GPUStageInterfaceInfo("anyimage_preview")
    interface.smooth("VEC2", "uv")
    info = gpu.types.GPUShaderCreateInfo()
    info.push_constant("MAT4", "ModelViewProjectionMatrix")
    # Blender sets this built-in uniform when binding the active framebuffer.
    info.push_constant("BOOL", "srgbTarget")
    info.vertex_in(0, "VEC2", "pos")
    info.vertex_in(1, "VEC2", "texCoord")
    info.vertex_out(interface)
    info.sampler(0, "FLOAT_2D", "image")
    info.fragment_out(0, "VEC4", "fragColor")
    info.vertex_source("""
        void main() {
            uv = texCoord;
            gl_Position = ModelViewProjectionMatrix * vec4(pos, 0.0, 1.0);
        }
    """)
    info.fragment_source("""
        void main() {
            fragColor = texture(image, uv);
            if (srgbTarget) {
                vec3 rgb = max(fragColor.rgb, vec3(0.0));
                fragColor.rgb = mix(rgb / 12.92,
                    pow((rgb + 0.055) / 1.055, vec3(2.4)),
                    step(vec3(0.04045), rgb));
            }
        }
    """)
    return gpu.shader.create_from_info(info)


def draw_preview_texture(texture, bounds):
    """Draw fixed sRGB colors while accounting for framebuffer encoding."""
    import gpu
    from gpu_extras.batch import batch_for_shader

    left, bottom, width, height = bounds
    shader = _preview_shader()
    batch = batch_for_shader(shader, "TRI_FAN", {
        "pos": ((left, bottom), (left + width, bottom),
                (left + width, bottom + height), (left, bottom + height)),
        "texCoord": ((0, 0), (1, 0), (1, 1), (0, 1)),
    })
    shader.bind()
    shader.uniform_float(
        "ModelViewProjectionMatrix",
        gpu.matrix.get_projection_matrix() @ gpu.matrix.get_model_view_matrix(),
    )
    shader.uniform_sampler("image", texture)
    gpu.state.blend_set("ALPHA")
    try:
        batch.draw(shader)
    finally:
        gpu.state.blend_set("NONE")


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
