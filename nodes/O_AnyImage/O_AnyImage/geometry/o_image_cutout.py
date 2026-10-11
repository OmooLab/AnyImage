from bpy.types import GeometryNodeTree
from omoonodes import geometry as g, TreeBuilder
from omoonodes.builder import CustomGeometryGroup


class OImageCutout(CustomGeometryGroup):
    _name = "O Image Cutout"
    _color_tag = "GEOMETRY"
    _tree_properties = {"is_modifier": True}

    def _build_group(self, tree: TreeBuilder[GeometryNodeTree]) -> None:
        geometry = tree.inputs.geometry("Geometry", structure_type="SINGLE", force_non_field=True)
        mode = tree.inputs.menu("Mode", "Balloon", structure_type="SINGLE", force_non_field=True)
        thickness = tree.inputs.float("Thickness", 1.0, description="Control how much the surface bulges in Balloon mode. Zero removes the bulge.", min_value=0.0, max_value=2.0, structure_type="SINGLE", force_non_field=True)
        thickness_1 = tree.inputs.float("Thickness", 0.0, description="Add thickness behind the original surface while keeping the front surface in place.", min_value=0.0, max_value=1.0, structure_type="SINGLE", subtype="DISTANCE", force_non_field=True)
        geometry_1 = tree.outputs.geometry("Geometry")

        boolean_math = g.Compare.integer.equal(g.EdgeNeighbors(), 1).o.result.edge.evaluate() | g.Compare.integer.equal(g.VertexNeighbors().o.vertex_count, 1)
        boolean_math_1 = g.Compare.integer.equal(g.EdgeNeighbors(), 1).o.result.edge.evaluate() | g.Compare.integer.equal(g.VertexNeighbors().o.vertex_count, 1)
        menu_switch = g.MenuSwitch.boolean(mode, {"Balloon": False, "Shell": True})
        store_named_attribute = g.StoreNamedAttribute.face.integer(geometry, name="o_image_region")
        switch = (thickness > 0.000001).switch.float(1.0, g.NamedAttribute.float("o_balloon").o.attribute)
        math_1 = g.NamedAttribute.float("o_balloon").o.attribute * thickness
        math_2 = thickness_1 * 0.0
        math_3 = thickness_1 * 1.0
        math_4 = (math_2 + math_3) * 0.5
        position = g.Position().o.position
        set_position = g.SetPosition(geometry=store_named_attribute, position=g.CombineXYZ(x=position.x, y=math_1 * -1.0, z=position.z))
        position_1 = g.Position().o.position
        store_named_attribute_1 = (
            g.SetPosition(geometry=store_named_attribute, position=g.CombineXYZ(x=position_1.x, y=math_1, z=position_1.z))
            >> g.FlipFaces()
            >> g.StoreNamedAttribute.face.integer(name="o_image_region", value=1)
        )
        merge_by_distance = g.MergeByDistance(geometry=g.JoinGeometry(geometry=(store_named_attribute_1, set_position)), distance=0.000001, mode="All")
        position_2 = g.Position().o.position
        set_position_1 = g.SetPosition(geometry=store_named_attribute, position=g.CombineXYZ(x=position_2.x, y=math_2, z=position_2.z))
        extrude_mesh = g.ExtrudeMesh.edges(set_position_1, boolean_math, (0.0, 1.0, 0.0))
        position_3 = g.Position().o.position
        store_named_attribute_2 = (
            g.SetPosition(geometry=store_named_attribute, position=g.CombineXYZ(x=position_3.x, y=math_3, z=position_3.z))
            >> g.FlipFaces()
            >> g.StoreNamedAttribute.face.integer(name="o_image_region", value=1)
        )
        extrude_mesh_1 = g.ExtrudeMesh.edges(store_named_attribute_2, boolean_math_1, (0.0, 1.0, 0.0))
        position_4 = g.Position().o.position
        separate_geometry = (
            extrude_mesh
            >> g.SetPosition(selection=extrude_mesh.o.top, position=g.CombineXYZ(x=position_4.x, y=math_4, z=position_4.z))
            >> g.SeparateGeometry.face(selection=extrude_mesh.o.side)
        )
        position_5 = g.Position().o.position
        separate_geometry_1 = (
            extrude_mesh_1
            >> g.SetPosition(selection=extrude_mesh_1.o.top, position=g.CombineXYZ(x=position_5.x, y=math_4, z=position_5.z))
            >> g.SeparateGeometry.face(selection=extrude_mesh_1.o.side)
        )
        join_geometry = g.JoinGeometry(geometry=(separate_geometry_1.o.selection, separate_geometry.o.selection, store_named_attribute_2, set_position_1))
        switch_1 = (thickness_1 < 0.000001).switch.geometry(g.MergeByDistance(geometry=join_geometry, distance=0.000001, mode="All"), store_named_attribute)
        (
            menu_switch.o.output.switch.geometry((thickness < 0.000001).switch.geometry(merge_by_distance, store_named_attribute), switch_1)
            >> g.StoreNamedAttribute.point.float(name="o_normal_reduction", value=1.0 - menu_switch.o.output.switch.float(switch, 1.0))
            >> g.SetShadeSmooth.face()
            >> geometry_1
        )

ASSET = OImageCutout

ASSET_METADATA = {
    "catalog_id": "00000000-0000-0000-0000-000000000000",
}
