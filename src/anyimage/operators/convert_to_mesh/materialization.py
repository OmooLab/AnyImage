"""Prepare static Cutout geometry and textures before an atomic commit."""

from contextlib import ExitStack, contextmanager

import bpy
import numpy as np

from ...common.image_target import is_image_object, object_color_texture
from ...common.material import IMAGE_MATERIAL_NODE_GROUP_NAME
from ..cutout_tool.shape import CUTOUT_NODE_GROUP_NAMES, IMAGE_REGION_ATTRIBUTE_NAME
from .textures import build_color_tiles


SOURCE_UV = "_anyimage_source_uv"
TARGET_UV = "_anyimage_target_uv"
MARGIN = 4
PROTOCOL_ATTRIBUTES = frozenset({
    "o_balloon", "o_normal_reduction", "o_depth_rotation", "o_depth_face",
    "o_depth_axis", IMAGE_REGION_ATTRIBUTE_NAME,
    "_o_depth_cut", "_o_depth_limit_boundary", "_o_boundary_smooth_weight",
    "_o_boundary_falloff", "_o_cut_boundary", "_o_front_normal", "_o_leaf_id",
    "_o_side_ring_target", "_o_leaf_source_index", "_o_side_base_uv", "_o_side_top_uv",
    "_o_symmetry_weld", "_o_pinned_smooth_boundary", "_o_pinned_smooth_normalization",
    "_o_pinned_smooth_region_point", "_o_pinned_smooth_region_corner",
})


def supports_conversion(obj):
    """Recognize the supported editable Cutout modifier stack."""
    if not is_image_object(obj) or not getattr(obj, "modifiers", None):
        return False
    groups = []
    for modifier in obj.modifiers:
        if modifier.type != "NODES" or modifier.node_group is None or not modifier.show_viewport or not modifier.show_render:
            return False
        groups.append(modifier.node_group.name)
    return groups in (
        [CUTOUT_NODE_GROUP_NAMES["SOLID"]],
        [CUTOUT_NODE_GROUP_NAMES["DEPTH_SOLID"]],
        [CUTOUT_NODE_GROUP_NAMES["SOLID"], CUTOUT_NODE_GROUP_NAMES["DEPTH_SYMMETRY"]],
        [CUTOUT_NODE_GROUP_NAMES["DEPTH_SOLID"], CUTOUT_NODE_GROUP_NAMES["DEPTH_SYMMETRY"]],
    )


def material_inputs(obj):
    """Validate the generated material before preparing any replacement data."""
    if not supports_conversion(obj):
        raise ValueError("Select a Cutout with a supported Geometry Nodes stack")
    if not obj.is_editable or obj.library is not None or obj.override_library is not None:
        raise ValueError("Conversion requires an editable local object")
    if len(obj.data.materials) != 1 or obj.data.shape_keys is not None:
        raise ValueError("Conversion requires one material and no shape keys")
    if obj.material_slots[0].link != "DATA":
        raise ValueError("Conversion requires a mesh-linked material")
    color = object_color_texture(obj)
    if color is None:
        raise ValueError("The Cutout Color texture is missing")
    material = obj.active_material
    layers = [node for node in material.node_tree.nodes
              if node.type == "GROUP" and node.node_tree is not None
              and node.node_tree.name == IMAGE_MATERIAL_NODE_GROUP_NAME]
    if len(layers) != 1:
        raise ValueError("Conversion requires one O Image Layer")
    layer = layers[0]
    for name in ("Normal Scale", "Object Space", "Bump Scale"):
        if layer.inputs[name].is_linked:
            raise ValueError(f"Linked {name} is not supported by Convert to Mesh")
    normal = None
    if layer.inputs["Normal"].is_linked:
        normal = layer.inputs["Normal"].links[0].from_node
        if normal.type != "TEX_IMAGE" or normal.image is None or normal == color:
            raise ValueError("Conversion requires an image Normal input")
    for node in (color, normal):
        if node is None:
            continue
        if node.image.source not in {"FILE", "GENERATED"} or min(node.image.size) < 1:
            raise ValueError("Conversion requires loaded static images")
        if node.interpolation != "Linear" or node.extension != "EXTEND" or node.projection != "FLAT":
            raise ValueError("Conversion requires linear, extended UV image textures")
        if node.inputs["Vector"].is_linked:
            source = node.inputs["Vector"].links[0].from_node
            if source.type != "UVMAP" or source.uv_map != "UVMap":
                raise ValueError("Conversion requires the Cutout UVMap")
    return material, layer, color, normal


