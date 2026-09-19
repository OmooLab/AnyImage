"""Identify connected calculations by their nearest geometry or shader consumers."""

from collections import defaultdict
from graphlib import TopologicalSorter


def calculation_blocks(nodes, edges):
    """Group fields with equal consumers, then attach their local interface reads."""
    ids = {node: i for i, node in enumerate(nodes)}
    parents = {i: set() for i in range(len(nodes))}
    children = {i: set() for i in parents}
    for edge in edges:
        parents[ids[edge.to_node]].add(ids[edge.from_node])
        children[ids[edge.from_node]].add(ids[edge.to_node])
    order = list(TopologicalSorter(parents).static_order())
    core = {
        i
        for i, n in enumerate(nodes)
        if n.bl_idname == "NodeGroupOutput"
        or n.bl_idname in {"ShaderNodeNormalMap", "ShaderNodeBump", "ShaderNodeDisplacement"}
        or any(s.type in {"GEOMETRY", "SHADER"} and s.is_linked for s in n.outputs)
        or getattr(n, "paired_output", None) is not None
    }
    inputs = {i for i, n in enumerate(nodes) if n.bl_idname == "NodeGroupInput"}
    core -= inputs
    fields = set(range(len(nodes))) - core - inputs
    destinations = {}
    for i in reversed(order):
        destinations[i] = frozenset().union(
            *(frozenset([j]) if j in core else destinations[j] for j in children[i])
        )
    groups = defaultdict(set)
    for i in fields:
        groups[destinations[i]].add(i)
    blocks = []
    for targets, members in groups.items():
        pending = set(members)
        while pending:
            component = set()
            queue = [min(pending)]
            while queue:
                i = queue.pop()
                if i not in pending:
                    continue
                pending.remove(i)
                component.add(i)
                queue.extend((parents[i] | children[i]) & pending)
            target = min(targets) if targets else None
            ports = list(
                dict.fromkeys(
                    e.to_socket.name
                    for e in edges
                    if ids[e.from_node] in component and ids[e.to_node] == target
                )
            )
            if ports:
                title = nodes[target].name + " · " + ", ".join(ports)
            else:
                outlets = [i for i in component if children[i] - component]
                source = (
                    max(outlets, key=lambda i: (len(children[i] - component), i))
                    if outlets
                    else max(component)
                )
                title = "共享 · " + nodes[source].name + " → " + str(len(targets)) + " 处计算"
            blocks.append(dict(title=title, members=sorted(component), targets=sorted(targets)))
    block_of = {i: k for k, b in enumerate(blocks) for i in b["members"]}
    # Keep one local original read; additional consumers receive local copies later.
    for i in sorted(inputs):
        owners = [block_of[j] for j in sorted(children[i]) if j in block_of]
        if any(j in core for j in children[i]):
            core.add(i)
        elif owners:
            k = owners[0]
            blocks[k]["members"].append(i)
            block_of[i] = k
        else:
            core.add(i)

    return blocks, core
