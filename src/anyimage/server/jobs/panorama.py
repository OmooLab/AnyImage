"""Generate radial depth and object normal textures from an RGBA panorama."""

from ..media.exr import write_float_exr
from ..media.input import load_ai_input
from ..geometry.panorama import (
    camera_bases, merge_distances, merge_normals, pad_panorama_seam,
    panorama_sample_coordinates, sample_panorama, view_rays,
)
from ..geometry.panorama_relief import refine_panorama_normals
from ..models import model_adapter


NORMAL_DETAIL_STRENGTH = 1.5


def run(context, parameters):
    import numpy as np
    from PIL import Image

    context.check_cancelled()
    context.directory.mkdir(parents=True, exist_ok=True)
    outputs = {
        "depth": context.directory / "depth.exr",
        "object_normal": context.directory / "object-normal.png",
    }
    try:
        source = load_ai_input(parameters["input"])
        source_shape = source.shape[:2]
        height, width = source_shape
        if width != height * 2:
            raise ValueError("Panorama conversion requires one static 2:1 image")
        size = min(width, max(512, width // 4))
        padded = pad_panorama_seam(source)
        alpha = source[..., 3].copy()
        del source
        manager = context.resource("model_manager")
        bases = camera_bases()
        rays = view_rays(size)
        distances, masks, normals = [], [], []
        adapter = model_adapter(parameters["model"])
        refinement_options = {"refine_steps": parameters["refine_steps"]} if "refine_steps" in parameters else {}
        session = None
        for index, basis in enumerate(bases):
            context.check_cancelled()
            context.progress(
                0.05 + 0.65 * index / len(bases),
                "Generating panorama view {index}/{total}",
                index=index + 1, total=len(bases),
            )
            coords = panorama_sample_coordinates(rays @ basis, source_shape)
            view_alpha = sample_panorama(padded[..., 3], coords, order=0)
            visible = view_alpha > 0
            if not visible.any():
                distances.append(np.ones((size, size), dtype=np.float32))
                masks.append(visible)
                normals.append(np.zeros((size, size, 3), dtype=np.float32))
                continue
            if session is None:
                session, _load_ms = manager.get_session(parameters["model"], parameters["device"])
            color = sample_panorama(padded[..., :3], coords)
            color[~visible] = 0
            prediction = adapter.infer(session, color, parameters["resolution_level"],
                                       fov_x=90.0, source_valid=visible,
                                       **refinement_options)
            distances.append(np.linalg.norm(prediction["points"], axis=-1))
            masks.append((prediction["mask"] > 0.5) & visible)
            normals.append(prediction["normal"])
            del prediction
        del padded, rays, coords
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
        encoded = np.empty((height, width, 4), dtype=np.uint8)
        encoded[..., :3] = np.clip(np.rint((normal + 1) * 127.5), 0, 255)
        encoded[..., 3] = np.rint(coverage * 255)
        Image.fromarray(encoded).save(outputs["object_normal"])
        context.check_cancelled()
        context.progress(1.0, "Panorama conversion data is ready")
        return {key: path.name for key, path in outputs.items()}
    except BaseException:
        for path in outputs.values():
            path.unlink(missing_ok=True)
        raise
