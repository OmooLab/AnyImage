"""Crop panorama inputs and create their World lighting."""

import bpy

from .image import image_base_name
from .node import load_node_group


def panorama_crop_bounds(width, height):
    """Return the largest centered integer-pixel 2:1 bounds."""
    width, height = int(width), int(height)
    crop_height = min(height, width // 2)
    crop_width = crop_height * 2
    if crop_width <= 0 or crop_height <= 0:
        raise ValueError("Panorama conversion requires an image at least 2 x 1 pixels")
    left = (width - crop_width) // 2
    top = (height - crop_height) // 2
    return left, top, left + crop_width, top + crop_height


def report_panorama_crop(operator, size, bounds):
    width, height = size
    crop_width = bounds[2] - bounds[0]
    crop_height = bounds[3] - bounds[1]
    if (crop_width, crop_height) != (width, height):
        operator.report({"WARNING"}, bpy.app.translations.pgettext_rpt(
            "Panorama input cropped from {width} x {height} to {crop_width} x {crop_height}"
        ).format(width=width, height=height, crop_width=crop_width, crop_height=crop_height))


def create_panorama_world(source_image, color_image, *, panorama_object=None):
    world = bpy.data.worlds.new(image_base_name(source_image))
    try:
        world.use_nodes = True
        nodes = world.node_tree.nodes
        nodes.clear()
        rotation = nodes.new("ShaderNodeGroup")
        rotation.node_tree = load_node_group("O World Vector")
        rotation.inputs["Horizon Bend"].default_value = -0.1
        rotation.location = (-580, 0)
        if panorama_object is not None:
            for index, axis in enumerate("XYZ"):
                driver = rotation.inputs["Rotation"].driver_add("default_value", index).driver
                driver.type = "SUM"
                variable = driver.variables.new()
                variable.name = "rotation"
                variable.type = "TRANSFORMS"
                target = variable.targets[0]
                target.id = panorama_object
                target.transform_type = f"ROT_{axis}"
                target.transform_space = "WORLD_SPACE"
                target.rotation_mode = "XYZ"
        texture = nodes.new("ShaderNodeTexEnvironment")
        texture.image = color_image
        texture.projection = "EQUIRECTANGULAR"
        texture.location = (-340, 0)
        background = nodes.new("ShaderNodeGroup")
        background.node_tree = load_node_group("O Background")
        background.location = (0, 0)
        output = nodes.new("ShaderNodeOutputWorld")
        output.location = (240, 0)
        links = world.node_tree.links
        links.new(rotation.outputs["Vector"], texture.inputs["Vector"])
        links.new(texture.outputs["Color"], background.inputs["Color"])
        links.new(texture.outputs["Color"], background.inputs["Light"])
        links.new(background.outputs["Shader"], output.inputs["Surface"])
    except Exception:
        bpy.data.worlds.remove(world, do_unlink=True)
        raise
    return world
