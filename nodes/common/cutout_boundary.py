"""Clean cutout boundary triangles and taper the split thickness profile."""

from .depth_surface import _math
from .nodes import boolean_node, compare_node, evaluate_field, read_float_attribute, store_float_attribute
from .smoothing import edge_boundary_field
from .boundary_smoothing import boundary_influence


def remove_boundary_triangles(group, geometry):
    """Remove all-boundary triangles once on the current topology."""
    nodes, links = group.nodes, group.links
    rim = evaluate_field(group, edge_boundary_field(nodes, links), "FLOAT", "POINT")
    all_boundary = compare_node(group, "GREATER_THAN", evaluate_field(group, rim, "FLOAT", "FACE"), 0.99999)
    count = nodes.new("GeometryNodeInputMeshFaceNeighbors").outputs["Vertex Count"]
    selected = boolean_node(group, "AND", all_boundary, compare_node(group, "EQUAL", count, 3, data_type="INT"))
    delete = nodes.new("GeometryNodeDeleteGeometry")
    delete.domain, delete.mode = "FACE", "ALL"
    links.new(geometry, delete.inputs["Geometry"])
    links.new(selected, delete.inputs["Selection"])
    return delete.outputs["Geometry"]


def taper_split_profile(group, geometry, cut_boundary):
    """Taper the balloon profile to zero across the Depth Split cuts."""
    nodes = group.nodes
    links = group.links
    retained = _math(group, "SUBTRACT", 1, boundary_influence(group, boundary=cut_boundary))
    profile = _math(group, "MULTIPLY", read_float_attribute(group, "o_balloon"), retained)
    return store_float_attribute(group, geometry, "o_balloon", profile)
