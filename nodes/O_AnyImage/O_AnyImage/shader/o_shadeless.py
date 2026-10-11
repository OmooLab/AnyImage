from bpy.types import ShaderNodeTree
from omoonodes import shader as s, TreeBuilder
from omoonodes.builder import CustomShaderGroup


class OShadeless(CustomShaderGroup):
    _name = "O Shadeless"
    _color_tag = "SHADER"
    _tree_properties = {"description": "Display color without scene lighting while preserving shadows and reflections."}

    def _build_group(self, tree: TreeBuilder[ShaderNodeTree]) -> None:
        color = tree.inputs.color("Color", (0.0, 0.0, 0.0, 1.0))
        alpha = tree.inputs.float("Alpha", 1.0, min_value=0.0, max_value=1.0, subtype="FACTOR")
        strength = tree.inputs.float("Strength", 1.0, description="Set the emission strength for camera rays. Zero renders the surface black.", min_value=0.0)
        shader = tree.outputs.shader("Shader")

        light_path = s.LightPath()
        math_1 = ((2.0 - light_path.o.ray_depth) * light_path.o.is_glossy_ray).max(light_path.o.is_shadow_ray)
        mix_shader = s.MixShader(fac=math_1.max(1.0 - (light_path.o.ray_depth - light_path.o.transmission_depth)), shader=s.DiffuseBSDF(color=color), shader_001=s.Emission(color=color, strength=strength))
        mix_shader_1 = s.MixShader(fac=alpha, shader=s.TransparentBSDF(), shader_001=mix_shader)

        mix_shader_1 >> shader

ASSET = OShadeless

ASSET_METADATA = {
    "description": "Display color without scene lighting while preserving shadows and reflections.",
    "catalog_id": "00000000-0000-0000-0000-000000000000",
}
