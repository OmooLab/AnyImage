"""Prepare a standalone color image for material and geometry tests."""

from anyimage.common.color_image import prepare_material_color_input, load_material_color_image, cleanup_material_color_input
from anyimage.operators.cutout_tool.texture import create_cutout_texture_atlas


def color_image(source, bounds=None, rgba=None, *, double_sided=False):
    path = prepare_material_color_input(source, bounds, rgba)
    try:
        image = load_material_color_image(path)
        if double_sided:
            create_cutout_texture_atlas(image)
        return image
    finally:
        cleanup_material_color_input(path)
