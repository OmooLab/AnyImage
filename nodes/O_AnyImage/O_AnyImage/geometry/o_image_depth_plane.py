from ..geometry.o_image_plane import OImagePlane
from bpy.types import GeometryNodeTree
from omoonodes import geometry as g, TreeBuilder
from omoonodes.builder import CustomGeometryGroup


class OImageDepthPlane(CustomGeometryGroup):
    _name = "O Image Depth Plane"
    _color_tag = "GEOMETRY"
    _tree_properties = {"description": "Build a camera-projected image shell.", "is_modifier": True}

    def _build_group(self, tree: TreeBuilder[GeometryNodeTree]) -> None:
        geometry = tree.inputs.geometry("Geometry", structure_type="SINGLE", force_non_field=True)
        subdivide = tree.inputs.integer("Subdivide", 6, description="Increase mesh density to represent finer shapes. Higher levels create more vertices and require more processing time.", min_value=0, max_value=10, structure_type="SINGLE", force_non_field=True)
        thickness = tree.inputs.float("Thickness", 0.0, description="Add shell thickness inward from the depth surface. Zero keeps a single surface.", min_value=0.0, structure_type="SINGLE", subtype="DISTANCE", force_non_field=True)
        depth_scale = tree.inputs.float("Depth Scale", 1.0, min_value=0.0, max_value=2.0, structure_type="SINGLE", force_non_field=True)
        depth_split = tree.inputs.float("Depth Split", 0.1, description="Split the mesh where depth changes abruptly. Scaled by Depth Scale: a flat projection stays whole, higher values detect smaller depth jumps.", min_value=0.0, max_value=1.0, structure_type="SINGLE", subtype="FACTOR", force_non_field=True)
        depth_mask = tree.inputs.boolean("Depth Mask", True, description="Remove mesh areas marked invalid by the depth mask.", structure_type="SINGLE", force_non_field=True)
        with tree.inputs.panel("Options", default_closed=True):
            boundary_smooth = tree.inputs.integer("Boundary Smooth", 4, description="Smooth depth and geometry near cut edges while preserving the original image border. Zero disables boundary smoothing.", min_value=0, max_value=16, structure_type="SINGLE", force_non_field=True)
            mask_threshold = tree.inputs.float("Mask Threshold", 0.9, description="Set the minimum depth mask value treated as valid. Higher values exclude more partially valid boundary areas.", min_value=0.0, max_value=0.99, structure_type="SINGLE", subtype="FACTOR", force_non_field=True)
            reference_depth = tree.inputs.float("Reference Depth", 1.0, min_value=0.0, structure_type="SINGLE", subtype="DISTANCE", force_non_field=True)
        with tree.inputs.panel("Data", default_closed=True):
            uniform_scale = tree.inputs.float("Uniform Scale", 1.0, min_value=0.0, hide_in_modifier=True, structure_type="SINGLE", force_non_field=True)
            depth_image = tree.inputs.image("Depth Image", hide_in_modifier=True, structure_type="SINGLE", force_non_field=True)
        geometry_1 = tree.outputs.geometry("Geometry")

        face_of_corner = g.FaceOfCorner(corner_index=g.CornersOfEdge().o.corner_index)
        face_of_corner_1 = g.FaceOfCorner(corner_index=g.CornersOfEdge(sort_index=1).o.corner_index)
        o_image_plane = OImagePlane(Geometry=geometry, Subdivide=subdivide)
        index = g.Index()
        boolean_math = g.Compare.integer.equal(g.EdgeNeighbors(), 1).o.result.edge.evaluate() | g.Compare.integer.equal(g.VertexNeighbors().o.vertex_count, 1)
        boolean_math_1 = g.Compare.integer.equal(g.EdgeNeighbors(), 1).o.result.edge.evaluate() | g.Compare.integer.equal(g.VertexNeighbors().o.vertex_count, 1)
        boolean_math_2 = g.Compare.integer.equal(g.EdgeNeighbors(), 1).o.result.edge.evaluate() | g.Compare.integer.equal(g.VertexNeighbors().o.vertex_count, 1)
        evaluate_on_domain = g.EvaluateOnDomain.point.float(boolean_math_2)
        boolean_math_3 = g.Compare.integer.equal(g.EdgeNeighbors(), 1).o.result.edge.evaluate() | g.Compare.integer.equal(g.VertexNeighbors().o.vertex_count, 1)
        named_attribute = g.NamedAttribute.vector("UVMap")
        image_texture = g.ImageTexture(image=depth_image, vector=named_attribute.o.attribute, extension="EXTEND")
        image_texture_1 = g.ImageTexture(image=depth_image, vector=g.NamedAttribute.vector("UVMap").o.attribute.face.evaluate(), extension="EXTEND")
        evaluate_on_domain_1 = g.EvaluateOnDomain.face.vector(image_texture_1.o.color)
        named_attribute_1 = g.NamedAttribute.boolean("_o_depth_cut")
        named_attribute_2 = g.NamedAttribute.boolean("_o_pinned_smooth_boundary")
        named_attribute_3 = g.NamedAttribute.float("_o_pinned_smooth_normalization")
        named_attribute_4 = g.NamedAttribute.vector("UVMap")
        evaluate_on_domain_2 = named_attribute_4.o.attribute.point.evaluate()
        position = g.Position()
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
        boolean_math_4 = g.Compare.integer.equal(evaluate_at_index, 1).o.result & g.Compare.integer.equal(evaluate_at_index_2, 1)
        boolean_math_5 = g.Compare.integer.equal(g.FaceNeighbors().o.vertex_count, 4).o.result & (compare.o.result & g.Compare.integer.equal(evaluate_at_index_1, 1) | boolean_math_4)
        switch = depth_mask.switch.geometry(o_image_plane, g.DeleteGeometry.face(o_image_plane, image_texture.o.color.a < mask_threshold))
        boolean_math_6 = (depth_split > 0.0).switch.boolean(true=named_attribute_1.o.attribute) | boolean_math.point.evaluate()
        switch_1 = (~named_attribute_1.o.attribute).switch.float(evaluate_on_domain)
        math_1 = named_attribute.o.attribute.x.min(named_attribute.o.attribute.y).min((1.0 - named_attribute.o.attribute.x).min(1.0 - named_attribute.o.attribute.y))
        evaluate_on_domain_3 = (math_1 < 0.000001).point.evaluate()
        switch_2 = evaluate_on_domain_3.switch.float(g.EvaluateOnDomain.point.float(boolean_math_1))
        switch_3 = evaluate_on_domain_3.switch.float(switch_1.point.evaluate())
        switch_4 = evaluate_on_domain_3.switch.float((evaluate_on_domain.o.value - switch_1).max(0.0).point.evaluate())
        switch_5 = evaluate_on_domain_3.switch.float(switch_2.max(switch_2.blur(2)))
        math_2 = evaluate_on_domain_3.switch.float(switch_3.max(switch_3.blur(2))).max(evaluate_on_domain_3.switch.float(switch_4.max(switch_4.blur(2))) * 1.0)
        integer_math = g.IntegerMath(value=position_2.o.position.x, value_001=g.IntegerMath.multiply(position_2.o.position.z, 4096))
        vector_math = evaluate_on_domain_1.o.value.length()
        evaluate_at_index_3 = vector_math.face.at(face_of_corner.o.face_index)
        evaluate_at_index_4 = vector_math.face.at(face_of_corner_1.o.face_index)
        math_3 = abs(evaluate_at_index_3 - evaluate_at_index_4) * depth_scale * reference_depth.max(0.00000001)
        vector_math_1 = position.o.position.face.at(face_of_corner.o.face_index).distance(position.o.position.face.at(face_of_corner_1.o.face_index))
        math_4 = vector_math_1 * ((evaluate_at_index_3 + evaluate_at_index_4) * 0.5).max(0.00000001) * 2.5
        boolean_math_7 = (math_3 * depth_split > math_4) & (vector_math_1 > 0.0) & g.Compare.integer.equal(g.EdgeNeighbors(), 2)
        delete_geometry = (
            g.StoreNamedAttribute.corner.boolean(switch, name="_o_depth_cut", value=g.EvaluateOnDomain.edge.float(boolean_math_7).o.value.point.evaluate() > 0.0)
            >> g.SplitEdges(selection=boolean_math_7)
            >> g.DeleteGeometry.face(selection=boolean_math_5)
        )
        vector_math_2 = g.VectorMath.scale(image_texture.o.color, evaluate_on_domain_1.o.value.z / g.SeparateXYZ(vector=image_texture.o.color).o.z)
        evaluate_on_domain_4 = boolean_math_6.switch.vector(image_texture.o.color, vector_math_2.o.vector).point.evaluate()
        evaluate_on_domain_5 = evaluate_on_domain_4.z.point.evaluate()
        mix = g.Mix.float(switch_5, evaluate_on_domain_5, evaluate_on_domain_5.blur(boundary_smooth, 0.5), clamp_factor=True)
        switch_6 = g.Switch.float(boundary_smooth, evaluate_on_domain_5, g.Switch.float(switch_5, evaluate_on_domain_5, mix.o.result_float))
        boolean_math_8 = (abs(switch_6.o.output - evaluate_on_domain_4.z) > 0.0) & (evaluate_on_domain_4.z > 0.00000001)
        switch_7 = boolean_math_8.switch.vector(evaluate_on_domain_4, evaluate_on_domain_4 * (switch_6.o.output / evaluate_on_domain_4.z))
        vector = switch_7 * uniform_scale
        math_5 = (vector.z - reference_depth) * depth_scale
        mix_1 = depth_scale.mix.vector(g.Position(), g.CombineXYZ(x=vector.x, y=math_5, z=vector.y * -1.0))
        remove_named_attribute = (
            ((depth_split > 0.0) & (depth_scale > 0.0)).switch.geometry(switch, delete_geometry)
            >> g.SetPosition(position=g.CombineXYZ(x=mix_1.x, y=math_5, z=mix_1.z))
            >> g.RemoveNamedAttribute(name="_o_depth_*", pattern_mode="Wildcard")
        )
        store_named_attribute = g.StoreNamedAttribute.point.boolean(remove_named_attribute, name="_o_pinned_smooth_boundary", value=boolean_math_3.point.evaluate())
        store_named_attribute_1 = g.StoreNamedAttribute.point.float(store_named_attribute, name="_o_pinned_smooth_normalization", value=g.BlurAttribute.float(named_attribute_2.o.attribute, weight=0.5))
        repeat_zone = g.RepeatZone(boundary_smooth)
        geometry_2 = repeat_zone.items.geometry(store_named_attribute_1, "Geometry")
        vector_math_3 = g.VectorMath.scale(position_1, named_attribute_2.o.attribute).o.vector.blur(weight=0.5) * (1.0 / named_attribute_3.o.attribute.max(0.00000001))
        math_6 = 1.0 * g.Normal().o.normal.blur(10).length() * math_2
        vector_math_4 = named_attribute_2.o.attribute.switch.vector(position_1.o.position.blur(), vector_math_3) - position_1
        blur_attribute = g.VectorMath.scale(evaluate_on_domain_2, named_attribute_2.o.attribute).o.vector.blur(weight=0.5)
        switch_8 = named_attribute_2.o.attribute.switch.vector(evaluate_on_domain_2.blur(), blur_attribute * (1.0 / named_attribute_3.o.attribute.max(0.00000001)))
        vector_math_5 = named_attribute_4.o.attribute + (switch_8.point.evaluate() - named_attribute_4.o.attribute) * math_6
        store_named_attribute_2 = g.StoreNamedAttribute.corner.vector_2d(geometry_2.current, name="UVMap", value=vector_math_5)
        set_position = (
            g.Compare.integer.less_than(repeat_zone.iteration, 4).o.result.switch.geometry(geometry_2.current, store_named_attribute_2)
            >> g.SetPosition(offset=vector_math_4 * math_6)
        )
        set_position >> geometry_2.next
        remove_named_attribute_1 = (
            geometry_2.result
            >> g.RemoveNamedAttribute(name="_o_pinned_smooth_*", pattern_mode="Wildcard")
        )
        switch_9 = g.Switch.geometry(boundary_smooth, remove_named_attribute, remove_named_attribute_1)
        set_position_1 = g.SetPosition(geometry=switch_9, position=g.CombineXYZ(x=g.IntegerMath.modulo(index, 4096), z=g.IntegerMath.divide(index, 4096)))
        extrude_mesh = g.ExtrudeMesh(mesh=set_position_1, offset=g.CombineXYZ(y=-1.0), individual=False)
        join_geometry = g.JoinGeometry(geometry=(extrude_mesh >> g.SeparateGeometry.face(selection=extrude_mesh.o.side) >> g.FlipFaces(), g.FlipFaces(mesh=g.SetPosition(geometry=set_position_1, offset=g.CombineXYZ(y=-1.0)))))
        sample_index = g.SampleIndex.point.vector(switch_9, g.Normal().o.normal.blur(100).normalize(), integer_math)
        vector_math_6 = sample_index.o.value * (position_2.o.position.y * g.SampleIndex.point.float(switch_9, thickness, integer_math))
        set_position_2 = (
            g.JoinGeometry(geometry=(join_geometry, set_position_1))
            >> g.MergeByDistance(distance=0.1, mode="All")
            >> g.SetPosition(position=g.SampleIndex.point.vector(switch_9, position_2, integer_math).o.value + vector_math_6)
        )
        (
            (thickness > 0.0).switch.geometry(switch_9, set_position_2)
            >> g.SetShadeSmooth.face()
            >> geometry_1
        )

ASSET = OImageDepthPlane

ASSET_METADATA = {
    "description": "Build a camera-projected image shell.",
    "catalog_id": "00000000-0000-0000-0000-000000000000",
}
