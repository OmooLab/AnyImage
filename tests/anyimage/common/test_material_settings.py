import unittest
from types import SimpleNamespace
from tests.anyimage.common.support import load_common_modules

class MaterialSettingsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = load_common_modules()

    def test_material_color_space_matches_scene_view_transform(self):
        mappings = {
            "ACES 1.3": "ACES 1.3 sRGB",
            "ACES 2.0": "ACES 2.0 sRGB",
            "AgX": "AgX Base sRGB",
            "Filmic": "Filmic sRGB",
            "Khronos PBR Neutral": "Khronos PBR Neutral sRGB",
            "Standard": "sRGB",
        }
        for view_transform, expected in mappings.items():
            with self.subTest(view_transform=view_transform):
                scene = SimpleNamespace(
                    view_settings=SimpleNamespace(
                        view_transform=view_transform,
                    )
                )
                self.assertEqual(
                    self.modules.material.material_color_space_name(scene),
                    expected,
                )


    def test_surface_displacement_is_set_to_displacement_only(self):
        class Material:
            surface_displacement_method = "BUMP"

        material = Material()
        self.modules.material.set_displacement_only(material)

        self.assertEqual(
            material.surface_displacement_method,
            "DISPLACEMENT",
        )
