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
                with patch.object(self.convert_to_plane, "material_color_image") as prepare:
                    result = self.convert_to_plane.ConvertToPlane.execute(
                        operator, SimpleNamespace(object=source))
                self.assertEqual(result, {"CANCELLED"})
                prepare.assert_not_called()
                operator.report.assert_called_once_with({"ERROR"}, "Material conversion supports static images only")


    def test_depth_plane_rejects_animation_and_requests_ai_setup(self):
        operator = SimpleNamespace(mesh_detail=6, report=Mock())
        context = SimpleNamespace(object=SimpleNamespace(data=object()))
        with (
            patch.object(self.convert_to_plane, "require_static_color_image", side_effect=ValueError("Material conversion supports static images only")),
            patch.object(self.convert_to_plane, "invoke_ai_setup_if_needed") as setup,
        ):
            self.assertEqual(self.convert_to_plane.ConvertToDepthPlane.execute(operator, context), {"CANCELLED"})
            setup.assert_not_called()
        with (
            patch.object(self.convert_to_plane, "require_static_color_image"),
            patch.object(self.convert_to_plane, "invoke_ai_setup_if_needed", return_value={"FINISHED"}) as setup,
            patch.object(self.convert_to_plane, "prepare_material_color_input") as prepare,
        ):
            self.assertEqual(self.convert_to_plane.ConvertToDepthPlane.execute(operator, context), {"FINISHED"})
            setup.assert_called_once()
            prepare.assert_not_called()


    def test_depth_and_relief_start_jobs_with_their_plane_type(self):
        for plane_type, operator_class in (("DEPTH", self.convert_to_plane.ConvertToDepthPlane), ("RELIEF", self.convert_to_plane.ConvertToReliefPlane)):
            module = self.convert_to_plane
            source = SimpleNamespace(name="Source", as_pointer=lambda: 1,
                                     data=SimpleNamespace(as_pointer=lambda: 2))
            context = SimpleNamespace(object=source, scene=object())
            operator = SimpleNamespace(mesh_detail=4, report=Mock())
            generate = Mock(return_value={"FINISHED"})
            with (
                patch.object(module, "invoke_ai_setup_if_needed", return_value=None),
                patch.object(module, "prepare_material_color_input", return_value=Path("input.png")),
                patch.object(module, "material_analysis_input", return_value=Path("input.png")),
                patch.object(module, "depth_plane_settings", return_value=("moge", 5)),
                patch.object(module, "configured_max_ai_input_size", return_value=1024),
                patch.object(module.bpy, "ops", SimpleNamespace(anyimage=SimpleNamespace(generate_depth_plane=generate)), create=True),
            ):
                self.assertEqual(operator_class.execute(operator, context), {"FINISHED"})
            self.assertEqual(generate.call_args.kwargs["source_object_name"], "Source")
            self.assertEqual(generate.call_args.kwargs["plane_type"], plane_type)

    def test_depth_and_relief_results_use_their_normal_space(self):
        for plane_type, normal_space in (("DEPTH", "OBJECT"), ("RELIEF", "TANGENT")):
            normal_key = f"{normal_space.lower()}_normal"
            module = self.convert_to_plane_object
            source = SimpleNamespace(data=SimpleNamespace(name="Source"))
            color_image = SimpleNamespace(name="", users=0)
            depth_image = SimpleNamespace(users=0)
            normal_image = SimpleNamespace(users=0)
            material = SimpleNamespace(users=0)
            metadata = {
                "image_size": (2, 1),
                "intrinsics": ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
            }
            files = {
                "depth_metadata": Path("depth.json"),
                "depth": Path("depth.exr"),
                normal_key: Path(f"{normal_key}.png"),
            }
            result = SimpleNamespace(
                directory=Path("result"),
                file=lambda key: files[key],
            )
            operator = SimpleNamespace(source_object_name="Source", color_path="color.png", mesh_detail=6, plane_type=plane_type)
            context = SimpleNamespace(scene=object())
            ops = SimpleNamespace(
                ed=SimpleNamespace(undo_push=Mock(return_value={"FINISHED"}))
            )

            with (
                patch.object(module, "require_conversion_source", return_value=source),
                patch.object(module, "material_color_image", return_value=nullcontext(color_image)),
                patch.object(module, "load_depth_metadata", return_value=metadata),
                patch.object(module, "load_depth_result_image", return_value=depth_image) as load_depth,
                patch.object(
                    module,
                    "load_normal_result_image",
                    return_value=normal_image,
                ) as load_normal,
                patch.object(
                    module,
                    "create_image_material",
                    return_value=material,
                ) as create_material,
                patch.object(module, "create_depth_plane_object") as create_object,
                patch.object(module.bpy, "ops", ops, create=True),
            ):
                module.create_depth_plane_from_result(context, result, operator)

            load_depth.assert_called_once_with(files["depth"], source, metadata)
            ops.ed.undo_push.assert_called_once_with(message=f"Convert to {plane_type.title()} Plane")
            load_normal.assert_called_once_with(files[normal_key], source)
            create_material.assert_called_once_with(
                source.data,
                color_image,
                normal_image=normal_image,
                normal_space=normal_space,
                scene=context.scene,
            )
            create_object.assert_called_once_with(
                context,
                source,
                6,
                material,
                depth_image,
                metadata,
                plane_type,
            )


    def test_depth_plane_result_cleans_unused_depth_and_normal_on_failure(self):
        module = self.convert_to_plane_object
        source = SimpleNamespace(data=SimpleNamespace(name="Source"))
        color_image = SimpleNamespace(name="", users=0)
        depth_image = SimpleNamespace(users=0)
        normal_image = SimpleNamespace(users=0)
        material = SimpleNamespace(users=0)
        files = {
            "depth_metadata": Path("depth.json"),
            "depth": Path("depth.exr"),
            "object_normal": Path("object-normal.png"),
        }
        result = SimpleNamespace(
            directory=Path("result"),
            file=lambda key: files[key],
        )
        remove_material = Mock()
        remove_image = Mock()
        data = SimpleNamespace(
            materials=SimpleNamespace(remove=remove_material),
            images=SimpleNamespace(remove=remove_image),
        )

        with (
            patch.object(module, "require_conversion_source", return_value=source),
            patch.object(module, "material_color_image", return_value=nullcontext(color_image)),
            patch.object(
                module,
                "load_depth_metadata",
                return_value={
                    "image_size": (2, 1),
                    "intrinsics": ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
                },
            ),
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
                SimpleNamespace(source_object_name="Source", color_path="color.png", mesh_detail=6, plane_type="DEPTH"),
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
