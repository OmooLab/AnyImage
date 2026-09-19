"""Compute Poisson and Teddy height profiles for Cutout meshes."""

import math


DEFAULT_INFLATION = 0.45


def distances_to_contour(points, contour):
    import numpy as np

    points = np.asarray(points, dtype=np.float64)
    contour = np.asarray(contour, dtype=np.float64)
    squared = np.full(len(points), np.inf, dtype=np.float64)
    for start, end in zip(contour, np.roll(contour, -1, axis=0)):
        segment = end - start
        length_squared = float(segment.dot(segment))
        if length_squared <= 1e-16:
            continue
        factor = np.clip(
            (points - start) @ segment / length_squared,
            0.0,
            1.0,
        )
        nearest = start + factor[:, None] * segment
        squared = np.minimum(
            squared,
            np.sum((points - nearest) ** 2, axis=1),
        )
    return np.sqrt(squared)


def chordal_axis(contour, epsilon=1e-9):
    import numpy as np
    from mathutils import Vector
    from mathutils.geometry import delaunay_2d_cdt

    contour = np.asarray(contour, dtype=np.float64)
    boundary_count = len(contour)
    boundary_edges = [
        (index, (index + 1) % boundary_count) for index in range(boundary_count)
    ]
    result = delaunay_2d_cdt(
        [Vector(point) for point in contour],
        boundary_edges,
        [list(range(boundary_count))],
        1,
        epsilon,
    )
    points = np.asarray(
        [tuple(point) for point in result[0]],
        dtype=np.float64,
    )
    triangles = [tuple(face) for face in result[2] if len(face) == 3]
    boundary = {tuple(sorted(edge)) for edge in boundary_edges}
    node_indices = {}
    nodes = []
    segments = set()

    def edge_node(edge):
        key = ("edge", *tuple(sorted(edge)))
        if key not in node_indices:
            node_indices[key] = len(nodes)
            nodes.append((points[edge[0]] + points[edge[1]]) * 0.5)
        return node_indices[key]

    for face_index, face in enumerate(triangles):
        edges = [
            (face[0], face[1]),
            (face[1], face[2]),
            (face[2], face[0]),
        ]
        internal = [edge for edge in edges if tuple(sorted(edge)) not in boundary]
        internal_nodes = [edge_node(edge) for edge in internal]
        if len(internal_nodes) == 2:
            segments.add(tuple(sorted(internal_nodes)))
        elif len(internal_nodes) == 3:
            key = ("face", face_index)
            center_index = len(nodes)
            node_indices[key] = center_index
            nodes.append(points[list(face)].mean(axis=0))
            for midpoint_index in internal_nodes:
                segments.add(tuple(sorted((center_index, midpoint_index))))

    if not nodes:
        center = contour.mean(axis=0)
        return (
            np.asarray((center,), dtype=np.float64),
            [],
            np.asarray(
                (distances_to_contour((center,), contour)[0],),
                dtype=np.float64,
            ),
        )

    nodes = np.asarray(nodes, dtype=np.float64)
    radii = distances_to_contour(nodes, contour)
    active = set(segments)
    while len(active) > 1:
        degree = [0] * len(nodes)
        for start, end in active:
            degree[start] += 1
            degree[end] += 1
        removable = []
        for edge in active:
            start, end = edge
            leaf = start if degree[start] == 1 else end if degree[end] == 1 else None
            if leaf is None:
                continue
            length = float(np.linalg.norm(nodes[start] - nodes[end]))
            if length < max(radii[leaf] * 0.5, epsilon):
                removable.append(edge)
        if not removable:
            break
        active.difference_update(removable)

    if active:
        used = sorted({index for edge in active for index in edge})
        remap = {old: new for new, old in enumerate(used)}
        nodes = nodes[used]
        radii = radii[used]
        active = {tuple(sorted((remap[start], remap[end]))) for start, end in active}
    else:
        widest = int(np.argmax(radii))
        nodes = nodes[[widest]]
        radii = radii[[widest]]

    return nodes, sorted(active), radii


