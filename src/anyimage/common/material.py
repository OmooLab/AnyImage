"""Create Blender material nodes for image results."""

import bpy

from .image import image_base_name
from . import color_image as color_images
from .node import load_node_group


IMAGE_MATERIAL_NODE_GROUP_NAME = "O Texture to Layer"


def create_image_material(
    source_image,
    color_image,
    *,
    color_is_full_source=False,
    normal_image=None,
    normal_space="TANGENT",
    scene=None,
    texture_extension="EXTEND",
    emission_strength=0.0,
    panorama=False,
    highlight_threshold=None,
    material_name=None,
):
    material_image = color_images.configure_material_color_image(
        color_image, scene,
    )
    if material_image.source == "GENERATED" or material_image.is_dirty:
        material_image.pack()
    material = bpy.data.materials.new(material_name or image_base_name(source_image))
    try:
        material.use_nodes = True
        material.surface_render_method = "DITHERED"
        nodes = material.node_tree.nodes
        nodes.clear()

        color_texture = nodes.new("ShaderNodeTexImage")
        output = nodes.new("ShaderNodeOutputMaterial")

        color_texture.image = material_image
        color_texture.interpolation = "Linear"
        color_texture.extension = texture_extension
        color_texture.location = (-700.0, 300.0)
        output.location = (500.0, 300.0)
        links = material.node_tree.links
        material_inputs = nodes.new("ShaderNodeGroup")
        material_inputs.node_tree = load_node_group(IMAGE_MATERIAL_NODE_GROUP_NAME)
        material_inputs.width = material_inputs.node_tree.default_group_node_width
        material_inputs.location = (-300.0, 300.0)
        if highlight_threshold is None:
            highlight_threshold = color_images.estimate_highlight_threshold(
                material_image if color_is_full_source else source_image,
                material_image=material_image, panorama=panorama,
            )
        material_inputs.inputs["Highlight Threshold"].default_value = highlight_threshold
        if normal_space not in {"TANGENT", "OBJECT"}:
            raise ValueError(f"Unsupported normal space: {normal_space}")
        # Without a normal texture, the neutral tangent input follows the mesh.
        material_inputs.inputs["Object Space"].default_value = normal_image is not None and normal_space == "OBJECT"
        links.new(color_texture.outputs["Color"], material_inputs.inputs["Color Texture"])
        links.new(color_texture.outputs["Alpha"], material_inputs.inputs["Alpha Texture"])
        if normal_image is not None:
            normal_texture = nodes.new("ShaderNodeTexImage")
            normal_texture.image = normal_image
            normal_texture.interpolation = "Linear"
            normal_texture.extension = texture_extension
            normal_texture.location = (-700.0, 0.0)
            links.new(normal_texture.outputs["Color"], material_inputs.inputs["Normal Texture"])
        shader = nodes.new("ShaderNodeBsdfPrincipled")
        shader.location = (100.0, 300.0)
        shader.inputs["IOR"].default_value = 1.2
        shader.inputs["Emission Strength"].default_value = emission_strength

        links.new(
            material_inputs.outputs["Color"],
            shader.inputs["Base Color"],
        )
        links.new(
            material_inputs.outputs["Emission"],
            shader.inputs["Emission Color"],
        )
        links.new(material_inputs.outputs["Alpha"], shader.inputs["Alpha"])
        links.new(material_inputs.outputs["Normal"], shader.inputs["Normal"])
        links.new(
            material_inputs.outputs["Roughness"],
            shader.inputs["Roughness"],
        )
        links.new(shader.outputs["BSDF"], output.inputs["Surface"])

        return material
    except Exception:
        bpy.data.materials.remove(material, do_unlink=True)
        raise
