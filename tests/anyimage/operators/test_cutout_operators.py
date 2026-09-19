from contextlib import nullcontext
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from tests.support.blender import BlenderTestCase


class CutoutOperatorsTest(BlenderTestCase):
    def test_cutout_gestures_start_on_empty_pick_and_lasso_finishes_on_release(self):
        viewport = importlib.import_module("anyimage.common.viewport")
        source = SimpleNamespace(name="Source", matrix_world="matrix", data=object())
        context = SimpleNamespace(
            area=SimpleNamespace(as_pointer=lambda: 1, tag_redraw=Mock()),
            region=SimpleNamespace(as_pointer=lambda: 2),
            workspace=SimpleNamespace(status_text_set=Mock()),
            window_manager=SimpleNamespace(modal_handler_add=Mock()),
            scene=SimpleNamespace(anyimage_settings=SimpleNamespace(mask_gesture="BRUSH")),
        )
        event = SimpleNamespace(type="LEFTMOUSE", value="PRESS", mouse_region_x=12, mouse_region_y=18)
        with (
            patch.object(viewport, "resolve_image_edit_click", return_value=(source, True)),
            patch.object(viewport, "is_animated_image", return_value=False),
            patch.object(viewport, "serialize_matrix", return_value="matrix"),
            patch.object(viewport, "active_view3d_tool_id", return_value=None),
            patch.object(self.fake_bpy.types, "SpaceView3D", SimpleNamespace(draw_handler_add=Mock()), create=True),
        ):
            for gesture in ("LASSO", "POLYLINE"):
                with self.subTest(gesture=gesture):
                    context.scene.anyimage_settings.cutout_gesture = gesture
                    operator = self.cutout_main.SelectCutoutSelection()
                    operator.report = Mock()
                    self.assertEqual(operator.invoke(context, event), {"RUNNING_MODAL"})
                    self.assertEqual(operator._path, [(12.0, 18.0)])
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
                        status = context.workspace.status_text_set.call_args.args[0]
                        self.assertIn("Polyline", status)
                        self.assertIn("Backspace", status)

    def test_flat_and_solid_without_ai_build_locally(self):
        import numpy as np

        source = SimpleNamespace(
            data=SimpleNamespace(size=(10, 10)), select_set=lambda _value: None
        )
        context = SimpleNamespace(
            view_layer=SimpleNamespace(objects=SimpleNamespace(active=None))
        )
        selection_mask = self.image_selection.SelectionMask(
            np.ones((8, 8), dtype=np.float32), (1, 1, 9, 9)
        )
        source_rgba = np.ones((10, 10, 4), dtype=np.float32)
        for shape in ("FLAT", "SOLID"):
            with self.subTest(shape=shape):
                operator = SimpleNamespace(
                    source_object_name="Source",
                    selection_path_json=json.dumps(
                        {"points": [[1, 1], [9, 1], [9, 9], [1, 9]]}
                    ),
                    shape=shape,
                    gesture="POLYLINE",
                    edge_length=0.1,
                    alpha_threshold=0.25,
                    fine_outline=False,
                    generate_normal=False,
                    report=lambda *_args: None,
                    _needs_generation=lambda: False,
                )
                with (
                    patch.object(
                        self.cutout_main,
                        "require_image_empty",
                        return_value=source,
                    ),
                    patch.object(
                        self.cutout_main, "is_animated_image", return_value=False
                    ),
                    patch.object(
                        self.cutout_main, "image_rgba", return_value=source_rgba
                    ) as read_rgba,
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
                        "_cutout_content_values",
                        return_value=selection_mask.values,
                    ),
                    patch.object(
                        self.cutout_main,
                        "material_color_image",
                        return_value=nullcontext("Color"),
                    ),
                    patch.object(
                        self.cutout_main, "create_cutout_shape"
                    ) as convert,
                ):
                    result = self.cutout_main.CutoutSelectionToShape.execute(
                        operator, context
                    )

                self.assertEqual(result, {"FINISHED"})
                read_rgba.assert_called_once_with(source.data)
                rasterize.assert_called_once()
                convert.assert_called_once_with(
                    context,
                    source,
                    shape,
                    0.1,
                    selection_mask.values,
                    selection_mask.bounds,
                    alpha_threshold=0.25,
                    fine_outline=False,
                    color_image="Color",
                    boundary_padding=2.0,
                    gesture="POLYLINE",
                    report=operator.report,
                )


    def test_ai_cutout_writes_the_selection_bounds_image(self):
        import numpy as np

        source = SimpleNamespace(
            data=SimpleNamespace(size=(4096, 2048)),
            select_set=lambda _value: None,
        )
        context = SimpleNamespace(
            view_layer=SimpleNamespace(objects=SimpleNamespace(active=None))
        )
        source_rgba = np.ones((4, 8, 4), dtype=np.float32)
        selection_mask = self.image_selection.SelectionMask(
            np.ones((2, 6), dtype=np.float32),
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
                "cutout_geometry_settings",
                return_value=("MODEL", 5),
            ),
            patch.object(
                self.cutout_main,
                "prepare_material_color_input",
                return_value=Path(__file__),
            ) as prepare_input,
            patch.object(self.cutout_main, "material_analysis_input", return_value=Path(__file__)),
            patch.object(
                self.cutout_main.JobOperatorBase,
                "execute",
                return_value={"FINISHED"},
            ),
        ):
            result = operator.execute(context)

        self.assertEqual(result, {"FINISHED"})
        read_rgba.assert_called_once_with(source.data)
        rasterize.assert_called_once()
        prepare_input.assert_called_once_with(
            source.data,
            selection_mask.bounds,
            source_rgba,
        )


    def test_empty_cutout_selection_is_rejected_after_shape_choice(self):
        source = SimpleNamespace(
            data=SimpleNamespace(size=(4096, 2048)),
            select_set=lambda _value: None,
        )
        context = SimpleNamespace(
            view_layer=SimpleNamespace(objects=SimpleNamespace(active=None))
        )
        reports = []
        operator = SimpleNamespace(
            source_object_name="Source",
            selection_path_json=json.dumps(
                {"points": [[1, 1], [7, 1], [7, 3], [1, 3]]}
            ),
            shape="FLAT",
            edge_length=0.1,
            generate_normal=False,
            report=lambda level, message: reports.append((level, message)),
        )

        with (
            patch.object(
                self.cutout_main,
                "require_image_empty",
                return_value=source,
            ),
            patch.object(self.cutout_main, "is_animated_image", return_value=False),
            patch.object(self.cutout_main, "image_rgba"),
            patch.object(
                self.cutout_main,
                "rasterize_selection_path",
                side_effect=self.image_selection.ImageEditWarning(
                    "The selection contains no visible image pixels"
                ),
            ),
            patch.object(self.cutout_main, "create_cutout_shape") as create_shape,
        ):
            result = self.cutout_main.CutoutSelectionToShape.execute(
                operator,
                context,
            )

        self.assertEqual(result, {"CANCELLED"})
        create_shape.assert_not_called()
        self.assertEqual(
            reports,
            [
                (
                    {"WARNING"},
                    "The selection contains no visible image pixels",
                )
            ],
        )


    def test_cutout_request_describes_ai_capabilities(self):
        operator = self.cutout_main.CutoutSelectionToShape()
        operator.alpha_threshold = 0.25
        operator.fine_outline = False
        operator.input_path = __file__
        operator.color_path = __file__
        operator.source_object_name = "Source"
        operator.shape = "DEPTH_SOLID"
        operator.model = self.anyimage.preferences.DEFAULT_GEOMETRY_MODEL_KEY
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
            patch.object(
                self.cutout_main, "production_device", return_value="CPU"
            ),
            patch.object(
                self.cutout_main,
                "moge2_parameters",
                return_value={"model": operator.model, "resolution_level": 5},
            ),
        ):
            parameters = operator.request(context)

        self.assertEqual(
            [call.args[0] for call in require_model.call_args_list],
            [operator.model],
        )
        self.assertTrue(parameters["generate_depth"])
        self.assertNotIn("alpha_threshold", parameters)
        self.assertEqual(parameters["normal_mode"], "OBJECT")


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
        setup = ("operator", "anyimage.setup_ai_environment", True)
        with patch.object(self.ai, "ai_status", return_value=missing):
            cutout_tool = importlib.import_module("anyimage.tools").CutoutTool
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


    def test_cutout_ai_response_reuses_bounds_color_and_gesture_snapshot(self):
        import numpy as np

        source = SimpleNamespace(data=SimpleNamespace())
        color_image = SimpleNamespace(users=0)
        pure_values = np.ones((3, 4), dtype=np.float32)
        pure_values[:, 0] = 0.0
        selection_mask = self.image_selection.SelectionMask(
            pure_values,
            (10, 20, 14, 23),
        )
        operator = self.cutout_main.CutoutSelectionToShape()
        operator.alpha_threshold = 0.25
        operator.fine_outline = False
        operator.source_object_name = "Source"
        operator.selection_bounds_json = "[10,20,14,23]"
        operator.input_path = __file__
        operator.color_path = __file__
        operator.shape = "FLAT"
        operator.gesture = "POLYLINE"
        operator.report = lambda *_args: None
        operator.edge_length = 0.1
        operator.generate_normal = True
        operator._selection_mask = selection_mask
        operator.boundary_padding = 3.5
        result = SimpleNamespace(value={}, file=lambda _key: Path(__file__))

        with (
            patch.object(
                self.cutout_main,
                "require_image_empty",
                return_value=source,
            ),
            patch.object(
                self.cutout_main,
                "_generated_color_result",
                return_value=(
                    color_image,
                    np.ones((3, 4), dtype=np.float32),
                    selection_mask.bounds,
                ),
            ) as color_result,
            patch.object(self.cutout_main, "create_cutout_shape") as create_shape,
        ):
            context = SimpleNamespace(scene=SimpleNamespace(
                anyimage_settings=SimpleNamespace(cutout_gesture="LASSO")
            ))
            message = operator.response(context, result)

        color_result.assert_called_once_with(
            __file__,
            selection_mask.bounds,
        )

        self.assertEqual(message, "Flat is ready")
        self.assertEqual(create_shape.call_args.kwargs["gesture"], "POLYLINE")
        content_values = create_shape.call_args.args[4]
        np.testing.assert_array_equal(content_values, pure_values)
        self.assertEqual(create_shape.call_args.args[5], selection_mask.bounds)
        self.assertIs(create_shape.call_args.kwargs["color_image"], color_image)
        self.assertEqual(create_shape.call_args.kwargs["alpha_threshold"], 0.25)
        self.assertIs(create_shape.call_args.kwargs["fine_outline"], False)
        self.assertEqual(create_shape.call_args.kwargs["boundary_padding"], 3.5)
