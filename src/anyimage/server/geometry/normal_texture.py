"""Encode camera-space normals as a texture."""

from pathlib import Path


def resized_visibility(visibility, shape):
    import numpy as np
    from PIL import Image

    visibility = np.asarray(visibility, dtype=bool)
    if visibility.shape == tuple(shape):
        return visibility
    resized = Image.fromarray(visibility.astype(np.uint8) * 255, mode="L")
    resized = resized.resize(
        (int(shape[1]), int(shape[0])),
        Image.Resampling.NEAREST,
    )
    return np.asarray(resized, dtype=np.uint8) > 0


def write_camera_normal_texture(
    frame,
    visibility,
    origin,
    crop_size,
    source_size,
    output_path,
    normal_mode="TANGENT",
):
    """Encode MoGe camera-axis normals in Blender tangent or object space."""
    import numpy as np
    from PIL import Image

    if frame.normal is None:
        raise ValueError("Normal texture requires a normal field")
    normal = np.asarray(frame.normal, dtype=np.float32)
    visibility = np.asarray(visibility, dtype=bool)
    if not np.isfinite(normal).all():
        raise ValueError("Normal field contains non-finite values")
    if visibility.shape != normal.shape[:2]:
        visibility = resized_visibility(visibility, normal.shape[:2])
    normal_mode = str(normal_mode).upper()
    if normal_mode in {"TANGENT", "OBJECT"}:
        converted = normal * np.asarray((1.0, -1.0, -1.0), dtype=np.float32)
        empty_normal = (128, 128, 255)
    else:
        raise ValueError(f"Unsupported normal mode: {normal_mode}")
    encoded = np.clip(
        (converted + 1.0)
        * 127.5,
        0.0,
        255.0,
    ).astype(np.uint8)
    encoded[~visibility] = empty_normal
    crop_width, crop_height = (int(value) for value in crop_size)
    crop = Image.fromarray(encoded, mode="RGB")
    if crop.size != (crop_width, crop_height):
        crop = crop.resize(
            (crop_width, crop_height),
            Image.Resampling.BILINEAR,
        )
    source_width, source_height = (int(value) for value in source_size)
    full = Image.new("RGB", (source_width, source_height), empty_normal)
    full.paste(crop, tuple(int(value) for value in origin))
    output_path = Path(output_path)
    full.save(output_path)
    return output_path
