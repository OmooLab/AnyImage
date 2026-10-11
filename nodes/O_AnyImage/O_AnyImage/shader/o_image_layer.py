from bpy.types import ShaderNodeTree
from omoonodes import geometry as g, shader as s, TreeBuilder
from omoonodes.builder import CustomShaderGroup


class OImageLayer(CustomShaderGroup):
    _name = "O Image Layer"
    _color_tag = "SHADER"
    _tree_properties = {"description": "Prepare O Image Layer material outputs."}

    def _build_group(self, tree: TreeBuilder[ShaderNodeTree]) -> None:
        color = tree.inputs.color("Color", (0.0, 0.0, 0.0, 1.0))
        alpha = tree.inputs.float("Alpha", 1.0, min_value=0.0, max_value=1.0, subtype="FACTOR")
        normal = tree.inputs.color("Normal", (0.5, 0.5, 1.0, 1.0))
        normal_scale = tree.inputs.float("Normal Scale", 1.0, description="Control the strength of surface detail from the normal map.", min_value=0.0, max_value=10.0)
        bump_scale = tree.inputs.float("Bump Scale", 0.0, description="Control bump detail derived from image brightness. Negative values reverse the bumps. Zero disables the effect.", min_value=-10000.0, max_value=10000.0)
        with tree.inputs.panel("Options", default_closed=True):
            alpha_fix = tree.inputs.float("Alpha Fix", 0.0, description="Reduce semi-transparent fringes around image edges. Higher values remove more faint edge pixels. Zero keeps the original transparency.", min_value=0.0, max_value=1.0, subtype="FACTOR")
            object_space = tree.inputs.boolean("Object Space", False, description="Interpret the normal map in object space when enabled, or tangent space when disabled.")
        color_1 = tree.outputs.color("Color", (0.0, 0.0, 0.0, 1.0))
        roughness = tree.outputs.float("Roughness")
        alpha_1 = tree.outputs.float("Alpha")
        normal_1 = tree.outputs.vector("Normal")

        attribute = s.Attribute(attribute_name="o_depth_face")
        float_curve = g.FloatCurve(value=color, items=((0.0, 0.5), (1.0, 0.1)))
        float_curve.node.mapping.update()
        float_curve.node.mapping.curves[0].points[0].select = True
        float_curve.node.mapping.curves[0].points[1].select = True
        float_curve_1 = g.FloatCurve(factor=alpha_fix, value=alpha, items=((0.0, 0.0, "AUTO_CLAMPED"), (0.8, 0.0, "AUTO_CLAMPED"), (0.925, 0.925, "AUTO_CLAMPED"), (1.0, 1.0, "AUTO_CLAMPED")))
        float_curve_1.node.mapping.extend = "HORIZONTAL"
        float_curve_1.node.mapping.update()
        float_curve_1.node.mapping.curves[0].points[2].select = True
        math_1 = normal_scale * (1.0 - s.Attribute(attribute_name="o_normal_reduction").o.fac)
        vector_math = g.VectorMath.scale((0.0, 0.0, 1.5707963), s.Attribute(attribute_name="o_depth_axis").o.fac)
        vector_rotate = g.VectorRotate.euler(g.VectorMath.multiply_add(normal, (2.0, 2.0, 2.0), (-1.0, -1.0, -1.0)).o.vector, rotation=(1.5707964, 0.0, 0.0))
        vector_rotate_1 = g.VectorRotate.euler(vector_rotate, rotation=s.Attribute(attribute_name="o_depth_rotation").o.vector, invert=True)
        math_2 = g.Math.compare(attribute.o.fac, 2.0).o.value.mul_add(vector_rotate_1.o.vector.y * -2.0, vector_rotate_1.o.vector.y)
        vector_rotate_2 = g.VectorRotate.euler(g.CombineXYZ(x=vector_rotate_1.o.vector.x, y=math_2, z=vector_rotate_1.o.vector.z), rotation=vector_math.o.vector)
        normal_map = s.NormalMap(strength=g.Math.less_than(attribute.o.fac, 2.5).o.value * math_1, color=vector_rotate_2.o.vector.mul_add((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)), space="OBJECT")
        mix = g.Mix.vector(object_space, s.NormalMap(strength=math_1, color=normal), normal_map, clamp_factor=True)
        bump = s.Bump(distance=bump_scale * 0.001, height=color, normal=mix.o.result_vector)

        color >> color_1
        float_curve >> roughness
        float_curve_1 >> alpha_1
        bump >> normal_1

ASSET = OImageLayer

ASSET_METADATA = {
    "description": "Prepare O Image Layer material outputs.",
    "catalog_id": "00000000-0000-0000-0000-000000000000",
}
