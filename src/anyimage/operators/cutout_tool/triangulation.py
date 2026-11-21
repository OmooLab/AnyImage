"""Build and verify constrained triangle meshes from Cutout contours."""

import numpy as np
from scipy.spatial import cKDTree

from .contours import contour_area, contour_edge_indices, contour_interior_point


def face_edge_counts(faces):
    """Return each undirected face edge and its number of incident faces."""
    edges = np.stack((faces, np.roll(faces, -1, axis=1)), axis=-1).reshape(-1, 2)
    edges.sort(axis=1)
    return np.unique(edges, axis=0, return_counts=True)


def _normalize_constraints(points, edges):
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
    edges = contour_edge_indices(contours)
    input_points = points
    points, segments, sources = _normalize_constraints(points, edges)
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
    face_edges, counts = face_edge_counts(faces)
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
