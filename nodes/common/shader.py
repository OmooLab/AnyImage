"""Build shared material inputs, roughness, and bump outputs."""
BUMP_BASE_DISTANCE = 0.001


def build_material_nodes(group):
    nodes = group.nodes
    group_input = nodes.new("NodeGroupInput")
    group_output = nodes.new("NodeGroupOutput")
    roughness_curve = nodes.new("ShaderNodeFloatCurve")
    roughness_curve.mapping.initialize()
    curve_points = roughness_curve.mapping.curves[0].points
    curve_points[0].location = (0.0, 0.5)
    curve_points[-1].location = (1.0, 0.1)
    roughness_curve.mapping.update()
    bump = nodes.new("ShaderNodeBump")
    return group_input, group_output, roughness_curve, bump


def connect_material_outputs(group, group_input, group_output, roughness_curve, bump, processed_alpha):
    nodes, links = group.nodes, group.links
    links.new(group_input.outputs["Color"], group_output.inputs["Color"])
    links.new(group_input.outputs["Color"], roughness_curve.inputs["Value"])
    links.new(
        roughness_curve.outputs["Value"],
        group_output.inputs["Roughness"],
    )
    links.new(processed_alpha, group_output.inputs["Alpha"])
    links.new(group_input.outputs["Color"], bump.inputs["Height"])
    bump_distance = nodes.new("ShaderNodeMath")
    bump_distance.operation = "MULTIPLY"
    bump_distance.inputs[1].default_value = BUMP_BASE_DISTANCE
    links.new(group_input.outputs["Bump Scale"], bump_distance.inputs[0])
    links.new(bump_distance.outputs[0], bump.inputs["Distance"])
    links.new(bump.outputs["Normal"], group_output.inputs["Normal"])
