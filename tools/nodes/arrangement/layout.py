"""Plan calculation bodies and shared wire passages in the same column layout."""

import math
from collections import defaultdict
from graphlib import TopologicalSorter
from statistics import median


def plan_layout(nodes, edges, size, blocks, core):
    """Return node positions and connection paths without modifying Blender data."""
    ids = {node: i for i, node in enumerate(nodes)}
    edge_ids = [(ids[e.from_node], ids[e.to_node]) for e in edges]
    edge_types = [e.from_socket.type for e in edges]
    block_of = {i: k for k, block in enumerate(blocks) for i in block["members"]}

    def bounds(positions):
        return (
            min(x for x, y in positions.values()),
            min(y for x, y in positions.values()),
            max(x + size[i].width for i, (x, y) in positions.items()),
            max(y + size[i].height for i, (x, y) in positions.items()),
        )

    def endpoint(edge, positions):
        a, b = ids[edge.from_node], ids[edge.to_node]
        return (
            (positions[a][0] + size[a].width, positions[a][1] + size[a].sockets[edge.from_socket]),
            (positions[b][0], positions[b][1] + size[b].sockets[edge.to_socket]),
        )

    source_keys = [(a, edges[e].from_socket.identifier) for e, (a, b) in enumerate(edge_ids)]

    def simplify(path):
        result = []
        for point in path:
            if result and math.dist(result[-1], point) < 1e-6:
                continue
            while (
                len(result) > 1
                and abs(result[-2][1] - result[-1][1]) < 1e-6
                and abs(point[1] - result[-1][1]) < 1e-6
            ):
                result.pop()
            result.append(point)
        return result

    def leaf(i):
        return dict(
            members={i},
            w=size[i].width,
            h=size[i].height,
            positions={i: (0.0, 0.0)},
            routes={},
            inputs={
                e: (0.0, size[i].sockets[edges[e].to_socket]) for e, (a, b) in enumerate(edge_ids) if b == i
            },
            outputs={
                e: (size[i].width, size[i].sockets[edges[e].from_socket])
                for e, (a, b) in enumerate(edge_ids)
                if a == i
            },
        )

    def plan_scope(items, rank_map=None):
        """Reserve relay rows at every crossed column, including nested boundaries."""
        items = {("item", k): v for k, v in enumerate(items)}
        owner = {i: k for k, item in items.items() for i in item["members"]}
        members = set(owner)
        incoming = [e for e, (a, b) in enumerate(edge_ids) if b in members and a not in members]
        outgoing = [e for e, (a, b) in enumerate(edge_ids) if a in members and b not in members]
        if rank_map is not None:
            incoming = []
            outgoing = []
        boundary = {}
        for e in incoming:
            boundary["in", e] = ("in", source_keys[e])
        for e in outgoing:
            boundary["out", e] = ("out", source_keys[e])
        for key in set(boundary.values()):
            items[key] = dict(members=set(), w=0.0, h=32.0, positions={}, routes={}, inputs={}, outputs={})
        links = []
        for e, (a, b) in enumerate(edge_ids):
            if a not in members and b not in members:
                continue
            if rank_map is not None and (a not in members or b not in members):
                continue
            u = owner[a] if a in members else boundary["in", e]
            v = owner[b] if b in members else boundary["out", e]
            if u == v:
                continue
            sy = items[u]["outputs"][e][1] if a in members else 16.0
            ty = items[v]["inputs"][e][1] if b in members else 16.0
            weight = 3.0 if edge_types[e] in {"GEOMETRY", "SHADER"} else 1.0
            links.append((e, u, v, sy, ty, weight))
        parents = {k: set() for k in items}
        children = {k: set() for k in items}
        for e, u, v, sy, ty, weight in links:
            parents[v].add(u)
            children[u].add(v)
        topo = list(TopologicalSorter(parents).static_order())
        earliest = {}
        for k in topo:
            earliest[k] = max((earliest[p] + 1 for p in parents[k]), default=0)
        depth = max(earliest.values(), default=0)
        ranks = {}
        for k in reversed(topo):
            ranks[k] = min((ranks[c] - 1 for c in children[k]), default=depth)
        for k in items:
            if k[0] == "in":
                ranks[k] = 0
        if rank_map is not None:
            ranks = {k: rank_map[min(item["members"])] for k, item in items.items()}
        # Relay vertices are space reservations, not routes fitted to placed nodes.
        chains = {}
        arcs = {}
        for e, u, v, sy, ty, weight in links:
            chain = [u]
            for rank in range(ranks[u] + 1, ranks[v]):
                key = ("relay", source_keys[e], rank)
                if key not in items:
                    items[key] = dict(
                        members=set(), w=0.0, h=36.0, positions={}, routes={}, inputs={}, outputs={}
                    )
                    ranks[key] = rank
                chain.append(key)
            chain.append(v)
            chains[e] = chain
            for j, (a, b) in enumerate(zip(chain, chain[1:])):
                ay = sy if j == 0 else items[a]["h"] / 2
                by = ty if j == len(chain) - 2 else items[b]["h"] / 2
                arcs[a, b, ay, by] = max(arcs.get((a, b, ay, by), 0), weight)
        layers = defaultdict(list)
        for k in items:
            layers[ranks[k]].append(k)
        for rank in range(min(ranks.values()), max(ranks.values()) + 1):
            layers[rank]
        families = {}
        for k, item in items.items():
            if item["members"]:
                i = min(item["members"])
                families[k] = ("block", block_of[i]) if i in block_of else ("core", i)
            else:
                families[k] = k
        for e, chain in chains.items():
            a, b = edge_ids[e]
            if a in block_of and block_of.get(a) == block_of.get(b):
                for k in chain[1:-1]:
                    families[k] = ("block", block_of[a])
        neighbors = defaultdict(list)
        for (a, b, ay, by), weight in arcs.items():
            if a[0] == "relay" and b[0] == "relay":
                weight *= 30.0
            neighbors[a].append((b, ay, by, weight))
            neighbors[b].append((a, by, ay, weight))
        gap = 64.0

        def separation(a, b):
            if families[a] != families[b] and (families[a][0] == "block" or families[b][0] == "block"):
                return 180.0
            return gap if items[a]["members"] and items[b]["members"] else 36.0

        y = {}
        for layer in layers.values():
            cursor = 0.0
            for k in layer:
                y[k] = cursor
                cursor += items[k]["h"] + gap

        def pack(layer, desired, weights):
            offsets = {}
            cursor = 0.0
            previous = None
            for k in layer:
                if previous is not None:
                    cursor += items[previous]["h"] + separation(previous, k)
                offsets[k] = cursor
                previous = k
            pools = []
            for k in layer:
                pools.append(([k], weights[k], (desired[k] - offsets[k]) * weights[k]))
                while len(pools) > 1 and pools[-2][2] / pools[-2][1] > pools[-1][2] / pools[-1][1]:
                    b = pools.pop()
                    a = pools.pop()
                    pools.append((a[0] + b[0], a[1] + b[1], a[2] + b[2]))
            for keys, weight, total in pools:
                for k in keys:
                    y[k] = total / weight + offsets[k]

        for sweep in range(16):
            for rank in sorted(layers, reverse=bool(sweep % 2)):
                layer = layers[rank]
                desired = {}
                weights = {}
                for k in layer:
                    adjacent = [
                        (y[b] + by - ay, weight)
                        for b, ay, by, weight in neighbors[k]
                        if (ranks[b] < rank) != bool(sweep % 2)
                    ]
                    if not adjacent:
                        adjacent = [(y[b] + by - ay, weight) for b, ay, by, weight in neighbors[k]]
                    weights[k] = sum(w for value, w in adjacent) or 1.0
                    desired[k] = sum(value * w for value, w in adjacent) / weights[k] if adjacent else y[k]
                family_centers = defaultdict(list)
                for k in layer:
                    family_centers[families[k]].append(desired[k] + items[k]["h"] / 2)
                centers = {key: sum(values) / len(values) for key, values in family_centers.items()}
                layer.sort(
                    key=lambda k: (
                        centers[families[k]],
                        repr(families[k]),
                        desired[k] + items[k]["h"] / 2,
                        repr(k),
                    )
                )
                pack(layer, desired, weights)
        # Coordinate relaxation holds the planned row order and never moves obstacles
        # in response to a routed wire. All channels remain participants in the solve.
        for sweep in range(24):
            for rank in sorted(layers, reverse=bool(sweep % 2)):
                desired = {}
                weights = {}
                for k in layers[rank]:
                    adj = neighbors[k]
                    weights[k] = sum(w for b, ay, by, w in adj) or 1.0
                    desired[k] = (
                        sum((y[b] + by - ay) * w for b, ay, by, w in adj) / weights[k] if adj else y[k]
                    )
                pack(layers[rank], desired, weights)
        top = min(y.values(), default=0.0)
        y = {k: value - top for k, value in y.items()}
        widths = {rank: max((items[k]["w"] for k in layer), default=0.0) for rank, layer in layers.items()}
        x = {}
        cursor = 0.0
        for rank in sorted(layers):
            x[rank] = cursor
            cursor += widths[rank] + 200.0
        width = cursor - 200.0
        if rank_map is not None:
            x = {rank: planned["columns"][rank] for rank in layers}
            widths = {rank: planned["column_widths"][rank] for rank in layers}
        height = max(y[k] + items[k]["h"] for k in items)
        result = dict(members=members, w=width, h=height, positions={}, routes={}, inputs={}, outputs={})
        for k, item in items.items():
            ox, oy = x[ranks[k]], y[k]
            result["positions"].update({i: (ox + px, oy + py) for i, (px, py) in item["positions"].items()})
            for e, path in item["routes"].items():
                result["routes"].setdefault(e, []).append([(ox + px, oy + py) for px, py in path])
        for e, u, v, sy, ty, weight in links:
            path = []
            chain = chains[e]
            for j, (a, b) in enumerate(zip(chain, chain[1:])):
                first_y = y[a] + (sy if j == 0 else items[a]["h"] / 2)
                last_y = y[b] + (ty if j == len(chain) - 2 else items[b]["h"] / 2)
                first_x = x[ranks[a]] + items[a]["w"]
                last_x = x[ranks[b]]
                path.append((first_x, first_y))
                if items[a]["w"] < widths[ranks[a]]:
                    path.append((x[ranks[a]] + widths[ranks[a]] + 60.0, first_y))
                path.append((last_x, last_y))
            result["routes"].setdefault(e, []).append(simplify(path))
        for e, key in ((e, boundary["in", e]) for e in incoming):
            result["inputs"][e] = (0.0, y[key] + 16.0)
        for e, key in ((e, boundary["out", e]) for e in outgoing):
            result["outputs"][e] = (width, y[key] + 16.0)
        for e, pieces in result["routes"].items():
            pieces.sort(key=lambda path: path[0][0])
            result["routes"][e] = simplify([point for path in pieces for point in path])
        result["ranks"] = {i: ranks[k] for i, k in owner.items()}
        result["columns"] = x
        result["column_widths"] = widths
        return result

    planned = plan_scope([leaf(i) for i in range(len(nodes))])
    seed = planned["positions"]
    for block in blocks:
        local = plan_scope([leaf(i) for i in block["members"]], rank_map=planned["ranks"])
        preferred = (
            sum(seed[i][1] + size[i].height / 2 for i in block["members"]) / len(block["members"])
            - local["h"] / 2
        )
        seed.update({i: (x, y + preferred) for i, (x, y) in local["positions"].items()})
        planned["routes"].update(
            {e: [(x, y + preferred) for x, y in path] for e, path in local["routes"].items()}
        )
    atoms = []
    node_atom = {}
    for members in [b["members"] for b in blocks] + [[i] for i in sorted(core)]:
        member_set = set(members)
        internal = [e for e, (a, b) in enumerate(edge_ids) if a in member_set and b in member_set]
        left, top, right, bottom = bounds({i: seed[i] for i in members})
        for e in internal:
            top = min(top, *(p[1] for p in planned["routes"][e]))
            bottom = max(bottom, *(p[1] for p in planned["routes"][e]))
        k = len(atoms)
        atoms.append(
            dict(
                members=member_set,
                x=left,
                w=right - left,
                h=bottom - top,
                preferred=top,
                internal=internal,
                bus=False,
            )
        )
        node_atom.update({i: k for i in members})

    external = [e for e, (a, b) in enumerate(edge_ids) if node_atom[a] != node_atom[b]]
    buses = {}
    edge_bus = {}
    for e in external:
        a, b = edge_ids[e]
        ra, rb = planned["ranks"][a], planned["ranks"][b]
        if rb == ra + 1:
            continue
        key = source_keys[e]
        if key not in buses:
            buses[key] = []
        buses[key].append(e)
    for key, links in buses.items():
        a = edge_ids[links[0]][0]
        ra = planned["ranks"][a]
        left = planned["columns"][ra + 1] - 60.0
        right = max(planned["columns"][planned["ranks"][edge_ids[e][1]]] - 60.0 for e in links)
        ys = [p[1] for e in links for p in planned["routes"][e][1:-1]]
        k = len(atoms)
        atoms.append(
            dict(
                members=set(),
                x=left,
                w=right - left,
                h=24.0,
                preferred=median(ys) - 12.0,
                internal=[],
                bus=True,
            )
        )
        edge_bus.update({e: k for e in links})

    # Shapes and long-wire reservations are packed in the same interval constraint
    # graph. No obstacle test or routing result can change these constraints later.
    atom_order = sorted(range(len(atoms)), key=lambda k: (atoms[k]["preferred"] + atoms[k]["h"] / 2, k))
    above = defaultdict(list)
    below = defaultdict(list)
    for j, a in enumerate(atom_order):
        for b in atom_order[j + 1 :]:
            u, v = atoms[a], atoms[b]
            if u["x"] < v["x"] + v["w"] + 32 and v["x"] < u["x"] + u["w"] + 32:
                gap = 32.0 if u["bus"] or v["bus"] else 220.0
                distance = u["h"] + gap
                above[b].append((a, distance))
                below[a].append((b, distance))
    ay = {}
    for k in atom_order:
        ay[k] = max([atoms[k]["preferred"], *(ay[a] + distance for a, distance in above[k])])
    neighbors = defaultdict(list)
    for e in external:
        a, b = edge_ids[e]
        u, v = node_atom[a], node_atom[b]
        sy = seed[a][1] + size[a].sockets[edges[e].from_socket] - atoms[u]["preferred"]
        ty = seed[b][1] + size[b].sockets[edges[e].to_socket] - atoms[v]["preferred"]
        weight = 3.0 if edge_types[e] in {"GEOMETRY", "SHADER"} else 1.0
        if e in edge_bus:
            weight *= 0.15
        sequence = [(u, sy), (v, ty)] if e not in edge_bus else [(u, sy), (edge_bus[e], 12.0), (v, ty)]
        for (k, ky), (j, jy) in zip(sequence, sequence[1:]):
            neighbors[k].append((j, ky, jy, weight))
            neighbors[j].append((k, jy, ky, weight))
    for sweep in range(80):
        for k in atom_order if sweep % 2 else reversed(atom_order):
            adjacent = neighbors[k]
            preferred = (
                sum((ay[j] + jy - ky) * w for j, ky, jy, w in adjacent) / sum(w for j, ky, jy, w in adjacent)
                if adjacent
                else ay[k]
            )
            low = max((ay[j] + d for j, d in above[k]), default=-1e9)
            high = min((ay[j] - d for j, d in below[k]), default=1e9)
            ay[k] = max(low, min(high, preferred))
    shift = min(ay.values())
    ay = {k: value - shift for k, value in ay.items()}
    positions = {i: (seed[i][0], seed[i][1] + ay[k] - atoms[k]["preferred"]) for i, k in node_atom.items()}
    routes = {}
    for k, atom in enumerate(atoms):
        for e in atom["internal"]:
            routes[e] = [(x, y + ay[k] - atom["preferred"]) for x, y in planned["routes"][e]]
    for e in external:
        a, b = edge_ids[e]
        start, end = endpoint(edges[e], positions)
        ra, rb = planned["ranks"][a], planned["ranks"][b]
        exit_x = planned["columns"][ra] + planned["column_widths"][ra] + 60.0
        entry_x = planned["columns"][rb] - 60.0
        if e in edge_bus:
            k = edge_bus[e]
            level = ay[k] + 12.0
            path = [start, (exit_x, start[1]), (atoms[k]["x"], level), (entry_x, level), end]
        else:
            path = (
                [start, end]
                if size[a].width == planned["column_widths"][ra]
                else [start, (exit_x, start[1]), end]
            )
        routes[e] = simplify(path)
    for block in blocks:
        block["box"] = bounds({i: positions[i] for i in block["members"]})
    return positions, routes
