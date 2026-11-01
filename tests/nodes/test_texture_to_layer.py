"""Check saved texture-layer color mappings through rendered shader outputs."""
import bpy
import numpy as np
import pytest

from anyimage.common.material import create_image_material
from tests.support.mesh_bake import render_material


@pytest.mark.parametrize("brightness,background,scale", [(0.0, 0.0, 1.0), (.25, 0.0, .5), (1.0, 1.0, .5), (4.0, 2.0, 1.0)])
@pytest.mark.parametrize("emission_weight", [0.0, .4, 1.0])
def test_texture_layer_mappings(tmp_path, brightness, background, scale, emission_weight):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = bpy.data.images.new("Linear texture", width=4, height=4, float_buffer=True)
    image.colorspace_settings.is_data = True
    image.pixels.foreach_set([brightness, brightness, brightness, .8] * 16)
    material = create_image_material(image, image, emission_strength=1)
    layer = next(n for n in material.node_tree.nodes if n.type == "GROUP")
    layer.inputs["Emission Threshold"].default_value = 1.0
    layer.inputs["Alpha Background"].default_value = background
    layer.inputs["Alpha Scale"].default_value = scale
    bpy.ops.mesh.primitive_plane_add(size=4)
    obj = bpy.context.object
    obj.data.materials.append(material)
    obj.data.attributes.new("o_emission", "FLOAT", "CORNER").data.foreach_set("value", [emission_weight] * 4)
    expected_alpha = min(abs(brightness - background) / max(background, 1), 1) ** (1 - scale) * .8
    factor = np.clip((brightness - 1) / 3, 0, 1)
    expected_emission = brightness * (factor ** 3 * (factor * (factor * 6 - 15) + 10) + emission_weight)
    expected_roughness = (.255 - .49 * (brightness / (brightness + .1) - .5)) ** 1.25
    for channel, expected in (("Alpha", expected_alpha), ("Roughness", expected_roughness), ("Emission", expected_emission)):
        pixels = render_material(obj, tmp_path / f"{channel}.exr", (0, 0, 1), channel=channel)
        np.testing.assert_allclose(pixels[24:40, 24:40, :3], expected, atol=1e-3)
