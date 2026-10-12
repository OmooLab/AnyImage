from bpy.types import GeometryNodeTree
from omoonodes import geometry as g, TreeBuilder
from omoonodes.builder import CustomGeometryGroup


class OImageDepthCutout(CustomGeometryGroup):
    _name = "O Image Depth Cutout"
    _color_tag = "GEOMETRY"
    _tree_properties = {"is_modifier": True}

    def _build_group(self, tree: TreeBuilder[GeometryNodeTree]) -> None:
        geometry = tree.inputs.geometry("Geometry", structure_type="SINGLE", force_non_field=True)
        mode = tree.inputs.menu("Mode", "Balloon", structure_type="SINGLE", force_non_field=True)
        thickness = tree.inputs.float("Thickness", 1.0, description="Control how much the surface bulges in Balloon mode. Zero removes the bulge.", min_value=0.0, max_value=2.0, structure_type="SINGLE", force_non_field=True)
        front_inflation = tree.inputs.float("Front Inflation", 0.2, description="Control how much the front surface bulges in Balloon mode, as a share of the balloon thickness. Zero keeps the original front surface.", min_value=0.0, max_value=1.0, structure_type="SINGLE", subtype="FACTOR", force_non_field=True)
        thickness_1 = tree.inputs.float("Thickness", 0.1, description="Add thickness behind the original surface while keeping the front surface in place.", min_value=0.0, max_value=1.0, structure_type="SINGLE", subtype="DISTANCE", force_non_field=True)
        depth_scale = tree.inputs.float("Depth Scale", 1.0, min_value=0.0, max_value=2.0, structure_type="SINGLE", force_non_field=True)
        depth_split = tree.inputs.float("Depth Split", 0.1, description="Split the mesh where depth changes abruptly. Scaled by Depth Scale: a flat projection stays whole, higher values detect smaller depth jumps.", min_value=0.0, max_value=1.0, structure_type="SINGLE", subtype="FACTOR", force_non_field=True)
        depth_limit = tree.inputs.float("Depth Limit", 1.0, description="Remove faces whose center lies beyond this distance behind the reference plane.", min_value=-1.0, structure_type="SINGLE", subtype="DISTANCE", force_non_field=True)
        with tree.inputs.panel("Options", default_closed=True):
            boundary_smooth = tree.inputs.integer("Boundary Smooth", 4, description="Smooth geometry near the original outline and Depth Split edges. Zero disables boundary smoothing.", min_value=0, max_value=16, structure_type="SINGLE", force_non_field=True)
            rear_smooth = tree.inputs.integer("Rear Smooth", 8, description="Soften the rear surface where the balloon is thick. The strength follows the square root of the balloon profile for a flatter transition while thin geometry and cut boundaries keep their positions.", min_value=0, max_value=16, structure_type="SINGLE", force_non_field=True)
            normal_bias = tree.inputs.float("Normal Bias", 0.0, description="Bias the thickness direction: zero uses the island average without normal blur, negative values turn toward the boundary-stabilized local normal, and positive values turn away from it.", min_value=-2.0, max_value=2.0, structure_type="SINGLE", force_non_field=True)
            reference_depth = tree.inputs.float("Reference Depth", 1.0, min_value=0.0, structure_type="SINGLE", subtype="DISTANCE", force_non_field=True)
        with tree.inputs.panel("Data", default_closed=True):
            uniform_scale = tree.inputs.float("Uniform Scale", 1.0, min_value=0.0, hide_in_modifier=True, structure_type="SINGLE", force_non_field=True)
            depth_image = tree.inputs.image("Depth Image", hide_in_modifier=True, structure_type="SINGLE", force_non_field=True)
        geometry_1 = tree.outputs.geometry("Geometry")

        compare = g.Compare.integer.greater_than(boundary_smooth)
        face_of_corner = g.FaceOfCorner(corner_index=g.CornersOfEdge().o.corner_index)
        face_of_corner_1 = g.FaceOfCorner(corner_index=g.CornersOfEdge(sort_index=1).o.corner_index)
        index = g.Index()
        corners_of_edge = g.CornersOfEdge(edge_index=index)
        corners_of_edge_1 = g.CornersOfEdge(edge_index=index, sort_index=1)
        edge_neighbors = g.EdgeNeighbors()
        evaluate_on_domain = g.EvaluateOnDomain.edge.float(g.Compare.integer.equal(edge_neighbors, 1)).o.value.face.evaluate()
        compare_1 = g.Compare.integer.equal(g.FaceNeighbors().o.vertex_count, 3)
        evaluate_at_index = compare_1.o.result.face.at(g.FaceOfCorner(corner_index=corners_of_edge.o.corner_index).o.face_index)
        evaluate_at_index_1 = compare_1.o.result.face.at(g.FaceOfCorner(corner_index=corners_of_edge_1.o.corner_index).o.face_index)
        boolean_math = g.Compare.integer.equal(g.EdgeNeighbors(), 1).o.result.edge.evaluate() | g.Compare.integer.equal(g.VertexNeighbors().o.vertex_count, 1)
        boolean_math_1 = g.Compare.integer.equal(g.EdgeNeighbors(), 1).o.result.edge.evaluate() | g.Compare.integer.equal(g.VertexNeighbors().o.vertex_count, 1)
        boolean_math_2 = (g.EvaluateOnDomain.point.float(boolean_math_1).o.value.face.evaluate() > 0.99999) & g.Compare.integer.equal(g.FaceNeighbors().o.vertex_count, 3)
        boolean_math_3 = g.Compare.integer.equal(g.EdgeNeighbors(), 1).o.result.edge.evaluate() | g.Compare.integer.equal(g.VertexNeighbors().o.vertex_count, 1)
        evaluate_on_domain_1 = g.EvaluateOnDomain.point.float(boolean_math_3)
        boolean_math_4 = g.Compare.integer.equal(g.EdgeNeighbors(), 1).o.result.edge.evaluate() | g.Compare.integer.equal(g.VertexNeighbors().o.vertex_count, 1)
        boolean_math_5 = g.Compare.integer.equal(g.EdgeNeighbors(), 1).o.result.edge.evaluate() | g.Compare.integer.equal(g.VertexNeighbors().o.vertex_count, 1)
        boolean_math_6 = g.Compare.integer.equal(g.EdgeNeighbors(), 1).o.result.edge.evaluate() | g.Compare.integer.equal(g.VertexNeighbors().o.vertex_count, 1)
        image_texture = g.ImageTexture(image=depth_image, vector=g.NamedAttribute.vector("UVMap").o.attribute.face.evaluate(), extension="EXTEND")
        evaluate_on_domain_2 = g.EvaluateOnDomain.face.vector(image_texture.o.color)
        named_attribute = g.NamedAttribute.boolean("_o_depth_cut")
        evaluate_on_domain_3 = g.EvaluateOnDomain.point.float(g.NamedAttribute.boolean("_o_cut_boundary").o.attribute)
        image_texture_1 = g.ImageTexture(image=depth_image, vector=g.NamedAttribute.vector("UVMap").o.attribute, extension="EXTEND")
        named_attribute_1 = g.NamedAttribute.float("o_balloon")
        named_attribute_2 = g.NamedAttribute.vector("_o_front_normal")
        named_attribute_3 = g.NamedAttribute.float("o_balloon")
        named_attribute_4 = g.NamedAttribute.boolean("_o_pinned_smooth_boundary")
        named_attribute_5 = g.NamedAttribute.float("_o_pinned_smooth_normalization")
        named_attribute_6 = g.NamedAttribute.vector("UVMap")
        evaluate_on_domain_4 = named_attribute_6.o.attribute.point.evaluate()
        evaluate_on_domain_5 = g.NamedAttribute.vector("UVMap").o.attribute.point.evaluate()
        named_attribute_7 = g.NamedAttribute.float("_o_boundary_falloff")
        named_attribute_8 = g.NamedAttribute.integer("_o_leaf_source_index")
        normal = g.Normal()
        position = g.Position()
        position_1 = g.Position()
        position_2 = g.Position()
        position_3 = g.Position()
        menu_switch = g.MenuSwitch.boolean(mode, {"Balloon": False, "Shell": True})
        edges_of_corner = g.EdgesOfCorner(corner_index=g.OffsetCornerInFace(corner_index=corners_of_edge.o.corner_index, offset=1))
        compare_2 = g.Compare.integer.equal(edge_neighbors.o.face_count.edge.at(edges_of_corner.o.next_edge_index), 1)
        offset_corner_in_face = g.OffsetCornerInFace(corner_index=corners_of_edge.o.corner_index, offset=2)
        evaluate_at_index_2 = edge_neighbors.o.face_count.edge.at(g.EdgesOfCorner(corner_index=offset_corner_in_face).o.next_edge_index)
        compare_3 = g.Compare.integer.equal(evaluate_at_index_2, 1)
        edges_of_corner_1 = g.EdgesOfCorner(corner_index=g.OffsetCornerInFace(corner_index=corners_of_edge_1.o.corner_index, offset=1))
        compare_4 = g.Compare.integer.equal(edge_neighbors.o.face_count.edge.at(edges_of_corner_1.o.next_edge_index), 1)
        offset_corner_in_face_1 = g.OffsetCornerInFace(corner_index=corners_of_edge_1.o.corner_index, offset=2)
        evaluate_at_index_3 = edge_neighbors.o.face_count.edge.at(g.EdgesOfCorner(corner_index=offset_corner_in_face_1).o.next_edge_index)
        compare_5 = g.Compare.integer.equal(evaluate_at_index_3, 1)
        boolean_math_7 = (depth_split > 0.0).switch.boolean(true=named_attribute.o.attribute) | boolean_math_4.point.evaluate()
        compare_6 = g.Compare.integer.equal(g.VertexOfCorner(corner_index=corners_of_edge.o.corner_index), g.VertexOfCorner(corner_index=corners_of_edge_1.o.corner_index))
        switch = compare_6.o.result.switch.boolean(compare_2.o.result & compare_4 | compare_3.o.result & compare_5, compare_2.o.result & compare_5 | compare_3.o.result & compare_4)
        boolean_math_8 = switch & g.Compare.integer.equal(edge_neighbors, 2) & evaluate_at_index & evaluate_at_index_1
        compare_7 = g.Compare.integer.not_equal(g.VertexOfCorner(corner_index=offset_corner_in_face), g.VertexOfCorner(corner_index=offset_corner_in_face_1))
        boolean_math_9 = (g.EvaluateOnDomain.edge.float(boolean_math_8 & compare_7).o.value.face.evaluate() > 0.0) | (evaluate_on_domain > 0.99999)
        switch_1 = menu_switch.o.output.switch.float(g.NamedAttribute.float("o_balloon").o.attribute * (thickness * (1.0 + depth_scale)), thickness_1)
        math_1 = evaluate_on_domain_3.o.value.max(evaluate_on_domain_3.o.value.blur(4)).max(g.NamedAttribute.float("_o_boundary_falloff").o.attribute * 0.1)
        switch_2 = menu_switch.o.output.switch.float(named_attribute_3.o.attribute * thickness * front_inflation)
        math_2 = menu_switch.o.output.switch.float(thickness, thickness_1).min(1.0) * named_attribute_3.o.attribute ** 0.5
        math_3 = (g.SeparateXYZ(vector=evaluate_on_domain_2).o.z * uniform_scale - reference_depth) * depth_scale
        compare_8 = math_3 > depth_limit
        math_4 = g.SeparateXYZ(vector=evaluate_on_domain_2).o.z / g.SeparateXYZ(vector=image_texture_1.o.color).o.z
        vector_math = evaluate_on_domain_2.o.value.length()
        evaluate_at_index_4 = vector_math.face.at(face_of_corner.o.face_index)
        evaluate_at_index_5 = vector_math.face.at(face_of_corner_1.o.face_index)
        math_5 = abs(evaluate_at_index_4 - evaluate_at_index_5) * depth_scale * reference_depth.max(0.00000001)
        vector_math_1 = position.o.position.face.at(face_of_corner.o.face_index).distance(position.o.position.face.at(face_of_corner_1.o.face_index))
        math_6 = vector_math_1 * ((evaluate_at_index_4 + evaluate_at_index_5) * 0.5).max(0.00000001) * 2.5
        boolean_math_10 = (math_5 * depth_split > math_6) & (vector_math_1 > 0.0) & g.Compare.integer.equal(g.EdgeNeighbors(), 2)
        delete_geometry = (
            g.StoreNamedAttribute.corner.boolean(geometry, name="_o_depth_cut", value=g.EvaluateOnDomain.edge.float(boolean_math_10).o.value.point.evaluate() > 0.0)
            >> g.SplitEdges(selection=boolean_math_10)
            >> g.DeleteGeometry.face(selection=compare_1.o.result & boolean_math_9)
        )
        switch_3 = ((depth_split > 0.0) & (depth_scale > 0.0)).switch.geometry(geometry, delete_geometry)
        compare_9 = g.AttributeStatistic.face.float(switch_3, attribute=compare_8).o.max > 0.0
        boolean_math_11 = compare_9 & (boolean_math_3 & ~g.NamedAttribute.boolean("_o_depth_limit_boundary").o.attribute)
        evaluate_on_domain_6 = g.EvaluateOnDomain.point.float(boolean_math_3 & (named_attribute.o.attribute | boolean_math_11))
        evaluate_on_domain_7 = evaluate_on_domain_6.o.value.point.evaluate()
        store_named_attribute = g.StoreNamedAttribute.point.boolean(switch_3, name="_o_depth_limit_boundary", value=boolean_math)
        math_7 = g.NamedAttribute.float("o_balloon").o.attribute * (1.0 - evaluate_on_domain_7.max(evaluate_on_domain_7.blur(2)))
        switch_4 = boolean_math_7.switch.vector(image_texture_1.o.color, g.VectorMath.scale(image_texture_1.o.color, math_4).o.vector)
        vector = switch_4.point.evaluate() * uniform_scale
        math_8 = (vector.z - reference_depth) * depth_scale
        mix = depth_scale.mix.vector(g.Position(), g.CombineXYZ(x=vector.x, y=math_8, z=vector.y * -1.0))
        remove_named_attribute = (
            compare_9.switch.geometry(switch_3, g.DeleteGeometry.face(store_named_attribute, compare_8))
            >> g.DeleteGeometry.face(selection=boolean_math_2)
            >> g.StoreNamedAttribute.point.float(name="o_balloon", value=math_7)
            >> g.StoreNamedAttribute.point.boolean(name="_o_cut_boundary", value=evaluate_on_domain_6)
            >> g.SetPosition(position=g.CombineXYZ(x=mix.x, y=math_8, z=mix.z))
            >> g.RemoveNamedAttribute(name="_o_depth_*", pattern_mode="Wildcard")
        )
        attribute_statistic = g.AttributeStatistic.point.float(remove_named_attribute, attribute=switch_1)
        compare_10 = attribute_statistic.o.max > 0.000001
        store_named_attribute_1 = g.StoreNamedAttribute.point.float(remove_named_attribute, name="_o_boundary_falloff", value=evaluate_on_domain_1.o.value.max(evaluate_on_domain_1.o.value.blur(4)))
        switch_5 = (compare.o.result | compare_10).switch.geometry(remove_named_attribute, store_named_attribute_1)
        store_named_attribute_2 = g.StoreNamedAttribute.point.float(switch_5, name="_o_boundary_smooth_weight", value=math_1)
        store_named_attribute_3 = (
            compare.o.result.switch.geometry(switch_5, store_named_attribute_2)
            >> g.RemoveNamedAttribute(name="_o_cut_boundary*", pattern_mode="Wildcard")
            >> g.StoreNamedAttribute.point.integer(name="_o_leaf_source_index", value=g.Index())
        )
        attribute_statistic_1 = g.AttributeStatistic.point.float(store_named_attribute_3, attribute=named_attribute_1.o.attribute)
        math_9 = attribute_statistic.o.max.map_range(interpolation_type="SMOOTHSTEP") ** 0.5
        math_10 = named_attribute_1.o.attribute / attribute_statistic_1.o.max.max(0.000001)
        switch_6 = menu_switch.o.output.switch.float(math_10)
        math_11 = depth_scale.min(1.0) * (1.0 - math_9 * (1.0 - menu_switch.o.output.switch.float(math_10, 1.0)))
        store_named_attribute_4 = g.StoreNamedAttribute.point.float(store_named_attribute_3, name="o_normal_reduction", value=g.Math.subtract(1.0, math_11, use_clamp=True))
        math_12 = switch_6 + (1.0 - switch_6) * (0.25 * g.NamedAttribute.float("_o_boundary_falloff").o.attribute)
        vector_math_2 = normal.o.normal.point.total(g.MeshIsland().o.island_index).normalize()
        vector_math_3 = vector_math_2 + (vector_math_2 - normal.o.normal.blur(128)) * ((1.0 - math_12) * normal_bias)
        switch_7 = g.Compare.float.equal(normal_bias, 0.0, 0.0).o.result.switch.vector(vector_math_3.normalize(), vector_math_2)
        store_named_attribute_5 = g.StoreNamedAttribute.point.vector(store_named_attribute_4, name="_o_front_normal", value=switch_7)
        switch_8 = compare_10.switch.geometry(store_named_attribute_4, store_named_attribute_5)
        store_named_attribute_6 = (
            g.SetPosition(geometry=switch_8, offset=named_attribute_2.o.attribute * switch_2)
            >> g.StoreNamedAttribute.face.integer(name="o_image_region")
            >> g.StoreNamedAttribute.point.integer(name="_o_leaf_id")
        )
        store_named_attribute_7 = (
            g.SetPosition(geometry=switch_8, offset=(named_attribute_2.o.attribute * (switch_1 * -1.0)).face.evaluate())
            >> g.SetPosition(offset=(position_1.o.position.blur(rear_smooth) - position_1) * math_2)
            >> g.FlipFaces()
            >> g.StoreNamedAttribute.face.integer(name="o_image_region", value=1)
            >> g.StoreNamedAttribute.point.integer(name="_o_leaf_id", value=1)
        )
        remove_named_attribute_1 = (
            compare_10.switch.geometry(store_named_attribute_6, g.JoinGeometry(geometry=(store_named_attribute_7, store_named_attribute_6)))
            >> g.RemoveNamedAttribute(name="_o_front_normal*", pattern_mode="Wildcard")
        )
        store_named_attribute_8 = g.StoreNamedAttribute.point.boolean(remove_named_attribute_1, name="_o_pinned_smooth_boundary", value=boolean_math_5.point.evaluate())
        store_named_attribute_9 = g.StoreNamedAttribute.point.float(store_named_attribute_8, name="_o_pinned_smooth_normalization", value=g.BlurAttribute.float(named_attribute_4.o.attribute, weight=0.5))
        repeat_zone = g.RepeatZone(boundary_smooth)
        geometry_2 = repeat_zone.items.geometry(store_named_attribute_9, "Geometry")
        vector_math_4 = g.VectorMath.scale(position_2, named_attribute_4.o.attribute).o.vector.blur(weight=0.5) * (1.0 / named_attribute_5.o.attribute.max(0.00000001))
        math_13 = 1.0 * g.Normal().o.normal.blur(10).length() * g.NamedAttribute.float("_o_boundary_smooth_weight").o.attribute
        vector_math_5 = named_attribute_4.o.attribute.switch.vector(position_2.o.position.blur(), vector_math_4) - position_2
        blur_attribute = g.VectorMath.scale(evaluate_on_domain_4, named_attribute_4.o.attribute).o.vector.blur(weight=0.5)
        switch_9 = named_attribute_4.o.attribute.switch.vector(evaluate_on_domain_4.blur(), blur_attribute * (1.0 / named_attribute_5.o.attribute.max(0.00000001)))
        vector_math_6 = named_attribute_6.o.attribute + (switch_9.point.evaluate() - named_attribute_6.o.attribute) * math_13
        store_named_attribute_10 = g.StoreNamedAttribute.corner.vector_2d(geometry_2.current, name="UVMap", value=vector_math_6)
        set_position = (
            g.Compare.integer.less_than(repeat_zone.iteration, 4).o.result.switch.geometry(geometry_2.current, store_named_attribute_10)
            >> g.SetPosition(offset=vector_math_5 * math_13)
        )
        set_position >> geometry_2.next
        remove_named_attribute_2 = (
            geometry_2.result
            >> g.RemoveNamedAttribute(name="_o_pinned_smooth_*", pattern_mode="Wildcard")
        )
        remove_named_attribute_3 = g.RemoveNamedAttribute(geometry=g.Switch.geometry(boundary_smooth, remove_named_attribute_1, remove_named_attribute_2), name="_o_boundary_smooth_weight*", pattern_mode="Wildcard")
        vector_math_7 = (evaluate_on_domain_5.blur(4) - evaluate_on_domain_5) * (0.5 * named_attribute_7.o.attribute * math_9)
        store_named_attribute_11 = (
            g.StoreNamedAttribute.point.vector(remove_named_attribute_3, name="_o_side_base_uv", value=evaluate_on_domain_5 + vector_math_7)
            >> g.StoreNamedAttribute.point.vector(name="_o_side_top_uv", value=evaluate_on_domain_5)
            >> g.StoreNamedAttribute.corner.vector_2d(selection=named_attribute_7.o.attribute > 0.00000001, name="UVMap", value=g.NamedAttribute.vector("_o_side_base_uv").o.attribute)
        )
        separate_geometry = (
            compare_10.switch.geometry(remove_named_attribute_3, store_named_attribute_11)
            >> g.SeparateGeometry.point(selection=g.Compare.integer.equal(g.NamedAttribute.integer("_o_leaf_id").o.attribute, 1))
        )
        sort_elements = g.SortElements.point(separate_geometry.o.selection, sort_weight=named_attribute_8.o.attribute)
        sample_index = g.SampleIndex.point.vector(sort_elements, g.Position(), named_attribute_8.o.attribute)
        sample_index_1 = g.SampleIndex.point.vector(sort_elements, g.Normal().o.normal, named_attribute_8.o.attribute)
        vector_math_8 = (g.Normal().o.normal - sample_index_1).normalize()
        vector_math_9 = position_3.o.position.blur() - position_3
        vector_math_10 = (vector_math_9 - vector_math_8 * vector_math_9.dot(vector_math_8)).normalize() * (position_3.o.position.distance(sample_index) * -0.125)
        store_named_attribute_12 = g.StoreNamedAttribute.point.vector(separate_geometry.o.inverted, name="_o_side_ring_target", value=(position_3.o.position + sample_index) * 0.5 + vector_math_10)
        sort_elements_1 = g.SortElements.point(store_named_attribute_12, sort_weight=named_attribute_8.o.attribute)
        sample_index_2 = g.SampleIndex.point.vector(sort_elements_1, g.NamedAttribute.vector("_o_side_ring_target").o.attribute, named_attribute_8.o.attribute)
        store_named_attribute_13 = g.StoreNamedAttribute.point.vector(separate_geometry.o.selection, name="_o_side_ring_target", value=sample_index_2)
        extrude_mesh = g.ExtrudeMesh.edges(g.JoinGeometry(geometry=(store_named_attribute_13, store_named_attribute_12)), boolean_math_6, (0.0, -1.0, 0.0))
        switch_10 = extrude_mesh.o.top.switch.vector(g.NamedAttribute.vector("_o_side_base_uv").o.attribute, g.NamedAttribute.vector("_o_side_top_uv").o.attribute)
        separate_geometry_1 = (
            extrude_mesh
            >> g.SetPosition(selection=extrude_mesh.o.top, position=g.NamedAttribute.vector("_o_side_ring_target").o.attribute)
            >> g.StoreNamedAttribute.corner.vector_2d(selection=extrude_mesh.o.side, name="UVMap", value=switch_10.point.evaluate())
            >> g.SeparateGeometry.face(selection=extrude_mesh.o.side)
        )
        store_named_attribute_14 = g.StoreNamedAttribute.point.float(g.JoinGeometry(geometry=(separate_geometry_1.o.selection, store_named_attribute_13)), name="o_normal_reduction", value=1.0)
        merge_by_distance = g.MergeByDistance(geometry=g.JoinGeometry(geometry=(store_named_attribute_14, store_named_attribute_12)), distance=0.000001, mode="All")
        (
            compare_10.switch.geometry(separate_geometry.o.inverted, merge_by_distance)
            >> g.RemoveNamedAttribute(name="_o_*", pattern_mode="Wildcard")
            >> g.SetShadeSmooth.face()
            >> geometry_1
        )

ASSET = OImageDepthCutout

ASSET_METADATA = {
    "catalog_id": "00000000-0000-0000-0000-000000000000",
}
