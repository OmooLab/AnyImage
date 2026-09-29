"""Materialize static geometry and update existing images and material inputs."""

from contextlib import ExitStack, contextmanager

import bpy
import numpy as np

from ...common.image import image_content_state, image_pixels, restore_image_content
from ...common.image_target import is_image_object, object_color_texture
from ...common.material import IMAGE_MATERIAL_NODE_GROUP_NAME, SHADELESS_NODE_GROUP_NAME
from ..cutout_tool.shape import CUTOUT_NODE_GROUP_NAMES, IMAGE_REGION_ATTRIBUTE_NAME
from ..convert_to_plane.image_plane import IMAGE_PLANE_NODE_GROUP_NAME
from .textures import build_color_tiles


SOURCE_UV = "_anyimage_source_uv"
TARGET_UV = "_anyimage_target_uv"
MARGIN = 4
SINGLE_REGION_GROUPS = frozenset({
    IMAGE_PLANE_NODE_GROUP_NAME, "O Image Depth Plane", "O Image Relief Plane",
    "O Image Depth Panorama",
})
PROTOCOL_ATTRIBUTES = frozenset({
    "o_balloon", "o_normal_reduction", "o_depth_rotation", "o_depth_face",
    "o_depth_axis", IMAGE_REGION_ATTRIBUTE_NAME,
    "_o_depth_cut", "_o_depth_limit_boundary", "_o_boundary_smooth_weight",
    "_o_boundary_falloff", "_o_cut_boundary", "_o_front_normal", "_o_leaf_id",
    "_o_side_ring_target", "_o_leaf_source_index", "_o_side_base_uv", "_o_side_top_uv",
    "_o_symmetry_weld", "_o_pinned_smooth_boundary", "_o_pinned_smooth_normalization",
    "_o_pinned_smooth_region_point", "_o_pinned_smooth_region_corner",
})


def supports_mesh_baking(obj):
    """Recognize supported image geometry modifier stacks."""
    if not is_image_object(obj) or not getattr(obj, "modifiers", None):
        return False
    groups = []
    for modifier in obj.modifiers:
        if modifier.type != "NODES" or modifier.node_group is None or not modifier.show_viewport or not modifier.show_render:
            return False
        groups.append(modifier.node_group.name)
    return (len(groups) == 1 and groups[0] in SINGLE_REGION_GROUPS) or groups in (
        [CUTOUT_NODE_GROUP_NAMES["SOLID"]],
        [CUTOUT_NODE_GROUP_NAMES["DEPTH_SOLID"]],
        [CUTOUT_NODE_GROUP_NAMES["SOLID"], CUTOUT_NODE_GROUP_NAMES["DEPTH_SYMMETRY"]],
        [CUTOUT_NODE_GROUP_NAMES["DEPTH_SOLID"], CUTOUT_NODE_GROUP_NAMES["DEPTH_SYMMETRY"]],
    )


def material_inputs(obj):
    """Validate the generated material before preparing any replacement data."""
    if not supports_mesh_baking(obj):
        raise ValueError("Select an image object with a supported Geometry Nodes stack")
    if not obj.is_editable or obj.library is not None or obj.override_library is not None:
        raise ValueError("Bake Mesh requires an editable local object")
    if len(obj.data.materials) != 1 or obj.data.shape_keys is not None:
        raise ValueError("Bake Mesh requires one material and no shape keys")
    if obj.material_slots[0].link != "DATA":
        raise ValueError("Bake Mesh requires a mesh-linked material")
    color = object_color_texture(obj)
    if color is None:
        raise ValueError("The Color texture is missing")
    material = obj.active_material
    layers = [node for node in material.node_tree.nodes
              if node.type == "GROUP" and node.node_tree is not None
              and node.node_tree.name == IMAGE_MATERIAL_NODE_GROUP_NAME]
    single_region = obj.modifiers[0].node_group.name in SINGLE_REGION_GROUPS
    if not layers and single_region:
        output = next(n for n in material.node_tree.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output)
        shader = output.inputs["Surface"].links[0].from_node
        if shader.type == "EMISSION" or (shader.type == "GROUP" and shader.node_tree.name == SHADELESS_NODE_GROUP_NAME):
            return material, None, color, None
    if len(layers) != 1:
        raise ValueError("Bake Mesh requires one O Image Layer")
    layer = layers[0]
    for name in ("Normal Scale", "Object Space", "Bump Scale"):
        if layer.inputs[name].is_linked:
            raise ValueError(f"Linked {name} is not supported by Bake Mesh")
    normal = None
    if layer.inputs["Normal"].is_linked:
        normal = layer.inputs["Normal"].links[0].from_node
        if normal.type != "TEX_IMAGE" or normal.image is None or normal == color:
            raise ValueError("Bake Mesh requires an image Normal input")
    elif layer.inputs["Object Space"].default_value or tuple(layer.inputs["Normal"].default_value) != (.5, .5, 1, 1):
        raise ValueError("Bake Mesh requires an existing Normal image for static normals")
    if normal is not None and normal.image == color.image:
        raise ValueError("Bake Mesh requires separate Color and Normal images")
    for node in (color, normal):
        if node is None:
            continue
        if node.image.source not in {"FILE", "GENERATED"} or min(node.image.size) < 1:
            raise ValueError("Bake Mesh requires loaded static images")
        if not node.image.is_editable or node.image.library is not None:
            raise ValueError("Bake Mesh requires editable local images")
        extensions = {"EXTEND", "REPEAT"} if single_region else {"EXTEND"}
        if node.interpolation != "Linear" or node.extension not in extensions or node.projection != "FLAT":
            raise ValueError("Bake Mesh requires linear, extended UV image textures")
        if node.inputs["Vector"].is_linked:
            source = node.inputs["Vector"].links[0].from_node
            if source.type != "UVMAP" or source.uv_map != "UVMap":
                raise ValueError("Bake Mesh requires the UVMap texture coordinates")
    return material, layer, color, normal


