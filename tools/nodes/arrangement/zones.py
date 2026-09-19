"""Identify paired execution zones and their exclusive input calculations."""

from graphlib import TopologicalSorter


def repeat_regions(node_group, positions, sizes):
    """Bound repeat execution and calculations without peripheral routing corners."""
    regions = []
    for entry, end, members in node_zones(node_group):
        if entry.bl_idname != "GeometryNodeRepeatInput":
            continue
        nodes = {node for node in members if node.bl_idname not in {"NodeReroute", "NodeFrame"}}
        regions.append((members, (positions[entry][0] - 60,
                                  positions[end][0] + sizes[end].width + 60,
                                  max(positions[node][1] for node in nodes) + 60,
                                  min(positions[node][1] - sizes[node].height for node in nodes) - 40)))
    return regions


def node_zones(node_group):
    """Return each paired entry, exit, and its data-dependent node membership."""
    parents = {node: set() for node in node_group.nodes}
    children = {node: set() for node in node_group.nodes}
    for link in node_group.links:
        parents[link.to_node].add(link.from_node)
        children[link.from_node].add(link.to_node)
    order = list(TopologicalSorter(parents).static_order())
    ancestors = {}
    for node in order:
        ancestors[node] = parents[node] | set().union(*(ancestors[parent] for parent in parents[node]))
    zones = []
    for entry in order:
        end = getattr(entry, "paired_output", None)
        if end is None:
            continue
        members = {node for node in ancestors[end] if entry in ancestors[node]} | {entry, end}
        for node in reversed(order):
            if (node not in members and node in ancestors[end] and children[node]
                    and children[node] <= members and entry not in children[node]):
                members.add(node)
        zones.append((entry, end, members))
    return zones
