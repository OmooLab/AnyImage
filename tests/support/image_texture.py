from types import SimpleNamespace

import bpy
import numpy as np
import pytest
from PIL import Image


@pytest.fixture
def texture():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    material = bpy.data.materials.new("Texture material")
    material.use_nodes = True
    material.use_fake_user = True
    tree = material.node_tree
    node = tree.nodes.new("ShaderNodeTexImage")
    node.name = "Source texture"
    node.image = bpy.data.images.new("Texture.png", width=4, height=3, alpha=True)
    node.image.pixels.foreach_set(np.tile([0.2, 0.4, 0.6, 0.75], 12).astype(np.float32))
    node.image.pack()
    node.location = (-400, 100)
    node.interpolation = "Closest"
    node.extension = "CLIP"
    node.projection = "BOX"
    tree.nodes.active = node
    tree.links.new(node.outputs["Color"], tree.nodes.get("Principled BSDF").inputs["Base Color"])
    yield node
    bpy.ops.wm.read_factory_settings(use_empty=True)


def texture_context(node, **space_options):
    return SimpleNamespace(
        space_data=SimpleNamespace(
            **dict(type="NODE_EDITOR", tree_type="ShaderNodeTree", shader_type="OBJECT",
                   edit_tree=node.id_data, id=bpy.data.materials["Texture material"], **space_options),
        ),
        object=None,
        scene=SimpleNamespace(anyimage_settings=SimpleNamespace()),
    )


def write_result(directory, filename="foreground.png"):
    path = directory / filename
    Image.new("RGBA", (8, 6), (128, 64, 32, 80)).save(path)
    return path
