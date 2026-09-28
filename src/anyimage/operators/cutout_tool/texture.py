"""Build Cutout material texture atlases."""


def create_cutout_texture_atlas(image, *, invert_rear_x=False):
    """Expand one image in place into mirrored Rear and Front vertical tiles."""
    import numpy as np

    width, height = (int(value) for value in image.size)
    atlas = np.empty((height * 2, width, 4), dtype=np.float32)
    front = atlas[height:]
    image.pixels.foreach_get(front.reshape(-1))
    atlas[:height] = front[:, ::-1]
    if invert_rear_x:
        atlas[:height, :, 0] = 1.0 - atlas[:height, :, 0]
    image.scale(width, height * 2)
    image.pixels.foreach_set(atlas.reshape(-1))
    image.update()
    image.pack()
    return image
