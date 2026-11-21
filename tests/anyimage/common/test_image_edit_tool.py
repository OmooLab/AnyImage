from types import SimpleNamespace
from unittest.mock import Mock, patch


from tests.support.blender import BlenderTestCase


class ImageEditToolTest(BlenderTestCase):


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


    def test_point_tools_start_inside_the_selected_image_and_pass_through_outside(self):
        from mathutils import Matrix

        source = SimpleNamespace(
            name="Photo", type="EMPTY", empty_display_type="IMAGE", data=SimpleNamespace(size=(200, 100)),
            matrix_world=Matrix.Identity(4), empty_image_offset=(-0.5, -0.5), empty_display_size=1,
        )
        context = SimpleNamespace(
            active_object=source, selected_objects=[source], region=Mock(width=200, height=200),
            area=Mock(), window_manager=Mock(), window=Mock(), workspace=Mock(),
            region_data=SimpleNamespace(is_perspective=False, view_perspective="ORTHO",
                                        perspective_matrix=Matrix.Identity(4), view_matrix=Matrix.Identity(4)),
        )
        center = SimpleNamespace(value="PRESS", mouse_region_x=100, mouse_region_y=100)
        outside = SimpleNamespace(value="PRESS", mouse_region_x=100, mouse_region_y=130)
        self.assertIs(self.image_interaction.clicked_image_source(context, center), source)
        self.assertIsNone(self.image_interaction.clicked_image_source(context, outside))
        context.scene = SimpleNamespace(anyimage_settings=SimpleNamespace(
            cutout_gesture="POLYLINE", mask_gesture="POLYLINE", mask_mode="SUBTRACT", mask_radius=25,
        ))
        with patch.object(self.fake_bpy.types, "SpaceView3D", Mock(), create=True), \
             patch.object(self.rectify, "image_content_signature", return_value=()):
            for operator in (self.rectify.RectifyImagePerspective(), self.edit_mask.EditImageAlpha(),
                             self.cutout_operators.SelectCutoutSelection()):
                self.assertEqual(operator.invoke(context, outside), {"PASS_THROUGH"})
                self.assertEqual(operator.invoke(context, center), {"RUNNING_MODAL"})
                context.window_manager.modal_handler_add.assert_called_with(operator)
        context.selected_objects = []
        self.assertIsNone(self.image_interaction.clicked_image_source(context, center))

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
