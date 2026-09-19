"""Prepare a standalone color image for material and geometry tests."""

from anyimage.common.color_image import prepare_material_color_input, load_material_color_image, cleanup_material_color_input


def color_image(source, bounds=None, rgba=None):
    path = prepare_material_color_input(source, bounds, rgba)
    try:
        return load_material_color_image(path)
    finally:
        cleanup_material_color_input(path)
