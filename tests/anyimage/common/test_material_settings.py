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
