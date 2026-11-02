from bpy.types import ShaderNodeTree
from omoonodes import geometry as g, shader as s, TreeBuilder
from omoonodes.builder import CustomShaderGroup


class OWorldVector(CustomShaderGroup):
    _name = "O World Vector"
    _color_tag = "INPUT"
    _tree_properties = {"default_group_node_width": 190}

    def _build_group(self, tree: TreeBuilder[ShaderNodeTree]) -> None:
        rotation = tree.inputs.vector("Rotation", (0.0, 0.0, 0.0), description="World rotation of the panorama object.", subtype="EULER")
        blur = tree.inputs.float("Blur", 0.0, description="Scatter environment directions to soften the panorama.", min_value=0.0, max_value=1.0, subtype="FACTOR")
        horizon_bend = tree.inputs.float("Horizon Bend", 0.0, description="Move scenery along the dome: positive values raise it, negative values lower it, and zero preserves the original panorama.", min_value=-1.0, max_value=1.0, subtype="FACTOR")
        vector = tree.outputs.vector("Vector")

        direction = g.VectorRotate.euler(s.TextureCoordinate().o.generated, rotation=rotation, invert=True).o.vector.normalize()
        horizontal_squared = direction.x * direction.x + direction.y * direction.y
        bent_direction = (direction - g.CombineXYZ(z=horizon_bend * horizontal_squared)).normalize()
        noise = g.VectorMath.subtract(g.WhiteNoiseTexture(vector=bent_direction).o.color, (0.5, 0.5, 0.5))
        mix = g.Mix.vector(blur.map_range(to_max=0.25), bent_direction, noise.o.vector, clamp_factor=True)
        mix.o.result_vector >> vector


ASSET = OWorldVector

ASSET_METADATA = {
    "catalog_id": "4dd41edf-4431-4f79-a357-c6b444a4416f",
}
