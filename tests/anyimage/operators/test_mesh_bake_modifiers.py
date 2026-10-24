"""Verify mesh bake boundaries and object menu availability."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from anyimage import ai_menu as menu
from anyimage.operators.bake_mesh import BakeMesh
from anyimage.operators.bake_mesh.materialization import mesh_bake_modifiers


class ImageObject(dict):
    type = "MESH"


def node_modifier(name):
    return SimpleNamespace(type="NODES", node_group=SimpleNamespace(name=name), show_viewport=True, show_render=True)


@pytest.mark.parametrize("groups,count", [
    (["O Image Plane"], 1),
    (["O Image Depth Plane"], 1),
    (["O Image Relief Plane"], 1),
    (["O Image Depth Panorama"], 1),
    (["O Image Cutout"], 1),
    (["O Image Depth Cutout"], 1),
    (["O Image Depth Cutout", "O Image Cutout Symmetry"], 2),
    (["O Image Cutout", "O Image Cutout Symmetry"], 1),
    (["User nodes", "O Image Depth Cutout"], 0),
    ([], 0),
])
def test_bake_menu_uses_image_prefix_with_arbitrary_modifiers(monkeypatch, groups, count):
    obj = ImageObject(o_image_object=True)
    prefix = [node_modifier(name) for name in groups]
    obj.modifiers = prefix + [
        SimpleNamespace(type="BEVEL", show_viewport=True, show_render=False),
        SimpleNamespace(type="NODES", node_group=None, show_viewport=False, show_render=True),
        node_modifier("Any user group"),
    ]
    assert mesh_bake_modifiers(obj) == tuple(prefix[:count])
    context = SimpleNamespace(object=obj, mode="OBJECT")
    assert BakeMesh.poll(context) is bool(count)
    layout = SimpleNamespace(operator=Mock(), separator=Mock())
    monkeypatch.setattr(menu, "draw_image_actions", Mock())
    menu.AnyImageObjectMenu.draw(SimpleNamespace(layout=layout), context)
    layout.operator.assert_called_once_with(BakeMesh.bl_idname, icon="MESH_DATA")
    context.mode = "EDIT_MESH"
    assert not BakeMesh.poll(context)
    del obj["o_image_object"]
    assert not mesh_bake_modifiers(obj)


@pytest.mark.parametrize("index,setting", [(0, "show_viewport"), (0, "show_render"), (1, "show_viewport"), (1, "show_render")])
def test_disabled_image_prefix_is_unavailable(index, setting):
    obj = ImageObject(o_image_object=True)
    obj.modifiers = [node_modifier("O Image Depth Cutout"), node_modifier("O Image Cutout Symmetry")]
    setattr(obj.modifiers[index], setting, False)
    assert not BakeMesh.poll(SimpleNamespace(object=obj, mode="OBJECT"))
