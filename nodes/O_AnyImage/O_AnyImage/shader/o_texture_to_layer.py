from bpy.types import ShaderNodeTree
from omoonodes import geometry as g, shader as s, TreeBuilder
from omoonodes.builder import CustomShaderGroup


class OTextureToLayer(CustomShaderGroup):
    _name = "O Texture to Layer"
    _color_tag = "SHADER"
    _tree_properties = {"description": "Prepare O Texture to Layer material outputs.", "default_group_node_width": 190}

    def _build_group(self, tree: TreeBuilder[ShaderNodeTree]) -> None:
        color_texture = tree.inputs.color("Color Texture", (0.8, 0.8, 0.8, 1.0))
        alpha_texture = tree.inputs.float("Alpha Texture", 1.0, min_value=0.0, max_value=1.0, subtype="FACTOR")
        normal_texture = tree.inputs.color("Normal Texture", (0.5, 0.5, 1.0, 1.0))
        roughness_scale = tree.inputs.float("Roughness Scale", 0.5, description="Adjust the overall surface roughness.", min_value=0.0, max_value=1.0, subtype="FACTOR")
        alpha_scale = tree.inputs.float("Alpha Scale", 1.0, description="Adjust opacity derived from color and texture alpha.", min_value=0.0, max_value=1.0, subtype="FACTOR")
        emission_threshold = tree.inputs.float("Emission Threshold", 1.0, description="Set the brightness at which emission starts increasing.", min_value=0.0001, max_value=2.0)
        normal_scale = tree.inputs.float("Normal Scale", 1.0, description="Control the strength of surface detail from the normal map.", min_value=0.0, max_value=4.0)
        bump_scale = tree.inputs.float("Bump Scale", 0.0, description="Control bump detail derived from image brightness. Negative values reverse the bumps. Zero disables the effect.", min_value=-128.0, max_value=128.0)
        with tree.inputs.panel("Options", default_closed=True):
            roughness_contrast = tree.inputs.float("Roughness Contrast", -1.0, description="Positive values smooth dark areas; negative values smooth bright areas.", min_value=-1.0, max_value=1.0, subtype="FACTOR")
            alpha_background = tree.inputs.float("Alpha Background", 0.0001, description="Set the linear brightness of the transparent background.", min_value=0.0, max_value=2.0)
            object_space = tree.inputs.boolean("Object Space", False, description="Interpret the normal map in object space when enabled, or tangent space when disabled.")
        color = tree.outputs.color("Color", (0.0, 0.0, 0.0, 1.0))
        roughness = tree.outputs.float("Roughness", min_value=0.0, max_value=1.0)
        alpha = tree.outputs.float("Alpha", min_value=0.0, max_value=1.0)
        normal = tree.outputs.vector("Normal", min_value=0.0, max_value=1.0)
        emission = tree.outputs.color("Emission", (0.0, 0.0, 0.0, 1.0))

        attribute = s.Attribute(attribute_name="o_depth_face")
        math_1 = normal_scale * (1.0 - s.Attribute(attribute_name="o_normal_reduction").o.fac)
        map_range = g.Math.divide(color_texture, emission_threshold).o.value.map_range(1.0, 4.0, interpolation_type="SMOOTHERSTEP")
        math_2 = (g.Math.divide(color_texture, g.Math(value=color_texture, value_001=0.1)).o.value - 0.5) * roughness_contrast
        math_3 = g.Math.power(math_2.mul_add(0.49, 0.255), roughness_scale.map_range(to_min=2.0, to_max=0.5), use_clamp=True)
        math_4 = g.Math.divide(abs(g.Math.subtract(color_texture, alpha_background).o.value), alpha_background.max(1.0), use_clamp=True)
        math_5 = g.Math.power(math_4, alpha_scale.map_range(to_min=1.0, to_max=0.0, clamp=False), use_clamp=True)
        math_6 = g.Math.multiply(math_5, alpha_texture, use_clamp=True)
        vector_math = g.VectorMath.scale((0.0, 0.0, 1.5707963), s.Attribute(attribute_name="o_depth_axis").o.fac)
        vector_math_1 = g.VectorMath.scale(color_texture, map_range + s.Attribute(attribute_name="o_emission").o.fac)
        vector_rotate = g.VectorRotate.euler(g.VectorMath.multiply_add(normal_texture, (2.0, 2.0, 2.0), (-1.0, -1.0, -1.0)).o.vector, rotation=(1.5707964, 0.0, 0.0))
        vector_rotate_1 = g.VectorRotate.euler(vector_rotate, rotation=s.Attribute(attribute_name="o_depth_rotation").o.vector, invert=True)
        math_7 = g.Math.compare(attribute.o.fac, 2.0).o.value.mul_add(vector_rotate_1.o.vector.y * -2.0, vector_rotate_1.o.vector.y)
        vector_rotate_2 = g.VectorRotate.euler(g.CombineXYZ(x=vector_rotate_1.o.vector.x, y=math_7, z=vector_rotate_1.o.vector.z), rotation=vector_math.o.vector)
        normal_map = s.NormalMap(strength=g.Math.less_than(attribute.o.fac, 2.5).o.value * math_1, color=vector_rotate_2.o.vector.mul_add((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)), space="OBJECT")
        mix = g.Mix.vector(object_space, s.NormalMap(strength=math_1, color=normal_texture), normal_map, clamp_factor=True)
        bump = s.Bump(distance=bump_scale * 0.001, height=color_texture, normal=mix.o.result_vector)

        color_texture >> color
        math_3 >> roughness
        math_6 >> alpha
        bump >> normal
        vector_math_1 >> emission

ASSET = OTextureToLayer

ASSET_METADATA = {
    "description": "Prepare O Texture to Layer material outputs.",
    "catalog_id": "00000000-0000-0000-0000-000000000000",
}
