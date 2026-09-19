"""Infer geometry flow and socket relationships for layout and preview."""

from collections import defaultdict

from .branches import calculation_blocks


SHARED_GEOMETRY_USES = 3


def socket_links(socket):
    return sorted(socket.links, key=lambda link: link.multi_input_sort_id, reverse=True)


def origin_socket(socket):
    while socket.node.bl_idname == "NodeReroute":
        socket = socket.node.inputs[0].links[0].from_socket
    return socket


def geometry_paths(node_group):
    """Trace every geometry input and split paths at forks and merges."""
    output = next((node for node in node_group.nodes if node.bl_idname == "NodeGroupOutput" and node.is_active_output), None)
    parents = {}
    uses = defaultdict(set)
    for link in node_group.links:
        if link.from_socket.type == "GEOMETRY" and link.to_node.bl_idname != "NodeReroute":
            uses[origin_socket(link.from_socket).node].add(link.to_node)
    paired = {member for node in node_group.nodes if getattr(node, "paired_output", None) is not None
              for member in (node, node.paired_output)}
    result_nodes, pending = set(), [*paired, *([output] if output else [])]
    while pending:
        node = pending.pop()
        if node in result_nodes:
            continue
        result_nodes.add(node)
        pending.extend(origin_socket(link.from_socket).node
                       for socket in node.inputs if socket.type == "GEOMETRY" for link in socket.links)
    shared = {node for node, targets in uses.items()
              if len(targets) >= SHARED_GEOMETRY_USES and node not in paired
              and (not any(socket.type == "GEOMETRY" and socket.is_linked for socket in node.inputs)
                   or len(targets & result_nodes) >= SHARED_GEOMETRY_USES)}

    def source_node(link):
        return link.from_node if link.from_node.get("arrangement_input") else origin_socket(link.from_socket).node

    def collect(node):
        if node in parents:
            return
        parents[node] = list(dict.fromkeys(
            source_node(link) for socket in node.inputs if socket.type == "GEOMETRY"
            for link in socket_links(socket)
            if source_node(link).bl_idname != "NodeGroupInput" and source_node(link) not in shared
        )) if not node.get("arrangement_input") else []
        for parent in parents[node]:
            collect(parent)

    roots = []
    if output is not None:
        collect(output)
        roots.append(output)
    for node in node_group.nodes:
        if node in paired and node not in parents:
            collect(node)
            roots.append(node)
    children = {node: set() for node in parents}
    for node, sources in parents.items():
        for source in sources:
            children[source].add(node)
    paths, assigned, pending = [], set(), roots
    while pending:
        node = pending.pop(0)
        path = []
        while node not in assigned:
            path.append(node)
            assigned.add(node)
            sources = parents[node]
            if len(sources) != 1 or len(children[sources[0]]) != 1:
                pending.extend(source for source in sources if source not in assigned)
                break
            node = sources[0]
        if path:
            paths.append(list(reversed(path)))
    return parents, paths


def node_roles(node_group):
    """Classify by contribution to the result, not by available socket types."""
    if node_group.bl_idname == "ShaderNodeTree":
        nodes = list(node_group.nodes)
        _, core = calculation_blocks(nodes, list(node_group.links))
        return {node: "shader" if i in core else "field" for i, node in enumerate(nodes)}
    core, _ = geometry_paths(node_group)
    return {node: "geometry" if node in core else "field" for node in node_group.nodes}
