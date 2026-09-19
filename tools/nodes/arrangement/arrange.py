"""Materialize the joint calculation and connection plan in node trees."""

from .branches import calculation_blocks
from .dimensions import estimate_node_dimensions, visible_socket
from .flow import origin_socket, socket_links
from .layout import plan_layout
from nodes.common.nodes import prepare_node_group, replace_link_source


def _remove_routes(node_group):
    previous = [node for node in node_group.nodes if node.bl_idname == "NodeReroute"]

    for node in [node for node in node_group.nodes if node not in previous]:
        for socket in node.inputs:
            links = socket_links(socket)
            if not any(link.from_node in previous for link in links):
                continue
            if not socket.is_multi_input:
                replace_link_source(node_group, links[0], origin_socket(links[0].from_socket))
                continue
            sources = [origin_socket(link.from_socket) for link in links]
            for link in links:
                node_group.links.remove(link)
            seen = set()
            for source in reversed(sources):
                original = source
                if source in seen:
                    # Blender coalesces identical direct links; retain repeated inputs.
                    duplicate = node_group.nodes.new("NodeReroute")
                    node_group.links.new(source, duplicate.inputs[0])
                    source = duplicate.outputs[0]
                seen.add(original)
                node_group.links.new(source, socket)
    for node in previous:
        node_group.nodes.remove(node)


def _localize_inputs(node_group, nodes, blocks, core):
    """Read interface values locally in each consuming calculation body."""
    ids = {node: i for i, node in enumerate(nodes)}
    block_of = {i: k for k, block in enumerate(blocks) for i in block["members"]}
    for node in list(nodes):
        if node.bl_idname != "NodeGroupInput":
            continue
        original = ("core", ids[node]) if ids[node] in core else ("block", block_of[ids[node]])
        uses = list(node_group.links)
        direct = [ids[edge.to_node] for edge in uses if edge.from_node == node and ids[edge.to_node] in core]
        if direct:
            original = ("core", direct[0])
        local_reads = {original: node}
        for edge in uses:
            if edge.from_node != node:
                continue
            target = ids[edge.to_node]
            owner = ("block", block_of[target]) if target in block_of else ("core", target)
            if owner not in local_reads:
                clone = node_group.nodes.new("NodeGroupInput")
                ids[clone] = len(nodes)
                nodes.append(clone)
                if owner[0] == "block":
                    blocks[owner[1]]["members"].append(ids[clone])
                    block_of[ids[clone]] = owner[1]
                else:
                    core.add(ids[clone])
                local_reads[owner] = clone
            source = next(
                socket
                for socket in local_reads[owner].outputs
                if socket.identifier == edge.from_socket.identifier
            )
            if source != edge.from_socket:
                replace_link_source(node_group, edge, source)


def arrange_nodes(node_group):
    """Arrange calculation bodies and shared channels before creating reroutes."""
    for frame in [node for node in node_group.nodes if node.bl_idname == "NodeFrame"]:
        for child in [node for node in node_group.nodes if node.parent == frame]:
            position = tuple(child.location_absolute)
            child.parent = None
            child.location = position
        node_group.nodes.remove(frame)
    _remove_routes(node_group)
    nodes = list(node_group.nodes)
    if not nodes:
        return
    blocks, core = calculation_blocks(nodes, list(node_group.links))
    _localize_inputs(node_group, nodes, blocks, core)
    prepare_node_group(node_group)
    for node in nodes:
        node.select = False
        if node.bl_idname in {"ShaderNodeMath", "ShaderNodeVectorMath", "FunctionNodeIntegerMath"}:
            node.hide = all(socket.is_linked for socket in node.inputs if visible_socket(socket))
    sizes = {i: estimate_node_dimensions(node) for i, node in enumerate(nodes)}
    edges = list(node_group.links)
    positions, routes = plan_layout(nodes, edges, sizes, blocks, core)
    for i, (x, y) in positions.items():
        nodes[i].location = (x, -y)
        nodes[i].width = sizes[i].width
    cache = {}
    for index, path in routes.items():
        edge = edges[index]
        source = edge.from_socket
        for x, y in path[1:-1]:
            key = (source, round(x, 4), round(y, 4))
            reroute = cache.get(key)
            if reroute is None:
                reroute = node_group.nodes.new("NodeReroute")
                reroute.location = (x - 8, -y + 8)
                node_group.links.new(source, reroute.inputs[0])
                cache[key] = reroute
            source = reroute.outputs[0]
        if len(path) > 2:
            replace_link_source(node_group, edge, source)
    for block in blocks:
        if len(block["members"]) < 5:
            continue
        left, top, right, bottom = block["box"]
        frame = node_group.nodes.new("NodeFrame")
        frame["arrangement_frame"] = True
        frame.name = frame.label = block["title"]
        frame.shrink = False
        frame.location = (left - 28, -top + 48)
        frame.width = right - left + 56
        frame.height = bottom - top + 76
        for i in block["members"]:
            absolute = nodes[i].location.copy()
            nodes[i].parent = frame
            nodes[i].location = absolute - frame.location
    prepare_node_group(node_group)
