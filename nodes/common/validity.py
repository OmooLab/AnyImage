"""Delete the faces the depth mask excludes."""


def delete_invalid_faces(group, geometry, invalid):
    nodes, links = group.nodes, group.links
    delete = nodes.new("GeometryNodeDeleteGeometry")
    delete.domain, delete.mode = "FACE", "ALL"
    links.new(geometry, delete.inputs["Geometry"])
    links.new(invalid, delete.inputs["Selection"])
    return delete.outputs["Geometry"]
