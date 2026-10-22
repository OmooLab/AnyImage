from bpy.types import GeometryNodeTree
from omoonodes import geometry as g, TreeBuilder
from omoonodes.builder import CustomGeometryGroup


class OImageDepthPanorama(CustomGeometryGroup):
    _name = "O Image Depth Panorama"
    _tree_properties = {"is_modifier": True}

    def _build_group(self, tree: TreeBuilder[GeometryNodeTree]) -> None:
        geometry = tree.inputs.geometry("Geometry", structure_type="SINGLE", force_non_field=True)
        subdivide = tree.inputs.integer("Subdivide", 8, description="Increase mesh density to represent finer shapes. Higher levels create more vertices and require more processing time.", min_value=0, max_value=10, structure_type="SINGLE", force_non_field=True)
        dome_radius = tree.inputs.float("Dome Radius", 50.0, description="Radius of the sphere kept at Depth Scale 0, and where mask areas below Mask Threshold land.", min_value=1.0, max_value=100.0, structure_type="SINGLE", subtype="DISTANCE", force_non_field=True)
        depth_scale = tree.inputs.float("Depth Scale", 1.0, description="Blend between a sphere at zero and the estimated depth surface at one.", min_value=0.0, max_value=1.0, structure_type="SINGLE", subtype="FACTOR", force_non_field=True)
        depth_split = tree.inputs.float("Depth Split", 0.1, description="Split the mesh where depth changes abruptly. Scaled by Depth Scale: a flat projection stays whole, higher values detect smaller depth jumps.", min_value=0.0, max_value=1.0, structure_type="SINGLE", subtype="FACTOR", force_non_field=True)
        depth_mask = tree.inputs.boolean("Depth Mask", True, description="Remove mesh areas marked invalid by the depth mask; with the mask off, they rest on the dome sphere.", structure_type="SINGLE", force_non_field=True)
        with tree.inputs.panel("Options", default_closed=True):
            boundary_smooth = tree.inputs.integer("Boundary Smooth", 2, description="Smooth depth and geometry near cut edges on the panorama surface. Zero disables boundary smoothing.", min_value=0, max_value=16, structure_type="SINGLE", force_non_field=True)
            mask_threshold = tree.inputs.float("Mask Threshold", 0.9, description="Set the minimum depth mask value treated as valid. Higher values exclude more partially valid boundary areas.", min_value=0.0, max_value=0.99, structure_type="SINGLE", subtype="FACTOR", force_non_field=True)
        with tree.inputs.panel("Data", default_closed=True):
            depth_image = tree.inputs.image("Depth Image", hide_in_modifier=True, structure_type="SINGLE", force_non_field=True)
        geometry_1 = tree.outputs.geometry("Geometry")

        face_of_corner = g.FaceOfCorner(corner_index=g.CornersOfEdge().o.corner_index)
        face_of_corner_1 = g.FaceOfCorner(corner_index=g.CornersOfEdge(sort_index=1).o.corner_index)
        boolean_math = g.Compare.integer.equal(g.EdgeNeighbors(), 1).o.result.edge.evaluate() | g.Compare.integer.equal(g.VertexNeighbors().o.vertex_count, 1)
        boolean_math_1 = g.Compare.integer.equal(g.EdgeNeighbors(), 1).o.result.edge.evaluate() | g.Compare.integer.equal(g.VertexNeighbors().o.vertex_count, 1)
        evaluate_on_domain = g.EvaluateOnDomain.point.float(boolean_math_1)
        boolean_math_2 = g.Compare.integer.equal(g.EdgeNeighbors(), 1).o.result.edge.evaluate() | g.Compare.integer.equal(g.VertexNeighbors().o.vertex_count, 1)
        evaluate_on_domain_1 = g.EvaluateOnDomain.point.float(boolean_math_2)
        boolean_math_3 = g.Compare.integer.equal(g.EdgeNeighbors(), 1).o.result.edge.evaluate() | g.Compare.integer.equal(g.VertexNeighbors().o.vertex_count, 1)
        boolean_math_4 = g.Compare.integer.equal(g.EdgeNeighbors(), 1).o.result.edge.evaluate() | g.Compare.integer.equal(g.VertexNeighbors().o.vertex_count, 1)
        evaluate_on_domain_2 = g.EvaluateOnDomain.point.float(boolean_math_4)
        boolean_math_5 = g.Compare.integer.equal(g.EdgeNeighbors(), 1).o.result.edge.evaluate() | g.Compare.integer.equal(g.VertexNeighbors().o.vertex_count, 1)
        named_attribute = g.NamedAttribute.boolean("_o_depth_cut")
        named_attribute_1 = g.NamedAttribute.boolean("_o_pinned_smooth_boundary")
        named_attribute_2 = g.NamedAttribute.float("_o_pinned_smooth_normalization")
        named_attribute_3 = g.NamedAttribute.vector("UVMap")
        evaluate_on_domain_3 = named_attribute_3.o.attribute.point.evaluate()
        named_attribute_4 = g.NamedAttribute.boolean("_o_pinned_smooth_boundary")
        named_attribute_5 = g.NamedAttribute.float("_o_pinned_smooth_normalization")
        named_attribute_6 = g.NamedAttribute.vector("UVMap")
        evaluate_on_domain_4 = named_attribute_6.o.attribute.point.evaluate()
        position = g.Position()
        evaluate_on_domain_5 = position.o.position.face.evaluate()
        position_1 = g.Position()
        position_2 = g.Position()
        edges_of_corner = g.EdgesOfCorner(corner_index=g.OffsetCornerInFace(corner_index=g.CornersOfFace(face_index=g.Index()).o.corner_index))
        compare = g.Compare.integer.equal(g.EdgeNeighbors().o.face_count.edge.at(edges_of_corner.o.next_edge_index), 1)
        offset_corner_in_face = g.OffsetCornerInFace(corner_index=g.CornersOfFace(face_index=g.Index()).o.corner_index, offset=1)
        evaluate_at_index = g.EdgeNeighbors().o.face_count.edge.at(g.EdgesOfCorner(corner_index=offset_corner_in_face).o.next_edge_index)
        offset_corner_in_face_1 = g.OffsetCornerInFace(corner_index=g.CornersOfFace(face_index=g.Index()).o.corner_index, offset=2)
        evaluate_at_index_1 = g.EdgeNeighbors().o.face_count.edge.at(g.EdgesOfCorner(corner_index=offset_corner_in_face_1).o.next_edge_index)
        offset_corner_in_face_2 = g.OffsetCornerInFace(corner_index=g.CornersOfFace(face_index=g.Index()).o.corner_index, offset=3)
        evaluate_at_index_2 = g.EdgeNeighbors().o.face_count.edge.at(g.EdgesOfCorner(corner_index=offset_corner_in_face_2).o.next_edge_index)
        boolean_math_6 = g.Compare.integer.equal(evaluate_at_index, 1).o.result & g.Compare.integer.equal(evaluate_at_index_2, 1)
        boolean_math_7 = g.Compare.integer.equal(g.FaceNeighbors().o.vertex_count, 4).o.result & (compare.o.result & g.Compare.integer.equal(evaluate_at_index_1, 1) | boolean_math_6)
        boolean_math_8 = (depth_split > 0.0).switch.boolean(true=named_attribute.o.attribute) | boolean_math.point.evaluate()
        switch = (~named_attribute.o.attribute).switch.float(evaluate_on_domain_1)
        evaluate_on_domain_6 = switch.point.evaluate()
        switch_1 = g.BooleanMath.l_not().o.boolean.switch.float(evaluate_on_domain_2)
        evaluate_on_domain_7 = switch_1.point.evaluate()
        math_1 = 2.0 ** subdivide + 1.0
        math_2 = 0.5 / g.ImageInfo(image=depth_image).o.height
        math_3 = 0.5 / g.ImageInfo(image=depth_image).o.height
        math_4 = 0.5 / g.ImageInfo(image=depth_image).o.height
        math_5 = 0.5 / g.ImageInfo(image=depth_image).o.height
        math_6 = evaluate_on_domain.o.value.max(evaluate_on_domain.o.value.blur(2))
        evaluate_on_domain_8 = (evaluate_on_domain_1.o.value - switch).max(0.0).point.evaluate()
        math_7 = evaluate_on_domain_6.max(evaluate_on_domain_6.blur(2)).max(evaluate_on_domain_8.max(evaluate_on_domain_8.blur(2)) * 1.0)
        evaluate_on_domain_9 = (evaluate_on_domain_2.o.value - switch_1).max(0.0).point.evaluate()
        math_8 = evaluate_on_domain_7.max(evaluate_on_domain_7.blur(2)).max(evaluate_on_domain_9.max(evaluate_on_domain_9.blur(2)) * 1.0)
        position_3 = g.Position().o.position
        math_9 = position_3.x * position_3.x
        math_10 = position_3.y * position_3.y
        math_11 = position_3.z * position_3.z
        combine_xyz = g.CombineXYZ(x=position_3.x * (1.0 - (math_10 + math_11) / 2.0 + math_10 * math_11 / 3.0).sqrt(), y=position_3.y * (1.0 - (math_11 + math_9) / 2.0 + math_11 * math_9 / 3.0).sqrt(), z=position_3.z * (1.0 - (math_9 + math_10) / 2.0 + math_9 * math_10 / 3.0).sqrt())
        vector = position.o.position.normalize()
        math_12 = vector.y.atan2(-vector.x) / 6.2831855
        math_13 = 1.0 - g.Math.maximum(-1.0, g.Math.minimum(1.0, vector.z)).o.value.acos() / 3.1415927
        evaluate_on_domain_10 = g.CombineXYZ(x=math_12, y=math_13).o.vector.point.evaluate()
        separate_xyz = g.SeparateXYZ(vector=evaluate_on_domain_10)
        image_texture = g.ImageTexture(image=depth_image, vector=g.CombineXYZ(x=separate_xyz.o.x, y=math_2.max(separate_xyz.o.y.min(1.0 - math_2))))
        separate_xyz_1 = g.SeparateXYZ(vector=evaluate_on_domain_10)
        image_texture_1 = g.ImageTexture(image=depth_image, vector=g.CombineXYZ(x=separate_xyz_1.o.x, y=math_3.max(separate_xyz_1.o.y.min(1.0 - math_3))), interpolation="Closest")
        switch_2 = (image_texture.o.color.a < image_texture_1.o.color.a - 0.000001).switch.color(image_texture.o.color, image_texture_1.o.color)
        evaluate_on_domain_11 = g.EvaluateOnDomain.point.vector(switch_2)
        vector_1 = evaluate_on_domain_5.normalize()
        math_14 = vector_1.y.atan2(-vector_1.x) / 6.2831855
        combine_xyz_1 = g.CombineXYZ(x=math_14, y=1.0 - g.Math.maximum(-1.0, g.Math.minimum(1.0, vector_1.z)).o.value.acos() / 3.1415927)
        combine_xyz_2 = g.CombineXYZ(x=(abs(vector.z) > 0.999999).switch.float(math_12 + (math_14 - math_12).round(), math_14), y=math_13)
        store_named_attribute = (
            g.Cube(vertices_x=math_1, vertices_y=math_1, vertices_z=math_1, size=(2.0, 2.0, 2.0))
            >> g.SetPosition(position=combine_xyz)
            >> g.StoreNamedAttribute.corner.vector_2d(name="UVMap", value=combine_xyz_2)
        )
        separate_xyz_2 = g.SeparateXYZ(vector=combine_xyz_1)
        image_texture_2 = g.ImageTexture(image=depth_image, vector=g.CombineXYZ(x=separate_xyz_2.o.x, y=math_4.max(separate_xyz_2.o.y.min(1.0 - math_4))))
        separate_xyz_3 = g.SeparateXYZ(vector=combine_xyz_1)
        image_texture_3 = g.ImageTexture(image=depth_image, vector=g.CombineXYZ(x=separate_xyz_3.o.x, y=math_5.max(separate_xyz_3.o.y.min(1.0 - math_5))), interpolation="Closest")
        separate_geometry = g.SeparateGeometry.face(store_named_attribute, image_texture_3.o.color.a.face.evaluate() < mask_threshold)
        switch_3 = (image_texture_2.o.color.a < image_texture_3.o.color.a - 0.000001).switch.color(image_texture_2.o.color, image_texture_3.o.color)
        separate_xyz_4 = g.SeparateXYZ(vector=switch_3)
        evaluate_at_index_3 = separate_xyz_4.o.x.face.at(face_of_corner.o.face_index)
        evaluate_at_index_4 = separate_xyz_4.o.x.face.at(face_of_corner_1.o.face_index)
        math_15 = abs(evaluate_at_index_3 - evaluate_at_index_4) * depth_scale * g.Math.maximum(1.0, 0.00000001)
        vector_math = evaluate_on_domain_5.face.at(face_of_corner.o.face_index).distance(evaluate_on_domain_5.face.at(face_of_corner_1.o.face_index))
        compare_1 = math_15 * depth_split > vector_math * ((evaluate_at_index_3 + evaluate_at_index_4) * 0.5).max(0.00000001) * 2.5
        boolean_math_9 = compare_1 & (vector_math > 0.0) & g.Compare.integer.equal(g.EdgeNeighbors(), 2)
        delete_geometry = (
            g.StoreNamedAttribute.corner.boolean(separate_geometry.o.inverted, name="_o_depth_cut", value=g.EvaluateOnDomain.edge.float(boolean_math_9).o.value.point.evaluate() > 0.0)
            >> g.SplitEdges(selection=boolean_math_9)
            >> g.DeleteGeometry.face(selection=boolean_math_7)
        )
        vector_math_1 = evaluate_on_domain_11.o.value * (g.EvaluateOnDomain.face.vector(switch_3).o.value.z / evaluate_on_domain_11.o.value.z)
        evaluate_on_domain_12 = boolean_math_8.switch.vector(evaluate_on_domain_11, vector_math_1).point.evaluate().x.point.evaluate()
        mix = g.Mix.float(math_6, evaluate_on_domain_12, evaluate_on_domain_12.blur(boundary_smooth, 0.5), clamp_factor=True)
        switch_4 = g.Switch.float(boundary_smooth, evaluate_on_domain_12, g.Switch.float(math_6, evaluate_on_domain_12, mix.o.result_float))
        remove_named_attribute = (
            ((depth_split > 0.0) & (depth_scale > 0.0)).switch.geometry(separate_geometry.o.inverted, delete_geometry)
            >> g.SetPosition(position=position.o.position * (dome_radius + depth_scale * (switch_4.o.output - dome_radius)))
            >> g.RemoveNamedAttribute(name="_o_*", pattern_mode="Wildcard")
        )
        store_named_attribute_1 = g.StoreNamedAttribute.point.boolean(remove_named_attribute, name="_o_pinned_smooth_boundary", value=boolean_math_3.point.evaluate())
        store_named_attribute_2 = g.StoreNamedAttribute.point.float(store_named_attribute_1, name="_o_pinned_smooth_normalization", value=g.BlurAttribute.float(named_attribute_1.o.attribute, weight=0.5))
        repeat_zone = g.RepeatZone(boundary_smooth)
        geometry_2 = repeat_zone.items.geometry(store_named_attribute_2, "Geometry")
        vector_math_2 = g.VectorMath.scale(position_1, named_attribute_1.o.attribute).o.vector.blur(weight=0.5) * (1.0 / named_attribute_2.o.attribute.max(0.00000001))
        math_16 = 1.0 * g.Normal().o.normal.blur(10).length() * math_7
        vector_math_3 = named_attribute_1.o.attribute.switch.vector(position_1.o.position.blur(), vector_math_2) - position_1
        blur_attribute = g.VectorMath.scale(evaluate_on_domain_3, named_attribute_1.o.attribute).o.vector.blur(weight=0.5)
        switch_5 = named_attribute_1.o.attribute.switch.vector(evaluate_on_domain_3.blur(), blur_attribute * (1.0 / named_attribute_2.o.attribute.max(0.00000001)))
        vector_math_4 = named_attribute_3.o.attribute + (switch_5.point.evaluate() - named_attribute_3.o.attribute) * math_16
        store_named_attribute_3 = g.StoreNamedAttribute.corner.vector_2d(geometry_2.current, name="UVMap", value=vector_math_4)
        set_position = (
            g.Compare.integer.less_than(repeat_zone.iteration, 4).o.result.switch.geometry(geometry_2.current, store_named_attribute_3)
            >> g.SetPosition(offset=vector_math_3 * math_16)
        )
        set_position >> geometry_2.next
        remove_named_attribute_1 = (
            geometry_2.result
            >> g.RemoveNamedAttribute(name="_o_pinned_smooth_*", pattern_mode="Wildcard")
        )
        switch_6 = g.Switch.geometry(boundary_smooth, remove_named_attribute, remove_named_attribute_1)
        vector_math_5 = position.o.position * dome_radius
        set_position_1 = separate_geometry >> g.SetPosition(position=vector_math_5)
        store_named_attribute_4 = g.StoreNamedAttribute.point.boolean(set_position_1, name="_o_pinned_smooth_boundary", value=boolean_math_5.point.evaluate())
        store_named_attribute_5 = g.StoreNamedAttribute.point.float(store_named_attribute_4, name="_o_pinned_smooth_normalization", value=g.BlurAttribute.float(named_attribute_4.o.attribute, weight=0.5))
        repeat_zone_1 = g.RepeatZone(boundary_smooth)
        geometry_3 = repeat_zone_1.items.geometry(store_named_attribute_5, "Geometry")
        vector_math_6 = g.VectorMath.scale(position_2, named_attribute_4.o.attribute).o.vector.blur(weight=0.5) * (1.0 / named_attribute_5.o.attribute.max(0.00000001))
        math_17 = 1.0 * g.Normal().o.normal.blur(10).length() * math_8
        vector_math_7 = named_attribute_4.o.attribute.switch.vector(position_2.o.position.blur(), vector_math_6) - position_2
        blur_attribute_1 = g.VectorMath.scale(evaluate_on_domain_4, named_attribute_4.o.attribute).o.vector.blur(weight=0.5)
        switch_7 = named_attribute_4.o.attribute.switch.vector(evaluate_on_domain_4.blur(), blur_attribute_1 * (1.0 / named_attribute_5.o.attribute.max(0.00000001)))
        vector_math_8 = named_attribute_6.o.attribute + (switch_7.point.evaluate() - named_attribute_6.o.attribute) * math_17
        store_named_attribute_6 = g.StoreNamedAttribute.corner.vector_2d(geometry_3.current, name="UVMap", value=vector_math_8)
        set_position_2 = (
            g.Compare.integer.less_than(repeat_zone_1.iteration, 4).o.result.switch.geometry(geometry_3.current, store_named_attribute_6)
            >> g.SetPosition(offset=vector_math_7 * math_17)
        )
        set_position_2 >> geometry_3.next
        remove_named_attribute_2 = (
            geometry_3.result
            >> g.RemoveNamedAttribute(name="_o_pinned_smooth_*", pattern_mode="Wildcard")
        )
        join_geometry = g.JoinGeometry(geometry=(g.Switch.geometry(boundary_smooth, set_position_1, remove_named_attribute_2), switch_6))
        switch_8 = (~(depth_scale > 0.0) & ~depth_mask).switch.geometry(join_geometry, g.SetPosition(geometry=store_named_attribute, position=vector_math_5))
        set_shade_smooth = (
            depth_mask.switch.geometry(switch_8, switch_6)
            >> g.FlipFaces()
            >> g.SetShadeSmooth.face()
        )
        (
            g.JoinGeometry(geometry=(geometry, set_shade_smooth))
            >> g.SetMaterialIndex()
            >> g.DeleteGeometry.point(selection=g.Compare.integer.less_than(g.Index(), g.DomainSize(geometry=geometry).o.point_count))
            >> geometry_1
        )

ASSET = OImageDepthPanorama

ASSET_METADATA = {
    "catalog_id": "00000000-0000-0000-0000-000000000000",
}
