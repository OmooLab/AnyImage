import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


from tests.support.blender import BlenderTestCase


class ImageEditToolTest(BlenderTestCase):


    def test_packed_image_export_does_not_use_scene_render_transform(self):
        with tempfile.TemporaryDirectory() as directory:
            output_directory = Path(directory)
            calls = []

            class Image:
                file_format = "JPEG"

                def save(self, **options):
                    calls.append(options)
                    Path(options["filepath"]).write_bytes(b"raw image")

            image = Image()
            scene = SimpleNamespace(
                view_settings=SimpleNamespace(look="AgX - Medium High Contrast")
            )
            with patch.object(
                self.image_data.tempfile,
                "mkdtemp",
                return_value=str(output_directory),
            ):
                output = self.image_data.save_packed_image(image, scene)

            self.assertEqual(output, output_directory / "input.png")
            self.assertEqual(
                calls,
                [{"filepath": str(output), "save_copy": True}],
            )
            self.assertEqual(image.file_format, "JPEG")


    def test_expected_empty_image_edits_are_reported_as_warnings(self):
        reports = []
        operator = SimpleNamespace(
            report=lambda level, message: reports.append((level, message))
        )

        self.image_interaction.report_image_edit_exception(
            operator,
            self.image_interaction.ImageEditWarning(
                "The edit contains no visible image pixels"
            ),
        )
        self.image_interaction.report_image_edit_exception(
            operator,
            ValueError("Unexpected invalid data"),
        )

        self.assertEqual(
            reports,
            [
                (
                    {"WARNING"},
                    "The edit contains no visible image pixels",
                ),
                ({"ERROR"}, "Unexpected invalid data"),
            ],
        )


    def test_image_edit_first_click_selects_another_image_without_editing(self):
        selected = []

        def image(name):
            return SimpleNamespace(
                name=name,
                type="EMPTY",
                empty_display_type="IMAGE",
                data=object(),
                select_set=lambda value: selected.append((name, value)),
            )

        active = image("Active")
        clicked = image("Clicked")
        context = SimpleNamespace(
            active_object=active,
            selected_objects=(active,),
            view_layer=SimpleNamespace(objects=SimpleNamespace(active=active)),
        )
        event = SimpleNamespace(mouse_region_x=10, mouse_region_y=20)
        previous_ops = getattr(self.fake_bpy, "ops", None)
        previous_objects = self.fake_bpy.data.objects

        def select(**_kwargs):
            context.active_object = clicked

        self.fake_bpy.ops = SimpleNamespace(
            view3d=SimpleNamespace(select=select),
            object=SimpleNamespace(select_all=lambda **_kwargs: None),
        )
        self.fake_bpy.data.objects = {
            active.name: active,
            clicked.name: clicked,
        }
        try:
            source, should_edit = self.image_interaction.resolve_image_edit_click(
                context, event, lambda *_args: None
            )
        finally:
            self.fake_bpy.data.objects = previous_objects
            if previous_ops is None:
                del self.fake_bpy.ops
            else:
                self.fake_bpy.ops = previous_ops

        self.assertIs(source, clicked)
        self.assertFalse(should_edit)
        self.assertEqual(selected, [])


    def test_image_edit_first_click_selects_another_object_without_editing(self):
        active = SimpleNamespace(
            name="Active",
            type="EMPTY",
            empty_display_type="IMAGE",
            data=object(),
        )
        clicked = SimpleNamespace(name="Mesh", type="MESH", data=object())
        context = SimpleNamespace(
            active_object=active,
            selected_objects=(active,),
        )
        event = SimpleNamespace(mouse_region_x=10, mouse_region_y=20)
        previous_ops = getattr(self.fake_bpy, "ops", None)
        select_options = []

        def select(**options):
            select_options.append(options)
            context.active_object = clicked

        self.fake_bpy.ops = SimpleNamespace(
            view3d=SimpleNamespace(select=select),
        )
        try:
            source, should_edit = self.image_interaction.resolve_image_edit_click(
                context, event, lambda *_args: None
            )
        finally:
            if previous_ops is None:
                del self.fake_bpy.ops
            else:
                self.fake_bpy.ops = previous_ops

        self.assertIs(source, clicked)
        self.assertFalse(should_edit)
        self.assertEqual(select_options[0]["deselect_all"], False)


    def test_image_edit_empty_click_keeps_active_image_and_starts_editing(self):
        active = SimpleNamespace(
            name="Active",
            type="EMPTY",
            empty_display_type="IMAGE",
            data=object(),
        )
        context = SimpleNamespace(
            active_object=active,
            selected_objects=(active,),
        )
        event = SimpleNamespace(mouse_region_x=10, mouse_region_y=20)
        previous_ops = getattr(self.fake_bpy, "ops", None)
        select_options = []
        self.fake_bpy.ops = SimpleNamespace(
            view3d=SimpleNamespace(
                select=lambda **options: select_options.append(options)
            ),
        )
        try:
            source, should_edit = self.image_interaction.resolve_image_edit_click(
                context, event, lambda *_args: None
            )
        finally:
            if previous_ops is None:
                del self.fake_bpy.ops
            else:
                self.fake_bpy.ops = previous_ops

        self.assertIs(source, active)
        self.assertTrue(should_edit)
        self.assertIs(context.active_object, active)
        self.assertEqual(select_options[0]["deselect_all"], False)


    def test_image_edit_source_requires_active_image_to_be_selected(self):
        active = SimpleNamespace(
            name="Active",
            type="EMPTY",
            empty_display_type="IMAGE",
            data=object(),
        )
        context = SimpleNamespace(
            active_object=active,
            selected_objects=(),
        )

        with self.assertRaisesRegex(
            self.image_interaction.ImageEditWarning,
            "Select an active Image Empty",
        ):
            self.image_interaction.active_image_edit_source(context)
