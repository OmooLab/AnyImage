"""Exercise clipboard replacement against real Blender images and owners."""

from io import BytesIO
from types import SimpleNamespace

import bpy
import numpy as np
import pytest
from PIL import Image

from anyimage.common import image as images
from anyimage.operators.clipboard_image import actions, operators


@pytest.fixture(autouse=True)
def clean_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    yield
    bpy.ops.wm.read_factory_settings(use_empty=True)


def clipboard_bytes(color=(40, 120, 200, 128), size=(3, 2)):
    stream = BytesIO()
    Image.new("RGBA", size, color).save(stream, format="PNG")
    return stream.getvalue()


def image_empty(image=None):
    obj = bpy.data.objects.new("Reference", None)
    obj.empty_display_type = "IMAGE"
    obj.data = image
    bpy.context.collection.objects.link(obj)
    return obj


def view_context(*objects, mode="OBJECT", brush=None):
    return SimpleNamespace(
        area=SimpleNamespace(type="VIEW_3D", tag_redraw=lambda: None),
        mode=mode, selected_objects=objects, brush=brush,
        scene=bpy.context.scene, collection=bpy.context.collection,
        view_layer=bpy.context.view_layer,
    )


def paste(context, monkeypatch, data=None, import_as="REFERENCE"):
    monkeypatch.setattr(operators, "read_clipboard_image", lambda: (
        clipboard_bytes() if data is None else data, ".png",
    ))
    reports = []
    operator = SimpleNamespace(
        paste_target="", location_set=False, import_as=import_as, shadeless=False,
        report=lambda level, message: reports.append((level, message)),
    )
    result = operators.PasteClipboardImage._paste(operator, context)
    return result, operator, reports


def owner_image():
    image = bpy.data.images.new("Original.png", width=2, height=1, alpha=True)
    image.pixels[:] = (.8, .2, .1, 1) * 2
    image.pack()
    return image


def node_context(node_type, image):
    tree_type = (
        "GeometryNodeTree" if node_type.startswith("Geometry") else
        "CompositorNodeTree" if node_type.startswith("Compositor") else "ShaderNodeTree"
    )
    tree = bpy.data.node_groups.new("Image Nodes", tree_type)
    node = tree.nodes.new(node_type)
    actions._assign_node_image(node, image)
    return node, SimpleNamespace(
        area=SimpleNamespace(type="NODE_EDITOR"), mode="OBJECT",
        space_data=SimpleNamespace(tree_type=tree_type, edit_tree=tree),
    )


