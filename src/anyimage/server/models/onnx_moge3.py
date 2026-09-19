"""MoGe-3 ONNX backbone and sparse refinement inference."""

from dataclasses import dataclass
from itertools import product
from pathlib import Path

from .onnx_moge2 import MAX_TOKENS, MIN_TOKENS, postprocess
from .onnx_runtime import create_session as create_runtime_session
from .onnx_runtime import run_session


@dataclass
class Moge3Session:
    backbone: object
    refiner: object


def create_session(model_directory, requested_device="auto"):
    directory = Path(model_directory)
    backbone = create_runtime_session(directory / "backbone.onnx", requested_device)
    refiner = create_runtime_session(directory / "refiner.onnx", requested_device)
    return Moge3Session(backbone, refiner)


def build_sparse_inputs(coord):
    """Build dynamic convolution, pooling and upsampling indices for five levels."""
    import numpy as np

    height, width = coord.shape[1:3]
    z = np.rint(coord[0, ..., 2] * 256).astype(np.int64)
    z -= z.min()
    y, x = np.indices((height, width))
    coords = np.stack((y, x, z), axis=-1).reshape(-1, 3)
    neighbors, pools, parents = [], [], []
    for level in range(5):
        maximum = coords.max(axis=0)
        dimensions = maximum + 3

        def keys(values):
            return (
                ((values[:, 0] + 1) * dimensions[1] + values[:, 1] + 1) * dimensions[2]
                + values[:, 2]
                + 1
            )

        order = np.argsort(keys(coords))
        sorted_keys = keys(coords)[order]
        indices = []
        for offset in product((-1, 0, 1), repeat=3):
            query = coords + offset
            query_keys = keys(query)
            positions = np.minimum(
                np.searchsorted(sorted_keys, query_keys), len(coords) - 1
            )
            valid = (
                (sorted_keys[positions] == query_keys)
                & (query >= 0).all(axis=1)
                & (query <= maximum).all(axis=1)
            )
            indices.append(np.where(valid, order[positions], len(coords)))
        neighbors.append(np.stack(indices, axis=1).astype(np.int64))
        if level < 4:
            coarse, inverse = np.unique(coords // 2, axis=0, return_inverse=True)
            children = np.full((len(coarse), 8), len(coords), dtype=np.int64)
            slot = (coords[:, 0] % 2) * 4 + (coords[:, 1] % 2) * 2 + coords[:, 2] % 2
            children[inverse, slot] = np.arange(len(coords))
            pools.append(children)
            parents.append(inverse.astype(np.int64))
            coords = coarse
    encoder_index = (coords[:, 0] * (width // 16) + coords[:, 1]).astype(np.int64)
    return {
        **{f"neighbor_{i}": value for i, value in enumerate(neighbors)},
        **{f"pool_{i}": value for i, value in enumerate(pools)},
        **{f"up_{i}": value for i, value in enumerate(parents)},
        "encoder_index": encoder_index,
    }


def _resize(array, height, width):
    """Resize an HWC array with half-pixel bilinear sampling."""
    import numpy as np
    from scipy.ndimage import map_coordinates

    y = (np.arange(height) + 0.5) * array.shape[0] / height - 0.5
    x = (np.arange(width) + 0.5) * array.shape[1] / width - 0.5
    coordinates = np.meshgrid(y, x, indexing="ij")
    if array.ndim == 2:
        return map_coordinates(
            array, coordinates, order=1, mode="nearest", prefilter=False
        )
    return np.stack(
        [
            map_coordinates(
                array[..., channel],
                coordinates,
                order=1,
                mode="nearest",
                prefilter=False,
            )
            for channel in range(array.shape[-1])
        ],
        axis=-1,
    )


def infer(
    session,
    image,
    resolution_level,
    *,
    release_memory=True,
    fov_x=None,
    source_valid=None,
):
    import numpy as np

    level = min(max(int(resolution_level), 0), 9)
    tokens = int(MIN_TOKENS + level / 9.0 * (MAX_TOKENS - MIN_TOKENS))
    coord, encoder, normal, mask, scale = run_session(
        session.backbone,
        ["coord", "encoder", "normal", "mask", "scale"],
        {
            "image": np.ascontiguousarray(
                image.transpose(2, 0, 1)[None], dtype=np.float32
            ),
            "num_tokens": np.asarray(tokens, dtype=np.int64),
        },
        release_memory=release_memory,
    )
    for step in range(3):
        if not np.isfinite(coord).all():
            raise ValueError("MoGe-3 produced non-finite coordinates")
        inputs = build_sparse_inputs(coord)
        inputs.update(coord=coord, encoder=encoder)
        (delta,) = run_session(
            session.refiner,
            ["delta"],
            inputs,
            release_memory=release_memory and step == 2,
        )
        coord[..., 2] += delta
        del inputs, delta
    height, width = image.shape[:2]
    coord = _resize(coord[0], height, width)
    depth = np.exp(coord[..., 2:])
    points = np.concatenate((coord[..., :2] * depth, depth), axis=-1)
    normal = _resize(normal[0].transpose(1, 2, 0), height, width)
    normal /= np.maximum(np.linalg.norm(normal, axis=-1, keepdims=True), 1e-12)
    mask = 1.0 / (1.0 + np.exp(-np.clip(_resize(mask[0, 0], height, width), -80, 80)))
    return postprocess(
        {
            "points": points[None],
            "normal": normal[None],
            "mask": mask[None],
            "metric_scale": np.exp(scale),
        },
        fov_x=fov_x,
        source_valid=source_valid,
    )
