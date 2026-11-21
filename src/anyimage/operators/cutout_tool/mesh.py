"""Build the Cutout support mesh from its selection mask."""

import numpy as np
from scipy import ndimage

from .contours import (
    contours_for_component,
    extract_selection_contours,
    separate_contour_contacts,
    smooth_selection_contour,
    valid_contours,
)
from .triangulation import face_edge_counts, triangulate


# Keep predicate tolerances independent of scene units and requested density.
NORMALIZED_EDGE_LENGTH = 32.0


def boundary_vertices_from_faces(vertex_count, faces):
    faces = np.asarray(faces, dtype=np.int32)
    boundary = np.zeros(vertex_count, dtype=bool)
    if not len(faces):
        return boundary
    edges, users = face_edge_counts(faces)
    boundary[edges[users == 1]] = True
    return boundary


def support_mesh(points, faces, *, max_vertices=50000):
    """Split boundary chords once so every face has an interior height sample."""
    edges, counts = face_edge_counts(faces)
    boundary = np.zeros(len(points), dtype=bool)
    boundary[edges[counts == 1]] = True
    chords = edges[(counts == 2) & boundary[edges].all(axis=1)]
    midpoints = {tuple(edge): len(points) + i for i, edge in enumerate(chords)}
    isolated = sum(
        boundary[face].all() and not any(
            tuple(sorted((face[i], face[(i+1) % 3]))) in midpoints for i in range(3)
        ) for face in faces
    )
    if len(points) + len(chords) + isolated > max_vertices:
        raise ValueError("Cutout support vertex limit exceeded")
    if not len(chords) and not isolated:
        return points, faces
    vertices = points.tolist() + points[chords].mean(axis=1).tolist()
    output = []
    for face in faces:
        pieces = [list(face)]
        for i in range(3):
            a, b = face[i], face[(i+1) % 3]
            midpoint = midpoints.get(tuple(sorted((a, b))))
            if midpoint is None:
                continue
            split = []
            for piece in pieces:
                if a in piece and b in piece:
                    k = next(
                        j for j in range(3)
                        if piece[j] in (a, b) and piece[(j+1) % 3] in (a, b)
                    )
                    x, y, z = piece[k], piece[(k+1) % 3], piece[(k+2) % 3]
                    split.extend(((x, midpoint, z), (midpoint, y, z)))
                else:
                    split.append(piece)
            pieces = split
        if len(pieces) == 1 and boundary[face].all():
            midpoint = len(vertices)
            vertices.append(points[face].mean(axis=0).tolist())
            pieces = [(face[i], face[(i+1) % 3], midpoint) for i in range(3)]
        output.extend(pieces)
    return np.asarray(vertices), np.asarray(output, dtype=np.int32)


def prepare_mask(alpha, threshold, transform, fine_outline):
    """Keep significant islands and fill holes at the target mesh spacing."""
    labels, count = ndimage.label((alpha > 0) & (alpha >= threshold))
    areas = np.bincount(labels.ravel(), minlength=count + 1)
    keep = areas >= 16
    keep[0] = False
    if count:
        keep[1 + np.argmax(areas[1:])] = True
    mask = keep[labels]
    filled = ndimage.binary_fill_holes(mask)
    if not fine_outline:
        return filled
    holes, _ = ndimage.label(filled & ~mask)
    areas = np.bincount(holes.ravel()) * abs(np.linalg.det(transform))
    for index, slices in enumerate(ndimage.find_objects(holes), 1):
        if slices is None or areas[index] > 0.04 * NORMALIZED_EDGE_LENGTH**2:
            continue
        y, x = slices
        corners = (
            np.array(
                (
                    (x.start, y.start),
                    (x.stop, y.start),
                    (x.stop, y.stop),
                    (x.start, y.stop),
                )
            )
            @ transform
        )
        if np.ptp(corners, axis=0).max() <= 0.25 * NORMALIZED_EDGE_LENGTH:
            mask[slices] |= holes[slices] == index
    return mask


def build_mesh(
    alpha,
    spacing,
    threshold,
    *,
    pixel_transform=None,
    fine_outline=True,
    include_components=True,
):
    """Return pixel-space quality triangles, component ranges and final Mask."""
    alpha = np.asarray(alpha, dtype=float)
    if alpha.ndim != 2 or not alpha.size or not np.isfinite(alpha).all():
        raise ValueError("The Cutout Alpha must be a finite two-dimensional array")
    if not np.isfinite(spacing) or spacing <= 0:
        raise ValueError("Cutout point spacing must be greater than zero")
    transform = (
        np.eye(2) if pixel_transform is None else np.asarray(pixel_transform)
    ) * (NORMALIZED_EDGE_LENGTH / spacing)
    inverse = np.linalg.inv(transform)
    mask = prepare_mask(alpha, threshold, transform, fine_outline)
    if not mask.any():
        raise ValueError("The Cutout selection contains no visible image pixels")
    points, faces, components = [], [], []
    offset = 0
    for component in extract_selection_contours(mask):
        raw = separate_contour_contacts([np.asarray(c) @ transform for c in component])
        if fine_outline:
            contours = contours_for_component(raw, NORMALIZED_EDGE_LENGTH, pixel_transform=transform)
        else:
            contours = [
                smooth_selection_contour(
                    c,
                    min(
                        NORMALIZED_EDGE_LENGTH,
                        np.linalg.norm(np.roll(c, -1, axis=0) - c, axis=1).sum() / 8,
                    ),
                )
                for c in raw
            ]
            contours = [
                np.clip(c @ inverse, (0, 0), mask.shape[::-1]) @ transform
                for c in contours
            ]
            if not valid_contours(contours):
                raise ValueError("Cutout simplified outline is invalid")
        vertices, triangles = triangulate(contours, NORMALIZED_EDGE_LENGTH)
        vertices, triangles = support_mesh(
            vertices, triangles, max_vertices=50000-offset
        )
        points.append(vertices @ inverse)
        faces.append(triangles + offset)
        if include_components:
            components.append(
                (offset, offset + len(vertices), triangles, contours[0] @ inverse)
            )
        offset += len(vertices)
    points, faces = np.concatenate(points), np.concatenate(faces)
    boundary = boundary_vertices_from_faces(len(points), faces)
    return points, faces, boundary, components, mask
