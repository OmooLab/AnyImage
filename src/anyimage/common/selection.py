"""Selection values, serialization, rasterization, and composition."""

import json
import math
from dataclasses import dataclass


class ImageEditWarning(ValueError):
    pass


def clip_polygon_halfplanes(points, boundaries):
    """Clip a 2D polygon to linear half-planes ax + by + c >= 0."""
    polygon = tuple(tuple(float(value) for value in point) for point in points)
    for coefficients in boundaries:
        scale = max(abs(float(value)) for value in coefficients)
        if scale == 0.0:
            continue
        a, b, c = (float(value) / scale for value in coefficients)
        result = []
        if not polygon:
            break
        previous = polygon[-1]
        previous_value = math.fsum((a * previous[0], b * previous[1], c))
        for current in polygon:
            value = math.fsum((a * current[0], b * current[1], c))
            if (value >= 0.0) != (previous_value >= 0.0):
                weight = previous_value / (previous_value - value)
                result.append(tuple(
                    previous[axis] + weight * (current[axis] - previous[axis])
                    for axis in range(2)
                ))
            if value >= 0.0:
                result.append(current)
            previous, previous_value = current, value
        polygon = tuple(result)
    return polygon


@dataclass(frozen=True)
class SelectionPath:
    points: tuple[tuple[float, float], ...]

    def __post_init__(self):
        points = tuple(
            (float(point[0]), float(point[1]))
            for point in self.points
        )
        selection_path_bounds(points)
        object.__setattr__(self, "points", points)

    def to_json(self):
        return json.dumps(
            {"points": self.points},
            separators=(",", ":"),
        )

    @classmethod
    def from_json(cls, value):
        data = json.loads(value)
        if not isinstance(data, dict) or set(data) != {"points"}:
            raise ValueError("The Selection Path data is invalid")
        return cls(points=tuple(data["points"]))


@dataclass(frozen=True)
class SelectionMask:
    values: object
    bounds: tuple[int, int, int, int]

    def __post_init__(self):
        import numpy as np

        values = np.asarray(self.values, dtype=np.float32)
        bounds = tuple(int(value) for value in self.bounds)
        if values.ndim != 2:
            raise ValueError("The selection mask must be two-dimensional")
        if len(bounds) != 4:
            raise ValueError("The selection bounds are invalid")
        left, top, right, bottom = bounds
        if right <= left or bottom <= top:
            raise ValueError("The selection bounds are empty")
        if values.shape != (bottom - top, right - left):
            raise ValueError("The selection mask does not match its bounds")
        if not np.isfinite(values).all():
            raise ValueError("The selection mask contains invalid values")
        object.__setattr__(self, "values", np.clip(values, 0.0, 1.0))
        object.__setattr__(self, "bounds", bounds)

    def full_values(self, image_size):
        import numpy as np

        width, height = (int(value) for value in image_size)
        result = np.zeros((height, width), dtype=np.float32)
        left, top, right, bottom = self.bounds
        source_left = max(left, 0)
        source_top = max(top, 0)
        source_right = min(right, width)
        source_bottom = min(bottom, height)
        if source_right <= source_left or source_bottom <= source_top:
            return result
        result[source_top:source_bottom, source_left:source_right] = self.values[
            source_top - top : source_bottom - top,
            source_left - left : source_right - left,
        ]
        return result


def selection_path_bounds(points):
    import numpy as np

    points = np.asarray(points, dtype=np.float64)
    if points.ndim != 2 or points.shape[0] < 3 or points.shape[1] != 2:
        raise ValueError("The selection does not define a valid image path")
    if not np.isfinite(points).all():
        raise ValueError("The selection contains invalid image coordinates")
    left = int(math.floor(float(points[:, 0].min())))
    top = int(math.floor(float(points[:, 1].min())))
    right = int(math.ceil(float(points[:, 0].max())))
    bottom = int(math.ceil(float(points[:, 1].max())))
    if right <= left or bottom <= top:
        raise ValueError("The selection does not define a valid image area")
    return left, top, right, bottom


def _rasterize_path(bounds, points):
    import numpy as np

    left, top, right, bottom = bounds
    width = right - left
    height = bottom - top
    points = np.asarray(points, dtype=np.float64)
    y = np.arange(top, bottom, dtype=np.float64) + 0.5
    changes = np.zeros((height, width + 1), dtype=np.int16)
    previous = points[-1]
    for current in points:
        rows = np.flatnonzero((current[1] > y) != (previous[1] > y))
        if len(rows):
            sample_y = y[rows]
            edge_x = (previous[0] - current[0]) * (sample_y - current[1]) / (
                previous[1] - current[1] + 1e-300
            ) + current[0]
            ends = np.ceil(edge_x - left - 0.5).astype(np.int64)
            ends = np.clip(ends, 0, width)
            starts = np.zeros_like(rows)
            winding = 1 if current[1] > previous[1] else -1
            np.add.at(changes, (rows, starts), winding)
            np.add.at(changes, (rows, ends), -winding)
        previous = current
    return np.cumsum(changes[:, :width], axis=1, dtype=np.int16) != 0


