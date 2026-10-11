from ..geometry.o_image_plane import OImagePlane
from bpy.types import GeometryNodeTree
from omoonodes import geometry as g, TreeBuilder
from omoonodes.builder import CustomGeometryGroup


class OImageReliefPlane(CustomGeometryGroup):
    _name = "O Image Relief Plane"
    _color_tag = "GEOMETRY"
    _tree_properties = {"description": "Build a fixed-base image relief.", "is_modifier": True}

    def _build_group(self, tree: TreeBuilder[GeometryNodeTree]) -> None:
        geometry = tree.inputs.geometry("Geometry", structure_type="SINGLE", force_non_field=True)
        subdivide = tree.inputs.integer("Subdivide", 6, description="Increase mesh density to represent finer shapes. Higher levels create more vertices and require more processing time.", min_value=0, max_value=10, structure_type="SINGLE", force_non_field=True)
        thickness = tree.inputs.float("Thickness", 0.0, description="Set the thickness of the flat base beneath the relief.", min_value=0.0, structure_type="SINGLE", subtype="DISTANCE", force_non_field=True)
        depth_direction = tree.inputs.vector("Depth Direction", (0.0, 0.0, 1.0), description="Set the direction used to orient the reference depth plane.", structure_type="SINGLE", subtype="DIRECTION", force_non_field=True)
        depth_offset = tree.inputs.float("Depth Offset", 0.0, description="Correct the reference depth before direction and scale are applied.", min_value=-10.0, max_value=10.0, structure_type="SINGLE", subtype="DISTANCE", force_non_field=True)
        depth_scale = tree.inputs.float("Depth Scale", 0.5, min_value=0.0, max_value=2.0, structure_type="SINGLE", force_non_field=True)
        depth_mask = tree.inputs.boolean("Depth Mask", True, description="Treat depth-mask-invalid areas as zero depth instead of deleting them.", structure_type="SINGLE", force_non_field=True)
        with tree.inputs.panel("Options", default_closed=True):
            mask_threshold = tree.inputs.float("Mask Threshold", 0.9, description="Set the minimum depth mask value treated as valid.", min_value=0.0, max_value=0.99, structure_type="SINGLE", subtype="FACTOR", force_non_field=True)
            reference_depth = tree.inputs.float("Reference Depth", 1.0, min_value=0.0, structure_type="SINGLE", subtype="DISTANCE", force_non_field=True)
        with tree.inputs.panel("Data", default_closed=True):
            uniform_scale = tree.inputs.float("Uniform Scale", 1.0, min_value=0.0, hide_in_modifier=True, structure_type="SINGLE", force_non_field=True)
            depth_image = tree.inputs.image("Depth Image", hide_in_modifier=True, structure_type="SINGLE", force_non_field=True)
        geometry_1 = tree.outputs.geometry("Geometry")

        boolean_math = g.Compare.integer.equal(g.EdgeNeighbors(), 1).o.result.edge.evaluate() | g.Compare.integer.equal(g.VertexNeighbors().o.vertex_count, 1)
        evaluate_on_domain = g.EvaluateOnDomain.point.float(boolean_math)
        image_texture = g.ImageTexture(image=depth_image, vector=g.NamedAttribute.vector("UVMap").o.attribute, extension="EXTEND")
        math_1 = 1.0 - evaluate_on_domain.o.value.max(evaluate_on_domain.o.value.blur(2)).clamp()
        position = g.Position().o.position
        switch = (thickness > 0.000001).switch.float(1.0, 1.0 - (g.Position().o.position.y / thickness).max(0.0).min(1.0))
        vector = depth_direction.normalize()
        vector_1 = g.CombineXYZ(x=vector.x * -1.0, y=vector.z, z=vector.y * -1.0).o.vector
        math_2 = reference_depth + depth_offset + (position.x * vector_1.x + position.z * vector_1.z) / vector_1.y
        math_3 = (g.SeparateXYZ(vector=image_texture.o.color).o.z * uniform_scale - math_2) * depth_scale * depth_mask.switch.float(1.0, (image_texture.o.alpha < mask_threshold).switch.float(1.0))
        (
            OImagePlane(Geometry=geometry, Subdivide=subdivide, Thickness=thickness)
            >> g.TransformGeometry(translation=g.CombineXYZ(y=thickness * 0.5), mode="Components")
            >> g.SetPosition(offset=g.CombineXYZ(y=math_3.min(0.0) * math_1 * switch))
            >> g.SetShadeSmooth.face()
            >> g.StoreNamedAttribute.point.float(name="o_normal_reduction", value=1.0 - depth_scale * math_1)
            >> geometry_1
        )

ASSET = OImageReliefPlane

ASSET_METADATA = {
    "description": "Build a fixed-base image relief.",
    "catalog_id": "00000000-0000-0000-0000-000000000000",
}
