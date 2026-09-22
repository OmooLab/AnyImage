"""Build interfaces and basic nodes shared by asset definitions."""
from types import SimpleNamespace


def prepare_node_group(node_group):
    """Hide unused outputs and discard disconnected interface nodes."""
    for node in list(node_group.nodes):
        for socket in node.outputs:
            socket.hide = not socket.is_linked
        if node.bl_idname == "NodeGroupInput" and not any(socket.is_linked for socket in node.outputs):
            node_group.nodes.remove(node)


def replace_link_source(node_group, link, source):
    """Replace a source while preserving multi-input socket order."""
    multi = link.to_socket.is_multi_input
    replacement = node_group.links.new(source, link.to_socket)
    if multi:
        replacement.swap_multi_input_sort_id(link)
        node_group.links.remove(link)


def interface_socket(group, name, in_out, socket_type, parent=None):
    socket = group.interface.new_socket(
        name=name,
        in_out=in_out,
        socket_type=socket_type,
        parent=parent,
    )
    if in_out == "INPUT" and hasattr(socket, "structure_type"):
        socket.structure_type = "SINGLE"
    return socket


def group_input(nodes, visible_names):
    node = nodes.new("NodeGroupInput")
    visible = set(visible_names)
    for output in node.outputs:
        output.hide = output.name not in visible
    return node


def float_input(
    group,
    name,
    default,
    minimum=0.0,
    maximum=None,
    subtype=None,
    parent=None,
):
    socket = interface_socket(group, name, "INPUT", "NodeSocketFloat", parent)
    socket.default_value = default
    socket.min_value = minimum
    if maximum is not None:
        socket.max_value = maximum
    if subtype is not None:
        socket.subtype = subtype
    return socket


def bool_input(group, name, default=False, parent=None):
    socket = interface_socket(group, name, "INPUT", "NodeSocketBool", parent)
    socket.default_value = default
    return socket


def vector_input(group, name, default, subtype=None, parent=None):
    socket = interface_socket(group, name, "INPUT", "NodeSocketVector", parent)
    socket.default_value = default
    if subtype is not None:
        socket.subtype = subtype
    return socket


def math_node(nodes, operation):
    node = nodes.new("ShaderNodeMath")
    node.operation = operation
    return node


_COMPARE_INPUTS = {
    "FLOAT": ("A", "B"),
    "INT": ("A_INT", "B_INT"),
    "VECTOR": ("A_VEC3", "B_VEC3"),
    "RGBA": ("A_COL", "B_COL"),
}


def compare_node(group, operation, a, b, data_type="FLOAT"):
    """Compare two inputs on the given data type and return the boolean result."""
    node = group.nodes.new("FunctionNodeCompare")
    node.data_type, node.operation = data_type, operation
    for value, identifier in zip((a, b), _COMPARE_INPUTS[data_type]):
        socket = next(item for item in node.inputs if item.identifier == identifier)
        if isinstance(value, (bool, int, float)):
            socket.default_value = value
        else:
            group.links.new(value, socket)
    return node.outputs["Result"]


def boolean_node(group, operation, a=None, b=None):
    """Combine boolean inputs and return the boolean result."""
    node = group.nodes.new("FunctionNodeBooleanMath")
    node.operation = operation
    for value, index in ((a, 0), (b, 1)):
        if value is None:
            continue
        if isinstance(value, bool):
            node.inputs[index].default_value = value
        else:
            group.links.new(value, node.inputs[index])
    return node.outputs["Boolean"]


def menu_switch(group, control, names, kind):
    selector = next((node for node in group.nodes if node.bl_idname == "GeometryNodeMenuSwitch" and node.inputs["Menu"].is_linked and node.inputs["Menu"].links[0].from_socket.name == control), None)
    if selector is None:
        selector = group.nodes.new("GeometryNodeMenuSwitch")
        selector.data_type = "BOOLEAN"
        for item, name in zip(selector.enum_items, names):
            item.name = name
        selector.inputs[names[0]].default_value = False
        selector.inputs[names[1]].default_value = True
        local = group_input(group.nodes, {control})
        group.links.new(local.outputs[control], selector.inputs["Menu"])
    node = group.nodes.new("GeometryNodeSwitch")
    node.input_type = kind
    group.links.new(selector.outputs[0], node.inputs["Switch"])
    return SimpleNamespace(inputs={names[0]: node.inputs["False"], names[1]: node.inputs["True"]}, outputs=node.outputs)