def _selection_canvas_bounds(image_size, selection_path, padding):
    width, height = (int(value) for value in image_size)
    if width <= 0 or height <= 0:
        raise ValueError("The source image has no readable dimensions")
    left, top, right, bottom = selection_path_bounds(selection_path.points)
    return (
        max(left - padding, 0),
        max(top - padding, 0),
        min(right + padding, width),
        min(bottom + padding, height),
    )


def _antialias_mask(mask):
    import numpy as np

    values = np.asarray(mask, dtype=np.float32)
    kernel = np.asarray((0.029, 0.235, 0.472, 0.235, 0.029), dtype=np.float32)
    radius = len(kernel) // 2
    horizontal = np.zeros_like(values)
    padded = np.pad(values, ((0, 0), (radius, radius)), mode="edge")
    for offset, weight in enumerate(kernel):
        horizontal += padded[:, offset : offset + values.shape[1]] * weight
    result = np.zeros_like(values)
    padded = np.pad(horizontal, ((radius, radius), (0, 0)), mode="edge")
    for offset, weight in enumerate(kernel):
        result += padded[offset : offset + values.shape[0]] * weight
    return result


def rasterize_selection_path(
    image_size,
    selection_path,
    *,
    antialias=False,
):
    import numpy as np

    width, height = (int(value) for value in image_size)
    canvas_bounds = _selection_canvas_bounds(
        (width, height),
        selection_path,
        2 if antialias else 0,
    )
    left, top, right, bottom = canvas_bounds
    if right <= left or bottom <= top:
        raise ImageEditWarning("The selection contains no visible image pixels")
    mask = _rasterize_path(canvas_bounds, selection_path.points)
    if antialias:
        mask = _antialias_mask(mask)
    else:
        mask = mask.astype(np.float32)
    if not np.any(mask > 0.0):
        raise ImageEditWarning("The selection contains no visible image pixels")
    return SelectionMask(mask, canvas_bounds)


def trim_pixels_to_alpha(pixels, bounds):
    """Trim Blender-order RGBA pixels to their nonzero Alpha bounds."""
    import numpy as np

    left, top, right, bottom = bounds
    width = right - left
    height = bottom - top
    rgba = np.flipud(
        np.asarray(pixels, dtype=np.float32).reshape((height, width, 4))
    )
    visible_y, visible_x = np.nonzero(rgba[:, :, 3] > 0.0)
    if not len(visible_x):
        raise ImageEditWarning("The edit contains no visible image pixels")
    content_left = int(visible_x.min())
    content_top = int(visible_y.min())
    content_right = int(visible_x.max()) + 1
    content_bottom = int(visible_y.max()) + 1
    output = rgba[content_top:content_bottom, content_left:content_right].copy()
    return np.flipud(output).ravel(), (
        left + content_left,
        top + content_top,
        left + content_right,
        top + content_bottom,
    )


def rasterize_selection_union(image_size, paths, *, antialias=False):
    """Rasterize a geometric union on one local canvas before antialiasing."""
    import numpy as np

    paths = tuple(paths)
    bounds = [
        _selection_canvas_bounds(image_size, path, 2 if antialias else 0)
        for path in paths
    ]
    entries = [(path, box) for path, box in zip(paths, bounds)
               if box[2] > box[0] and box[3] > box[1]]
    if not entries:
        raise ImageEditWarning("The selection contains no visible image pixels")
    left = min(box[0] for _, box in entries)
    top = min(box[1] for _, box in entries)
    right = max(box[2] for _, box in entries)
    bottom = max(box[3] for _, box in entries)
    coverage = np.zeros((bottom - top, right - left), dtype=bool)
    for path, box in entries:
        x0, y0, x1, y1 = box
        coverage[y0 - top:y1 - top, x0 - left:x1 - left] |= _rasterize_path(box, path.points)
    if not coverage.any():
        raise ImageEditWarning("The selection contains no visible image pixels")
    values = _antialias_mask(coverage) if antialias else coverage.astype(np.float32)
    return SelectionMask(values, (left, top, right, bottom))
