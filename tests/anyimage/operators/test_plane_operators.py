from pathlib import Path
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock, patch
from tests.support.blender import BlenderTestCase


class PlaneOperatorsTest(BlenderTestCase):
    def test_plane_rejects_animated_images_before_creating_resources(self):
        for kind in ("MOVIE", "SEQUENCE"):
            for duration in (1, 24):
                source = SimpleNamespace(data=SimpleNamespace(source=kind, frame_duration=duration))
                operator = SimpleNamespace(report=Mock())
                result = self.convert_to_plane.ConvertToPlane.execute(
                    operator, SimpleNamespace(object=source))
                self.assertEqual(result, {"CANCELLED"})
                operator.report.assert_called_once_with({"ERROR"}, "Material conversion supports static images only")


    def test_depth_plane_rejects_animation_and_requests_ai_setup(self):
        module = self.depth_plane_operators
        operator = SimpleNamespace(report=Mock())
        source = SimpleNamespace(source="MOVIE")
        context = SimpleNamespace(object=SimpleNamespace(data=source))
        with patch.object(module, "invoke_ai_setup_if_needed", return_value={"FINISHED"}) as setup:
            self.assertEqual(module.ConvertToDepthPlane.execute(operator, context), {"CANCELLED"})
            setup.assert_not_called()
            source.source = "FILE"
            self.assertEqual(module.ConvertToDepthPlane.execute(operator, context), {"FINISHED"})
            setup.assert_called_once()

    def test_depth_and_relief_results_use_their_normal_space(self):
        for plane_type, normal_space in (("DEPTH", "OBJECT"), ("RELIEF", "TANGENT")):
            normal_key = f"{normal_space.lower()}_normal"
            module = self.depth_plane
            source = SimpleNamespace(data=SimpleNamespace(name="Source"))
            result = SimpleNamespace(file=lambda key: Path("result") / key, value={"intrinsics": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]})
            operator = SimpleNamespace(plane_type=plane_type, bl_label=plane_type)
            context = SimpleNamespace(scene=object())
            ops = SimpleNamespace(
                ed=SimpleNamespace(undo_push=Mock(return_value={"FINISHED"}))
            )

            with (
                patch.object(module, "read_conversion_source", return_value=(source, None)),
                patch.object(module, "image_rgba"),
                patch.object(module, "material_color_image", return_value=nullcontext(object())),
                patch.object(module, "load_depth_result_image"),
                patch.object(module, "load_normal_result_image") as load_normal,
                patch.object(module, "create_image_material") as create_material,
                patch.object(module, "create_depth_plane_object"),
                patch.object(module.bpy, "ops", ops, create=True),
            ):
                module.create_depth_plane_from_result(context, result, operator)

            load_normal.assert_called_once_with(Path("result") / normal_key, source)
            self.assertIs(create_material.call_args.kwargs["normal_image"], load_normal.return_value)
            self.assertEqual(create_material.call_args.kwargs["normal_space"], normal_space)


    def test_depth_plane_result_cleans_unused_depth_and_normal_on_failure(self):
        module = self.depth_plane
        source = SimpleNamespace(data=SimpleNamespace(name="Source"))
        color_image = SimpleNamespace(name="", users=0)
        depth_image = SimpleNamespace(users=0, pack=Mock())
        normal_image = SimpleNamespace(users=0)
        material = SimpleNamespace(users=0)
        files = {
            "depth": Path("depth.exr"),
            "object_normal": Path("object-normal.png"),
        }
        result = SimpleNamespace(
            directory=Path("result"),
            file=lambda key: files[key],
            value={"intrinsics": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]},
        )
        remove_material = Mock()
        remove_image = Mock()
        data = SimpleNamespace(
            materials=SimpleNamespace(remove=remove_material),
            images=SimpleNamespace(remove=remove_image),
        )

        with (
            patch.object(module, "read_conversion_source", return_value=(source, None)),
            patch.object(module, "image_rgba"),
            patch.object(module, "material_color_image", return_value=nullcontext(color_image)),
            patch.object(module, "load_depth_result_image", return_value=depth_image),
            patch.object(module, "load_normal_result_image", return_value=normal_image),
            patch.object(module, "create_image_material", return_value=material),
            patch.object(
                module,
                "create_depth_plane_object",
                side_effect=RuntimeError("failed"),
            ),
            patch.object(module.bpy, "data", data),
            self.assertRaisesRegex(RuntimeError, "failed"),
        ):
            module.create_depth_plane_from_result(
                SimpleNamespace(scene=object()),
                result,
                SimpleNamespace(plane_type="DEPTH"),
            )

        remove_material.assert_called_once_with(material, do_unlink=True)
        self.assertEqual(
            [entry.args[0] for entry in remove_image.call_args_list],
            [depth_image, normal_image],
        )
        self.assertTrue(
            all(
                entry.kwargs == {"do_unlink": True}
                for entry in remove_image.call_args_list
            )
        )
