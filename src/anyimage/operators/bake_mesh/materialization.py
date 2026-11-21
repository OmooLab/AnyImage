"""Materialize static geometry and update existing images and material inputs."""

import bpy

from ...common.bake import BAKE_MARGIN, bake_context
from ...common.color_image import create_normalized_color_image
from ...common.image import (
    create_image_edit_result, has_other_image_user, image_content_state, image_pixels,
    replace_image_content, restore_image_content,
)
from ...common.image_target import material_has_other_object_user
from .geometry import PROTOCOL_ATTRIBUTES, SINGLE_REGION_GROUPS, TARGET_UV, build_layout, isolate_bake_modifiers
from .textures import build_color_tiles, create_emission_color_image, merge_color_alpha
from .materials import material_inputs, remove_unused_material_nodes, static_material_outputs


def bake_material_output(material, layer_name, size, output_name, emitter_name=None):
    """Bake a layer output using explicit source and target UVs."""
    layer = material.node_tree.nodes[layer_name]
    image = None
    nodes, links = material.node_tree.nodes, material.node_tree.links
    created = []
    output = material.node_tree.get_output_node("CYCLES")
    if output is None:
        raise ValueError("Bake Mesh requires a Cycles material output")
    surface = output.inputs["Surface"]
    original_surface = surface.links[0].from_socket if surface.is_linked else None
    active = nodes.active
    try:
        is_normal = output_name == "Normal"
        is_roughness = output_name == "Roughness"
        image = bpy.data.images.new(f"Mesh bake {output_name.lower()}", width=size[0], height=size[1], alpha=True, float_buffer=not is_roughness)
        image.colorspace_settings.name = "Non-Color"
        image.file_format = "PNG" if is_roughness else "OPEN_EXR"
        shader = nodes.new("ShaderNodeBsdfDiffuse" if is_normal else "ShaderNodeEmission")
        created.append(shader)
        if emitter_name is not None:
            emitter = nodes[emitter_name]
            source = emitter.inputs["Emission Color"].links[0].from_socket
            strength = emitter.inputs["Emission Strength"]
            if strength.is_linked:
                links.new(strength.links[0].from_socket, shader.inputs["Strength"])
            else:
                shader.inputs["Strength"].default_value = strength.default_value
        else:
            source = layer.outputs[output_name]
        links.new(source, shader.inputs["Normal" if is_normal else "Color"])
        links.new(shader.outputs[0], surface)
        target = nodes.new("ShaderNodeTexImage")
        created.append(target)
        target.image = image
        nodes.active = target
        result = bpy.ops.object.bake(type="NORMAL" if is_normal else "EMIT", normal_space="TANGENT", normal_r="POS_X", normal_g="POS_Y", normal_b="POS_Z",
                                     use_selected_to_active=False, uv_layer=bpy.context.object.data.uv_layers.active.name,
                                     margin=BAKE_MARGIN, margin_type="EXTEND")
        if result != {"FINISHED"}:
            raise RuntimeError(f"{output_name} baking was cancelled")
        return image
    except Exception:
        if image is not None:
            bpy.data.images.remove(image, do_unlink=True)
        raise
    finally:
        for node in created:
            nodes.remove(node)
        if original_surface is not None:
            links.new(original_surface, surface)
        nodes.active = active


