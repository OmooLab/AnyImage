"""Read image-layer material inputs and replace baked outputs with shader nodes."""

from contextlib import contextmanager
from dataclasses import dataclass, field


from ...common.color_image import require_static_color_image
from ...common.material import IMAGE_MATERIAL_NODE_GROUP_NAME
from .geometry import SINGLE_REGION_GROUPS


SHADELESS_NODE_GROUP_NAME = "O Shadeless"


def surface_color_texture(socket):
    """Follow the surface color connection to its image texture."""
    visited = set()
    while socket and socket.is_linked:
        link = socket.links[0]
        node = link.from_node
        if node in visited:
            break
        visited.add(node)
        if node.type == "TEX_IMAGE":
            if link.from_socket.name == "Color" and node.image:
                return node
            break
        if node.type == "REROUTE":
            socket = node.inputs[0]
        elif node.type == "BSDF_PRINCIPLED":
            socket = node.inputs["Base Color"]
        elif node.type == "GROUP":
            group_name = getattr(node.node_tree, "name", "")
            if group_name == IMAGE_MATERIAL_NODE_GROUP_NAME and link.from_socket.name == "Color":
                socket = node.inputs.get("Color Texture")
            elif group_name == SHADELESS_NODE_GROUP_NAME:
                socket = node.inputs.get("Color")
            else:
                break
        else:
            socket = node.inputs.get("Color")
    return None


@dataclass
class MaterialInputs:
    material: object
    color: object
    layer: object = None
    normal: object = None
    channels: tuple = ()
    emission_strengths: dict = field(default_factory=dict)


def material_inputs(obj, modifiers):
    """Validate the generated material before preparing any replacement data."""
    if not modifiers:
        raise ValueError("Select an image object with a supported Geometry Nodes prefix")
    if not obj.is_editable or obj.library is not None or obj.override_library is not None:
        raise ValueError("Bake Mesh requires an editable local object")
    if len(obj.data.materials) != 1 or obj.data.shape_keys is not None:
        raise ValueError("Bake Mesh requires one material and no shape keys")
    if obj.material_slots[0].link != "DATA":
        raise ValueError("Bake Mesh requires a mesh-linked material")
    material = obj.active_material
    if material is None or not material.is_editable or material.library is not None or material.override_library is not None:
        raise ValueError("Bake Mesh requires an editable local material")
    tree = material.node_tree
    output = tree.get_output_node("CYCLES") if tree and tree.is_editable else None
    surface = output.inputs["Surface"] if output else None
    color = surface_color_texture(surface)
    if color is None:
        raise ValueError("The Color texture is missing")
    require_static_color_image(color.image)
    if not color.image.is_editable or color.image.library is not None:
        raise ValueError("Bake Mesh requires an editable local Color image")
    layers = [node for node in tree.nodes
              if node.type == "GROUP" and node.node_tree is not None
              and node.node_tree.name == IMAGE_MATERIAL_NODE_GROUP_NAME]
    single_region = modifiers[0].node_group.name in SINGLE_REGION_GROUPS
    if not layers and single_region:
        shader = surface.links[0].from_node
        if shader.type == "EMISSION" or (shader.type == "GROUP" and shader.node_tree.name == SHADELESS_NODE_GROUP_NAME):
            return MaterialInputs(material, color)
    if len(layers) != 1:
        raise ValueError("Bake Mesh requires one O Texture to Layer")
    layer = layers[0]
    validate_layer(layer, color)
    normal = None
    if layer.inputs["Normal Texture"].is_linked:
        normal = layer.inputs["Normal Texture"].links[0].from_node
        if (normal.type != "TEX_IMAGE" or normal.image is None or normal == color
                or layer.inputs["Normal Texture"].links[0].from_socket != normal.outputs["Color"]):
            raise ValueError("Bake Mesh requires an image Normal input")
    elif layer.inputs["Object Space"].default_value or tuple(layer.inputs["Normal Texture"].default_value) != (.5, .5, 1, 1):
        raise ValueError("Bake Mesh requires an existing Normal image for static normals")
    if normal is not None and normal.image == color.image:
        raise ValueError("Bake Mesh requires separate Color and Normal images")
    emitters = emission_shaders(layer, color)
    emission_strengths = {}
    for shader in emitters:
        strength = shader.inputs["Emission Strength"]
        transformed = shader.inputs["Emission Color"].links[0].from_socket == layer.outputs["Emission"]
        emission_strengths[shader.name] = (
            None if strength.is_linked or (transformed and strength.default_value != 0)
            else strength.default_value
        )
    channels = [name for name in ("Roughness", "Alpha") if layer.outputs[name].is_linked]
    if layer.outputs["Normal"].is_linked and (normal is not None or layer.inputs["Bump Scale"].default_value):
        channels.append("Normal")
    if any(link.to_node not in emitters or link.to_socket.name != "Emission Color"
           for link in layer.outputs["Emission"].links):
        channels.append("Emission")
    inputs = MaterialInputs(
        material, color, layer=layer, normal=normal,
        channels=tuple(channels), emission_strengths=emission_strengths,
    )
    if single_region and not channels and None not in emission_strengths.values():
        return inputs
    extensions = {"EXTEND", "REPEAT"} if single_region else {"EXTEND"}
    for node in (color, normal):
        if node is None:
            continue
        if node.image.source not in {"FILE", "GENERATED"} or min(node.image.size) < 1:
            raise ValueError("Bake Mesh requires loaded static images")
        if (node is normal or not single_region) and (not node.image.is_editable or node.image.library is not None):
            raise ValueError("Bake Mesh requires editable local images")
        if node.interpolation != "Linear" or node.extension not in extensions or node.projection != "FLAT":
            raise ValueError("Bake Mesh requires linear, extended UV image textures")
        if node.inputs["Vector"].is_linked:
            source = node.inputs["Vector"].links[0].from_node
            if source.type != "UVMAP" or source.uv_map != "UVMap":
                raise ValueError("Bake Mesh requires the UVMap texture coordinates")
    return inputs


def validate_layer(layer, color):
    """Validate texture inputs and the color passthrough before baking."""
    if layer.mute or layer.node_tree.animation_data:
        raise ValueError("Bake Mesh requires an unanimated texture layer")
    controls = {"Normal Scale", "Bump Scale", "Object Space", "Roughness Scale",
                "Roughness Contrast", "Alpha Scale", "Alpha Background", "Highlight Threshold"}
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


@contextmanager
def static_material_outputs(material, layer, color, normal, output_images, emission_images, emission_strengths):
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
        for channel, image in output_images.items():
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
        for name, source in sources.items():
            for link in tuple(layer.outputs[name].links):
                links.new(source, link.to_socket)
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
