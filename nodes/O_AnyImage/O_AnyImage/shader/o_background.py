from bpy.types import ShaderNodeTree
from omoonodes import geometry as g, shader as s, TreeBuilder
from omoonodes.builder import CustomShaderGroup


class OBackground(CustomShaderGroup):
    _name = "O Background"
    _color_tag = "SHADER"
    _tree_properties = {"default_group_node_width": 160}

    def _build_group(self, tree: TreeBuilder[ShaderNodeTree]) -> None:
        color = tree.inputs.color("Color", (0.050876, 0.050876, 0.050876, 1.0), description="Color of the emitted light")
        strength = tree.inputs.float("Strength", 1.0, description="Strength of the emitted light", min_value=0.0, max_value=1000000.0)
        light = tree.inputs.color("Light", (0.0, 0.0, 0.0, 1.0), description="Color of the emitted light")
        strength_1 = tree.inputs.float("Strength", 1.0, description="Strength of the emitted light", min_value=0.0, max_value=1000000.0)
        with tree.inputs.panel("Options", default_closed=True):
            transmission_cycles = tree.inputs.boolean("Transmission (Cycles)", False, description="Amount of mixing between the A and B inputs")
        shader = tree.outputs.shader("Shader")

        light_path = s.LightPath()
        math_1 = g.Math.maximum(light_path.o.is_camera_ray, g.Mix.float(transmission_cycles, b=light_path.o.is_transmission_ray, clamp_factor=True).o.result_float, use_clamp=True)
        mix_shader = s.MixShader(fac=math_1, shader=s.Background(color=light, strength=strength_1), shader_001=s.Background(color=color, strength=strength))

        mix_shader >> shader

ASSET = OBackground

ASSET_METADATA = {
    "catalog_id": "4dd41edf-4431-4f79-a357-c6b444a4416f",
}
