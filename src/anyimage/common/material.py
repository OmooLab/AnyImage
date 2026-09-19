"""Build and configure Blender materials for Image results."""

import bpy

from ..preferences import configured_material_view_adaptation
from .image import (
    VIEW_TRANSFORM_COLOR_SPACES,
    color_alpha_mode,
    image_base_name,
    image_pixels,
)
from .node import load_node_group


IMAGE_MATERIAL_NODE_GROUP_NAME = "O Image Layer"
DEPTH_MATERIAL_NODE_GROUP_NAME = "O Image Depth Layer"
SHADELESS_NODE_GROUP_NAME = "O Shadeless"


def material_color_space_name(scene):
    view_settings = getattr(scene, "view_settings", None)
    view_transform = getattr(view_settings, "view_transform", "")
    normalized = str(view_transform).strip().casefold()
    for view_name, color_space in VIEW_TRANSFORM_COLOR_SPACES:
        if normalized.startswith(view_name.casefold()):
            return color_space
    return "sRGB"


def configure_material_color_image(image, scene=None):
    """Configure the selected Color image in place using the shading preference."""
    if getattr(image, "is_float", False):
        return image
    if scene is None:
        scene = getattr(bpy.context, "scene", None)
    preferred = (
        material_color_space_name(scene)
        if configured_material_view_adaptation()
        else "sRGB"
    )
    pixels = (
        image_pixels(image)
        if getattr(image, "source", None) == "GENERATED"
        or getattr(image, "is_dirty", False)
        else None
    )
    settings = image.colorspace_settings
    original_space = settings.name
    original_alpha = image.alpha_mode
    try:
        for color_space in dict.fromkeys((preferred, "sRGB")):
            try:
                settings.name = color_space
            except (TypeError, ValueError):
                continue
            if settings.name == color_space:
                break
        else:
            raise RuntimeError("Unable to configure the material color space")
        image.alpha_mode = color_alpha_mode(settings.name)
        if pixels is not None:
            image.pixels.foreach_set(pixels)
            image.update()
    except Exception:
        settings.name = original_space
        image.alpha_mode = original_alpha
        if pixels is not None:
            image.pixels.foreach_set(pixels)
            image.update()
        raise
    return image


def material_node_group(depth_plane=False):
    group_name = (
        DEPTH_MATERIAL_NODE_GROUP_NAME
        if depth_plane
        else IMAGE_MATERIAL_NODE_GROUP_NAME
    )
    return load_node_group(group_name)


def create_emission_material(
    source_image,
    color_image,
    scene=None,
    texture_extension="EXTEND",
):
    """Emit the color image unchanged, without alpha blending or lighting."""
    preserve_color = color_image.is_float or not color_image.colorspace_settings.name.endswith("sRGB")
    material_image = color_image if preserve_color else configure_material_color_image(color_image, scene)
    if material_image.source == "GENERATED" or material_image.is_dirty:
        material_image.pack()
    material = bpy.data.materials.new(image_base_name(source_image))
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    color_texture = nodes.new("ShaderNodeTexImage")
    emission = nodes.new("ShaderNodeEmission")
    output = nodes.new("ShaderNodeOutputMaterial")
    color_texture.image = material_image
    color_texture.interpolation = "Linear"
    color_texture.extension = texture_extension
    color_texture.location = (-700.0, 300.0)
    emission.location = (-300.0, 300.0)
    output.location = (100.0, 300.0)
    links = material.node_tree.links
    links.new(color_texture.outputs["Color"], emission.inputs["Color"])
    links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return material


