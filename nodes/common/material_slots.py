"""Carry the input mesh's material slots onto generated geometry."""


def inherit_material_slots(group, geometry, source):
    nodes, links = group.nodes, group.links
    size = nodes.new("GeometryNodeAttributeDomainSize")
    size.component = "MESH"
    links.new(source, size.inputs["Geometry"])
    index = nodes.new("GeometryNodeInputIndex")
    source_vertices = nodes.new("FunctionNodeCompare")
    source_vertices.data_type, source_vertices.operation = "INT", "LESS_THAN"
    links.new(index.outputs["Index"], source_vertices.inputs[2])
    links.new(size.outputs["Point Count"], source_vertices.inputs[3])
    join = nodes.new("GeometryNodeJoinGeometry")
    # Multi-input links are prepended: source occupies the first point range.
    links.new(geometry, join.inputs["Geometry"])
    links.new(source, join.inputs["Geometry"])
    material = nodes.new("GeometryNodeSetMaterialIndex")
    material.inputs["Material Index"].default_value = 0
    links.new(join.outputs["Geometry"], material.inputs["Geometry"])
    delete = nodes.new("GeometryNodeDeleteGeometry")
    delete.domain = "POINT"
    links.new(material.outputs["Geometry"], delete.inputs["Geometry"])
    links.new(source_vertices.outputs["Result"], delete.inputs["Selection"])
    return delete.outputs["Geometry"]
