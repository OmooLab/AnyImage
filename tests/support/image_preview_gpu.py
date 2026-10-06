"""Verify the preview shader in a foreground Blender GPU context."""

import importlib
import json
from pathlib import Path
import sys
from types import ModuleType


def verify_preview_gpu(preview):
    import gpu
    import numpy as np
    from mathutils import Matrix

    colors = np.asarray([
        [[.18, .18, .18, 1], [1, 0, 0, .5]],
        [[0, 1, 0, 1], [0, 0, 1, .25]],
    ], dtype=np.float32)
    source = preview.create_preview_texture(colors)
    color_space = importlib.import_module(f"{preview.__package__}.color_space")
    results = []
    for format_name in ("RGBA8", "SRGB8_A8"):
        target = gpu.types.GPUTexture((2, 2), format=format_name)
        framebuffer = gpu.types.GPUFrameBuffer(color_slots=target)
        background = np.full(3, .2, dtype=np.float32)
        linear_background = color_space.srgb_to_linear_rgb(background)
        with framebuffer.bind(), gpu.matrix.push_pop(), gpu.matrix.push_pop_projection():
            gpu.state.viewport_set(0, 0, 2, 2)
            gpu.matrix.load_matrix(Matrix.Identity(4))
            gpu.matrix.load_projection_matrix(Matrix.Identity(4))
            clear = linear_background if format_name == "SRGB8_A8" else background
            framebuffer.clear(color=(*clear, 1))
            preview.draw_preview_texture(source, (-1, -1, 2, 2))
            buffer = framebuffer.read_color(0, 0, 2, 2, 4, 0, "FLOAT")
            buffer.dimensions = 16
            actual = np.flipud(np.array(buffer).reshape((2, 2, 4)))
        alpha = colors[..., 3:4]
        if format_name == "SRGB8_A8":
            expected = preview.linear_rgb_to_srgb(colors[..., :3] * alpha + linear_background * (1 - alpha))
        else:
            expected = preview.linear_rgb_to_srgb(colors[..., :3]) * alpha + background * (1 - alpha)
        np.testing.assert_allclose(actual[..., :3], expected, atol=2 / 255)
        results.append({"format": format_name, "maximum_error": float(np.max(abs(actual[..., :3] - expected)))})
    preview._preview_shader.cache_clear()
    return results


if __name__ == "__main__":
    import bpy
    import traceback

    output = Path(sys.argv[sys.argv.index("--") + 1])
    package = ModuleType("preview_gpu_validation")
    package.__path__ = [str(Path(__file__).resolve().parents[2] / "src/anyimage/common")]
    sys.modules[package.__name__] = package

    def run():
        try:
            preview = importlib.import_module("preview_gpu_validation.image_preview")
            result = {"version": bpy.app.version_string, "passed": True, "checks": verify_preview_gpu(preview)}
        except Exception:
            result = {"version": bpy.app.version_string, "passed": False, "error": traceback.format_exc()}
        output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        bpy.ops.wm.quit_blender()

    bpy.app.timers.register(run, first_interval=1.0)