@contextmanager
def bake_context(mesh, material, matrix):
    """Isolate baking and release resources even when scene setup fails."""
    with ExitStack() as cleanup:
        scene = bpy.data.scenes.new("AnyImage conversion")
        cleanup.callback(bpy.data.scenes.remove, scene)
        obj = bpy.data.objects.new("AnyImage conversion", mesh)
        cleanup.callback(bpy.data.objects.remove, obj, do_unlink=True)
        obj.matrix_world = matrix
        scene.collection.objects.link(obj)
        mesh.materials.clear()
        mesh.materials.append(material)
        layer = scene.view_layers[0]
        layer.objects.active = obj
        obj.select_set(True, view_layer=layer)
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = 1
        scene.cycles.use_denoising = False
        window = bpy.context.window
        if window:
            cleanup.callback(setattr, window, "scene", window.scene)
            window.scene = scene
        with bpy.context.temp_override(scene=scene, view_layer=layer, object=obj,
                                       active_object=obj, selected_objects=[obj],
                                       selected_editable_objects=[obj]):
            yield scene, obj


def build_layout(mesh):
    """Scale and offset source UVs into regular surface tiles."""
    attribute = mesh.attributes.get(IMAGE_REGION_ATTRIBUTE_NAME)
    if attribute is None or attribute.domain != "FACE" or attribute.data_type != "INT":
        raise ValueError("This Cutout lacks surface regions; recreate it from the source image")
    regions = np.empty(len(mesh.polygons), dtype=np.int32)
    attribute.data.foreach_get("value", regions)
    values = sorted(set(regions.tolist()))
    if not values or not set(values) <= {0, 1, 2, 3}:
        raise ValueError("The Cutout has no supported surface regions")
    if SOURCE_UV in mesh.uv_layers or TARGET_UV in mesh.uv_layers:
        raise ValueError("The Cutout contains reserved conversion UV names")
    original = mesh.uv_layers.get("UVMap")
    if original is None:
        raise ValueError("The Cutout UVMap is missing")
    source_uv = np.empty((len(mesh.loops), 2), dtype=np.float32)
    original.data.foreach_get("uv", source_uv.ravel())
    if not np.isfinite(source_uv).all():
        raise ValueError("The Cutout UVMap contains non-finite coordinates")
    original.name = SOURCE_UV
    target = mesh.uv_layers.new(name=TARGET_UV)
    mesh.uv_layers.active = target
    target.active_render = True
    bodies = sorted({region // 2 for region in values})
    sides = sorted({region % 2 for region in values}, reverse=True)
    columns, rows = len(bodies), len(sides)
    tiles = tuple(tuple(body * 2 + side if body * 2 + side in values else None
                        for body in bodies) for side in sides)
    result = np.empty_like(source_uv)
    for region in values:
        loops = np.concatenate([np.array(p.loop_indices) for p in mesh.polygons if regions[p.index] == region])
        local = source_uv[loops].copy()
        if region in (1, 2):
            local[:, 0] = 1 - local[:, 0]
        offset = (bodies.index(region // 2), sides.index(region % 2))
        result[loops] = (local + offset) / (columns, rows)
    target.data.foreach_set("uv", result.ravel())
    mesh.update()
    return tiles


def create_static_image(source, pixels, name):
    """Create a packed image preserving the source's pixel interpretation."""
    height, width = pixels.shape[:2]
    image = bpy.data.images.new(name, width=width, height=height, alpha=True, float_buffer=source.is_float)
    try:
        image.colorspace_settings.name = source.colorspace_settings.name
        image.alpha_mode = source.alpha_mode
        image.pixels.foreach_set(np.asarray(pixels, dtype=np.float32).ravel())
        image.update()
        image.pack()
        return image
    except Exception:
        bpy.data.images.remove(image)
        raise


def bake_normal(material, layer_name, size):
    """Bake the pre-bump shader normal using explicit source and target UVs."""
    layer = material.node_tree.nodes[layer_name]
    original_group = layer.node_tree
    group = original_group.copy()
    image = None
    nodes, links = material.node_tree.nodes, material.node_tree.links
    created = []
    try:
        image = bpy.data.images.new("Cutout_normal", width=size[0], height=size[1], alpha=True, float_buffer=True)
        image.colorspace_settings.name = "Non-Color"
        layer.node_tree = group
        layer.inputs["Bump Scale"].default_value = 0
        for node in group.nodes:
            if node.type == "NORMAL_MAP" and node.space == "TANGENT":
                node.uv_map = SOURCE_UV
        uv = nodes.new("ShaderNodeUVMap")
        created.append(uv)
        uv.uv_map = SOURCE_UV
        for node in tuple(nodes):
            if node.type == "TEX_IMAGE":
                links.new(uv.outputs["UV"], node.inputs["Vector"])
        output = next(node for node in nodes if node.type == "OUTPUT_MATERIAL" and node.is_active_output)
        shader = nodes.new("ShaderNodeBsdfDiffuse")
        created.append(shader)
        links.new(layer.outputs["Normal"], shader.inputs["Normal"])
        links.new(shader.outputs[0], output.inputs["Surface"])
        target = nodes.new("ShaderNodeTexImage")
        created.append(target)
        target.image = image
        nodes.active = target
        result = bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT", normal_r="POS_X", normal_g="POS_Y", normal_b="POS_Z",
                                     use_selected_to_active=False, uv_layer=TARGET_UV, margin=MARGIN, margin_type="EXTEND")
        if result != {"FINISHED"}:
            raise RuntimeError("Normal baking was cancelled")
        image.pack()
        return image
    except Exception:
        if image is not None:
            bpy.data.images.remove(image, do_unlink=True)
        raise
    finally:
        layer.node_tree = original_group
        for node in created:
            nodes.remove(node)
        bpy.data.node_groups.remove(group)


def build_conversion_mesh(context, obj):
    """Build an isolated static mesh synchronously and release failed results."""
    material, layer, color, normal = material_inputs(obj)
    has_normal = (normal is not None or layer.inputs["Object Space"].default_value
                  or tuple(layer.inputs["Normal"].default_value) != (.5, .5, 1, 1))
    mesh = None
    target_material = None
    bake_material = None
    images = []
    transferred = False
    try:
        graph = context.evaluated_depsgraph_get()
        mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(graph), preserve_all_data_layers=True, depsgraph=graph)
        if not mesh.polygons:
            raise ValueError("The evaluated Cutout has no faces")
        target_material = material.copy()
        tiles = build_layout(mesh)
        grid = (len(tiles[0]), len(tiles))
        size = tuple(max(c, n) for c, n in zip(color.image.size, normal.image.size)) if normal else tuple(color.image.size)
        size = tuple(int(v) * count for v, count in zip(size, grid))
        pixels = build_color_tiles(color.image, tiles)
        static_color = create_static_image(color.image, pixels, color.image.name + "_mesh")
        images.append(static_color)
        del pixels
        target_material.node_tree.nodes[color.name].image = static_color
        if has_normal:
            bake_material = material.copy()
            with bake_context(mesh, bake_material, obj.matrix_world):
                static_normal = bake_normal(bake_material, layer.name, size)
                images.append(static_normal)
            normal_texture = (target_material.node_tree.nodes[normal.name] if normal is not None
                              else target_material.node_tree.nodes.new("ShaderNodeTexImage"))
            normal_texture.image = static_normal
            target_layer = target_material.node_tree.nodes[layer.name]
            if normal is None:
                normal_texture.extension = "EXTEND"
                target_material.node_tree.links.new(normal_texture.outputs["Color"], target_layer.inputs["Normal"])
        target_layer = target_material.node_tree.nodes[layer.name]
        target_layer.inputs["Object Space"].default_value = False
        target_layer.inputs["Normal Scale"].default_value = 1
        mesh.uv_layers.remove(mesh.uv_layers[SOURCE_UV])
        mesh.uv_layers[TARGET_UV].name = "UVMap"
        mesh.uv_layers.active = mesh.uv_layers["UVMap"]
        mesh.uv_layers.active.active_render = True
        for name in tuple(mesh.attributes.keys()):
            if name in PROTOCOL_ATTRIBUTES:
                mesh.attributes.remove(mesh.attributes[name])
        for name in PROTOCOL_ATTRIBUTES:
            if name in mesh:
                del mesh[name]
        mesh.materials.clear()
        mesh.materials.append(target_material)
        mesh.update()
        transferred = True
        return mesh
    finally:
        if bake_material is not None:
            bpy.data.materials.remove(bake_material)
        if not transferred:
            if mesh is not None:
                bpy.data.meshes.remove(mesh)
            if target_material is not None:
                bpy.data.materials.remove(target_material)
            for image in images:
                bpy.data.images.remove(image)
