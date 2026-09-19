"""Estimate node bounds and socket offsets in unscaled editor units."""

import json
from dataclasses import dataclass
from pathlib import Path


RULES = json.loads(Path(__file__).with_suffix(".json").read_text(encoding="utf-8"))


@dataclass(frozen=True)
class NodeDimensions:
    width: float
    height: float
    sockets: dict


def visible_socket(socket):
    """Include only sockets drawn for the node's current operation."""
    return socket.enabled and not socket.is_unavailable and not socket.hide


def estimate_node_dimensions(node):
    """Reserve socket rows, expanded vector values, and node-specific controls."""
    if node.bl_idname == "NodeFrame":
        return NodeDimensions(node.width, node.height, {})
    if node.bl_idname == "NodeReroute":
        return NodeDimensions(16, 16, {socket: 8 for socket in (*node.inputs, *node.outputs)})
    inputs = [s for s in node.inputs if visible_socket(s)]
    outputs = [s for s in node.outputs if visible_socket(s)]
    width = RULES["wide_width"] if (
        "Attribute" in node.bl_idname or node.bl_idname in {"GeometryNodeGroup", "ShaderNodeGroup", "ShaderNodeFloatCurve"}
    ) else RULES["width"]
    if node.hide:
        height = max(RULES["collapsed_height"], 16 + 12 * max(len(inputs), len(outputs)))
        sockets = {
            socket: (index + 1) * height / (len(side) + 1)
            for side in (inputs, outputs)
            for index, socket in enumerate(side)
        }
        return NodeDimensions(width, height, sockets)

    # Conservative reserves include spacing between UI sections.
    controls = RULES["controls"][node.bl_idname]
    for collection in ("repeat_items", "state_items", "input_items", "main_items", "generation_items", "enum_items"):
        controls += len(getattr(node, collection, ()))
    if node.bl_idname in {"GeometryNodeGroup", "ShaderNodeGroup"} and node.node_tree:
        controls += sum(item.item_type == "PANEL" for item in node.node_tree.interface.items_tree)
    cursor = RULES["header"] + RULES["padding"]
    sockets = {}
    for socket in outputs:
        sockets[socket] = cursor + RULES["row"] / 2
        cursor += RULES["row"]
    cursor += controls * RULES["row"] + RULES["padding"]
    for socket in inputs:
        rows = 1
        if not socket.is_linked and not socket.hide_value:
            if socket.type in {"VECTOR", "ROTATION"}:
                rows = 4
            elif socket.type == "MATRIX":
                rows = 5
        extra = max(0, len(socket.links) - 1) * 8 if socket.is_multi_input else 0
        sockets[socket] = cursor + RULES["row"] / 2 + extra / 2
        cursor += rows * RULES["row"] + extra
    return NodeDimensions(width, cursor + RULES["padding"], sockets)
