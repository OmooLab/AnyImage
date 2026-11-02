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


def write_normal_texture(frame, visibility, output_size, output_path, *, normal_space="TANGENT"):
    """Encode camera normals in flat tangent or image-object space."""
    import numpy as np
    from PIL import Image

    if frame.normal is None:
        raise ValueError("Normal texture requires a normal field")
    normal = np.asarray(frame.normal, dtype=np.float32)
    if not np.isfinite(normal).all():
        raise ValueError("Normal field contains non-finite values")
    visibility = resized_visibility(visibility, normal.shape[:2])
    if normal_space == "OBJECT":
        converted = normal[..., (0, 2, 1)] * np.asarray((1.0, 1.0, -1.0), dtype=np.float32)
        empty_normal = (128, 0, 128)
    elif normal_space == "TANGENT":
        converted = normal * np.asarray((1.0, -1.0, -1.0), dtype=np.float32)
        empty_normal = (128, 128, 255)
    else:
        raise ValueError(f"Unsupported normal space: {normal_space}")
    encoded = np.clip((converted + 1.0) * 127.5, 0.0, 255.0).astype(np.uint8)
    encoded[~visibility] = empty_normal
    image = Image.fromarray(encoded, mode="RGB")
    if image.size != output_size:
        image = image.resize(output_size, Image.Resampling.BILINEAR)
    output_path = Path(output_path)
    image.save(output_path)
    return output_path
