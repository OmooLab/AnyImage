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