def materialize_mesh_and_textures(context, obj, modifiers):
    """Return a static mesh and update source textures and material inputs.

    Keep the object mesh and modifiers unchanged for the operator to assign.
    Restore source images and material inputs if materialization fails.
    """
    inputs = material_inputs(obj, modifiers)
    material, layer = inputs.material, inputs.layer
    color, normal = inputs.color, inputs.normal
    channels, emission_strengths = inputs.channels, inputs.emission_strengths
    single_region = modifiers[0].node_group.name in SINGLE_REGION_GROUPS
    mesh = None
    bake_material = None
    source_color = color.image
    source_normal = normal.image if normal is not None else None
    isolate_material = material_has_other_object_user(material, obj)
    isolated_images = {node.name: isolate_material or has_other_image_user(node)
                       for node in (color, normal) if node is not None}
    static_material = None
    updates = []
    originals = []
    output_images = {}
    emission_images = {}
    static_normal = None
    images = []
    transferred = False
    try:
        with isolate_bake_modifiers(context, obj, modifiers) as graph:
            mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(graph), preserve_all_data_layers=True, depsgraph=graph)
        if not mesh.polygons:
            raise ValueError("The evaluated image object has no faces")
        tiles = build_layout(mesh, single_region=single_region)
        pixels = build_color_tiles(source_color, tiles)
        color_size = (pixels.shape[1], pixels.shape[0])
        if channels or None in emission_strengths.values():
            bake_material = material.copy()
            with bake_context(mesh, bake_material, obj.matrix_world):
                for channel in channels:
                    size = color_size
                    if channel == "Normal" and source_normal is not None:
                        size = (max(color_size[0], source_normal.size[0] * len(tiles[0])),
                                max(color_size[1], source_normal.size[1] * len(tiles)))
                    image = bake_material_output(bake_material, layer.name, size, channel)
                    if channel == "Alpha":
                        try:
                            merge_color_alpha(pixels, image_pixels(image).reshape(-1, 4)[:, 0], source_color)
                        finally:
                            bpy.data.images.remove(image)
                        continue
                    images.append(image)
                    image.pack()
                    if channel == "Normal":
                        static_normal = image
                        if normal is not None:
                            updates.append((normal.name, source_normal, image))
                        else:
                            image.name = f"{material.name}_normal.exr"
                    else:
                        extension = "exr" if channel == "Emission" else "png"
                        image.name = f"{material.name}_{channel.lower()}.{extension}"
                        output_images[channel] = image
                for name, strength in emission_strengths.items():
                    if strength is not None:
                        continue
                    shader = material.node_tree.nodes[name]
                    shader_strength = shader.inputs["Emission Strength"]
                    if ("Emission" in output_images and not shader_strength.is_linked and shader_strength.default_value == 1
                            and shader.inputs["Emission Color"].links[0].from_socket == layer.outputs["Emission"]):
                        image, emission_strengths[name] = create_emission_color_image(output_images["Emission"])
                    else:
                        linear_emission = bake_material_output(bake_material, layer.name, color_size, "Emission", name)
                        try:
                            image, emission_strengths[name] = create_emission_color_image(linear_emission)
                        finally:
                            bpy.data.images.remove(linear_emission)
                    images.append(image)
                    image.name = f"{material.name}_emissioncolor.png"
                    emission_images[name] = image
            bpy.data.materials.remove(bake_material)
            bake_material = None
        final_color = create_image_edit_result(source_color, pixels.ravel(), color_size, pack=False)
        images.append(final_color)
        if "Alpha" in channels and final_color.alpha_mode == "NONE":
            final_color.alpha_mode = "STRAIGHT"
        del pixels
        constant_emitters = [name for name, strength in emission_strengths.items() if name not in emission_images and strength > 0]
        if constant_emitters:
            emission_image, strength_scale = create_emission_color_image(final_color)
            images.append(emission_image)
            emission_image.name = f"{material.name}_emissioncolor.png"
            for name in constant_emitters:
                emission_images[name] = emission_image
                emission_strengths[name] *= strength_scale
        normalized_color = create_normalized_color_image(final_color)
        images.append(normalized_color)
        updates.insert(0, (color.name, source_color, normalized_color))
        if not single_region:
            mesh.uv_layers.remove(mesh.uv_layers["UVMap"])
            mesh.uv_layers[TARGET_UV].name = "UVMap"
        mesh.uv_layers.active = mesh.uv_layers["UVMap"]
        mesh.uv_layers.active.active_render = True
        for name in tuple(mesh.attributes.keys()):
            if name in PROTOCOL_ATTRIBUTES:
                mesh.attributes.remove(mesh.attributes[name])
        for name in PROTOCOL_ATTRIBUTES:
            if name in mesh:
                del mesh[name]
        static_material = material.copy() if isolate_material else material
        mesh.materials.clear()
        mesh.materials.append(static_material)
        mesh.update()
        static_nodes = static_material.node_tree.nodes
        static_layer = static_nodes[layer.name] if layer is not None else None
        static_color = static_nodes[color.name]
        static_normal_node = static_nodes[normal.name] if normal is not None else None
        with static_material_outputs(static_material, static_layer, static_color,
                                     (static_normal, static_normal_node), output_images, emission_images, emission_strengths):
            for node_name, source, result in updates:
                if isolated_images[node_name]:
                    originals.append((node_name, source, None))
                    static_nodes[node_name].image = result
                    result.name = source.name
                else:
                    originals.append((node_name, source, image_content_state(source)))
                    replace_image_content(source, result)
        remove_unused_material_nodes(static_material)
        transferred = True
        return mesh
    finally:
        if bake_material is not None:
            bpy.data.materials.remove(bake_material)
        if not transferred:
            for node_name, image, content in reversed(originals):
                static_material.node_tree.nodes[node_name].image = image
                if content is not None:
                    restore_image_content(image, content)
            if mesh is not None:
                bpy.data.meshes.remove(mesh)
            if static_material is not None and static_material != material:
                bpy.data.materials.remove(static_material)
        for image in images:
            if image.users == 0:
                bpy.data.images.remove(image)