def create_image_material(
    source_image,
    color_image,
    depth_scale=0.0,
    displacement_image=None,
    displacement_midlevel=0.0,
    displacement_scale=1.0,
    shadeless=False,
    normal_image=None,
    normal_space="TANGENT",
    scene=None,
    texture_extension="EXTEND",
):
    preserve_color = color_image.is_float or (
        shadeless and not color_image.colorspace_settings.name.endswith("sRGB")
    )
    material_image = color_image if preserve_color else configure_material_color_image(color_image, scene)
    if material_image.source == "GENERATED" or material_image.is_dirty:
        material_image.pack()
    material = bpy.data.materials.new(image_base_name(source_image))
    try:
        material.use_nodes = True
        if hasattr(material, "surface_render_method"):
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
        alpha = color_texture.outputs["Alpha"]
        if shadeless and displacement_image is None:
            shader = nodes.new("ShaderNodeGroup")
            shader.node_tree = load_node_group(SHADELESS_NODE_GROUP_NAME)
            shader.location = (-300.0, 300.0)
            output.location = (100.0, 300.0)
            links.new(color_texture.outputs["Color"], shader.inputs["Color"])
            links.new(alpha, shader.inputs["Alpha"])
            links.new(shader.outputs["Shader"], output.inputs["Surface"])
            return material
        material_inputs = nodes.new("ShaderNodeGroup")
        is_depth_plane = displacement_image is not None
        material_inputs.node_tree = material_node_group(is_depth_plane)
        material_inputs.location = (-300.0, 300.0)
        material_inputs.inputs["Bump Scale"].default_value = depth_scale
        if not is_depth_plane:
            material_inputs.inputs["Alpha Fix"].default_value = float(
                not material_image.is_float and configured_material_view_adaptation()
            )
        if "Object Space" in material_inputs.inputs:
            if normal_space not in {"TANGENT", "OBJECT"}:
                raise ValueError(f"Unsupported normal space: {normal_space}")
            material_inputs.inputs["Object Space"].default_value = normal_space == "OBJECT"
        links.new(color_texture.outputs["Color"], material_inputs.inputs["Color"])
        links.new(alpha, material_inputs.inputs["Alpha"])
        if normal_image is not None and "Normal" in material_inputs.inputs:
            normal_texture = nodes.new("ShaderNodeTexImage")
            normal_texture.image = normal_image
            normal_texture.interpolation = "Linear"
            normal_texture.extension = "EXTEND"
            normal_texture.location = (-700.0, 0.0)
            links.new(normal_texture.outputs["Color"], material_inputs.inputs["Normal"])
        if shadeless:
            shader = nodes.new("ShaderNodeGroup")
            shader.node_tree = load_node_group(SHADELESS_NODE_GROUP_NAME)
            shader.name = SHADELESS_NODE_GROUP_NAME
            shader.location = (100.0, 300.0)
            links.new(
                material_inputs.outputs["Color"],
                shader.inputs["Color"],
            )
            links.new(
                material_inputs.outputs["Alpha"],
                shader.inputs["Alpha"],
            )
            links.new(
                shader.outputs["Shader"],
                output.inputs["Surface"],
            )
        else:
            shader = nodes.new("ShaderNodeBsdfPrincipled")
            shader.location = (100.0, 300.0)
            shader.inputs["IOR"].default_value = 1.2

            links.new(
                material_inputs.outputs["Color"],
                shader.inputs["Base Color"],
            )
            links.new(
                material_inputs.outputs["Color"],
                shader.inputs["Subsurface Radius"],
            )
            links.new(
                material_inputs.outputs["Color"],
                shader.inputs["Emission Color"],
            )
            links.new(material_inputs.outputs["Alpha"], shader.inputs["Alpha"])
            links.new(material_inputs.outputs["Normal"], shader.inputs["Normal"])
            links.new(
                material_inputs.outputs["Normal"],
                shader.inputs["Coat Normal"],
            )
            links.new(
                material_inputs.outputs["Roughness"],
                shader.inputs["Roughness"],
            )
            links.new(
                material_inputs.outputs["Color"],
                shader.inputs["Specular IOR Level"],
            )
            links.new(shader.outputs["BSDF"], output.inputs["Surface"])

        if displacement_image is not None:
            depth_texture = nodes.new("ShaderNodeTexImage")
            depth_texture.image = displacement_image
            depth_texture.interpolation = "Linear"
            depth_texture.extension = "EXTEND"
            depth_texture.location = (-1200.0, -300.0)
            displacement_height = depth_texture.outputs["Color"]
            if displacement_midlevel != 0.0 or displacement_scale != 1.0:
                depth_adjust = nodes.new("ShaderNodeMath")
                depth_adjust.operation = "SUBTRACT"
                depth_adjust.inputs[1].default_value = displacement_midlevel
                depth_adjust.location = (-950.0, -300.0)
                depth_scale_node = nodes.new("ShaderNodeMath")
                depth_scale_node.operation = "MULTIPLY"
                depth_scale_node.inputs[1].default_value = displacement_scale
                depth_scale_node.location = (-700.0, -300.0)
                links.new(displacement_height, depth_adjust.inputs[0])
                links.new(depth_adjust.outputs[0], depth_scale_node.inputs[0])
                links.new(depth_scale_node.outputs[0], material_inputs.inputs["Depth"])
            else:
                links.new(displacement_height, material_inputs.inputs["Depth"])
            links.new(
                material_inputs.outputs["Displacement"],
                output.inputs["Displacement"],
            )
            set_displacement_only(material)
        return material
    except Exception:
        bpy.data.materials.remove(material, do_unlink=True)
        raise


def set_displacement_only(material):
    for owner, property_name in (
        (material, "surface_displacement_method"),
        (material, "displacement_method"),
        (getattr(material, "cycles", None), "displacement_method"),
    ):
        if owner is not None and hasattr(owner, property_name):
            setattr(owner, property_name, "DISPLACEMENT")
            return
