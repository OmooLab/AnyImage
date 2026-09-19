"""Preview node groups with the socket dimension model in a self-contained HTML file."""

import argparse
import json
from pathlib import Path

import bpy

from ..arrangement.dimensions import estimate_node_dimensions
from ..arrangement.flow import node_roles
from ..arrangement.connections import link_endpoints
from ..arrangement.zones import node_zones, repeat_regions


def _display_value(value):
    if isinstance(value, bpy.types.ID):
        return value.name
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        return str(round(value, 4))
    if value is None:
        return ""
    try:
        return ", ".join(str(round(x, 3)) for x in value)
    except TypeError:
        return str(value)


def _node_group_data(node_group):
    nodes = [node for node in node_group.nodes if node.bl_idname != "NodeFrame"]
    ids = {node: index for index, node in enumerate(nodes)}
    dimensions = {node: estimate_node_dimensions(node) for node in nodes}
    roles = node_roles(node_group)
    records = []
    for node in nodes:
        size = dimensions[node]
        settings = []
        for name in ("operation", "data_type", "input_type", "domain", "mode", "pattern_mode"):
            if not hasattr(node, name):
                continue
            value = getattr(node, name)
            prop = node.bl_rna.properties[name]
            label = prop.enum_items[value].name if prop.type == "ENUM" and value in prop.enum_items else str(value)
            settings.append(label)
        title = node.bl_label
        if node.bl_idname in {"GeometryNodeGroup", "ShaderNodeGroup"}:
            title = node.node_tree.name
        elif hasattr(node, "operation") and settings:
            title = settings[0]
        sockets = []
        for socket, offset in size.sockets.items():
            default = _display_value(socket.default_value) if not socket.is_linked and hasattr(socket, "default_value") else ""
            sockets.append([socket.name, round(offset, 2), int(socket.is_output), socket.type, default])
        records.append({"id": ids[node], "name": node.name, "title": title,
                        "type": node.bl_idname, "role": roles[node],
                        "x": round(node.location_absolute.x, 2), "y": round(-node.location_absolute.y, 2),
                        "w": size.width, "h": size.height, "folded": bool(node.hide),
                        "settings": settings, "sockets": sockets})
    links = []
    positions = {node: tuple(node.location_absolute) for node in nodes}
    for link in node_group.links:
        source, target = link.from_node, link.to_node
        (x1, y1), (x2, y2) = link_endpoints(link, positions, dimensions)
        links.append([ids[source], ids[target], *[round(v, 2) for v in (x1, -y1, x2, -y2)], link.from_socket.type])
    zones = []
    repeats = {frozenset(members): box for members, box in repeat_regions(node_group, positions, dimensions)}
    for entry, end, members in node_zones(node_group):
        if entry.bl_idname != "GeometryNodeRepeatInput":
            members = {node for node in members if roles[node] == "geometry"} | {entry, end}
        boxes = [records[ids[node]] for node in members]
        padding = 60 if entry.bl_idname == "GeometryNodeRepeatInput" else 40
        left = min(node["x"] for node in boxes) - padding
        top = min(node["y"] for node in boxes) - 60
        right = max(node["x"] + node["w"] for node in boxes) + padding
        bottom = max(node["y"] + node["h"] for node in boxes) + 40
        if entry.bl_idname == "GeometryNodeRepeatInput":
            left, right, upper, lower = repeats[frozenset(members)]
            top, bottom = -upper, -lower
        zones.append({"title": entry.bl_label.removesuffix(" Input"),
                      "type": entry.bl_idname, "entry": ids[entry], "exit": ids[end],
                      "nodes": sorted(ids[node] for node in members),
                      "x": left, "y": top, "w": right - left, "h": bottom - top})
    zones.sort(key=lambda zone: zone["w"] * zone["h"], reverse=True)
    frames = [{"title": node.label or node.name, "x": node.location_absolute.x,
               "y": -node.location_absolute.y, "w": node.width, "h": node.height,
               "nodes": [ids[child] for child in nodes if child.parent == node]}
              for node in node_group.nodes if node.bl_idname == "NodeFrame"]
    return {"name": node_group.name, "nodes": records, "links": links, "zones": zones, "frames": frames}


def write_node_preview(node_groups, output_path, *, fragment=False):
    """Write an interactive preview without changing the supplied node groups."""
    data = [_node_group_data(node_group) for node_group in node_groups]
    if not data or any(not node_group["nodes"] for node_group in data):
        raise ValueError("The preview requires nonempty node groups")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    markup = Path(__file__).with_name("template.html").read_text(encoding="utf-8").replace("__NODE_DATA__", payload)
    if not fragment:
        markup = """<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>节点排列预览</title>
<style>
:root { color-scheme: dark; --background: #191919; --foreground: #ededed;
        --muted-foreground: #a0a0a0; --border: #404040; }
body { margin: 24px; background: var(--background); color: var(--foreground); font: 14px system-ui,sans-serif; }
h3 { font-size: 16px; font-weight: 500; }
.viz-controls,.viz-row { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin: 8px 0; }
.form-label { display: flex; align-items: center; gap: 8px; }
button,select { padding: 8px; font: inherit; max-width: 100%; }
.text-small { font-size: 12px; }
@media(max-width:440px) { body { margin: 12px; } .form-label { width: 100%; } select { flex: 1; min-width: 0; } }
</style><body>
""" + markup + "\n</body></html>"
    output_path = Path(output_path).resolve()
    output_path.write_text(markup, encoding="utf-8")
    return output_path


def main():
    """Build and arrange node assets in memory for preview."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Output HTML path")
    parser.add_argument("--fragment", action="store_true", help="Write a fragment for an inline preview")
    args = parser.parse_args()
    output_path = args.output.resolve()
    from ..build import build_node_groups
    from ..arrangement.arrange import arrange_nodes

    bpy.ops.wm.read_factory_settings(use_empty=True)
    node_groups = build_node_groups()
    for node_group in node_groups:
        arrange_nodes(node_group)
    print(write_node_preview(node_groups, output_path, fragment=args.fragment))


if __name__ == "__main__":
    main()
