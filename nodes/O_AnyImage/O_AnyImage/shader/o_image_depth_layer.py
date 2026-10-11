from bpy.types import ShaderNodeTree
from omoonodes import geometry as g, shader as s, TreeBuilder
from omoonodes.builder import CustomShaderGroup


class OImageDepthLayer(CustomShaderGroup):
    _name = "O Image Depth Layer"
    _color_tag = "SHADER"
    _tree_properties = {"description": "Prepare image depth material outputs."}

    def _build_group(self, tree: TreeBuilder[ShaderNodeTree]) -> None:
        color = tree.inputs.color("Color", (0.0, 0.0, 0.0, 1.0))
        alpha = tree.inputs.float("Alpha", 1.0, min_value=0.0, max_value=1.0, subtype="FACTOR")
        depth = tree.inputs.float("Depth", 0.0)
        bump_scale = tree.inputs.float("Bump Scale", 0.0, description="Control bump detail derived from image brightness. Negative values reverse the bumps. Zero disables the effect.", min_value=-10000.0, max_value=10000.0)
        color_1 = tree.outputs.color("Color", (0.0, 0.0, 0.0, 1.0))
        roughness = tree.outputs.float("Roughness")
        alpha_1 = tree.outputs.float("Alpha")
        normal = tree.outputs.vector("Normal")
        displacement = tree.outputs.vector("Displacement")

        attribute = s.Attribute(attribute_name="o_background_depth")
        float_curve = g.FloatCurve(value=color, items=((0.0, 0.5), (1.0, 0.1)))
        float_curve.node.mapping.update()
        float_curve.node.mapping.curves[0].points[0].select = True
        float_curve.node.mapping.curves[0].points[1].select = True
        math_1 = g.Math.greater_than(alpha)
        bump = s.Bump(distance=bump_scale * 0.001, height=color)
        math_2 = g.Mix.float(math_1, attribute.o.fac, depth.max(attribute.o.fac), clamp_factor=True).o.result_float * s.Attribute(attribute_name="o_material_displacement").o.fac
        displacement_1 = s.Displacement(height=math_2 * s.Attribute(attribute_name="o_depth_scale").o.fac, midlevel=0.0, scale=1.0)

        color >> color_1
        float_curve >> roughness
        math_1 >> alpha_1
        bump >> normal
        displacement_1 >> displacement

ASSET = OImageDepthLayer

ASSET_METADATA = {
    "description": "Prepare image depth material outputs.",
    "catalog_id": "00000000-0000-0000-0000-000000000000",
}
