from types import SimpleNamespace

import pytest

from anyimage.common.viewport import apply_material_preview


@pytest.mark.parametrize("mode", ["WIREFRAME", "SOLID", "MATERIAL", "RENDERED"])
@pytest.mark.parametrize("use_scene_world", [False, True])
@pytest.mark.parametrize("enabled", [False, True])
def test_material_preview_preserves_other_shading_settings(mode, use_scene_world, enabled):
    shading = SimpleNamespace(type=mode, use_scene_world=False, use_scene_world_render=False,
                              use_scene_lights=False, use_scene_lights_render=True, studiolight_intensity=0.6)
    addon = SimpleNamespace(preferences=SimpleNamespace(auto_material_preview=enabled))
    context = SimpleNamespace(space_data=SimpleNamespace(type="VIEW_3D", shading=shading),
                              preferences=SimpleNamespace(addons={"anyimage": addon}))
    expected = vars(shading).copy()
    if enabled:
        expected["type"] = "RENDERED" if mode == "RENDERED" else "MATERIAL"
        if use_scene_world:
            expected["use_scene_world_render" if mode == "RENDERED" else "use_scene_world"] = True

    apply_material_preview(context, use_scene_world=use_scene_world)
    assert vars(shading) == expected


@pytest.mark.parametrize("space", [None, SimpleNamespace(type="OUTLINER")])
def test_material_preview_skips_non_viewport_context(space):
    apply_material_preview(SimpleNamespace(space_data=space), use_scene_world=True)
