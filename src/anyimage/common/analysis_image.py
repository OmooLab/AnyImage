import numpy as np
from pathlib import Path
import bpy
from .image import image_rgba
from .color_image import load_material_color_image, _save_byte_color


def material_analysis_input(color_path):
    """Return the byte color file or an HDR recognition preview in the same directory."""

    path = Path(color_path)
    if path.suffix == ".png":
        return path
    image = load_material_color_image(path)
    try:
        rgba = image_rgba(image)
        if image.alpha_mode == "NONE":
            rgba[..., 3] = 1
        preview = recognition_rgba(
            rgba, associated=image.alpha_mode not in {"CHANNEL_PACKED", "NONE"}
        )
        output = path.parent / "analysis.png"
        _save_byte_color(preview, output, "sRGB")
        return output
    finally:
        bpy.data.images.remove(image)


def recognition_rgba(rgba, *, associated=True):
    """Tone-map scene-linear pixels for sRGB recognition without changing the source."""
    alpha = rgba[..., 3:4]
    rgb = rgba[..., :3].astype(np.float64)
    if associated:
        rgb = np.divide(rgb, alpha, out=np.zeros_like(rgb), where=alpha > 0)
    rgb = np.maximum(rgb, 0)
    luminance = rgb @ np.array([0.2126, 0.7152, 0.0722])
    rgb /= 1 + luminance[..., None]
    encoded = np.where(rgb <= 0.0031308, rgb * 12.92, 1.055 * rgb ** (1 / 2.4) - 0.055)
    preview = np.ones(rgba.shape, dtype=np.float32)
    preview[..., :3] = np.clip(encoded, 0, 1) * alpha
    return preview