def smooth_interior_heights(
    heights,
    planar_faces,
    boundary_mask,
    iterations=2,
    factor=0.3,
):
    import numpy as np

    values = np.asarray(heights, dtype=np.float64).copy()
    boundary_mask = np.asarray(boundary_mask, dtype=bool)
    neighbors = [set() for _index in range(len(values))]
    for face in planar_faces:
        for start, end in zip(face, face[1:] + face[:1]):
            neighbors[start].add(end)
            neighbors[end].add(start)
    for _iteration in range(iterations):
        updated = values.copy()
        for index in np.flatnonzero(~boundary_mask):
            adjacent = [
                neighbor for neighbor in neighbors[index] if not boundary_mask[neighbor]
            ]
            if adjacent:
                average = float(values[adjacent].mean())
                updated[index] = values[index] * (1.0 - factor) + average * factor
        updated[boundary_mask] = 0.0
        values = updated
    return values


def teddy_balloon_heights(
    planar_points,
    planar_faces,
    contour,
    boundary_mask,
    inflation,
):
    import numpy as np

    points = np.asarray(planar_points, dtype=np.float64)
    boundary_mask = np.asarray(boundary_mask, dtype=bool)
    nodes, segments, radii = chordal_axis(contour)
    squared_heights = np.zeros(len(points), dtype=np.float64)

    for start, end in segments:
        axis_start = nodes[start]
        axis_end = nodes[end]
        axis = axis_end - axis_start
        length_squared = float(axis.dot(axis))
        if length_squared <= 1e-16:
            continue
        factors = np.clip(
            (points - axis_start) @ axis / length_squared,
            0.0,
            1.0,
        )
        centers = axis_start + factors[:, None] * axis
        local_radii = radii[start] + factors * (radii[end] - radii[start])
        distance_squared = np.sum((points - centers) ** 2, axis=1)
        squared_heights = np.maximum(
            squared_heights,
            local_radii * local_radii - distance_squared,
        )

    degree = np.zeros(len(nodes), dtype=np.int64)
    for start, end in segments:
        degree[start] += 1
        degree[end] += 1
    for index in np.flatnonzero(degree != 2):
        distance_squared = np.sum((points - nodes[index]) ** 2, axis=1)
        squared_heights = np.maximum(
            squared_heights,
            radii[index] * radii[index] - distance_squared,
        )

    missing = (~boundary_mask) & (squared_heights <= 0.0)
    if np.any(missing):
        fallback = distances_to_contour(points[missing], contour)
        squared_heights[missing] = fallback * fallback
    heights = inflation * np.sqrt(np.maximum(squared_heights, 0.0))
    heights[boundary_mask] = 0.0
    return smooth_interior_heights(
        heights,
        planar_faces,
        boundary_mask,
    )


