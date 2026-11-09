"""Bake terrain boundary normals while preserving the generated sky normals."""

from contextlib import ExitStack

import bpy
import numpy as np

from ...common.bake import BAKE_MARGIN, bake_context
from ...common.image import image_pixels
from ...common.material import IMAGE_MATERIAL_NODE_GROUP_NAME


def bake_panorama_normal(context, obj, depth, coverage_path, *, name):
    """Combine a terrain-only bake and the generated sky in one packed image."""
    material = obj.active_material
    layer = next(node for node in material.node_tree.nodes
                 if node.type == "GROUP" and node.node_tree.name == IMAGE_MATERIAL_NODE_GROUP_NAME)
    normal_texture = layer.inputs["Normal Texture"].links[0].from_node
    source = normal_texture.image
    width, height = source.size
    image = bpy.data.images.new(name, width=width, height=height, alpha=False)
    try:
        image.colorspace_settings.name = "Non-Color"
        with ExitStack() as cleanup:
            coverage = bpy.data.images.load(str(coverage_path), check_existing=False)
            cleanup.callback(bpy.data.images.remove, coverage, do_unlink=True)
            coverage.colorspace_settings.name = "Non-Color"
            if tuple(coverage.size) != (width, height) or tuple(depth.size) != (width, height):
                raise ValueError("Panorama depth and normal dimensions do not match")

            graph = context.evaluated_depsgraph_get()
            mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(graph),
                                                   preserve_all_data_layers=True, depsgraph=graph)
            cleanup.callback(bpy.data.meshes.remove, mesh)
            uv = mesh.uv_layers.get("UVMap")
            if uv is None:
                raise ValueError("The evaluated panorama mesh is missing UVMap")
            mesh.uv_layers.active = uv
            uv.active_render = True
            bake_material = material.copy()
            cleanup.callback(bpy.data.materials.remove, bake_material, do_unlink=True)
            nodes, links = bake_material.node_tree.nodes, bake_material.node_tree.links
            bake_layer = nodes[layer.name]
            bake_layer.inputs["Bump Scale"].default_value = 0.0
            weight = nodes.new("ShaderNodeTexImage")
            weight.image = coverage
            weight.extension = "REPEAT"
            geometry = nodes.new("ShaderNodeNewGeometry")
            mix = nodes.new("ShaderNodeMix")
            mix.data_type = "VECTOR"
            links.new(weight.outputs["Color"], mix.inputs[0])
            links.new(geometry.outputs["Normal"], mix.inputs[4])
            links.new(bake_layer.outputs["Normal"], mix.inputs[5])
            local = nodes.new("ShaderNodeVectorTransform")
            local.vector_type = "NORMAL"
            local.convert_from = "WORLD"
            local.convert_to = "OBJECT"
            links.new(mix.outputs[1], local.inputs["Vector"])
            encode = nodes.new("ShaderNodeVectorMath")
            encode.operation = "MULTIPLY_ADD"
            encode.inputs[1].default_value = (.5, .5, .5)
            encode.inputs[2].default_value = (.5, .5, .5)
            links.new(local.outputs["Vector"], encode.inputs[0])
            emission = nodes.new("ShaderNodeEmission")
            links.new(encode.outputs["Vector"], emission.inputs["Color"])
            output = next(node for node in nodes if node.type == "OUTPUT_MATERIAL" and node.is_active_output)
            links.new(emission.outputs[0], output.inputs["Surface"])
            target = nodes.new("ShaderNodeTexImage")
            target.image = image
            nodes.active = target

            with bake_context(mesh, bake_material, obj.matrix_world):
                result = bpy.ops.object.bake(type="EMIT", uv_layer=uv.name,
                                             use_selected_to_active=False, margin=BAKE_MARGIN, margin_type="EXTEND")
            if result != {"FINISHED"}:
                raise RuntimeError("Panorama normal baking was cancelled")

        baked = image_pixels(image).reshape(-1, 4)
        generated = image_pixels(source).reshape(-1, 4)
        terrain = image_pixels(depth).reshape(-1, 4)[:, 3] >= 0.9
        # Black is unfilled bake output. An encoded unit normal cannot be black.
        usable = terrain & np.any(baked[:, :3] > 0, axis=1)
        generated[usable, :3] = baked[usable, :3]
        image.pixels.foreach_set(generated.ravel())
        image.update()
        image.pack()
        normal_texture.image = image
        return image
    except Exception:
        bpy.data.images.remove(image, do_unlink=True)
        raise