def read_float_attribute(group, name):
    node = group.nodes.new("GeometryNodeInputNamedAttribute")
    node.data_type = "FLOAT"
    node.inputs["Name"].default_value = name
    return node.outputs["Attribute"]


def read_vector_attribute(group, name):
    node = group.nodes.new("GeometryNodeInputNamedAttribute")
    node.data_type = "FLOAT_VECTOR"
    node.inputs["Name"].default_value = name
    return node.outputs["Attribute"]


def read_int_attribute(group, name):
    node = group.nodes.new("GeometryNodeInputNamedAttribute")
    node.data_type = "INT"
    node.inputs["Name"].default_value = name
    return node.outputs["Attribute"]


def store_float_attribute(group, geometry, name, value, domain="POINT"):
    node = group.nodes.new("GeometryNodeStoreNamedAttribute")
    node.domain, node.data_type = domain, "FLOAT"
    node.inputs["Name"].default_value = name
    group.links.new(geometry, node.inputs["Geometry"])
    if isinstance(value, (int, float)):
        node.inputs["Value"].default_value = value
    else:
        group.links.new(value, node.inputs["Value"])
    return node.outputs["Geometry"]


def store_vector_attribute(group, geometry, name, value, domain="POINT"):
    node = group.nodes.new("GeometryNodeStoreNamedAttribute")
    node.domain, node.data_type = domain, "FLOAT_VECTOR"
    node.inputs["Name"].default_value = name
    group.links.new(geometry, node.inputs["Geometry"])
    group.links.new(value, node.inputs["Value"])
    return node.outputs["Geometry"]


def store_int_attribute(group, geometry, name, value, domain="POINT"):
    node = group.nodes.new("GeometryNodeStoreNamedAttribute")
    node.domain, node.data_type = domain, "INT"
    node.inputs["Name"].default_value = name
    group.links.new(geometry, node.inputs["Geometry"])
    if isinstance(value, int):
        node.inputs["Value"].default_value = value
    else:
        group.links.new(value, node.inputs["Value"])
    return node.outputs["Geometry"]


def evaluate_field(group, value, data_type, domain):
    """Evaluate a field on an explicit domain before downstream adaptation."""
    node = group.nodes.new("GeometryNodeFieldOnDomain")
    node.data_type, node.domain = data_type, domain
    group.links.new(value, node.inputs["Value"])
    return node.outputs["Value"]


def sample_field(group, geometry, value, data_type, domain="POINT", index=None):
    """Evaluate a field on an explicit source geometry and index domain."""
    node = group.nodes.new("GeometryNodeSampleIndex")
    node.data_type, node.domain = data_type, domain
    node.clamp = False
    if index is None:
        index = group.nodes.new("GeometryNodeInputIndex").outputs["Index"]
    group.links.new(geometry, node.inputs["Geometry"])
    group.links.new(value, node.inputs["Value"])
    group.links.new(index, node.inputs["Index"])
    return node.outputs["Value"]


def store_boolean_attribute(group, geometry, name, value, domain="POINT"):
    """Store a topology marker needed after destructive mesh operations."""
    node = group.nodes.new("GeometryNodeStoreNamedAttribute")
    node.domain, node.data_type = domain, "BOOLEAN"
    node.inputs["Name"].default_value = name
    group.links.new(geometry, node.inputs["Geometry"])
    group.links.new(value, node.inputs["Value"])
    read = group.nodes.new("GeometryNodeInputNamedAttribute")
    read.data_type = "BOOLEAN"
    read.inputs["Name"].default_value = name
    return node.outputs["Geometry"], read.outputs["Attribute"]


def remove_attribute_pattern(group, geometry, pattern):
    """Remove every attribute matching an internal wildcard pattern.

    Always clean internal attributes with a pattern: naming an attribute that a
    branch never stored makes the Remove Named Attribute node warn.
    """
    node = group.nodes.new("GeometryNodeRemoveAttribute")
    node.inputs["Name"].default_value = pattern
    node.pattern_mode = "WILDCARD"
    group.links.new(geometry, node.inputs["Geometry"])
    return node.outputs["Geometry"]