def test_last_image_user_preserves_identity_and_saved_content(monkeypatch, tmp_path):
    image = owner_image()
    image.use_fake_user = True
    image["custom"] = "keep"
    image[actions.CLIPBOARD_HASH_PROPERTY] = "old"
    image[actions.CLIPBOARD_CONTENT_PROPERTY] = "old baseline"
    obj = image_empty(image)
    area = bpy.context.screen.areas[0]
    area.type = "IMAGE_EDITOR"
    area.spaces.active.image = image
    obj.location = (2, 3, 4)
    obj.rotation_euler = (.2, .4, .6)
    obj.scale = (2, 1, 3)
    obj.empty_display_size = 7
    obj.empty_image_offset = (.1, -.7)
    obj.use_empty_image_alpha = False
    original_file = tmp_path / "original.png"
    original_file.write_bytes(clipboard_bytes())
    image.filepath_raw = str(original_file)
    before = (obj.matrix_basis.copy(), obj.empty_display_size, tuple(obj.empty_image_offset))
    identity = image.as_pointer()
    resources = {kind: set(getattr(bpy.data, kind)) for kind in ("images", "objects", "textures", "brushes")}

    result, operator, reports = paste(view_context(obj), monkeypatch)

    assert result == {"FINISHED"} and operator.is_replacement
    assert reports[-1][1] == "Replaced and packed Original.png"
    assert image.as_pointer() == identity and image.name == "Original.png"
    assert obj.data == image and area.spaces.active.image == image
    assert image.use_fake_user and image["custom"] == "keep"
    assert actions.CLIPBOARD_HASH_PROPERTY not in image and actions.CLIPBOARD_CONTENT_PROPERTY not in image
    assert (obj.matrix_basis, obj.empty_display_size, tuple(obj.empty_image_offset)) == before
    assert not obj.use_empty_image_alpha
    assert image.filepath_raw != str(original_file)
    assert original_file.read_bytes() == clipboard_bytes()
    assert tuple(image.size) == (3, 2) and image.packed_file
    expected = np.tile(np.array([40, 120, 200, 128], np.float32) / 255, 6)
    np.testing.assert_allclose(images.image_pixels(image), expected, atol=1 / 255)
    for kind, items in resources.items():
        assert set(getattr(bpy.data, kind)) == items
    path = str(tmp_path / "replacement.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    restored = bpy.data.images["Original.png"]
    assert tuple(restored.size) == (3, 2) and restored.packed_file
    np.testing.assert_allclose(images.image_pixels(restored), expected, atol=1 / 255)
    assert bpy.data.objects["Reference"].data == restored


@pytest.mark.parametrize("suffix", [".jpg", ".png"])
@pytest.mark.parametrize("shared", [False, True])
def test_replace_unpacked_file_image_preserves_references_and_new_alpha(suffix, shared, monkeypatch, tmp_path):
    path = tmp_path / ("Dragged" + suffix)
    Image.new("RGB", (8, 4), (200, 80, 40)).save(path)
    file_bytes = path.read_bytes()
    source = bpy.data.images.load(str(path), check_existing=False)
    assert source.source == "FILE" and not source.packed_file
    original_pixels = images.image_pixels(source)
    obj = image_empty(source)
    other = image_empty(source) if shared else None
    identity, name = source.as_pointer(), source.name
    result, _, reports = paste(view_context(obj), monkeypatch)
    assert result == {"FINISHED"}, reports
    destination = obj.data
    assert (destination == source) == (not shared)
    assert tuple(destination.size) == (3, 2) and destination.packed_file
    expected = np.tile(np.array([40, 120, 200, 128], np.float32) / 255, 6)
    np.testing.assert_allclose(images.image_pixels(destination), expected, atol=1 / 255)
    assert source.as_pointer() == identity and source.name == name
    assert path.read_bytes() == file_bytes
    if shared:
        assert other.data == source and not source.packed_file
        np.testing.assert_array_equal(images.image_pixels(source), original_pixels)
    destination.reload()
    np.testing.assert_allclose(images.image_pixels(destination), expected, atol=1 / 255)
    selected_name = obj.name
    blend_path = str(tmp_path / "dragged-replacement.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    bpy.ops.wm.open_mainfile(filepath=blend_path)
    restored = bpy.data.objects[selected_name].data
    np.testing.assert_allclose(images.image_pixels(restored), expected, atol=1 / 255)


@pytest.mark.parametrize("other_kind", ["empty", "node", "brush"])
def test_shared_empty_image_isolated_then_last_user_overwritten(other_kind, monkeypatch, tmp_path):
    source = owner_image()
    obj = image_empty(source)
    if other_kind == "empty":
        other = image_empty(source)
    elif other_kind == "node":
        other, _ = node_context("ShaderNodeTexImage", source)
    else:
        other = bpy.data.textures.new("Brush Texture", type="IMAGE")
        other.image = source
    pixels = images.image_pixels(source)
    packed = bytes(source.packed_file.data)
    result, _, _ = paste(view_context(obj), monkeypatch)
    replacement = obj.data
    assert result == {"FINISHED"} and replacement != source
    assert source.name == "Original.png" and replacement.name.startswith("Original.png.")
    assert tuple(replacement.size) == (3, 2) and replacement.packed_file
    assert len(bpy.data.images) == 2
    assert (other.data if other_kind == "empty" else other.image) == source
    assert bytes(source.packed_file.data) == packed
    np.testing.assert_array_equal(images.image_pixels(source), pixels)
    # The selected owner now holds the only reference to its new image.
    result, _, _ = paste(view_context(obj), monkeypatch, clipboard_bytes(size=(4, 1)))
    assert result == {"FINISHED"} and obj.data == replacement
    assert tuple(replacement.size) == (4, 1) and len(bpy.data.images) == 2
    np.testing.assert_array_equal(images.image_pixels(source), pixels)
    if other_kind == "empty":
        selected_name, other_name, replacement_name = obj.name, other.name, replacement.name
        path = str(tmp_path / "shared-replacement.blend")
        bpy.ops.wm.save_as_mainfile(filepath=path)
        bpy.ops.wm.open_mainfile(filepath=path)
        restored = bpy.data.objects[selected_name].data
        assert restored.name == replacement_name and tuple(restored.size) == (4, 1)
        assert bpy.data.objects[other_name].data.name == "Original.png"
        np.testing.assert_array_equal(images.image_pixels(bpy.data.objects[other_name].data), pixels)


@pytest.mark.parametrize("node_type", sorted(actions.IMAGE_NODE_TYPES))
def test_shared_node_image_isolated_within_same_tree(node_type, monkeypatch):
    source = owner_image()
    node, context = node_context(node_type, source)
    other_type = (
        "GeometryNodeInputImage" if node_type == "GeometryNodeImageTexture" else
        "GeometryNodeImageTexture" if node_type == "GeometryNodeInputImage" else node_type
    )
    other = context.space_data.edit_tree.nodes.new(other_type)
    actions._assign_node_image(other, source)
    other.select = False
    before = images.image_pixels(source)
    result, _, _ = paste(context, monkeypatch)
    target = actions.replacement_for_context(context)
    assert result == {"FINISHED"} and target.image != source
    assert (other.image if hasattr(other, "image") else other.inputs["Image"].default_value) == source
    assert tuple(target.image.size) == (3, 2) and len(bpy.data.images) == 2
    np.testing.assert_array_equal(images.image_pixels(source), before)


@pytest.mark.parametrize("node_type", sorted(actions.IMAGE_NODE_TYPES))
def test_image_node_replacement_preserves_node_and_links(node_type, monkeypatch):
    image = owner_image()
    node, context = node_context(node_type, image)
    tree = context.space_data.edit_tree
    node.location = (50, 100)
    node.label = "Keep label"
    if node_type.startswith("Shader"):
        consumer = tree.nodes.new("ShaderNodeEmission")
        tree.links.new(node.outputs[0], consumer.inputs[0])
    elif node_type == "GeometryNodeInputImage":
        consumer = tree.nodes.new("GeometryNodeImageTexture")
        tree.links.new(node.outputs[0], consumer.inputs["Image"])
    else:
        consumer = tree.nodes.new("NodeReroute")
        tree.links.new(node.outputs[0], consumer.inputs[0])
    consumer.select = False
    nodes, links = set(tree.nodes), tuple(tree.links)
    pointer = image.as_pointer()
    assert actions.replacement_for_context(context).image == image
    result, _, _ = paste(context, monkeypatch)
    assert result == {"FINISHED"}
    assert image.as_pointer() == pointer and tuple(image.size) == (3, 2)
    assert set(tree.nodes) == nodes and tuple(tree.links) == links
    assert tuple(node.location) == (50, 100) and node.label == "Keep label"
    assert actions.replacement_for_context(context).image == image


@pytest.mark.parametrize("kind", ["objects", "nodes"])
def test_mixed_multiselection_creates_without_replacing(kind, monkeypatch):
    image = owner_image()
    before = images.image_pixels(image)
    if kind == "objects":
        obj = image_empty(image)
        other = bpy.data.objects.new("Other", None)
        bpy.context.collection.objects.link(other)
        context = view_context(obj, other)
        count = len(bpy.data.objects)
    else:
        _, context = node_context("ShaderNodeTexImage", image)
        context.space_data.edit_tree.nodes.new("ShaderNodeValue")
        count = len(context.space_data.edit_tree.nodes)
    assert actions.replacement_for_context(context) is None
    result, operator, _ = paste(context, monkeypatch)
    assert result == {"FINISHED"} and not operator.is_replacement
    np.testing.assert_array_equal(images.image_pixels(image), before)
    assert (len(bpy.data.objects) if kind == "objects" else len(context.space_data.edit_tree.nodes)) == count + 1


def test_linked_geometry_input_and_empty_image_slots_are_not_targets():
    image = owner_image()
    node, context = node_context("GeometryNodeImageTexture", image)
    upstream = context.space_data.edit_tree.nodes.new("GeometryNodeInputImage")
    upstream.image = image
    upstream.select = False
    context.space_data.edit_tree.links.new(upstream.outputs[0], node.inputs["Image"])
    assert actions.replacement_for_context(context) is None
    node, context = node_context("ShaderNodeTexImage", None)
    assert actions.replacement_for_context(context) is None
    assert actions.replacement_for_context(view_context(image_empty())) is None


def test_plane_creation_retains_original_clipboard_cache(monkeypatch):
    result, operator, _ = paste(view_context(), monkeypatch, import_as="PLANE")
    assert result == {"FINISHED"} and not operator.is_replacement
    cached, reused = actions.acquire_packed_image(clipboard_bytes(), ".png")
    assert reused and cached.users == 0
    plane = bpy.context.view_layer.objects.active
    material_image = next(node.image for node in plane.active_material.node_tree.nodes
                          if node.bl_idname == "ShaderNodeTexImage")
    assert material_image != cached


@pytest.mark.parametrize("source", ["SEQUENCE", "MOVIE", "TILED"])
def test_nonstatic_target_cancels_without_allocating(source, monkeypatch):
    image = owner_image()
    image.source = source
    obj = image_empty(image)
    before = set(bpy.data.images)
    result, _, reports = paste(view_context(obj), monkeypatch)
    assert result == {"CANCELLED"} and "still images" in reports[-1][1]
    assert obj.data == image and image.source == source and set(bpy.data.images) == before


def test_linked_image_cancels_without_creating_a_local_copy(tmp_path, monkeypatch):
    image = owner_image()
    path = str(tmp_path / "library.blend")
    bpy.data.libraries.write(path, {image})
    with bpy.data.libraries.load(path, link=True) as (_, loaded):
        loaded.images = [image.name]
    linked = loaded.images[0]
    obj = image_empty(linked)
    before = set(bpy.data.images)
    result, _, reports = paste(view_context(obj), monkeypatch)
    assert result == {"CANCELLED"} and "editable" in reports[-1][1]
    assert obj.data == linked and set(bpy.data.images) == before


@pytest.mark.parametrize("shared", [False, True])
@pytest.mark.parametrize("failure", ["decode", "commit"])
def test_failed_replacement_keeps_original_content_and_cleans_input(failure, shared, monkeypatch):
    image = owner_image()
    obj = image_empty(image)
    if shared:
        image_empty(image)
    image[actions.CLIPBOARD_HASH_PROPERTY] = "original"
    before = images.image_content_state(image)
    pixels = images.image_pixels(image)
    resources = set(bpy.data.images)
    if failure == "commit":
        restore = actions.restore_image_content
        failed = False
        def fail(destination, content):
            nonlocal failed
            restore(destination, content)
            if not failed:
                failed = True
                raise RuntimeError("Commit failed")
        monkeypatch.setattr(actions, "restore_image_content", fail)
    result, _, _ = paste(view_context(obj), monkeypatch, b"invalid image" if failure == "decode" else None)
    assert result == {"CANCELLED"}
    assert set(bpy.data.images) == resources and obj.data == image
    assert image[actions.CLIPBOARD_HASH_PROPERTY] == "original"
    assert bytes(image.packed_file.data) == before["packed"]
    assert image.filepath_raw == before["filepath"] and tuple(image.size) == before["size"]
    np.testing.assert_array_equal(images.image_pixels(image), pixels)


def test_operator_reuses_target_as_input_without_removing_it(monkeypatch):
    image, _ = actions.acquire_packed_image(clipboard_bytes(), ".png")
    obj = image_empty(image)
    before = set(bpy.data.images)
    pixels = images.image_pixels(image)
    result, operator, _ = paste(view_context(obj), monkeypatch)
    assert result == {"FINISHED"} and operator.is_replacement
    assert obj.data == image and set(bpy.data.images) == before
    np.testing.assert_array_equal(images.image_pixels(image), pixels)
    assert actions.CLIPBOARD_HASH_PROPERTY not in image


@pytest.mark.parametrize("mode", ["SCULPT", "PAINT_TEXTURE", "PAINT_VERTEX"])
def test_existing_brush_replaces_content_without_changing_settings(mode, monkeypatch):
    image = owner_image()
    texture = bpy.data.textures.new("Existing Texture", type="IMAGE")
    texture.image = image
    brush = bpy.data.brushes.new("Existing Brush", mode={
        "SCULPT": "SCULPT", "PAINT_TEXTURE": "TEXTURE_PAINT", "PAINT_VERTEX": "VERTEX_PAINT",
    }[mode])
    brush.texture = texture
    brush.texture_slot.map_mode = "VIEW_PLANE"
    brush.stencil_dimension = (123, 456)
    brush.color = (.2, .5, .7)
    state = (tuple(brush.color), tuple(brush.stencil_dimension), brush.texture_slot.map_mode)
    previews = []
    monkeypatch.setattr(actions, "_set_brush_preview", lambda *args: previews.append(args))
    original, _ = actions.acquire_packed_image(clipboard_bytes(), ".png")
    pixels = images.image_pixels(original)
    original_state = images.image_content_state(original)
    before = {kind: set(getattr(bpy.data, kind)) for kind in ("images", "brushes", "textures")}
    context = view_context(image_empty(), image_empty(), mode=mode, brush=brush)
    for _ in range(2):
        result, operator, _ = paste(context, monkeypatch)
        assert result == {"FINISHED"} and operator.is_replacement
        assert brush.texture == brush.texture_slot.texture == texture and texture.image == image
        assert (tuple(brush.color), tuple(brush.stencil_dimension), brush.texture_slot.map_mode) == state
        assert image[images.COLOR_NORMALIZED_PROPERTY] and image.alpha_mode == "PREMUL"
        np.testing.assert_allclose(images.image_pixels(image), pixels, atol=1 / 255)
        np.testing.assert_array_equal(images.image_pixels(original), pixels)
        assert bytes(original.packed_file.data) == original_state["packed"]
        for kind, items in before.items():
            assert set(getattr(bpy.data, kind)) == items
    assert len(previews) == (2 if mode == "PAINT_TEXTURE" else 0)


def test_preview_failure_keeps_committed_content_and_cleans_temporary_images(monkeypatch):
    image = owner_image()
    texture = bpy.data.textures.new("Brush Texture", type="IMAGE")
    texture.image = image
    brush = bpy.data.brushes.new("Brush", mode="TEXTURE_PAINT")
    brush.texture = texture
    def fail(*args):
        raise actions.BrushPreviewError("Preview failed")
    monkeypatch.setattr(actions, "_set_brush_preview", fail)
    before = set(bpy.data.images)
    result, _, reports = paste(view_context(mode="PAINT_TEXTURE", brush=brush), monkeypatch)
    assert result == {"FINISHED"} and reports[-1] == ({"WARNING"}, "Preview failed")
    assert tuple(image.size) == (3, 2) and image.packed_file
    assert brush.texture == texture and texture.image == image and set(bpy.data.images) == before


@pytest.mark.parametrize("reference", ["image", "texture", "mask"])
def test_brush_replacement_isolates_shared_image_and_texture(reference, monkeypatch):
    source = owner_image()
    pixels = images.image_pixels(source)
    texture = bpy.data.textures.new("Original Texture", type="IMAGE")
    texture.image = source
    brush = bpy.data.brushes.new("Current Brush", mode="TEXTURE_PAINT")
    brush.texture = texture
    brush.texture_slot.map_mode = "VIEW_PLANE"
    brush.stencil_dimension = (100, 200)
    brush.color = (.3, .5, .7)
    other = bpy.data.brushes.new("Other Brush", mode="TEXTURE_PAINT")
    if reference == "image":
        other.texture = bpy.data.textures.new("Other Texture", type="IMAGE")
        other.texture.image = source
    elif reference == "texture":
        other.texture = texture
    else:
        brush.mask_texture = texture
    state = (tuple(brush.color), tuple(brush.stencil_dimension), brush.texture_slot.map_mode)
    texture_count = len(bpy.data.textures)
    monkeypatch.setattr(actions, "_set_brush_preview", lambda *_: None)
    context = view_context(mode="PAINT_TEXTURE", brush=brush)
    result, _, _ = paste(context, monkeypatch)
    replacement = brush.texture.image
    assert result == {"FINISHED"} and replacement != source
    assert tuple(replacement.size) == (3, 2) and len(bpy.data.images) == 2
    assert (tuple(brush.color), tuple(brush.stencil_dimension), brush.texture_slot.map_mode) == state
    assert (brush.texture == texture) == (reference == "image")
    assert brush.texture_slot.texture == brush.texture
    assert len(bpy.data.textures) == texture_count + (reference != "image")
    if reference == "mask":
        assert brush.mask_texture == texture and texture.image == source
    else:
        assert other.texture.image == source
    np.testing.assert_array_equal(images.image_pixels(source), pixels)
    destination_texture = brush.texture
    result, _, _ = paste(context, monkeypatch, clipboard_bytes(size=(1, 4)))
    assert result == {"FINISHED"}
    assert brush.texture == destination_texture and brush.texture.image == replacement
    assert tuple(replacement.size) == (1, 4) and len(bpy.data.images) == 2
    assert len(bpy.data.textures) == texture_count + (reference != "image")
    np.testing.assert_array_equal(images.image_pixels(source), pixels)


def test_failed_shared_assignment_restores_binding_and_releases_new_image(monkeypatch):
    source = owner_image()
    obj = image_empty(source)
    other = image_empty(source)
    pixels = images.image_pixels(source)
    assign = actions.ClipboardImageTarget.assign_image
    def fail(self, image):
        assign(self, image)
        if image != source:
            raise RuntimeError("Assignment failed")
    monkeypatch.setattr(actions.ClipboardImageTarget, "assign_image", fail)
    result, _, _ = paste(view_context(obj), monkeypatch)
    assert result == {"CANCELLED"} and obj.data == other.data == source
    assert len(bpy.data.images) == 1
    np.testing.assert_array_equal(images.image_pixels(source), pixels)
