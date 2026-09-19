from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from tests.support.blender import BlenderTestCase


class RecordingLayout:
    """Minimal Blender layout that records the properties and operators drawn."""

    enabled = True

    def __init__(self, operators):
        self.properties = []
        self.operators = operators

    def prop(self, _owner, name, **_options):
        self.properties.append(name)

    def operator(self, identifier, **_options):
        operator = SimpleNamespace(model="")
        self.operators.append((identifier, operator))
        return operator

    def box(self):
        return self

    def row(self, **_options):
        return self

    def split(self, **_options):
        return self

    def column(self, **_options):
        return self

    def label(self, **_options):
        return None

    def separator(self, **_options):
        return None


class PreferencesTest(BlenderTestCase):
    def test_apple_silicon_architectures_support_coreml(self):
        properties = self.anyimage.properties
        for architecture in ("arm64", "aarch64"):
            with (
                self.subTest(architecture=architecture),
                patch.object(
                    self.anyimage.runtime,
                    "environment_manifest",
                    return_value={},
                ),
                patch.object(properties.sys, "platform", "darwin"),
                patch.object(
                    properties.platform,
                    "machine",
                    return_value=architecture,
                ),
            ):
                self.assertEqual(
                    properties.supported_devices(),
                    ["cpu", "coreml"],
                )


    def test_non_apple_silicon_mac_uses_cpu(self):
        properties = self.anyimage.properties
        with (
            patch.object(
                self.anyimage.runtime,
                "environment_manifest",
                return_value={},
            ),
            patch.object(properties.sys, "platform", "darwin"),
            patch.object(
                properties.platform,
                "machine",
                return_value="x86_64",
            ),
        ):
            self.assertEqual(properties.supported_devices(), ["cpu"])


    def test_manifest_coreml_requires_apple_silicon(self):
        properties = self.anyimage.properties
        manifest = {"devices": ["coreml", "cpu"]}
        with (
            patch.object(
                self.anyimage.runtime,
                "environment_manifest",
                return_value=manifest,
            ),
            patch.object(properties.sys, "platform", "linux"),
        ):
            self.assertEqual(properties.supported_devices(), ["cpu"])
        with (
            patch.object(
                self.anyimage.runtime,
                "environment_manifest",
                return_value=manifest,
            ),
            patch.object(properties.sys, "platform", "darwin"),
            patch.object(
                properties.platform,
                "machine",
                return_value="aarch64",
            ),
        ):
            self.assertEqual(
                properties.supported_devices(),
                ["cpu", "coreml"],
            )


    def test_windows_keeps_default_directml_device(self):
        properties = self.anyimage.properties
        with (
            patch.object(
                self.anyimage.runtime,
                "environment_manifest",
                return_value={},
            ),
            patch.object(properties.sys, "platform", "win32"),
        ):
            self.assertEqual(
                properties.supported_devices(),
                ["directml", "cpu"],
            )


    def test_model_preferences_keep_valid_choices_and_reset_unknown_keys(self):
        module = self.anyimage.preferences
        stored = self.fake_bpy.context.preferences.addons["anyimage"].preferences
        for attribute, reader, valid, default in (
            ("geometry_model", module.configured_geometry_model, "MOGE3_VITL", "MOGE2_VITS_NORMAL"),
            ("background_model", module.configured_background_model, "BEN2_BASE", "BIREFNET_LITE"),
            ("upscale_model", module.configured_upscale_model, "REALESRGAN_X4PLUS", "REALESRGAN_GENERAL_WDN_X4V3"),
        ):
            setattr(stored, attribute, valid)
            self.assertEqual(reader(), valid)
            setattr(stored, attribute, "UNKNOWN")
            self.assertEqual(reader(), default)
            self.assertEqual(getattr(stored, attribute), default)


    def test_numeric_preferences_clamp_to_supported_ranges(self):
        module = self.anyimage.preferences
        preferences = self.fake_bpy.context.preferences.addons["anyimage"].preferences
        cases = (
            (module.configured_max_ai_input_size, "max_ai_input_size", (10000, 1), (8192, 256)),
            (module.configured_max_frame_resolution, "max_frame_resolution", (10000, 1), (8192, 64)),
            (module.configured_cutout_boundary_padding, "cutout_boundary_padding", (3.5, 100, -1), (3.5, 4, 1)),
            (
                module.configured_min_cutout_relative_edge_length,
                "min_cutout_relative_edge_length",
                (2, 200, 0),
                (0.02, 1, 0.00001),
            ),
        )
        for reader, attribute, values, expected in cases:
            with self.subTest(attribute=attribute):
                for value, result in zip(values, expected):
                    setattr(preferences, attribute, value)
                    self.assertAlmostEqual(reader(), result)


    def test_preferences_draw_follows_ai_status(self):
        catalog = tuple(
            {
                "key": key,
                "label": key,
                "family": family,
                "enabled": True,
                "ready": False,
            }
            for key, family in (
                ("MOGE2_VITS_NORMAL", "moge"),
                ("BEN2_BASE", "ben2"),
                ("HAT_GAN_X4_SHARPER", "upscale"),
            )
        )
        missing_environment = {
            "environment_ready": False,
            "missing_models": (),
            "ready": False,
        }
        operators = self.draw_preferences(missing_environment, ())
        self.assertEqual(
            [identifier for identifier, _options in operators],
            ["anyimage.setup_ai_environment", "anyimage.open_server_log"],
        )

        ready = {"environment_ready": True, "missing_models": (), "ready": True}
        operators = self.draw_preferences(ready, catalog)
        downloads = [
            operator.model
            for identifier, operator in operators
            if identifier == "anyimage.download_model"
        ]
        self.assertEqual(
            downloads,
            ["MOGE2_VITS_NORMAL", "BEN2_BASE", "HAT_GAN_X4_SHARPER"],
        )

    def draw_preferences(self, status, catalog):
        operators = []
        preferences = self.anyimage.preferences.AnyImagePreferences()
        preferences.layout = RecordingLayout(operators)
        preferences.geometry_model = "MOGE2_VITS_NORMAL"
        preferences.background_model = "BEN2_BASE"
        preferences.upscale_model = "HAT_GAN_X4_SHARPER"
        with (
            patch.object(self.anyimage.properties, "ai_status", return_value=status),
            patch.object(self.anyimage.properties, "model_catalog", return_value=catalog),
            patch.object(self.anyimage.runtime, "server_busy", return_value=False),
        ):
            preferences.draw(None)
        return operators


    def test_depth_plane_request_includes_the_global_ai_input_limit(self):
        operator = self.convert_to_plane.GenerateDepthPlane()
        operator.plane_type = "DEPTH"
        operator.input_path = __file__
        operator.analysis_input_path = __file__
        operator.source_object_name = "Source"
        operator.mesh_detail = 0
        operator.model = self.anyimage.preferences.DEFAULT_GEOMETRY_MODEL_KEY
        operator.resolution_level = 5
        operator.max_input_size = 1536
        context = SimpleNamespace(
            scene=SimpleNamespace(anyimage_settings=SimpleNamespace())
        )
        with (
            patch.object(self.convert_to_plane, "require_environment"),
            patch.object(self.convert_to_plane, "require_model"),
            patch.object(self.convert_to_plane, "require_input_path", return_value=Path("input.png")),
            patch.object(self.convert_to_plane, "production_device", return_value="CPU"),
        ):
            parameters = operator.request(context)

        self.assertEqual(parameters["max_input_size"], 1536)


    def test_upscale_execute_reads_model_and_size_from_preferences(self):
        source_image = SimpleNamespace(
            name="Original",
            source="FILE",
        )
        source_object = SimpleNamespace(
            name="Source",
            type="EMPTY",
            empty_display_type="IMAGE",
            data=source_image,
            image_user=None,
        )
        context = SimpleNamespace(
            object=source_object,
            scene=SimpleNamespace(anyimage_settings=SimpleNamespace()),
        )
        operator = self.upscale.UpscaleImage()
        with (
            patch.object(
                self.upscale,
                "configured_upscale_model",
                return_value="HAT_GAN_X4_SHARPER",
            ),
            patch.object(
                self.upscale,
                "configured_max_ai_input_size",
                return_value=1024,
            ),
            patch.object(
                self.upscale.ImageEditTarget,
                "prepare",
                return_value=(Path("input.png"), False),
            ),
            patch.object(
                self.runtime.JobOperatorBase,
                "execute",
                return_value={"RUNNING_MODAL"},
            ),
        ):
            result = operator.execute(context)

        self.assertEqual(result, {"RUNNING_MODAL"})
        self.assertEqual(operator.model, "HAT_GAN_X4_SHARPER")
        self.assertEqual(operator.max_input_size, 1024)