def cotangent_poisson_field(
    planar_points,
    planar_faces,
    boundary_mask,
    tolerance=1e-8,
):
    import numpy as np

    points = np.asarray(planar_points, dtype=np.float64)
    faces = np.asarray(planar_faces, dtype=np.int64)
    if faces.size == 0:
        faces = np.empty((0, 3), dtype=np.int64)
    if faces.ndim != 2 or faces.shape[1] != 3:
        raise ValueError("Balloon profile faces must be triangles")
    boundary_mask = np.asarray(boundary_mask, dtype=bool)
    triangles = points[faces]
    a, b, c = (triangles[:, index] for index in range(3))
    cross = np.abs(
        (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1])
        - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])
    )
    usable = cross > 1e-14
    faces = faces[usable]
    a, b, c = a[usable], b[usable], c[usable]
    cross = cross[usable]
    loads = np.bincount(
        faces.ravel(),
        weights=np.repeat(cross / 6.0, 3),
        minlength=len(points),
    )
    edges = np.concatenate(
        (
            faces[:, (1, 2)],
            faces[:, (0, 2)],
            faces[:, (0, 1)],
        ),
        axis=0,
    )
    edge_weights = np.concatenate(
        (
            np.sum((b - a) * (c - a), axis=1),
            np.sum((a - b) * (c - b), axis=1),
            np.sum((a - c) * (b - c), axis=1),
        )
    ) / np.tile(cross * 2.0, 3)
    edges.sort(axis=1)
    edges, inverse = np.unique(edges, axis=0, return_inverse=True)
    edge_weights = np.bincount(
        inverse,
        weights=edge_weights,
        minlength=len(edges),
    )

    interior = np.flatnonzero(~boundary_mask)
    field = np.zeros(len(points), dtype=np.float64)
    if not len(interior):
        return field
    compact = np.full(len(points), -1, dtype=np.int64)
    compact[interior] = np.arange(len(interior), dtype=np.int64)
    # Constrained triangulation can create negative cotangent weights.
    # Clamping them keeps the Dirichlet system positive definite.
    edge_weights = np.maximum(edge_weights, 0.0)
    usable = edge_weights > 1e-14
    compact_edges = compact[edges[usable]]
    edge_weights = edge_weights[usable]
    start_compact = compact_edges[:, 0]
    end_compact = compact_edges[:, 1]
    start_usable = start_compact >= 0
    end_usable = end_compact >= 0
    diagonal = np.zeros(len(interior), dtype=np.float64)
    diagonal += np.bincount(
        start_compact[start_usable],
        weights=edge_weights[start_usable],
        minlength=len(interior),
    )
    diagonal += np.bincount(
        end_compact[end_usable],
        weights=edge_weights[end_usable],
        minlength=len(interior),
    )
    if np.any(diagonal <= 1e-14):
        raise ValueError("Unable to build a stable Balloon profile")

    interior_edges = start_usable & end_usable
    edge_starts = start_compact[interior_edges]
    edge_ends = end_compact[interior_edges]
    weights = edge_weights[interior_edges]
    directed_starts = np.concatenate((edge_starts, edge_ends))
    directed_ends = np.concatenate((edge_ends, edge_starts))
    directed_weights = np.concatenate((weights, weights))

    def multiply(values):
        result = diagonal * values
        if len(directed_weights):
            result -= np.bincount(
                directed_starts,
                weights=directed_weights * values[directed_ends],
                minlength=len(values),
            )
        return result

    right_hand_side = loads[interior]
    solution = np.zeros(len(interior), dtype=np.float64)
    residual = right_hand_side.copy()
    preconditioned = residual / diagonal
    direction = preconditioned.copy()
    residual_product = float(residual.dot(preconditioned))
    target = max(float(np.linalg.norm(right_hand_side)) * tolerance, 1e-12)
    max_iterations = max(64, min(len(interior) * 4, 4000))
    for _iteration in range(max_iterations):
        if float(np.linalg.norm(residual)) <= target:
            break
        multiplied = multiply(direction)
        denominator = float(direction.dot(multiplied))
        if denominator <= 0.0 or not math.isfinite(denominator):
            raise ValueError("Unable to solve the Balloon profile")
        step = residual_product / denominator
        solution += step * direction
        residual -= step * multiplied
        preconditioned = residual / diagonal
        next_product = float(residual.dot(preconditioned))
        if not math.isfinite(next_product):
            raise ValueError("Unable to solve the Balloon profile")
        if abs(residual_product) <= 1e-30:
            break
        direction = preconditioned + next_product / residual_product * direction
        residual_product = next_product

    field[interior] = np.maximum(solution, 0.0)
    return field


def poisson_balloon_profile(
    planar_points,
    planar_faces,
    boundary_mask,
    inflation=DEFAULT_INFLATION,
):
    import numpy as np

    field = cotangent_poisson_field(
        planar_points,
        planar_faces,
        boundary_mask,
    )
    return 2.0 * float(inflation) * np.sqrt(field)


def balloon_profile(
    algorithm,
    planar_points,
    planar_faces,
    boundary_mask,
    components,
    inflation=DEFAULT_INFLATION,
):
    import numpy as np

    algorithm = str(algorithm).upper()
    if algorithm == "POISSON":
        return poisson_balloon_profile(
            planar_points,
            planar_faces,
            boundary_mask,
            inflation,
        )
    if algorithm != "TEDDY":
        raise ValueError(f"Unknown Balloon profile algorithm: {algorithm}")
    result = np.zeros(len(planar_points), dtype=np.float64)
    for start, end, component_faces, outer_contour in components:
        result[start:end] = teddy_balloon_heights(
            np.asarray(planar_points)[start:end],
            component_faces,
            outer_contour,
            np.asarray(boundary_mask)[start:end],
            inflation,
        )
    return result
