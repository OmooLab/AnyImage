from contextlib import nullcontext
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from tests.support.blender import BlenderTestCase


class CutoutOperatorsTest(BlenderTestCase):
    def test_cutout_gestures_use_click_or_drag_and_lasso_finishes_on_release(self):
        from mathutils import Matrix

        image_gesture = importlib.import_module("anyimage.common.image_gesture")
        source = SimpleNamespace(name="Source", matrix_world=Matrix.Identity(4), data=object())
        context = SimpleNamespace(
            area=SimpleNamespace(as_pointer=lambda: 1, tag_redraw=Mock()),
            region=SimpleNamespace(as_pointer=lambda: 2, x=100, y=50),
            workspace=SimpleNamespace(status_text_set=Mock()),
            window_manager=SimpleNamespace(modal_handler_add=Mock()),
            scene=SimpleNamespace(anyimage_settings=SimpleNamespace(mask_gesture="BRUSH")),
        )
        event = SimpleNamespace(type="LEFTMOUSE", value="PRESS", mouse_region_x=12, mouse_region_y=18, mouse_prev_press_x=96, mouse_prev_press_y=69)
        with (
            patch.object(image_gesture, "clicked_image_source", return_value=source),
            patch.object(image_gesture, "active_image_edit_source", return_value=source),
            patch.object(image_gesture, "is_animated_image", return_value=False),
            patch.object(image_gesture, "active_view3d_tool_id", return_value=None),
            patch.object(self.fake_bpy.types, "SpaceView3D", SimpleNamespace(draw_handler_add=Mock()), create=True),
        ):
            for gesture in ("LASSO", "POLYLINE"):
                with self.subTest(gesture=gesture):
                    context.scene.anyimage_settings.cutout_gesture = gesture
                    operator = self.cutout_operators.SelectCutoutSelection()
                    operator.report = Mock()
                    event.value = "PRESS" if gesture == "LASSO" else "CLICK_DRAG"
                    self.assertEqual(operator.invoke(context, event), {"PASS_THROUGH"})
                    event.value = "CLICK_DRAG" if gesture == "LASSO" else "PRESS"
                    self.assertEqual(operator.invoke(context, event), {"RUNNING_MODAL"})
                    self.assertEqual(operator._path, [(-4, 19)] if gesture == "LASSO" else [(12, 18)])
                    self.assertEqual(operator.gesture, gesture)
                    self.assertEqual(context.scene.anyimage_settings.mask_gesture, "BRUSH")
                    operator._complete = Mock(return_value={"FINISHED"})
                    release = SimpleNamespace(type="LEFTMOUSE", value="RELEASE", mouse_region_x=20, mouse_region_y=30)
                    result = operator.modal(context, release)
                    if gesture == "LASSO":
                        self.assertEqual(result, {"FINISHED"})
                        operator._complete.assert_called_once_with(context)
                    else:
                        operator._complete.assert_not_called()

    def test_flat_and_solid_without_ai_build_locally(self):
        import numpy as np

        source = SimpleNamespace(data=SimpleNamespace(size=(10, 10)), select_set=Mock(),
                                 empty_display_size=10, empty_image_offset=(-0.5, -0.5))
        context = SimpleNamespace(view_layer=SimpleNamespace(objects=SimpleNamespace(active=None)))
        selection = self.image_selection.SelectionMask(np.ones((8, 8)), (1, 1, 9, 9))
        module = self.cutout_operators
        for shape in ("FLAT", "SOLID"):
            operator = SimpleNamespace(source_object_name="Source", selection_path_json=json.dumps({"points": [[1, 1], [9, 1], [9, 9]]}), shape=shape, gesture="POLYLINE", edge_length=0.1, alpha_threshold=0.25, fine_outline=False, report=Mock())
            mesh = SimpleNamespace(mask="Mask")
            with (
                patch.object(module, "require_image_empty", return_value=source),
                patch.object(module, "is_animated_image", return_value=False),
                patch.object(module, "image_rgba", return_value=np.ones((10, 10, 4))),
                patch.object(module, "rasterize_selection_path", return_value=selection),
                patch.object(module, "material_color_image", return_value=nullcontext("Color")),
                patch.object(self.cutout_object, "build_cutout_shape", return_value=mesh),
                patch.object(self.cutout_object, "pad_cutout_images") as pad,
                patch.object(self.cutout_object, "push_cutout_undo") as undo,
                patch.object(self.cutout_object, "create_shape_object") as create,
            ):
                self.assertEqual(module.CreateCutoutShape.execute(operator, context), {"FINISHED"})
            self.assertEqual(create.call_args.args, (context, source, shape, (-4, 4, -4, 4), mesh))
            self.assertEqual(create.call_args.kwargs["color_image"], "Color")
            self.assertEqual(create.call_args.kwargs["gesture"], "POLYLINE")
            pad.assert_called_once_with("Color", None, None, "Mask", 2.0)
            undo.assert_called_once_with(shape)

    def test_ai_cutout_writes_the_selection_bounds_image(self):
        import numpy as np

        source = SimpleNamespace(
            data=SimpleNamespace(size=(8, 4)),
            select_set=lambda _value: None,
        )
        context = SimpleNamespace(
            view_layer=SimpleNamespace(objects=SimpleNamespace(active=None))
        )
        source_rgba = np.ones((4, 8, 4), dtype=np.float32)
        source_rgba[1:3, 1:7, 3] = 0.5
        selection_mask = self.image_selection.SelectionMask(
            np.full((2, 6), 0.75, dtype=np.float32),
            (1, 1, 7, 3),
        )
        operator = self.cutout_main.CutoutSelectionToShape()
        operator.alpha_threshold = 0.25
        operator.fine_outline = False
        operator.source_object_name = "Source"
        operator.selection_path_json = json.dumps(
            {"points": [[1, 1], [7, 1], [7, 3], [1, 3]]}
        )
        operator.shape = "DEPTH_SOLID"
        operator.report = lambda *_args: None
        operator.edge_length = 0.1
        operator.generate_normal = False
        operator.report = lambda *_args: None

        with (
            patch.object(
                self.cutout_main,
                "require_image_empty",
                return_value=source,
            ),
            patch.object(self.cutout_main, "is_animated_image", return_value=False),
            patch.object(
                self.cutout_main,
                "image_rgba",
                return_value=source_rgba,
            ) as read_rgba,
            patch.object(self.cutout_main, "image_content_signature", return_value="snapshot"),
            patch.object(
                self.cutout_main,
                "rasterize_selection_path",
                return_value=selection_mask,
            ) as rasterize,
            patch.object(
                self.cutout_main,
                "configured_max_ai_input_size",
                return_value=2048,
            ),
            patch.object(
                self.cutout_main,
                "invoke_ai_setup_if_needed",
                return_value=None,
            ),
            patch.object(
                self.cutout_main,
                "configured_geometry_model",
                return_value="MODEL",
            ),
            patch.object(
                self.cutout_main,
                "prepare_recognition_input",
                return_value=Path(__file__),
            ) as prepare_input,
            patch.object(
                self.cutout_main.JobOperator,
                "execute",
                return_value={"FINISHED"},
            ),
        ):
            result = operator.execute(context)

        self.assertEqual(result, {"FINISHED"})
        np.testing.assert_array_equal(operator._content_values, np.full((2, 6), 0.375))
        self.assertEqual(operator._content_bounds, selection_mask.bounds)
        read_rgba.assert_called_once_with(source.data)
        rasterize.assert_called_once()
        self.assertIs(prepare_input.call_args.args[0], source.data)
        np.testing.assert_array_equal(prepare_input.call_args.args[1], source_rgba[1:3, 1:7])


    def test_transparent_cutout_stops_before_material_export_or_ai_setup(self):
        import numpy as np

        source = SimpleNamespace(data=SimpleNamespace(size=(8, 8)), select_set=Mock())
        context = SimpleNamespace(view_layer=SimpleNamespace(objects=SimpleNamespace(active=None)))
        rgba = np.ones((8, 8, 4), dtype=np.float32)
        rgba[1:7, 1:7, 3] = 0
        for module, operator_type, shape in (
            (self.cutout_operators, self.cutout_operators.CreateCutoutShape, "FLAT"),
            (self.cutout_main, self.cutout_main.CutoutSelectionToShape, "DEPTH_SOLID"),
        ):
            with self.subTest(shape=shape):
                operator = operator_type()
                operator.source_object_name = "Source"
                operator.selection_path_json = json.dumps({"points": [[2, 2], [6, 2], [6, 6], [2, 6]]})
                operator.shape = shape
                operator.alpha_threshold = 0.25
                operator.report = Mock()
                with (
                    patch.object(module, "require_image_empty", return_value=source),
                    patch.object(module, "image_rgba", return_value=rgba),
                    patch.object(self.cutout_main, "invoke_ai_setup_if_needed") as setup,
                    patch.object(self.cutout_operators, "material_color_image") as local_color,
                    patch.object(self.cutout_main, "prepare_recognition_input") as ai_color,
                ):
                    self.assertEqual(operator.execute(context), {"CANCELLED"})
                operator.report.assert_called_once_with({"WARNING"}, "The Cutout selection contains no visible image pixels")
                setup.assert_not_called()
                local_color.assert_not_called()
                ai_color.assert_not_called()


    def test_cutout_request_describes_ai_capabilities(self):
        operator = self.cutout_main.CutoutSelectionToShape()
        operator.alpha_threshold = 0.25
        operator.fine_outline = False
        operator.input_path = __file__
        operator.source_object_name = "Source"
        operator.shape = "DEPTH_SOLID"
        operator.model = self.anyimage.ai_preferences.DEFAULT_GEOMETRY_MODEL_KEY
        operator.resolution_level = 5
        operator.max_ai_input_size = 2048
        operator.generate_normal = True
        context = SimpleNamespace(
            scene=SimpleNamespace(anyimage_settings=SimpleNamespace())
        )
        with (
            patch.object(self.cutout_main, "require_environment"),
            patch.object(self.cutout_main, "require_model") as require_model,
            patch.object(self.cutout_main, "require_input_path", return_value=Path("input.png")),
        ):
            for shape in ("FLAT", "SOLID", "DEPTH_SOLID", "DEPTH_SYMMETRY"):
                for enabled in (False, True):
                    with self.subTest(shape=shape, enabled=enabled):
                        operator.shape = shape
                        operator.generate_normal = enabled
                        require_model.reset_mock()
                        parameters = operator.request(context)
                        depth = shape in {"DEPTH_SOLID", "DEPTH_SYMMETRY"}
                        self.assertEqual(parameters["input"], "input.png")
                        self.assertEqual(parameters["device"], "cuda")
                        self.assertEqual(parameters["max_input_size"], 2048)
                        self.assertEqual(parameters["generate_depth"], depth)
                        self.assertEqual(parameters["generate_normal"], depth or enabled)
                        self.assertNotIn("alpha_threshold", parameters)
                        if depth or enabled:
                            self.assertEqual(parameters["model"], operator.model)
                            self.assertEqual(parameters["resolution_level"], 5)
                            require_model.assert_called_once_with(operator.model)
                        else:
                            self.assertNotIn("model", parameters)
                            require_model.assert_not_called()


    def test_cutout_tool_settings_gate_normal_generation(self):
        class Row:
            def __init__(self, events):
                self.events = events
                self.enabled = True

            def prop(self, _owner, name, **_options):
                self.events.append(("prop", name, self.enabled))

        class Layout:
            def __init__(self):
                self.events = []

            def operator(self, identifier, **_options):
                self.events.append(("operator", identifier, True))

            def row(self):
                return Row(self.events)

            def prop(self, _owner, name, **_options):
                self.events.append(("prop", name, True))

        context = SimpleNamespace(
            scene=SimpleNamespace(anyimage_settings=SimpleNamespace())
        )
        missing = {
            "environment_ready": False,
            "missing_models": (),
            "ready": False,
        }
        setup = ("operator", "anyimage.setup_ai_server", True)
        with patch.object(self.ai, "ai_status", return_value=missing):
            cutout_tool = importlib.import_module("anyimage.ai_tools").CutoutTool
            layout = Layout()
            cutout_tool.draw_settings(context, layout, None)
            self.assertEqual(
                layout.events,
                [
                    ("prop", "cutout_gesture", True),
                    ("prop", "cutout_edge_length", True),
                    ("prop", "cutout_fine_outline", True),
                    ("prop", "cutout_alpha_threshold", True),
                    setup,
                    ("prop", "cutout_generate_normal", False),
                ],
            )

        ready = {"environment_ready": True, "missing_models": (), "ready": True}
        with patch.object(self.ai, "ai_status", return_value=ready):
            layout = Layout()
            cutout_tool.draw_settings(context, layout, None)
        self.assertNotIn(setup, layout.events)
        self.assertTrue(all(event[2] for event in layout.events))


    def test_cutout_ai_response_crops_validated_source_and_reuses_selection(self):
        import numpy as np
        from blendjob.result import JobResult

        source = SimpleNamespace(data=SimpleNamespace(size=(24, 24)))
        pixels = np.arange(24 * 24 * 4, dtype=np.float32)
        color_image = SimpleNamespace(users=0)
        content_values = np.ones((3, 4), dtype=np.float32)
        content_values[:, 0] = 0.0
        bounds = (10, 20, 14, 23)
        operator = self.cutout_main.CutoutSelectionToShape()
        operator.alpha_threshold = 0.25
        operator.fine_outline = False
        operator.source_object_name = "Source"
        operator.input_path = __file__
        operator.shape = "FLAT"
        operator.gesture = "POLYLINE"
        operator.report = Mock()
        operator.edge_length = 0.1
        operator.generate_normal = True
        operator._content_values = content_values
        operator._content_bounds = bounds
        operator._source_object = source
        operator._source_image = source.data
        operator.boundary_padding = 3.5
        results = (
            JobResult("cutout", Path(__file__).parent, {}),
            JobResult("cutout", Path(__file__).parent, {"object_normal": "missing.png"}),
        )

        with (
            patch.object(
                self.cutout_main,
                "read_conversion_source",
                return_value=(source, pixels),
            ),
            patch.object(
                self.cutout_main,
                "material_color_image",
                side_effect=lambda *args, **kwargs: nullcontext(color_image),
            ) as color_result,
            patch.object(self.cutout_main, "create_cutout_shape") as create_shape,
        ):
            context = SimpleNamespace(scene=SimpleNamespace(
                anyimage_settings=SimpleNamespace(cutout_gesture="LASSO")
            ))
            for result in results:
                message = operator.response(context, result)

        self.assertEqual(color_result.call_count, 2)
        self.assertIs(color_result.call_args.args[0], source.data)
        self.assertEqual(color_result.call_args.kwargs["bounds"], bounds)
        np.testing.assert_array_equal(color_result.call_args.kwargs["rgba"], pixels.reshape(24, 24, 4)[::-1])

        self.assertEqual(message, "Flat is ready")
        self.assertEqual(operator.report.call_count, 2)
        operator.report.assert_called_with(
            {"WARNING"}, "The normal texture is missing; the shape was created without it",
        )
        self.assertEqual(create_shape.call_args.kwargs["gesture"], "POLYLINE")
        self.assertIs(create_shape.call_args.args[4], content_values)
        self.assertEqual(create_shape.call_args.args[5], bounds)
        self.assertIs(create_shape.call_args.kwargs["color_image"], color_image)
        self.assertEqual(create_shape.call_args.kwargs["alpha_threshold"], 0.25)
        self.assertIs(create_shape.call_args.kwargs["fine_outline"], False)
        self.assertEqual(create_shape.call_args.kwargs["boundary_padding"], 3.5)
