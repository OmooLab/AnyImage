from anyimage.common.image_preview import preview_draw_bounds


def test_preview_is_centered_at_requested_aspect():
    left, bottom, width, height = preview_draw_bounds((1000, 800), 2.0)

    assert width / height == 2.0
    assert left + width * 0.5 == 500.0
    assert bottom + height * 0.5 == 400.0
