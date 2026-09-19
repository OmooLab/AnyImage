"""Build nodes that decode legacy Direction parameters into canonical space."""


def legacy_direction_to_canonical(group, legacy):
    nodes = group.nodes
    links = group.links
    axes = nodes.new("ShaderNodeSeparateXYZ")
    links.new(legacy, axes.inputs[0])
    negative_x = nodes.new("ShaderNodeMath")
    negative_x.operation = "MULTIPLY"
    negative_x.inputs[1].default_value = -1.0
    links.new(axes.outputs["X"], negative_x.inputs[0])
    negative_y = nodes.new("ShaderNodeMath")
    negative_y.operation = "MULTIPLY"
    negative_y.inputs[1].default_value = -1.0
    links.new(axes.outputs["Y"], negative_y.inputs[0])
    direction = nodes.new("ShaderNodeCombineXYZ")
    links.new(negative_x.outputs[0], direction.inputs["X"])
    links.new(axes.outputs["Z"], direction.inputs["Y"])
    links.new(negative_y.outputs[0], direction.inputs["Z"])
    return direction.outputs["Vector"]


def symmetry_legacy_direction_to_canonical(group, legacy):
    nodes = group.nodes
    links = group.links
    axes = nodes.new("ShaderNodeSeparateXYZ")
    links.new(legacy, axes.inputs[0])
    direction = nodes.new("ShaderNodeCombineXYZ")
    links.new(axes.outputs["X"], direction.inputs["X"])
    links.new(axes.outputs["Z"], direction.inputs["Y"])
    links.new(axes.outputs["Y"], direction.inputs["Z"])
    return direction.outputs["Vector"]
