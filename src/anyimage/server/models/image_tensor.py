"""Prepare RGB input tensors for image models."""


def imagenet_rgb_tensor(image):
    """Normalize RGB with ImageNet statistics and return a contiguous NCHW tensor."""
    import numpy as np

    array = np.asarray(image, dtype=np.float32) / 255.0
    array -= np.array((0.485, 0.456, 0.406), dtype=np.float32)
    array /= np.array((0.229, 0.224, 0.225), dtype=np.float32)
    return np.ascontiguousarray(array.transpose(2, 0, 1)[None])
