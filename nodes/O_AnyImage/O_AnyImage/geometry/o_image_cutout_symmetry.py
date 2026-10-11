from bpy.types import GeometryNodeTree
from omoonodes import geometry as g, TreeBuilder
from omoonodes.builder import CustomGeometryGroup


class OImageCutoutSymmetry(CustomGeometryGroup):
    _name = "O Image Cutout Symmetry"
    _color_tag = "GEOMETRY"
    _tree_properties = {"is_modifier": True}

    def _build_group(self, tree: TreeBuilder[GeometryNodeTree]) -> None:
        geometry = tree.inputs.geometry("Geometry", structure_type="SINGLE", force_non_field=True)
        direction = tree.inputs.vector("Direction", (0.0, 0.0, 1.0), description="Align this direction with the local symmetry axis.", structure_type="SINGLE", subtype="DIRECTION", force_non_field=True)
        offset = tree.inputs.float("Offset", 0.0, description="Offset geometry along the aligned symmetry axis before scaling.", min_value=-10.0, max_value=10.0, structure_type="SINGLE", subtype="DISTANCE", force_non_field=True)
        scale = tree.inputs.float("Scale", 1.0, description="Scale the offset geometry along the aligned symmetry axis.", min_value=0.0, max_value=2.0, structure_type="SINGLE", force_non_field=True)
        with tree.inputs.panel("Options", default_closed=True):
            fill_sides = tree.inputs.boolean("Fill Sides", True, description="Connect matching retained and mirrored boundaries.", structure_type="SINGLE", force_non_field=True)
            smooth = tree.inputs.integer("Smooth", 4, description="Smooth the cut ring and the fill band around the outline and the fill, each over four rings. Zero keeps both raw.", min_value=0, max_value=16, structure_type="SINGLE", force_non_field=True)
        geometry_1 = tree.outputs.geometry("Geometry")

        index = g.Index()
        edges_of_corner = g.EdgesOfCorner(corner_index=index)
        compare = g.Compare.integer.less_than(g.FaceOfCorner(corner_index=index).o.index_in_face, 4)
        edge_neighbors = g.EdgeNeighbors()
        compare_1 = g.Compare.integer.equal(edge_neighbors, 1)
        evaluate_on_domain = g.EvaluateOnDomain.corner.float(compare_1.o.result.edge.at(edges_of_corner.o.next_edge_index) & compare)
        edge_vertices = g.EdgeVertices()
        edge_vertices_1 = g.EdgeVertices()
        face_neighbors = g.FaceNeighbors()
        boolean_math = g.Compare.integer.equal(g.EdgeNeighbors(), 1).o.result.edge.evaluate() | g.Compare.integer.equal(g.VertexNeighbors().o.vertex_count, 1)
        boolean_math_1 = g.Compare.integer.equal(g.EdgeNeighbors(), 1).o.result.edge.evaluate() | g.Compare.integer.equal(g.VertexNeighbors().o.vertex_count, 1)
        named_attribute = g.NamedAttribute.boolean("_o_pinned_smooth_boundary")
        named_attribute_1 = g.NamedAttribute.float("_o_pinned_smooth_normalization")
        named_attribute_2 = g.NamedAttribute.vector("UVMap")
        evaluate_on_domain_1 = named_attribute_2.o.attribute.point.evaluate()
        named_attribute_3 = g.NamedAttribute.boolean("_o_symmetry_weld")
        position = g.Position()
        position_1 = g.Position()
        math_1 = g.Math.maximum(named_attribute_3.o.attribute, g.BlurAttribute.float(named_attribute_3.o.attribute, 4))
        align_rotation_to_vector = g.AlignRotationToVector(vector=g.CombineXYZ(x=direction.x, y=direction.z, z=direction.y), axis="Y")
        rotation_to_euler = align_rotation_to_vector.o.rotation.to_euler()
        position_2 = g.Position().o.position
        compare_2 = position_2.y > 0.000001
        combine_xyz = g.CombineXYZ(x=position_2.x, z=position_2.z)
        math_2 = abs(position_2.y)
        compare_3 = math_2 < 0.000001
        boolean_math_2 = compare_3 | compare_2
        boolean_math_3 = boolean_math.point.evaluate() & compare_3
        math_3 = abs(edge_vertices_1.o.position_1.y).max(abs(edge_vertices_1.o.position_2.y))
        evaluate_at_index = ((math_3 < 0.000001) & g.Compare.integer.equal(edge_neighbors, 2)).edge.at(edges_of_corner.o.next_edge_index)
        math_4 = g.EvaluateOnDomain.corner.float(evaluate_at_index & compare).o.value.face.evaluate() * face_neighbors.o.vertex_count
        vector_math = g.VectorMath.scale(position, named_attribute.o.attribute).o.vector.blur(weight=0.5) * (1.0 / named_attribute_1.o.attribute.max(0.00000001))
        math_5 = 1.0 * g.Normal().o.normal.blur(10).length() * g.Math.maximum(boolean_math_3, g.BlurAttribute.float(boolean_math_3, 4))
        vector_math_1 = named_attribute.o.attribute.switch.vector(position.o.position.blur(), vector_math) - position
        blur_attribute = g.VectorMath.scale(evaluate_on_domain_1, named_attribute.o.attribute).o.vector.blur(weight=0.5)
        switch = named_attribute.o.attribute.switch.vector(evaluate_on_domain_1.blur(), blur_attribute * (1.0 / named_attribute_1.o.attribute.max(0.00000001)))
        vector_math_2 = named_attribute_2.o.attribute + (switch.point.evaluate() - named_attribute_2.o.attribute) * math_5
        math_6 = 0.2 * g.Normal().o.normal.blur(10).length() * g.NamedAttribute.float("_o_pinned_smooth_region_point").o.attribute
        vector_math_3 = g.VectorRotate.euler(g.Position(), rotation=rotation_to_euler, invert=True).o.vector + g.CombineXYZ(y=offset * -1.0)
        store_named_attribute = (
            geometry
            >> g.SetPosition(position=vector_math_3 * g.CombineXYZ(y=scale, x=1.0, z=1.0))
            >> g.StoreNamedAttribute.face.vector(name="o_depth_rotation", value=rotation_to_euler)
        )
        attribute_statistic = g.AttributeStatistic.edge.float(store_named_attribute, attribute=edge_vertices.o.position_1.distance(edge_vertices.o.position_2))
        store_named_attribute_1 = (
            g.DeleteGeometry.face(store_named_attribute, compare_2.point.evaluate())
            >> g.DeleteGeometry.face(selection=evaluate_on_domain.o.value.face.evaluate() * face_neighbors.o.vertex_count > 1.5)
            >> g.SetPosition(selection=boolean_math_2, position=combine_xyz)
            >> g.SetShadeSmooth.face()
            >> g.StoreNamedAttribute.face.float(name="o_depth_face", value=1.0)
        )
        store_named_attribute_2 = g.StoreNamedAttribute.point.boolean(store_named_attribute_1, name="_o_pinned_smooth_boundary", value=boolean_math_1.point.evaluate())
        store_named_attribute_3 = g.StoreNamedAttribute.point.float(store_named_attribute_2, name="_o_pinned_smooth_normalization", value=g.BlurAttribute.float(named_attribute.o.attribute, weight=0.5))
        repeat_zone = g.RepeatZone(smooth)
        geometry_2 = repeat_zone.items.geometry(store_named_attribute_3, "Geometry")
        store_named_attribute_4 = g.StoreNamedAttribute.corner.vector_2d(geometry_2.current, name="UVMap", value=vector_math_2)
        set_position = (
            g.Compare.integer.less_than(repeat_zone.iteration, 4).o.result.switch.geometry(geometry_2.current, store_named_attribute_4)
            >> g.SetPosition(offset=vector_math_1 * math_5)
        )
        set_position >> geometry_2.next
        remove_named_attribute = (
            geometry_2.result
            >> g.RemoveNamedAttribute(name="_o_pinned_smooth_*", pattern_mode="Wildcard")
        )
        delete_geometry = (
            g.Switch.geometry(smooth, store_named_attribute_1, remove_named_attribute)
            >> g.SetPosition(selection=boolean_math_3 | boolean_math_2, position=combine_xyz)
            >> g.DeleteGeometry.face(selection=(math_2.face.evaluate() < 0.000001) & (abs(g.Normal().o.normal.y) > 0.999))
            >> g.DeleteGeometry.face(selection=math_4 > 0.0)
        )
        extrude_mesh = g.ExtrudeMesh.edges(delete_geometry, compare_1.o.result & (math_3 > 0.000001), offset_scale=0.0)
        store_named_attribute_5 = (
            extrude_mesh
            >> g.SetPosition(selection=extrude_mesh.o.top, position=combine_xyz)
            >> g.StoreNamedAttribute.face.boolean(name="_o_symmetry_weld", value=extrude_mesh.o.side.point.evaluate())
            >> g.StoreNamedAttribute.face.float(selection=extrude_mesh.o.side, name="o_depth_face", value=3.0)
        )
        switch_1 = fill_sides.switch.geometry(delete_geometry, store_named_attribute_5)
        store_named_attribute_6 = (
            g.TransformGeometry(geometry=switch_1, scale=(1.0, -1.0, 1.0), mode="Components")
            >> g.FlipFaces()
            >> g.StoreNamedAttribute.face.float(selection=g.Compare.float.equal(g.NamedAttribute.float("o_depth_face").o.attribute, 1.0, 0.001), name="o_depth_face", value=2.0)
            >> g.StoreNamedAttribute.face.integer(name="o_image_region", value=g.NamedAttribute.integer("o_image_region").o.attribute + 2.0)
        )
        merge_by_distance = g.MergeByDistance(geometry=g.JoinGeometry(geometry=(store_named_attribute_6, switch_1)), selection=compare_3, distance=0.000001, mode="All")
        store_named_attribute_7 = g.StoreNamedAttribute.point.float(merge_by_distance, name="_o_pinned_smooth_region_point", value=math_1)
        repeat_zone_1 = g.RepeatZone(smooth)
        geometry_3 = repeat_zone_1.items.geometry(store_named_attribute_7, "Geometry")
        set_position_1 = g.SetPosition(geometry=geometry_3.current, offset=(position_1.o.position.blur() - position_1) * math_6)
        set_position_1 >> geometry_3.next
        remove_named_attribute_1 = (
            geometry_3.result
            >> g.RemoveNamedAttribute(name="_o_pinned_smooth_*", pattern_mode="Wildcard")
        )
        map_range = abs(position_2.x).map_range(from_max=attribute_statistic.o.median * 4.0, to_min=1.0, to_max=0.0, interpolation_type="SMOOTHSTEP")
        (
            fill_sides.switch.geometry(merge_by_distance, g.Switch.geometry(smooth, merge_by_distance, remove_named_attribute_1))
            >> g.StoreNamedAttribute.face.float(name="o_depth_axis", value=1.0)
            >> g.TransformGeometry(rotation=(0.0, 0.0, 1.5707963), mode="Components")
            >> g.StoreNamedAttribute.point.float(name="o_normal_reduction", value=g.NamedAttribute.float("o_normal_reduction").o.attribute.max(map_range))
            >> g.RemoveNamedAttribute(name="_o_*", pattern_mode="Wildcard")
            >> geometry_1
        )

ASSET = OImageCutoutSymmetry

ASSET_METADATA = {
    "catalog_id": "00000000-0000-0000-0000-000000000000",
}
