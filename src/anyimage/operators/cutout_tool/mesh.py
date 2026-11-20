"""Cutout contours, quality triangulation and local height support."""

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

from .contours import (
    contour_area,
    contour_interior_point,
    contours_for_component,
    extract_selection_contours,
    separate_contour_contacts,
    smooth_selection_contour,
    valid_contours,
)


# Keep predicate tolerances independent of scene units and requested density.
NORMALIZED_EDGE_LENGTH = 32.0


def boundary_vertices_from_faces(vertex_count, faces):
    faces = np.asarray(faces, dtype=np.int32)
    boundary = np.zeros(vertex_count, dtype=bool)
    if not len(faces):
        return boundary
    edges = np.concatenate(
        [
            faces[:, (index, (index + 1) % faces.shape[1])]
            for index in range(faces.shape[1])
        ],
        axis=0,
    )
    edges.sort(axis=1)
    unique_edges, users = np.unique(edges, axis=0, return_counts=True)
    boundary[unique_edges[users == 1].ravel()] = True
    return boundary


def support_mesh(points, faces, *, max_vertices=50000):
    """Split boundary chords once so every face has an interior height sample."""
    edges, counts = np.unique(
        np.sort(np.concatenate((faces[:, :2], faces[:, 1:], faces[:, ::2])), axis=1),
        axis=0, return_counts=True,
    )
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
        if offset > 50000:
            raise ValueError("Cutout mesh vertex limit exceeded")
    points, faces = np.concatenate(points), np.concatenate(faces)
    boundary = boundary_vertices_from_faces(len(points), faces)
    return points, faces, boundary, components, mask


def normalize_constraints(points, edges):
    """Merge coincident vertices and split constraints at existing vertices."""
    tree = cKDTree(points)
    parents = np.arange(len(points))

    def root(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for a, b in sorted(tree.query_pairs(1e-8)):
        parents[root(b)] = root(a)
    representatives = np.array([root(i) for i in range(len(points))])
    used, inverse = np.unique(representatives, return_inverse=True)
    points = points[used]
    tree = cKDTree(points)
    segments = []
    seen = {}
    sources = {}
    for marker, (a, b) in enumerate(edges, 1):
        a, b = inverse[a], inverse[b]
        delta = points[b] - points[a]
        length = np.linalg.norm(delta)
        if length <= 1e-8:
            raise ValueError("Cutout constraint collapsed during normalization")
        candidates = np.array(
            tree.query_ball_point((points[a] + points[b]) / 2, length / 2 + 1e-8),
            dtype=int,
        )
        fraction = (points[candidates] - points[a]) @ delta / length**2
        distance = np.linalg.norm(
            points[candidates] - points[a] - fraction[:, None] * delta, axis=1
        )
        valid = (fraction >= -1e-10) & (fraction <= 1 + 1e-10) & (distance < 1e-8)
        ids = candidates[valid][np.argsort(fraction[valid])]
        for x, y in zip(ids, ids[1:]):
            key = tuple(sorted((int(x), int(y))))
            if key in seen:
                sources[seen[key]].add(marker)
                continue
            identity = len(segments) + 1
            seen[key] = identity
            sources[identity] = {marker}
            segments.append((int(x), int(y), identity))
    return points, segments, sources


def triangulate(contours, spacing):
    """Build and validate a quality mesh with complete constraint chains."""
    from . import tangle
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    points = np.concatenate(contours)
    if len(points) > 20000:
        raise ValueError("Cutout constraint vertex limit exceeded")
    edges = []
    offset = 0
    for contour in contours:
        edges.extend(
            (offset + i, offset + (i + 1) % len(contour)) for i in range(len(contour))
        )
        offset += len(contour)
    input_points = points
    points, segments, sources = normalize_constraints(points, edges)
    points = np.vstack((points, contour_interior_point(contours, spacing)))
    holes = [contour_interior_point([contour], spacing).tolist() for contour in contours[1:]]
    raw_points, raw_faces, raw_segments = tangle.build_mesh(
        points.tolist(), segments, holes, np.sqrt(3) / 4 * spacing**2
    )
    points = np.asarray(raw_points)
    faces = np.asarray(raw_faces, dtype=np.int32).reshape(-1, 3)
    if not len(faces) or not np.isfinite(points).all():
        raise ValueError("Cutout triangulation is empty or nonfinite")
    used = np.unique(faces)
    remap = np.full(len(points), -1, dtype=np.int32)
    remap[used] = np.arange(len(used))
    points, faces = points[used], remap[faces]
    triangles = points[faces]
    areas = (
        abs(
            np.cross(
                triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]
            )
        )
        / 2
    )
    expected_area = abs(contour_area(contours[0])) - sum(
        abs(contour_area(c)) for c in contours[1:]
    )
    if np.any(areas <= 1e-10) or not np.isclose(
        areas.sum(), expected_area, rtol=1e-8, atol=1e-7
    ):
        raise ValueError("Cutout triangulation has degenerate faces or incorrect area")
    face_edges, counts = np.unique(
        np.sort(np.concatenate((faces[:, :2], faces[:, 1:], faces[:, ::2])), axis=1),
        axis=0,
        return_counts=True,
    )
    if counts.max() > 2:
        raise ValueError("Cutout triangulation has nonmanifold edges")
    graph = coo_matrix(
        (np.ones(len(face_edges)), (face_edges[:, 0], face_edges[:, 1])),
        shape=(len(points), len(points)),
    ).tocsr()
    components, _ = connected_components(graph, directed=False)
    if (
        components != 1
        or components - len(points) + len(face_edges) - len(faces) != len(contours) - 1
    ):
        raise ValueError(
            "Cutout triangulation has incorrect component or hole topology"
        )
    actual_edges = {tuple(e) for e in face_edges}
    chains = [[] for _ in edges]
    for a, b, marker in raw_segments:
        if marker in sources and min(remap[a], remap[b]) >= 0:
            edge = tuple(sorted((int(remap[a]), int(remap[b]))))
            if edge in actual_edges:
                for original in sources[marker]:
                    chains[original - 1].append(edge)
    tree = cKDTree(points)
    for (a, b), chain in zip(edges, chains):
        error = "Cutout lost a boundary constraint"
        if not chain:
            raise ValueError(error)
        chain = np.asarray(chain)
        start, end = input_points[[a, b]]
        delta = end - start
        length = np.linalg.norm(delta)
        vertices = np.unique(chain)
        distance = np.linalg.norm(
            points[vertices]
            - start
            - ((points[vertices] - start) @ delta / length**2)[:, None] * delta,
            axis=1,
        )
        covered = np.linalg.norm(
            points[chain[:, 1]] - points[chain[:, 0]], axis=1
        ).sum()
        endpoint_distance, endpoints = tree.query([start, end])
        adjacency = {}
        for x, y in chain:
            adjacency.setdefault(x, set()).add(y)
            adjacency.setdefault(y, set()).add(x)
        visited = set()
        pending = [endpoints[0]]
        while pending:
            vertex = pending.pop()
            if vertex not in visited:
                visited.add(vertex)
                pending.extend(adjacency.get(vertex, ()))
        if (
            distance.max() > 1e-6
            or endpoint_distance.max() > 1e-6
            or endpoints[1] not in visited
            or not np.isclose(covered, length, rtol=1e-7, atol=1e-6)
        ):
            raise ValueError(error)
    return points, faces
