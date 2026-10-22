"""Generate radial depth and object normal textures from the current RGBA panorama."""

import json

from ..geometry.depth_texture import write_float_exr
from ..geometry.panorama import camera_bases, merge_distances, merge_normals, sample_panorama, view_rays
from ..media.input import open_image, validate_input_path
from ..media.resolution import DEFAULT_MAX_AI_INPUT_SIZE, normalized_max_input_size
from ..models import model_adapter


def run(context, parameters):
    import numpy as np
    from PIL import Image

    context.check_cancelled()
    input_path = validate_input_path(parameters["input"])
    maximum = normalized_max_input_size(parameters.get("max_input_size", DEFAULT_MAX_AI_INPUT_SIZE))
    context.directory.mkdir(parents=True, exist_ok=True)
    outputs = [context.directory / name for name in ("depth.exr", "depth.json", "object-normal.png")]
    try:
        with open_image(input_path) as opened:
            if opened.width != opened.height * 2:
                raise ValueError("Panorama conversion requires one static 2:1 image")
            source = opened.convert("RGBA")
        width, height = source.size
        size = min(maximum, max(512, width // 4))
        image = np.asarray(source, dtype=np.float32) / 255.0
        manager = context.resource("model_manager")
        bases = camera_bases()
        rays = view_rays(size)
        distances, masks, normals = [], [], []
        adapter = model_adapter(parameters["model"])
        session = None
        for index, basis in enumerate(bases):
            context.check_cancelled()
            context.progress(0.05 + 0.65 * index / len(bases), f"Generating panorama view {index + 1}/12")
            directions = rays @ basis
            alpha = sample_panorama(image[..., 3], directions, order=0)
            visible = alpha > 0
            if not visible.any():
                distances.append(np.ones((size, size), dtype=np.float32))
                normals.append(np.zeros((size, size, 3), dtype=np.float32))
                masks.append(visible)
                continue
            if session is None:
                session, _load_ms = manager.get_session(parameters["model"], parameters["device"])
            color = sample_panorama(image[..., :3], directions) * alpha[..., None]
            prediction = adapter.infer(session, color, parameters["resolution_level"],
                               fov_x=90.0, source_valid=visible)
            distances.append(np.linalg.norm(prediction["points"], axis=-1))
            masks.append((prediction["mask"] > 0.5) & visible)
            normals.append(prediction["normal"])
            del prediction
        context.progress(0.75, "Merging panoramic distance")
        distance, valid = merge_distances(distances, masks, bases, width, height,
                                         cancel_check=context.check_cancelled)
        alpha = np.asarray(source.getchannel("A"),
                           dtype=np.float32) / 255.0
        alpha *= valid
        valid_depth = (alpha >= 0.9) & np.isfinite(distance) & (distance > 0)
        if not valid_depth.any():
            raise ValueError("The panorama contains no valid depth pixels")
        if not np.isfinite(distance).all() or (distance <= 0).any():
            raise ValueError("Panorama fusion produced invalid distances")
        rgba = np.empty((height, width, 4), dtype=np.float32)
        rgba[..., :3], rgba[..., 3] = distance[..., None], alpha
        write_float_exr(rgba, outputs[0])
        outputs[1].write_text(json.dumps({
            "projection": "equirectangular", "image_size": [width, height],
        }, separators=(",", ":")), encoding="utf-8")
        context.progress(0.9, "Merging panoramic normals")
        normal = merge_normals(normals, masks, bases, width, height,
                               cancel_check=context.check_cancelled)
        # Panorama geometry mirrors projection X. O Image Layer rotates +90 degrees
        # around X, so encode its inverse: (x, y, z) -> (-x, z, -y).
        normal = normal[..., [0, 2, 1]] * np.array((-1, 1, -1), dtype=np.float32)
        encoded = np.round(np.clip(normal * 0.5 + 0.5, 0, 1) * 255).astype(np.uint8)
        Image.fromarray(encoded).save(outputs[2])
        context.check_cancelled()
        context.progress(1.0, "Panorama conversion data is ready")
        return {"depth": outputs[0].name, "depth_metadata": outputs[1].name,
                "object_normal": outputs[2].name}
    except BaseException:
        for path in outputs:
            path.unlink(missing_ok=True)
        raise
