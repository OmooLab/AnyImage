"""Replace baked image-layer outputs with standard shader nodes."""

from contextlib import contextmanager


def validate_layer(layer, color):
    """Validate texture inputs and the color passthrough before baking."""
    if layer.mute or layer.node_tree.animation_data:
        raise ValueError("Bake Mesh requires an unanimated texture layer")
    controls = {"Normal Scale", "Bump Scale", "Object Space", "Roughness Scale",
                "Roughness Contrast", "Alpha Scale", "Alpha Background", "Emission Threshold"}
    if (not controls | {"Color Texture", "Alpha Texture", "Normal Texture"} <= set(layer.inputs.keys())
            or set(layer.outputs.keys()) != {"Color", "Alpha", "Roughness", "Normal", "Emission"}):
        raise ValueError("Unsupported texture layer interface")
    for name in controls:
        if layer.inputs[name].is_linked:
            raise ValueError(f"Linked {name} is not supported by Bake Mesh")
    for name in ("Color", "Alpha"):
        socket = layer.inputs[f"{name} Texture"]
        if not socket.is_linked or socket.links[0].from_socket != color.outputs[name]:
            raise ValueError(f"Bake Mesh requires the Color texture's {name} output")
    output = next((n for n in layer.node_tree.nodes if n.type == "GROUP_OUTPUT" and n.is_active_output), None)
    if output is None or any(n.type == "GROUP" for n in layer.node_tree.nodes):
        raise ValueError("Unsupported texture layer structure")
    socket = output.inputs["Color"]
    if (not socket.is_linked or socket.links[0].from_node.type != "GROUP_INPUT"
            or socket.links[0].from_node.mute or socket.links[0].from_socket.name != "Color Texture"):
        raise ValueError("Unsupported texture layer Color output")


def emission_shaders(layer, color):
    """Return Principled shaders receiving the image color as emission."""
    return {link.to_node for socket in (layer.outputs["Emission"], layer.outputs["Color"], color.outputs["Color"])
            for link in socket.links if link.to_node.type == "BSDF_PRINCIPLED"
            and link.to_socket.name == "Emission Color"}


def remove_unused_material_nodes(material):
    """Keep only nodes feeding an active material output."""
    nodes = material.node_tree.nodes
    pending = [node for node in nodes if node.type == "OUTPUT_MATERIAL" and node.is_active_output]
    used = set()
    while pending:
        node = pending.pop()
        if node in used:
            continue
        used.add(node)
        pending.extend(link.from_node for socket in node.inputs for link in socket.links)
    for node in tuple(nodes):
        if node not in used:
            nodes.remove(node)


def arrange_material_textures(material):
    """Align texture rows in the order of their Principled inputs."""
    nodes = material.node_tree.nodes
    shaders = [node for node in nodes if node.type == "BSDF_PRINCIPLED"]
    if not shaders:
        return
    textures = []
    for shader in shaders:
        for socket in shader.inputs:
            pending = [link.from_node for link in socket.links]
            visited = set()
            while pending:
                node = pending.pop()
                if node in visited:
                    continue
                visited.add(node)
                if node.type == "TEX_IMAGE":
                    if node not in textures:
                        textures.append(node)
                else:
                    pending.extend(link.from_node for input in node.inputs for link in input.links)
    textures.extend(node for node in nodes if node.type == "TEX_IMAGE" and node not in textures)
    x, y = shaders[0].location
    for index, node in enumerate(textures):
        node.location = (x - 650, y - index * 360)
        node.width = 240
        for link in node.outputs["Color"].links:
            if link.to_node.type == "NORMAL_MAP":
                link.to_node.location = (x - 330, node.location.y)


def connect_static_outputs(links, layer, sources):
    """Reconnect every consumer of the original image-layer outputs."""
    for output in layer.outputs:
        for link in tuple(output.links):
            links.new(sources[output.name], link.to_socket)


@contextmanager
def static_material_outputs(material, layer, color, normal, scalar_images, emission_images, emission_strengths):
    """Stage replacement nodes and restore original links on any failure."""
    if layer is None:
        yield
        return
    normal_image, normal_node = normal
    nodes, links = material.node_tree.nodes, material.node_tree.links
    original_nodes = set(nodes)
    positions = {node: (tuple(node.location), node.width) for node in nodes}
    original_links = [(link.from_socket, link.to_socket) for link in links]
    active = nodes.active
    original_strengths = {name: nodes[name].inputs["Emission Strength"].default_value for name in emission_strengths}

    def create(kind, offset):
        node = nodes.new(kind)
        node.location = (layer.location.x + offset[0], layer.location.y + offset[1])
        return node

    def texture(image, offset):
        node = create("ShaderNodeTexImage", offset)
        node.image = image
        node.extension = color.extension
        return node.outputs["Color"]

    try:
        sources = {"Color": color.outputs["Color"], "Alpha": color.outputs["Alpha"]}
        for channel, image in scalar_images.items():
            sources[channel] = texture(image, (-400, -1000))
        if layer.outputs["Normal"].is_linked:
            if normal_image is not None:
                shader = create("ShaderNodeNormalMap", (0, -620))
                shader.uv_map = "UVMap"
                source = normal_node.outputs["Color"] if normal_node is not None else texture(normal_image, (-400, -620))
                links.new(source, shader.inputs["Color"])
            else:
                shader = create("ShaderNodeNewGeometry", (0, -620))
            sources["Normal"] = shader.outputs["Normal"]
        connect_static_outputs(links, layer, sources)
        emission_sources = {image: texture(image, (-400, -1400)) for image in set(emission_images.values())}
        for name, strength in emission_strengths.items():
            socket = nodes[name].inputs["Emission Color"]
            if strength == 0:
                for link in tuple(socket.links):
                    links.remove(link)
            elif strength > 0:
                links.new(emission_sources[emission_images[name]], socket)
            strength_socket = nodes[name].inputs["Emission Strength"]
            for link in tuple(strength_socket.links):
                links.remove(link)
            strength_socket.default_value = strength
        yield
        arrange_material_textures(material)
    except Exception:
        for node in set(nodes) - original_nodes:
            nodes.remove(node)
        links.clear()
        for source, target in original_links:
            links.new(source, target)
        for node, (location, width) in positions.items():
            node.location = location
            node.width = width
        nodes.active = active
        for name, strength in original_strengths.items():
            nodes[name].inputs["Emission Strength"].default_value = strength
        raise
