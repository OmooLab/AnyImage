"""Generate radial depth and object normal textures from an RGBA panorama."""

import json

from ..geometry.depth_texture import write_float_exr
from ..geometry.panorama import camera_bases, merge_distances, merge_normals, sample_panorama, view_rays
from ..geometry.panorama_relief import refine_panorama_normals
from ..media.input import open_image, validate_input_path
from ..media.resolution import DEFAULT_MAX_AI_INPUT_SIZE, normalized_max_input_size
from ..models import model_adapter


NORMAL_DETAIL_STRENGTH = 1.5


def run(context, parameters):
    import numpy as np
    from PIL import Image

    context.check_cancelled()
    input_path = validate_input_path(parameters["input"])
    maximum = normalized_max_input_size(parameters.get("max_input_size", DEFAULT_MAX_AI_INPUT_SIZE))
    if maximum < 2:
        raise ValueError("Panorama geometry requires a maximum AI input size of at least 2 pixels")
    context.directory.mkdir(parents=True, exist_ok=True)
    outputs = {
        "depth": context.directory / "depth.exr",
        "depth_metadata": context.directory / "depth.json",
        "object_normal": context.directory / "object-normal.png",
        "normal_coverage": context.directory / "normal-coverage.png",
    }
    try:
        with open_image(input_path) as opened:
            if opened.width != opened.height * 2:
                raise ValueError("Panorama conversion requires one static 2:1 image")
            with opened.convert("RGBA") as source:
                size = min(maximum, max(512, source.width // 4))
                height = min(source.width, maximum) // 2
                width = 2 * height
                image = np.asarray(source, dtype=np.float32) / 255.0
                source_alpha = source.getchannel("A")
                if width < source.width:
                    source_alpha = source_alpha.resize((width, height), Image.Resampling.BOX)
                alpha = np.asarray(source_alpha, dtype=np.float32) / 255.0
        manager = context.resource("model_manager")
        bases = camera_bases()
        rays = view_rays(size)
        distances, masks, normals = [], [], []
        adapter = model_adapter(parameters["model"])
        session = None
        for index, basis in enumerate(bases):
            context.check_cancelled()
            context.progress(
                0.05 + 0.65 * index / len(bases),
                "Generating panorama view {index}/{total}",
                index=index + 1, total=len(bases),
            )
            directions = rays @ basis
            view_alpha = sample_panorama(image[..., 3], directions, order=0)
            visible = view_alpha > 0
            if not visible.any():
                distances.append(np.ones((size, size), dtype=np.float32))
                masks.append(visible)
                normals.append(np.zeros((size, size, 3), dtype=np.float32))
                continue
            if session is None:
                session, _load_ms = manager.get_session(parameters["model"], parameters["device"])
            color = sample_panorama(image[..., :3], directions) * view_alpha[..., None]
            prediction = adapter.infer(session, color, parameters["resolution_level"],
                                       fov_x=90.0, source_valid=visible)
            distances.append(np.linalg.norm(prediction["points"], axis=-1))
            masks.append((prediction["mask"] > 0.5) & visible)
            normals.append(prediction["normal"])
            del prediction
        del image, rays, directions
        context.progress(0.75, "Merging panorama depth maps")
        distance, valid = merge_distances(distances, masks, bases, width, height,
                                         cancel_check=context.check_cancelled)
        alpha *= valid
        valid_depth = (alpha >= 0.9) & np.isfinite(distance) & (distance > 0)
        if not valid_depth.any():
            raise ValueError("The panorama contains no valid depth pixels")
        if not np.isfinite(distance).all() or (distance <= 0).any():
            raise ValueError("Panorama fusion produced invalid distances")
        rgba = np.empty((height, width, 4), dtype=np.float32)
        rgba[..., :3], rgba[..., 3] = distance[..., None], alpha
        write_float_exr(rgba, outputs["depth"])
        del rgba, distances
        context.progress(0.9, "Generating surface normal")
        normal = merge_normals(normals, masks, bases, width, height,
                               coverage=valid_depth, cancel_check=context.check_cancelled)
        del normals, masks
        normal, coverage = refine_panorama_normals(distance, normal, valid_depth,
                                                    detail_strength=NORMAL_DETAIL_STRENGTH,
                                                    cancel_check=context.check_cancelled)
        encoded = np.clip(np.rint((normal + 1) * 127.5), 0, 255).astype(np.uint8)
        Image.fromarray(encoded).save(outputs["object_normal"])
        Image.fromarray(np.rint(coverage * 255).astype(np.uint8)).save(outputs["normal_coverage"])
        outputs["depth_metadata"].write_text(json.dumps({
            "projection": "equirectangular", "image_size": [width, height],
        }, separators=(",", ":")), encoding="utf-8")
        context.check_cancelled()
        context.progress(1.0, "Panorama conversion data is ready")
        return {key: path.name for key, path in outputs.items()}
    except BaseException:
        for path in outputs.values():
            path.unlink(missing_ok=True)
        raise
