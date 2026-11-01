"""Create panorama environment lighting driven by the object's world rotation."""

import bpy

from ...common.node import load_node_group


def create_panorama_world(obj, color_image):
    world = bpy.data.worlds.new(f"{obj.name} World")
    try:
        world.use_nodes = True
        nodes = world.node_tree.nodes
        nodes.clear()
        coordinates = nodes.new("ShaderNodeTexCoord")
        coordinates.location = (-800, 0)
        rotation = nodes.new("ShaderNodeVectorRotate")
        rotation.rotation_type = "EULER_XYZ"
        rotation.invert = True
        rotation.location = (-580, 0)
        for index, axis in enumerate("XYZ"):
            driver = rotation.inputs["Rotation"].driver_add("default_value", index).driver
            driver.type = "SUM"
            variable = driver.variables.new()
            variable.name = "rotation"
            variable.type = "TRANSFORMS"
            target = variable.targets[0]
            target.id = obj
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
        links.new(coordinates.outputs["Generated"], rotation.inputs["Vector"])
        links.new(rotation.outputs["Vector"], texture.inputs["Vector"])
        links.new(texture.outputs["Color"], background.inputs["Light"])
        links.new(background.outputs["Shader"], output.inputs["Surface"])
    except Exception:
        bpy.data.worlds.remove(world, do_unlink=True)
        raise
    return world
