from types import SimpleNamespace
from unittest.mock import Mock, patch
from tests.support.blender import BlenderTestCase


class FrameToolTest(BlenderTestCase):
    def test_frame_builds_a_canonical_rectangular_screen_path(self):
        self.assertEqual(
            self.image_interaction.rectangle_screen_path((2, 3), (8, 9)),
            ((2.0, 9.0), (8.0, 9.0), (8.0, 3.0), (2.0, 3.0)),
        )
        self.assertEqual(
            self.image_interaction.rectangle_screen_path((2, 3), (3, 9)),
            (),
        )


    def test_frame_reports_missing_active_overlap_as_warning(self):
        active = SimpleNamespace(name="Active")
        context = SimpleNamespace(
            active_object=active,
            region=object(),
            region_data=SimpleNamespace(view_matrix="view-matrix"),
        )
        descriptor = {
            "active": True,
        }

        with (
            patch.object(self.image_frame, "_frame_source", return_value=descriptor),
            patch.object(self.image_frame, "frame_source_overlap", return_value=()),
            self.assertRaises(self.image_selection.ImageEditWarning),
        ):
            self.image_frame.apply_frame(
                context,
                (active,),
                ((2, 3), (3, 3), (3, 2), (2, 2)),
            )


    def test_frame_uses_selected_still_images_and_ignores_other_objects(self):
        active = SimpleNamespace(
            name="Active",
            type="EMPTY",
            empty_display_type="IMAGE",
            data=SimpleNamespace(source="FILE"),
        )
        other = SimpleNamespace(
            name="Other",
            type="EMPTY",
            empty_display_type="IMAGE",
            data=SimpleNamespace(source="FILE"),
        )
        mesh = SimpleNamespace(name="Mesh", type="MESH")
        context = SimpleNamespace(
            active_object=active,
            selected_objects=(mesh, active, other),
        )

        self.assertEqual(
            self.image_frame.selected_frame_sources(context),
            (other, active),
        )


    def test_frame_rejects_active_image_that_is_not_selected(self):
        active = SimpleNamespace(
            name="Active",
            type="EMPTY",
            empty_display_type="IMAGE",
            data=SimpleNamespace(source="FILE"),
        )
        other = SimpleNamespace(
            name="Other",
            type="EMPTY",
            empty_display_type="IMAGE",
            data=SimpleNamespace(source="FILE"),
        )
        context = SimpleNamespace(
            active_object=active,
            selected_objects=(other,),
        )

        with self.assertRaisesRegex(
            self.image_frame.ImageEditWarning,
            "Select an active Image Empty",
        ):
            self.image_frame.selected_frame_sources(context)


    def test_frame_warns_when_active_is_not_an_image(self):
        image = SimpleNamespace(
            name="Image",
            type="EMPTY",
            empty_display_type="IMAGE",
            data=SimpleNamespace(source="FILE"),
        )
        mesh = SimpleNamespace(name="Mesh", type="MESH")
        context = SimpleNamespace(
            active_object=mesh,
            selected_objects=(image, mesh),
            area=SimpleNamespace(type="VIEW_3D"),
        )
        operator = self.image_frame.FrameImages()
        operator.report = Mock()

        self.assertTrue(operator.poll(context))
        self.assertEqual(operator.invoke(context, object()), {"CANCELLED"})
        operator.report.assert_called_once_with(
            {"WARNING"},
            "Select an active Image Empty to use an Image tool",
        )


    def test_frame_modal_can_start_outside_source_projection(self):
        active = SimpleNamespace(name="Active")
        other = SimpleNamespace(name="Other")
        redraw = Mock()
        status = Mock()
        modal_handler_add = Mock()
        context = SimpleNamespace(
            active_object=active,
            area=SimpleNamespace(as_pointer=lambda: 1, tag_redraw=redraw),
            region=SimpleNamespace(as_pointer=lambda: 2),
            workspace=SimpleNamespace(status_text_set=status),
            window_manager=SimpleNamespace(modal_handler_add=modal_handler_add),
        )
        event = SimpleNamespace(mouse_region_x=-20, mouse_region_y=300)
        space = SimpleNamespace(
            draw_handler_add=Mock(return_value="handle"),
            draw_handler_remove=Mock(),
        )
        operator = self.image_frame.FrameImages()

        with (
            patch.object(
                self.image_frame,
                "selected_frame_sources",
                return_value=(other, active),
            ),
            patch.object(
                self.image_frame.bpy.types,
                "SpaceView3D",
                space,
                create=True,
            ),
        ):
            result = operator.invoke(context, event)
            operator.cancel(context)

        self.assertEqual(result, {"RUNNING_MODAL"})
        self.assertEqual(operator._active_name, "Active")
        self.assertEqual(operator._source_names, ("Other", "Active"))
        self.assertEqual(operator._start, (-20.0, 300.0))
        modal_handler_add.assert_called_once_with(operator)
        space.draw_handler_remove.assert_called_once_with("handle", "WINDOW")


    def test_frame_rejects_an_animated_selected_image(self):
        active = SimpleNamespace(
            name="Active",
            type="EMPTY",
            empty_display_type="IMAGE",
            data=SimpleNamespace(source="FILE"),
        )
        video = SimpleNamespace(
            name="Video",
            type="EMPTY",
            empty_display_type="IMAGE",
            data=SimpleNamespace(source="MOVIE", frame_duration=2),
        )
        context = SimpleNamespace(
            active_object=active,
            selected_objects=(active, video),
        )

        with self.assertRaisesRegex(ValueError, "still images"):
            self.image_frame.selected_frame_sources(context)


    def test_frame_keeps_active_object_and_removes_other_image_empties(self):
        import numpy as np

        class MatrixStub:
            translation = SimpleNamespace(copy=lambda: "active-origin")

            def copy(self):
                return "old-matrix"

        active_image = Mock(users=1, use_fake_user=False)
        other_image = Mock(users=1, use_fake_user=False)
        active = SimpleNamespace(
            name="Active",
            data=active_image,
            matrix_world=MatrixStub(),
            empty_display_size=1.0,
            empty_image_offset=(-0.5, -0.5),
        )
        other = SimpleNamespace(name="Other", data=other_image)
        context = SimpleNamespace(
            active_object=active,
            region=SimpleNamespace(width=100, height=100),
            region_data=SimpleNamespace(view_matrix="view-matrix"),
        )
        frame = ((0.0, 2.0), (2.0, 2.0), (2.0, 0.0), (0.0, 0.0))
        descriptors = iter(
            (
                {
                    "active": False,
                    "image_size": (2, 2),
                },
                {
                    "active": True,
                    "image_size": (2, 2),
                },
            )
        )
        result_image = Mock(users=1)
        remove_object = Mock()

        def replace(source, result, *, removed_objects):
            self.assertEqual(removed_objects, (other,))
            source.data = result

        with (
            patch.object(self.image_frame, "_frame_source", side_effect=descriptors),
            patch.object(
                self.image_frame,
                "frame_source_overlap",
                return_value=frame,
            ),
            patch.object(self.image_frame, "frame_output_size", return_value=(2, 2)),
            patch.object(
                self.image_frame,
                "composite_frame_pixels",
                return_value=np.zeros(16, dtype=np.float32),
            ),
            patch.object(
                self.image_frame,
                "frame_result_transform",
                return_value=("new-matrix", 2.0),
            ),
            patch.object(
                self.image_frame,
                "frame_depth_location",
                return_value="active-origin",
            ),
            patch.object(
                self.image_frame,
                "create_image_edit_result",
                return_value=result_image,
            ),
            patch.object(self.image_frame, "replace_empty_image", side_effect=replace),
            patch.object(
                self.image_frame.bpy.data,
                "objects",
                SimpleNamespace(remove=remove_object),
            ),
            patch.object(
                self.image_frame.bpy.data,
                "images",
                SimpleNamespace(remove=Mock()),
                create=True,
            ),
        ):
            result = self.image_frame.apply_frame(
                context,
                (other, active),
                frame,
            )

        self.assertIs(result, active)
        self.assertIs(active.data, result_image)
        self.assertEqual(active.matrix_world, "new-matrix")
        self.assertEqual(active.empty_display_size, 2.0)
        self.assertEqual(active.empty_image_offset, (-0.5, -0.5))
        remove_object.assert_called_once_with(other, do_unlink=True)


    def test_frame_invalid_result_depth_does_not_create_or_replace_image(self):
        import numpy as np

        active_image = Mock(users=1, use_fake_user=False)
        active = SimpleNamespace(
            name="Active",
            data=active_image,
            matrix_world=SimpleNamespace(
                translation=SimpleNamespace(copy=lambda: "active-origin")
            ),
        )
        context = SimpleNamespace(
            active_object=active,
            region=SimpleNamespace(width=100, height=100),
            region_data=SimpleNamespace(view_matrix="view-matrix"),
        )
        frame = ((0.0, 2.0), (2.0, 2.0), (2.0, 0.0), (0.0, 0.0))
        descriptor = {"active": True, "image_size": (2, 2)}
        create_result = Mock()
        replace_result = Mock()

        with (
            patch.object(self.image_frame, "_frame_source", return_value=descriptor),
            patch.object(self.image_frame, "frame_source_overlap", return_value=frame),
            patch.object(self.image_frame, "frame_output_size", return_value=(2, 2)),
            patch.object(
                self.image_frame,
                "composite_frame_pixels",
                return_value=np.zeros(16, dtype=np.float32),
            ),
            patch.object(
                self.image_frame,
                "frame_depth_location",
                side_effect=ValueError("The Frame result depth is invalid"),
            ),
            patch.object(
                self.image_frame,
                "create_image_edit_result",
                create_result,
            ),
            patch.object(self.image_frame, "replace_empty_image", replace_result),
            self.assertRaisesRegex(ValueError, "result depth"),
        ):
            self.image_frame.apply_frame(context, (active,), frame)

        create_result.assert_not_called()
        replace_result.assert_not_called()
        self.assertIs(active.data, active_image)
