"""Verify the shared storage and processing color contract."""

from types import SimpleNamespace

import numpy as np
import pytest

from anyimage.common.color_space import image_rgba_to_linear, linear_rgba_to_image


@pytest.mark.parametrize("floating", [False, True])
def test_color_conversion_depends_only_on_storage_type(floating):
    class Image:
        is_float = floating

        @property
        def colorspace_settings(self):
            raise AssertionError("Color processing must not inspect OCIO settings")

    rgba = np.asarray([[0.5, 0.0, 1.0, 0.25]], dtype=np.float32)
    linear = image_rgba_to_linear(Image(), rgba)
    assert linear[0, 0] == pytest.approx(0.5 if floating else 0.21404114)
    np.testing.assert_array_equal(linear[:, 3], rgba[:, 3])
    np.testing.assert_allclose(linear_rgba_to_image(Image(), linear), rgba, atol=1e-6)
    np.testing.assert_array_equal(rgba, [[0.5, 0.0, 1.0, 0.25]])


def test_float_conversion_preserves_hdr_values():
    image = SimpleNamespace(is_float=True)
    rgba = np.asarray([[-0.2, 2.0, 8.0, 0.5]], dtype=np.float32)
    np.testing.assert_array_equal(image_rgba_to_linear(image, rgba), rgba)
    np.testing.assert_array_equal(linear_rgba_to_image(image, rgba), rgba)
