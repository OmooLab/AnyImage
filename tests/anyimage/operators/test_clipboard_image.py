import importlib
import struct
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch
from tests.support.blender import BlenderTestCase


class ClipboardImageTest(BlenderTestCase):
    def setUp(self):
        super().setUp()
        self.clipboard_image = importlib.import_module(
            "anyimage.operators.clipboard_image.operators"
        )
        self.actions = importlib.import_module(
            "anyimage.operators.clipboard_image.actions"
        )
        self.clipboard = importlib.import_module(
            "anyimage.operators.clipboard_image.clipboard"
        )

    def test_registers_and_removes_clipboard_shortcuts(self):
        class KeyMapItems:
            def __init__(self):
                self.items = []

            def new(self, operator_id, event_type, value, **modifiers):
                item = SimpleNamespace(
                    idname=operator_id,
                    type=event_type,
                    value=value,
                    **modifiers,
                )
                self.items.append(item)
                return item

            def remove(self, item):
                self.items.remove(item)

        class KeyMaps:
            def __init__(self):
                self.items = []

            def new(self, name, space_type):
                keymap = SimpleNamespace(
                    name=name,
                    space_type=space_type,
                    keymap_items=KeyMapItems(),
                )
                self.items.append(keymap)
                return keymap

        keymaps = KeyMaps()
        window_manager = SimpleNamespace(
            keyconfigs=SimpleNamespace(
                addon=SimpleNamespace(keymaps=keymaps),
            ),
        )
        with patch.object(
            self.fake_bpy.context,
            "window_manager",
            window_manager,
            create=True,
        ):
            self.keymaps.register()
            items = [
                item
                for keymap in keymaps.items
                for item in keymap.keymap_items.items
            ]
            self.assertEqual(
                [item.idname for item in items],
                [
                    "anyimage.paste_clipboard_image",
                    "anyimage.paste_clipboard_image",
                ],
            )
            modifier = "oskey" if sys.platform == "darwin" else "ctrl"
            self.assertTrue(all(getattr(item, modifier) for item in items))
            self.assertTrue(all(item.shift for item in items))
            self.assertTrue(all(item.type == "V" for item in items))
            self.keymaps.unregister()

        self.assertTrue(
            all(not keymap.keymap_items.items for keymap in keymaps.items)
        )

    def test_routes_supported_contexts(self):
        contexts = (
            (self.make_context("VIEW_3D"), "IMAGE_EMPTY"),
            (
                self.make_context("VIEW_3D", mode="SCULPT"),
                "TOOL_TEXTURE",
            ),
            (
                self.make_context("VIEW_3D", mode="PAINT_VERTEX"),
                "TOOL_TEXTURE",
            ),
            (
                self.make_context("VIEW_3D", mode="PAINT_TEXTURE"),
                "TOOL_TEXTURE",
            ),
            (
                self.make_context(
                    "NODE_EDITOR",
                    tree_type="ShaderNodeTree",
                ),
                "NODE",
            ),
            (
                self.make_context(
                    "NODE_EDITOR",
                    tree_type="CompositorNodeTree",
                ),
                "NODE",
            ),
            (
                self.make_context(
                    "NODE_EDITOR",
                    tree_type="GeometryNodeTree",
                ),
                "NODE",
            ),
        )

        for context, expected_target in contexts:
            with self.subTest(expected_target=expected_target):
                self.assertEqual(
                    self.actions.target_for_context(context),
                    expected_target,
                )

    def test_rejects_unsupported_node_tree(self):
        context = self.make_context(
            "NODE_EDITOR",
            tree_type="TextureNodeTree",
        )

        self.assertIsNone(self.actions.target_for_context(context))

    def test_rejects_unsupported_view_modes(self):
        for mode in (
            "EDIT_MESH",
            "POSE",
            "EDIT_GREASE_PENCIL",
            "PAINT_GREASE_PENCIL",
        ):
            with self.subTest(mode=mode):
                context = self.make_context("VIEW_3D", mode=mode)
                self.assertIsNone(self.actions.target_for_context(context))
                self.assertFalse(
                    self.clipboard_image.PasteClipboardImage.poll(context)
                )

    def test_node_type_follows_the_world_space(self):
        self.assertEqual(
            self.actions._node_type_for_space(
                SimpleNamespace(tree_type="ShaderNodeTree", shader_type="WORLD")
            ),
            "ShaderNodeTexEnvironment",
        )
        self.assertEqual(
            self.actions._node_type_for_space(
                SimpleNamespace(tree_type="ShaderNodeTree", shader_type="OBJECT")
            ),
            "ShaderNodeTexImage",
        )
        self.assertEqual(
            self.actions._node_type_for_space(
                SimpleNamespace(
                    tree_type="ShaderNodeTree",
                    shader_type="OBJECT",
                    id=SimpleNamespace(
                        bl_rna=SimpleNamespace(identifier="World"),
                    ),
                )
            ),
            "ShaderNodeTexEnvironment",
        )

    def test_node_location_matches_native_ui_scale_and_anchor_offset(self):
        view2d = SimpleNamespace(
            region_to_view=Mock(return_value=(200.0, 100.0)),
        )
        context = SimpleNamespace(
            region=SimpleNamespace(view2d=view2d),
            preferences=SimpleNamespace(
                system=SimpleNamespace(ui_scale=2.0),
            ),
            space_data=SimpleNamespace(cursor_location=(1.0, 2.0)),
        )
        event = SimpleNamespace(mouse_region_x=80, mouse_region_y=60)

        location = self.actions._node_location(context, event)

        self.assertEqual(location, (85.0, 55.0))
        view2d.region_to_view.assert_called_once_with(80, 60)
        cursor_context = SimpleNamespace(
            space_data=SimpleNamespace(cursor_location=(12.0, -8.0)),
        )

        self.assertEqual(
            self.actions._node_location(cursor_context, None),
            (12.0, -8.0),
        )


    def test_reference_image_uses_drag_and_drop_size(self):
        reference = SimpleNamespace(select_set=Mock())
        objects = SimpleNamespace(new=Mock(return_value=reference))
        context = SimpleNamespace(
            mode="OBJECT",
            collection=SimpleNamespace(objects=SimpleNamespace(link=Mock())),
            selected_objects=(),
            view_layer=SimpleNamespace(objects=SimpleNamespace(active=None)),
            region_data=None,
        )
        image = SimpleNamespace(name="Clipboard", size=(1920, 1080))

        with patch.object(self.actions.bpy.data, "objects", objects, create=True):
            result = self.actions.add_reference_image(
                context,
                image,
                location=(1.0, 2.0, 3.0),
            )

        self.assertIs(result, reference)
        self.assertEqual(reference.empty_display_size, 5.0)

    def test_redo_reuses_captured_node_location(self):
        operator = self.clipboard_image.PasteClipboardImage()
        operator.paste_target = "NODE"
        operator.location = (10.0, 20.0, 0.0)
        operator.location_set = True
        operator.report = Mock()
        context = self.make_context(
            "NODE_EDITOR",
            tree_type="ShaderNodeTree",
        )
        image = SimpleNamespace(name="Clipboard Image")

        clipboard_image = self.clipboard_image
        with (
            patch.object(
                clipboard_image,
                "read_clipboard_image",
                return_value=(b"image", ".png"),
            ),
            patch.object(
                clipboard_image,
                "acquire_packed_image",
                return_value=(image, True),
            ),
            patch.object(clipboard_image, "paste_image") as paste_image,
        ):
            result = operator.execute(context)

        self.assertEqual(result, {"FINISHED"})
        paste_image.assert_called_once_with(
            context,
            image,
            None,
            location=(10.0, 20.0),
        )


    def test_empty_clipboard_leaves_selected_target_untouched(self):
        operator = self.clipboard_image.PasteClipboardImage()
        operator.paste_target = "IMAGE_EMPTY"
        with (
            patch.object(self.clipboard_image, "read_clipboard_image",
                         side_effect=self.clipboard.ClipboardImageUnavailable),
            patch.object(self.clipboard_image, "replacement_for_context") as resolve,
            patch.object(self.clipboard_image, "acquire_packed_image") as acquire,
        ):
            self.assertEqual(operator.execute(self.make_context("VIEW_3D")), {"PASS_THROUGH"})
        resolve.assert_not_called()
        acquire.assert_not_called()

    def test_replacement_operator_remains_registered_with_undo(self):
        operator = self.clipboard_image.PasteClipboardImage
        self.assertEqual(self.anyimage.CLASSES.count(operator), 1)
        self.assertIn("UNDO", operator.bl_options)


    def test_stencil_dimensions_preserve_scale_and_image_aspect(self):
        self.assertEqual(
            self.actions._stencil_dimensions(
                (1920, 1080),
                (400.0, 200.0),
            ),
            (400.0, 225.0),
        )
        self.assertEqual(
            self.actions._stencil_dimensions(
                (800, 1200),
                (128.0, 256.0),
            ),
            (256.0 * 2 / 3, 256.0),
        )

    def test_finds_existing_packed_clipboard_image(self):
        matching_image = FakeImage(
            self.actions.CLIPBOARD_HASH_PROPERTY,
            "matching-hash",
            packed=True,
        )
        unpacked_image = FakeImage(
            self.actions.CLIPBOARD_HASH_PROPERTY,
            "unpacked-hash",
            packed=False,
        )
        original_data = self.actions.bpy.data
        self.actions.bpy.data = SimpleNamespace(
            images=[matching_image, unpacked_image],
        )
        try:
            with patch.object(matching_image, "get", side_effect=lambda key: "matching-hash" if key == self.actions.CLIPBOARD_HASH_PROPERTY else "pixels"), patch.object(self.actions, "_clipboard_content_hash", return_value="pixels"):
                self.assertIs(
                    self.actions._find_packed_clipboard_image("matching-hash"),
                    matching_image,
                )
            self.assertIsNone(
                self.actions._find_packed_clipboard_image("unpacked-hash")
            )
        finally:
            self.actions.bpy.data = original_data

    def test_names_new_packed_image_clipboard(self):
        image = FakeLoadedImage()
        images = FakeLoadedImages(image)
        original_data = self.actions.bpy.data
        self.actions.bpy.data = SimpleNamespace(images=images)
        try:
            with patch.object(self.actions, "_clipboard_content_hash", return_value="pixels"):
                loaded_image, reused = self.actions.acquire_packed_image(
                    b"image-data",
                    ".png",
                )
        finally:
            self.actions.bpy.data = original_data

        self.assertIs(loaded_image, image)
        self.assertFalse(reused)
        self.assertEqual(image.name, "Clipboard")
        self.assertTrue(image.packed)

    def test_sets_and_reuses_stencil_brush_texture(self):
        textures = FakeTextures()
        original_data = self.actions.bpy.data
        self.actions.bpy.data = SimpleNamespace(textures=textures, images=SimpleNamespace(remove=Mock()))
        brush = SimpleNamespace(
            is_editable=True,
            texture=None,
            texture_slot=SimpleNamespace(
                texture=None,
                map_mode="VIEW_PLANE",
            ),
            stencil_dimension=(256.0, 256.0),
            update_tag=lambda: None,
        )
        context = SimpleNamespace(
            brush=brush,
            scene=SimpleNamespace(view_settings=SimpleNamespace(view_transform="AgX")),
        )
        image = SimpleNamespace(
            name="Clipboard Image", size=(1920, 1080), is_float=False,
            colorspace_settings=SimpleNamespace(name="sRGB"), alpha_mode="STRAIGHT",
        )
        try:
            with (
                patch.object(self.actions, "image_content_state", return_value={"filepath": ""}),
                patch.object(self.actions, "replace_image_content"),
                patch.object(self.actions, "create_normalized_color_image") as configure,
            ):
                first_texture = self.actions.set_tool_texture(context, image)
                configure.assert_called_once_with(image)
                second_texture = self.actions.set_tool_texture(context, image)
        finally:
            self.actions.bpy.data = original_data

        self.assertIs(first_texture, second_texture)
        self.assertEqual(len(textures), 1)
        self.assertIs(brush.texture, first_texture)
        self.assertIs(brush.texture_slot.texture, first_texture)
        self.assertEqual(brush.texture_slot.map_mode, "STENCIL")
        self.assertEqual(brush.stencil_dimension, (256.0, 144.0))

    def test_vertex_and_texture_paint_use_unbiased_white(self):
        for mode in ("PAINT_VERTEX", "PAINT_TEXTURE"):
            with self.subTest(mode=mode):
                brush = SimpleNamespace(color=(0.2, 0.4, 0.8))
                unified_settings = SimpleNamespace(color=(0.8, 0.4, 0.2))
                context = SimpleNamespace(
                    mode=mode,
                    tool_settings=SimpleNamespace(
                        **{
                            self.actions.PAINT_SETTINGS_BY_MODE[mode][0]:
                                SimpleNamespace(
                                    unified_paint_settings=unified_settings,
                                )
                        },
                    ),
                )

                self.actions._set_unbiased_paint_color(context, brush)

                self.assertEqual(brush.color, (1.0, 1.0, 1.0))
                self.assertEqual(
                    unified_settings.color,
                    (1.0, 1.0, 1.0),
                )

    def test_sculpt_keeps_brush_color(self):
        brush = SimpleNamespace(color=(0.2, 0.4, 0.8))

        self.actions._set_unbiased_paint_color(
            SimpleNamespace(mode="SCULPT"),
            brush,
        )

        self.assertEqual(brush.color, (0.2, 0.4, 0.8))

    def test_wraps_info_dib_as_bmp(self):
        dib_header = struct.pack(
            "<IiiHHIIiiII",
            40,
            1,
            1,
            1,
            24,
            0,
            4,
            0,
            0,
            0,
            0,
        )
        dib_data = dib_header + b"\x00\x00\xff\x00"

        bmp_data = self.clipboard.dib_to_bmp(dib_data)

        signature, file_size, _, _, pixel_offset = struct.unpack_from(
            "<2sIHHI",
            bmp_data,
        )
        self.assertEqual(signature, b"BM")
        self.assertEqual(file_size, len(bmp_data))
        self.assertEqual(pixel_offset, 54)
        self.assertEqual(bmp_data[14:], dib_data)

    def test_rejects_truncated_dib(self):
        with self.assertRaises(self.clipboard.ClipboardImageError):
            self.clipboard.dib_to_bmp(b"\x28\x00\x00\x00")

    def test_bitfields_preserve_pixels_with_external_or_embedded_masks(self):
        for header_size in (40, 108, 124):
            for compression, mask_size in ((3, 12), (6, 16)):
                for bit_count in (16, 32):
                    for height in (-2, 2):
                        for duplicate in ((True,) if header_size == 40 else (False, True)):
                            with self.subTest(
                                header_size=header_size, compression=compression,
                                bit_count=bit_count, height=height, duplicate=duplicate,
                            ):
                                header = build_dib_header(
                                    header_size, width=3, height=height,
                                    bit_count=bit_count, compression=compression,
                                )
                                stride = ((3 * bit_count + 31) // 32) * 4
                                pixels = bytes(range(stride * abs(height)))
                                masks = build_dib_header(bit_count=bit_count)[40:40 + mask_size]
                                table = masks if header_size == 40 or duplicate else b""
                                dib = header + table + pixels

                                bmp = self.clipboard.dib_to_bmp(dib)

                                offset = struct.unpack_from("<I", bmp, 10)[0]
                                self.assertEqual(offset, 14 + header_size + len(table))
                                self.assertEqual(bmp[offset:], pixels)

    def test_preserves_pixels_that_match_embedded_masks(self):
        for header_size in (108, 124):
            for compression, mask_size in ((0, 12), (3, 12), (6, 16)):
                with self.subTest(header_size=header_size, compression=compression):
                    header = build_dib_header(header_size, compression=compression)
                    pixels = header[40:40 + mask_size] + bytes(64 - mask_size)

                    bmp = self.clipboard.dib_to_bmp(header + pixels)

                    offset = struct.unpack_from("<I", bmp, 10)[0]
                    self.assertEqual(offset, 14 + header_size)
                    self.assertEqual(bmp[offset:], pixels)

    def test_requires_matching_alpha_mask_before_skipping_table(self):
        header = build_dib_header(compression=6)
        pixels = header[40:52] + bytes(52)
        dib = header + pixels + bytes(16)

        bmp = self.clipboard.dib_to_bmp(dib)

        self.assertEqual(struct.unpack_from("<I", bmp, 10)[0], 138)

    def test_bitfields_account_for_color_table(self):
        header = build_dib_header()
        struct.pack_into("<I", header, 32, 2)
        masks = header[40:52]
        colors = bytes(8)
        pixels = bytes(range(64))

        bmp = self.clipboard.dib_to_bmp(header + masks + colors + pixels)

        offset = struct.unpack_from("<I", bmp, 10)[0]
        self.assertEqual(offset, 158)
        self.assertEqual(bmp[offset:], pixels)

    def test_v5_profile_is_excluded_from_pixel_data(self):
        for profile_before in (False, True):
            for duplicate in (False, True):
                with self.subTest(profile_before=profile_before, duplicate=duplicate):
                    header = build_dib_header()
                    masks = header[40:52] if duplicate else b""
                    # A normal pixel array may begin with the mask values.
                    pixels = header[40:52] + bytes(52)
                    profile = bytes(32)
                    profile_offset = 124 + len(masks) + (0 if profile_before else 64)
                    struct.pack_into("<I", header, 56, 0x4D424544)  # PROFILE_EMBEDDED
                    struct.pack_into("<II", header, 112, profile_offset, len(profile))
                    payload = profile + pixels if profile_before else pixels + profile

                    bmp = self.clipboard.dib_to_bmp(header + masks + payload)

                    offset = struct.unpack_from("<I", bmp, 10)[0]
                    expected = 138 + len(masks) + (len(profile) if profile_before else 0)
                    self.assertEqual(offset, expected)
                    self.assertEqual(bmp[offset:offset + 64], pixels)

    def test_rejects_incomplete_bitfields_pixels_and_masks(self):
        for header_size in (40, 108, 124):
            for compression, mask_size in ((3, 12), (6, 16)):
                for payload_size in (0, mask_size - 1, 63):
                    with self.subTest(
                        header_size=header_size, compression=compression,
                        payload_size=payload_size,
                    ):
                        header = build_dib_header(header_size, compression=compression)
                        with self.assertRaises(self.clipboard.ClipboardImageError):
                            self.clipboard.dib_to_bmp(header + bytes(payload_size))

    def test_rejects_invalid_bitfields_dimensions_and_depth(self):
        for options in ({"width": 0}, {"width": -1}, {"height": 0}, {"bit_count": 24}):
            with self.subTest(options=options):
                with self.assertRaises(self.clipboard.ClipboardImageError):
                    self.clipboard.dib_to_bmp(build_dib_header(**options) + bytes(64))

    def test_rejects_out_of_range_v5_profile(self):
        for profile_offset, profile_size in ((120, 4), (188, 32)):
            with self.subTest(profile_offset=profile_offset, profile_size=profile_size):
                header = build_dib_header()
                struct.pack_into("<II", header, 112, profile_offset, profile_size)
                with self.assertRaises(self.clipboard.ClipboardImageError):
                    self.clipboard.dib_to_bmp(header + bytes(64))

    @staticmethod
    def make_context(area_type, mode="OBJECT", **space_options):
        return SimpleNamespace(
            area=SimpleNamespace(type=area_type),
            mode=mode,
            region=SimpleNamespace(type="WINDOW"),
            space_data=SimpleNamespace(**space_options),
        )

def build_dib_header(
    header_size=124, *, width=8, height=2, bit_count=32, compression=3,
):
    header = bytearray(header_size)
    struct.pack_into(
        "<IiiHHIIiiII", header, 0,
        header_size, width, height, 1, bit_count, compression, 0, 0, 0, 0, 0,
    )
    if header_size >= 56:
        masks = (0xF800, 0x07E0, 0x001F, 0) if bit_count == 16 else (
            0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000,
        )
        struct.pack_into("<4I", header, 40, *masks)
    return header


class FakeImage:
    def __init__(self, property_name, image_hash, packed):
        self.properties = {property_name: image_hash}
        self.packed_file = object() if packed else None
        self.packed_files = ()

    def get(self, property_name, default=None):
        return self.properties.get(property_name, default)


class FakeLoadedImage(dict):
    def __init__(self):
        super().__init__()
        self.name = None
        self.packed = False

    def pack(self):
        self.packed = True


class FakeLoadedImages(list):
    def __init__(self, loaded_image):
        super().__init__()
        self.loaded_image = loaded_image

    def load(self, _path, check_existing):
        return self.loaded_image

    def remove(self, image):
        super().remove(image)


class FakeTexture(dict):
    def __init__(self, name, texture_type):
        super().__init__()
        self.name = name
        self.type = texture_type
        self.image = None


class FakeTextures(list):
    def new(self, name, type):
        texture = FakeTexture(name, type)
        self.append(texture)
        return texture

    def remove(self, texture):
        super().remove(texture)
