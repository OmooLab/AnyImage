"""Build the Shadeless shader node group."""

import bpy


SHADELESS_GROUP_NAME = "O Shadeless"


def build_shadeless_group():
    group = bpy.data.node_groups.new(SHADELESS_GROUP_NAME, "ShaderNodeTree")
    group.interface.new_socket(
        name="Shader", in_out="OUTPUT", socket_type="NodeSocketShader"
    )
    group.interface.new_socket(
        name="Color", in_out="INPUT", socket_type="NodeSocketColor"
    )
    alpha = group.interface.new_socket(name="Alpha", in_out="INPUT", socket_type="NodeSocketFloat")
    alpha.default_value, alpha.min_value, alpha.max_value = 1.0, 0.0, 1.0
    alpha.subtype = "FACTOR"
    strength = group.interface.new_socket(
        name="Strength", in_out="INPUT", socket_type="NodeSocketFloat"
    )
    strength.description = "Set the emission strength for camera rays. Zero renders the surface black."
    strength.default_value, strength.min_value = 1.0, 0.0
    nodes = group.nodes
    links = group.links
    group_input = nodes.new("NodeGroupInput")
    group_output = nodes.new("NodeGroupOutput")

    diffuse = nodes.new("ShaderNodeBsdfDiffuse")
    emission = nodes.new("ShaderNodeEmission")
    links.new(group_input.outputs["Color"], diffuse.inputs["Color"])
    links.new(group_input.outputs["Color"], emission.inputs["Color"])
    links.new(group_input.outputs["Strength"], emission.inputs["Strength"])

    light_path = nodes.new("ShaderNodeLightPath")
    bounce_count = nodes.new("ShaderNodeMath")
    bounce_count.operation = "SUBTRACT"
    links.new(light_path.outputs["Ray Depth"], bounce_count.inputs[0])
    links.new(light_path.outputs["Transmission Depth"], bounce_count.inputs[1])
    refracted = nodes.new("ShaderNodeMath")
    refracted.operation = "SUBTRACT"
    refracted.inputs[0].default_value = 1.0
    links.new(bounce_count.outputs[0], refracted.inputs[1])

    reflection_limit = nodes.new("ShaderNodeMath")
    reflection_limit.operation = "SUBTRACT"
    reflection_limit.inputs[0].default_value = 2.0
    links.new(light_path.outputs["Ray Depth"], reflection_limit.inputs[1])
    camera_reflected = nodes.new("ShaderNodeMath")
    camera_reflected.operation = "MULTIPLY"
    links.new(reflection_limit.outputs[0], camera_reflected.inputs[0])
    links.new(light_path.outputs["Is Glossy Ray"], camera_reflected.inputs[1])
    shadow_or_reflect = nodes.new("ShaderNodeMath")
    shadow_or_reflect.operation = "MAXIMUM"
    links.new(camera_reflected.outputs[0], shadow_or_reflect.inputs[0])
    links.new(light_path.outputs["Is Shadow Ray"], shadow_or_reflect.inputs[1])
    shader_factor = nodes.new("ShaderNodeMath")
    shader_factor.operation = "MAXIMUM"
    links.new(shadow_or_reflect.outputs[0], shader_factor.inputs[0])
    links.new(refracted.outputs[0], shader_factor.inputs[1])

    mix = nodes.new("ShaderNodeMixShader")
    links.new(shader_factor.outputs[0], mix.inputs["Fac"])
    links.new(diffuse.outputs["BSDF"], mix.inputs[1])
    links.new(emission.outputs["Emission"], mix.inputs[2])
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    alpha_mix = nodes.new("ShaderNodeMixShader")
    links.new(group_input.outputs["Alpha"], alpha_mix.inputs["Fac"])
    links.new(transparent.outputs["BSDF"], alpha_mix.inputs[1])
    links.new(mix.outputs["Shader"], alpha_mix.inputs[2])
    links.new(alpha_mix.outputs["Shader"], group_output.inputs["Shader"])
    group.color_tag = "SHADER"
    group.description = (
        "Display color without scene lighting while preserving shadows "
        "and reflections."
    )
    group.use_fake_user = True
    return group
