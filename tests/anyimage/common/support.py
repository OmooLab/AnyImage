from tests.support.paths import PROJECT_ROOT
import importlib
import importlib.util
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
from tests.support.blender import mock_bpy_imports


def load_common_modules():
    fake_bpy = ModuleType("bpy")
    fake_bpy.path = SimpleNamespace(abspath=lambda path: path)
    fake_bpy.context = SimpleNamespace(scene=None)

    module_paths = (
        (
            "anyimage.common.image",
            PROJECT_ROOT
            / "src"
            / "anyimage"
            / "common"
            / "image.py",
        ),
        (
            "anyimage.common.node",
            PROJECT_ROOT
            / "src"
            / "anyimage"
            / "common"
            / "node.py",
        ),
        (
            "anyimage.common.material",
            PROJECT_ROOT
            / "src"
            / "anyimage"
            / "common"
            / "material.py",
        ),
        (
            "anyimage.common.object",
            PROJECT_ROOT
            / "src"
            / "anyimage"
            / "common"
            / "object.py",
        ),
    )
    packages = {
        name: ModuleType(name)
        for name in (
            "anyimage",
            "anyimage.common",
        )
    }
    for package in packages.values():
        package.__path__ = []

    loaded = []
    preferences = ModuleType("anyimage.preferences")
    preferences.configured_material_view_adaptation = lambda: True
    with mock_bpy_imports(fake_bpy), patch.dict(sys.modules, {"anyimage.preferences": preferences, **packages}):
        for module_name, module_path in module_paths:
            specification = importlib.util.spec_from_file_location(
                module_name,
                module_path,
            )
            module = importlib.util.module_from_spec(specification)
            sys.modules[module_name] = module
            specification.loader.exec_module(module)
            loaded.append(module)

    return SimpleNamespace(image=loaded[0], material=loaded[2], object=loaded[3])
