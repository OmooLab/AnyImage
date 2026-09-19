import bpy

from anyimage.common.object import (
    modifier_input_identifier,
    set_modifier_input,
)

from anyimage.operators.convert_to_plane.image_plane import (
    add_image_plane_processing,
    create_image_plane_mesh,
)


def evaluated_mesh(obj):
    bpy.context.view_layer.update()
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    return evaluated, evaluated.to_mesh()


def test_material_inheritance_removes_only_source_vertices():
    from nodes.common.material_slots import inherit_material_slots

    bpy.ops.wm.read_factory_settings(use_empty=True)
    source_count = 4
    mesh = bpy.data.meshes.new("Source")
    mesh.from_pydata([(20 + i % 3, i // 3, 0) for i in range(source_count)], [],
                     [(0, 1, 3, 2)])
    materials = [bpy.data.materials.new(name) for name in ("First", "Second")]
    for material in materials:
        mesh.materials.append(material)
    obj = bpy.data.objects.new("Material Source", mesh)
    bpy.context.collection.objects.link(obj)
    group = bpy.data.node_groups.new("Material Inheritance", "GeometryNodeTree")
    group.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    group.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    source = group.nodes.new("NodeGroupInput")
    grid = group.nodes.new("GeometryNodeMeshGrid")
    grid.inputs["Vertices X"].default_value = 3
    grid.inputs["Vertices Y"].default_value = 2
    geometry = inherit_material_slots(group, grid.outputs["Mesh"], source.outputs["Geometry"])
    group.links.new(geometry, group.nodes.new("NodeGroupOutput").inputs["Geometry"])
    obj.modifiers.new("Material Inheritance", "NODES").node_group = group
    obj.update_tag(refresh={"DATA"})
    ev, result = evaluated_mesh(obj)
    try:
        assert len(result.vertices) == 6 and len(result.polygons) == 2
        assert all(abs(v.co.x) <= 0.5 for v in result.vertices)
        assert [material.original for material in result.materials if material] == materials
        assert result.materials[0].original == materials[0]
        assert all(face.material_index == 0 for face in result.polygons)
    finally:
        ev.to_mesh_clear()


def test_saved_image_plane_evaluation():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mesh = create_image_plane_mesh("Image Plane", (-1.0, 1.0, -0.5, 0.5))
    assert len(mesh.polygons) == 1
    material = bpy.data.materials.new("Image Plane Material")
    mesh.materials.append(material)
    obj = bpy.data.objects.new("Image Plane", mesh)
    bpy.context.scene.collection.objects.link(obj)
    modifier = add_image_plane_processing(obj)
    group = modifier.node_group
    assert group.name == "O Image Plane"
    assert group.is_modifier
    inputs = {
        item.name: item
        for item in group.interface.items_tree
        if item.item_type == "SOCKET" and item.in_out == "INPUT"
    }
    assert list(inputs) == ["Geometry", "Subdivide", "Thickness"]
    assert inputs["Subdivide"].default_value == 0
    assert inputs["Subdivide"].max_value == 10
    assert inputs["Thickness"].default_value == 0.0
    assert obj.data.materials[0] == material

    evaluated, result = evaluated_mesh(obj)
    try:
        assert result.materials[0].original == material
        assert len(result.polygons) == 2
        assert len(result.vertices) == 6
        assert "UVMap" in result.attributes
        uv_values = {
            tuple(round(value, 6) for value in loop.uv)
            for loop in result.uv_layers["UVMap"].data
        }
        assert uv_values == {
            (0.0, 0.0),
            (0.5, 0.0),
            (1.0, 0.0),
            (0.0, 1.0),
            (0.5, 1.0),
            (1.0, 1.0),
        }
        assert all(abs(vertex.co.y) < 1e-6 for vertex in result.vertices)
        assert all(polygon.material_index == 0 for polygon in result.polygons)
    finally:
        evaluated.to_mesh_clear()

    set_modifier_input(modifier, modifier_input_identifier(group, "Subdivide"), 3)
    obj.update_tag(refresh={"DATA"})
    evaluated, result = evaluated_mesh(obj)
    try:
        assert len(result.polygons) == 128
        assert len(result.vertices) == 153
    finally:
        evaluated.to_mesh_clear()

    set_modifier_input(modifier, modifier_input_identifier(group, "Subdivide"), 2)
    set_modifier_input(modifier, modifier_input_identifier(group, "Thickness"), 1.2)
    obj.update_tag(refresh={"DATA"})
    evaluated, result = evaluated_mesh(obj)
    try:
        assert result.materials[0].original == material
        assert len(result.polygons) == 184
        y_values = [vertex.co.y for vertex in result.vertices]
        assert abs(min(y_values) + 0.6) < 1e-6
        assert abs(max(y_values) - 0.6) < 1e-6
        assert len({round(value, 6) for value in y_values}) == 6
        edge_users = {edge.key: 0 for edge in result.edges}
        for polygon in result.polygons:
            for edge_key in polygon.edge_keys:
                edge_users[edge_key] += 1
        assert all(users == 2 for users in edge_users.values())
        assert all(polygon.material_index == 0 for polygon in result.polygons)
    finally:
        evaluated.to_mesh_clear()

    set_modifier_input(modifier, modifier_input_identifier(group, "Subdivide"), 0)
    set_modifier_input(modifier, modifier_input_identifier(group, "Thickness"), 0.01)
    obj.update_tag(refresh={"DATA"})
    evaluated, result = evaluated_mesh(obj)
    try:
        y_values = {round(vertex.co.y, 6) for vertex in result.vertices}
        assert len(y_values) >= 4
    finally:
        evaluated.to_mesh_clear()

    if bpy.app.version >= (5, 0, 0):
        assert group.library is not None
