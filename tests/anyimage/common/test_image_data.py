import unittest
from types import SimpleNamespace
from tests.anyimage.common.support import load_common_modules

class ImageDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = load_common_modules()

    def test_is_animated_image_accepts_movie_and_sequence(self):
        self.assertTrue(
            self.modules.image.is_animated_image(SimpleNamespace(source="MOVIE"))
        )
        self.assertTrue(
            self.modules.image.is_animated_image(SimpleNamespace(source="SEQUENCE"))
        )
        self.assertFalse(
            self.modules.image.is_animated_image(SimpleNamespace(source="FILE"))
        )

    def test_panorama_crop_bounds_returns_largest_centered_two_to_one_region(self):
        cases = (
            ((32, 16), (0, 0, 32, 16)),
            ((40, 16), (4, 0, 36, 16)),
            ((30, 20), (0, 2, 30, 17)),
            ((31, 20), (0, 2, 30, 17)),
            ((35, 16), (1, 0, 33, 16)),
        )
        for size, expected in cases:
            with self.subTest(size=size):
                self.assertEqual(
                    self.modules.image.panorama_crop_bounds(*size), expected
                )

    def test_panorama_crop_bounds_rejects_unusable_dimensions(self):
        for size in ((0, 1), (1, 1), (2, 0), (-2, 1)):
            with self.subTest(size=size):
                with self.assertRaisesRegex(ValueError, "at least 2 x 1 pixels"):
                    self.modules.image.panorama_crop_bounds(*size)


    def test_image_user_settings_reads_empty_values(self):
        source_object = SimpleNamespace(
            image_user=SimpleNamespace(
                frame_start=4,
                frame_offset=70,
                frame_duration=12,
            )
        )

        self.assertEqual(
            self.modules.image.image_user_settings(source_object),
            (4, 70, 12, False),
        )

        source_object.image_user.use_cyclic = True
        self.assertEqual(
            self.modules.image.image_user_settings(source_object),
            (4, 70, 12, True),
        )


    def test_image_user_settings_defaults_without_user(self):
        self.assertEqual(
            self.modules.image.image_user_settings(SimpleNamespace(image_user=None)),
            (1, 0, 0, False),
        )


    def test_depth_data_uses_source_image_name(self):
        source_object = SimpleNamespace(
            name="obj_img",
            data=SimpleNamespace(name="img.png"),
        )

        self.assertEqual(
            self.modules.image.depth_data_name(source_object),
            "img_depth.exr",
        )
        source_object.data.name = "img.png.001"
        self.assertEqual(
            self.modules.image.depth_data_name(source_object),
            "img.001_depth.exr",
        )


    def test_moge_normal_name_uses_source_image_name(self):
        source_object = SimpleNamespace(
            name="obj_img",
            data=SimpleNamespace(name="img.png"),
        )

        self.assertEqual(
            self.modules.image.normal_data_name(source_object),
            "img_normal.png",
        )


    def test_image_empty_bounds_keep_image_aspect_and_empty_offset(self):
        source = SimpleNamespace(
            data=SimpleNamespace(size=(800, 400)),
            empty_display_size=2.0,
            empty_image_offset=(-0.5, -0.5),
        )

        bounds = self.modules.image.image_empty_bounds(source)

        self.assertEqual(bounds, (-1.0, 1.0, -0.5, 0.5))