@contextmanager
def bake_context(mesh, material, matrix):
    """Isolate baking and release resources even when scene setup fails."""
    with ExitStack() as cleanup:
        scene = bpy.data.scenes.new("AnyImage mesh bake")
        cleanup.callback(bpy.data.scenes.remove, scene)
        obj = bpy.data.objects.new("AnyImage mesh bake", mesh)
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


def build_layout(mesh, *, single_region=False):
    """Scale and offset source UVs into regular surface tiles."""
    regions = np.zeros(len(mesh.polygons), dtype=np.int32)
    if not single_region:
        attribute = mesh.attributes.get(IMAGE_REGION_ATTRIBUTE_NAME)
        if attribute is None or attribute.domain != "FACE" or attribute.data_type != "INT":
            raise ValueError("This Cutout lacks surface regions; recreate it from the source image")
        attribute.data.foreach_get("value", regions)
    values = sorted(set(regions.tolist()))
    if not values or not set(values) <= {0, 1, 2, 3}:
        raise ValueError("The Cutout has no supported surface regions")
    if SOURCE_UV in mesh.uv_layers or TARGET_UV in mesh.uv_layers:
        raise ValueError("The mesh contains reserved mesh bake UV names")
    original = mesh.uv_layers.get("UVMap")
    if original is None:
        raise ValueError("The mesh UVMap is missing")
    source_uv = np.empty((len(mesh.loops), 2), dtype=np.float32)
    original.data.foreach_get("uv", source_uv.ravel())
    if not np.isfinite(source_uv).all():
        raise ValueError("The mesh UVMap contains non-finite coordinates")
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
        image = bpy.data.images.new("Mesh bake normal", width=size[0], height=size[1], alpha=True, float_buffer=True)
        image.colorspace_settings.name = "Non-Color"
        layer.node_tree = group
        layer.inputs["Bump Scale"].default_value = 0
        layer.inputs["Normal Scale"].default_value = 1
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


def replace_static_image(image, result):
    """Write packed pixels in place without reloading the original disk file."""
    image.colorspace_settings.name = result.colorspace_settings.name
    image.alpha_mode = result.alpha_mode
    image.scale(*result.size)
    image.pixels.foreach_set(image_pixels(result))
    image.update()
    image.pack()


def materialize_mesh_and_textures(context, obj):
    """Return a static mesh and update source textures and material inputs.

    Keep the object mesh and modifiers unchanged for the operator to assign.
    Restore source images and material inputs if materialization fails.
    """
    material, layer, color, normal = material_inputs(obj)
    single_region = obj.modifiers[0].node_group.name in SINGLE_REGION_GROUPS
    mesh = None
    bake_material = None
    source_color = color.image
    source_normal = normal.image if normal is not None else None
    source_object_space = layer.inputs["Object Space"].default_value if layer is not None else None
    originals = []
    images_updated = False
    images = []
    transferred = False
    try:
        graph = context.evaluated_depsgraph_get()
        mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(graph), preserve_all_data_layers=True, depsgraph=graph)
        if not mesh.polygons:
            raise ValueError("The evaluated image object has no faces")
        tiles = build_layout(mesh, single_region=single_region)
        grid = (len(tiles[0]), len(tiles))
        size = tuple(max(c, n) for c, n in zip(color.image.size, normal.image.size)) if normal else tuple(color.image.size)
        size = tuple(int(v) * count for v, count in zip(size, grid))
        if not single_region:
            originals.append((source_color, image_content_state(source_color)))
            pixels = build_color_tiles(source_color, tiles)
            images.append(create_static_image(source_color, pixels, source_color.name + "_mesh"))
            del pixels
        if normal is not None:
            originals.append((source_normal, image_content_state(source_normal)))
            bake_material = material.copy()
            with bake_context(mesh, bake_material, obj.matrix_world):
                static_normal = bake_normal(bake_material, layer.name, size)
                images.append(static_normal)
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
        mesh.materials.append(material)
        mesh.update()
        images_updated = True
        for (source, _), result in zip(originals, images):
            replace_static_image(source, result)
        if layer is not None:
            layer.inputs["Object Space"].default_value = False
        transferred = True
        return mesh
    finally:
        if bake_material is not None:
            bpy.data.materials.remove(bake_material)
        if not transferred:
            if images_updated:
                for image, content in reversed(originals):
                    restore_image_content(image, content)
            if layer is not None:
                layer.inputs["Object Space"].default_value = source_object_space
            if mesh is not None:
                bpy.data.meshes.remove(mesh)
        for image in images:
            bpy.data.images.remove(image)
