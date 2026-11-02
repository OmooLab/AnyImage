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
        roughness_scale = tree.inputs.float("Roughness Scale", 1.0, description="Adjust the overall surface roughness.", min_value=0.0, max_value=1.0, subtype="FACTOR")
        alpha_scale = tree.inputs.float("Alpha Scale", 1.0, description="Adjust opacity derived from color and texture alpha.", min_value=0.0, max_value=1.0, subtype="FACTOR")
        normal_scale = tree.inputs.float("Normal Scale", 1.0, description="Control the strength of surface detail from the normal map.", min_value=0.0, max_value=2.0)
        bump_scale = tree.inputs.float("Bump Scale", 1.0, description="Control bump detail derived from image brightness. Negative values reverse the bumps. Zero disables the effect.", min_value=-10.0, max_value=10.0)
        with tree.inputs.panel("Options", default_closed=True):
            highlight_threshold = tree.inputs.float("Highlight Threshold", 1.0, description="Increase emission and suppress color-derived bump from this brightness to four times it.", min_value=0.0001, max_value=2.0)
            roughness_contrast = tree.inputs.float("Roughness Contrast", -1.0, description="Positive values smooth dark areas; negative values smooth bright areas.", min_value=-1.0, max_value=1.0, subtype="FACTOR")
            alpha_background = tree.inputs.float("Alpha Background", 0.0001, description="Set the linear brightness of the transparent background.", min_value=0.0, max_value=2.0)
            object_space = tree.inputs.boolean("Object Space", False, description="Interpret the normal map in object space when enabled, or tangent space when disabled.")
        color = tree.outputs.color("Color", (0.0, 0.0, 0.0, 1.0))
        roughness = tree.outputs.float("Roughness", min_value=0.0, max_value=1.0)
        alpha = tree.outputs.float("Alpha", min_value=0.0, max_value=1.0)
        normal = tree.outputs.vector("Normal", min_value=0.0, max_value=1.0)
        emission = tree.outputs.color("Emission", (0.0, 0.0, 0.0, 1.0))

        normal_strength = normal_scale * (1.0 - s.Attribute(attribute_name="o_normal_reduction").o.fac)
        highlight_weight = g.Math.divide(color_texture, highlight_threshold).o.value.map_range(1.0, 4.0, interpolation_type="SMOOTHERSTEP")
        compressed_brightness = g.Math.divide(color_texture, g.Math.add(color_texture, 0.1)).o.value
        roughness_variation = (compressed_brightness - 0.5) * roughness_contrast
        mapped_roughness = g.Math.power(roughness_variation.mul_add(0.49, 0.255), roughness_scale.map_range(from_max=1.0, to_min=1.5, to_max=0.5), use_clamp=True)
        dark_roughness = compressed_brightness.map_range(to_min=1.0, to_max=0.0, interpolation_type="SMOOTHERSTEP")
        background_difference = g.Math.divide(abs(g.Math.subtract(color_texture, alpha_background).o.value), alpha_background.max(1.0), use_clamp=True)
        color_alpha = g.Math.power(background_difference, alpha_scale.map_range(to_min=1.0, to_max=0.0, clamp=False), use_clamp=True)
        combined_alpha = g.Math.multiply(color_alpha, alpha_texture, use_clamp=True)
        emission_color = g.VectorMath.scale(color_texture, highlight_weight + s.Attribute(attribute_name="o_emission").o.fac)

        normal_transform = s.Attribute(attribute_name="o_normal_transform").o.vector
        decoded_normal = g.VectorMath.multiply_add(normal_texture, (2.0, 2.0, 2.0), (-1.0, -1.0, -1.0)).o.vector
        aligned_normal = g.VectorRotate.axis_angle(
            decoded_normal,
            axis=g.CombineXYZ(x=normal_transform.x.cos(), z=normal_transform.x.sin()),
            angle=normal_transform.y,
            invert=True,
        ).o.vector
        transformed_normal = g.VectorRotate.euler(
            aligned_normal * g.CombineXYZ(x=1.0, y=normal_transform.z, z=1.0),
            rotation=(0.0, 0.0, 1.5707963267948966),
        ).o.vector.normalize()
        object_color = g.Mix.vector(
            g.Math.greater_than(abs(normal_transform.z), 0.0),
            normal_texture,
            transformed_normal.mul_add((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
        ).o.result_vector
        object_normal = s.NormalMap(strength=normal_strength, color=object_color, space="OBJECT")
        selected_normal = g.Mix.vector(object_space, s.NormalMap(strength=normal_strength, color=normal_texture), object_normal, clamp_factor=True)
        bump = s.Bump(strength=1.0 - highlight_weight, distance=bump_scale * 0.01, height=compressed_brightness, normal=selected_normal.o.result_vector)

        color_texture >> color
        g.Math.add(mapped_roughness, dark_roughness, use_clamp=True) >> roughness
        combined_alpha >> alpha
        bump >> normal
        g.VectorMath.minimum(emission_color, (4.0, 4.0, 4.0)) >> emission

ASSET = OTextureToLayer

ASSET_METADATA = {
    "description": "Prepare O Texture to Layer material outputs.",
    "catalog_id": "00000000-0000-0000-0000-000000000000",
}
