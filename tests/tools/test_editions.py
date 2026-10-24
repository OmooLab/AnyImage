"""Verify standalone artifacts and edition switching in a fresh Blender process."""

import os
import subprocess
import sys
import tomllib
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import pytest

from tools import pack
from tools.editions import AI_PATHS, edition_sources


def test_editions_share_every_non_entry_source():
    full = edition_sources(pack.SOURCE_DIR, "full")
    base = edition_sources(pack.SOURCE_DIR, "base")
    for relative, source in base.items():
        if relative == Path("__init__.py"):
            assert source == pack.SOURCE_DIR / "__init_base__.py"
            continue
        assert source == full[relative], relative
    assert full[Path("__init_base__.py")] == pack.SOURCE_DIR / "__init_base__.py"
    assert list(pack.SOURCE_DIR.rglob("__init_base__.py")) == [pack.SOURCE_DIR / "__init_base__.py"]
    assert not (pack.SOURCE_DIR / "registration.py").exists()


def test_base_contents_and_dependencies(tmp_path):
    with patch.object(pack, "DIST_DIR", tmp_path):
        full = pack._build_extension("windows-x64", [], "full")
        base = pack._build_extension("windows-x64", [], "base")
    with ZipFile(base) as archive, ZipFile(full) as other:
        manifest = tomllib.loads(archive.read("blender_manifest.toml").decode())
        assert manifest["id"] == "anyimage_base"
        assert manifest["name"] == "AnyImage Base"
        assert "network" not in manifest["permissions"]
        assert archive.read("assets/O_AnyImage.blend") == other.read("assets/O_AnyImage.blend")
        assert not any(name.startswith("server/") for name in archive.namelist())
        assert "runtime.py" not in archive.namelist()
        assert "common/job_image.py" not in archive.namelist()
        assert "common/analysis_image.py" not in archive.namelist()
        assert not any(
            name == excluded or name.startswith(excluded + "/")
            for name in archive.namelist()
            for excluded in AI_PATHS
        )
        assert not any("__init_base__" in name for name in archive.namelist())
    requirements = pack.project_dependencies("base")
    assert all(not item.startswith("blendjob") for item in requirements)
    assert any(item.startswith("pillow") for item in requirements)
    assert any(item.startswith("scipy") for item in requirements)


@pytest.mark.parametrize("first", ["full", "base"])
def test_artifacts_register_and_switch_without_interference(tmp_path, first):
    for edition, repository in (("full", "first_repo"), ("base", "second_repo")):
        with patch.object(pack, "DIST_DIR", tmp_path):
            archive_path = pack._build_extension("windows-x64", [], edition)
        repository_path = tmp_path / repository
        repository_path.mkdir()
        (repository_path / "__init__.py").touch()
        with ZipFile(archive_path) as archive:
            archive.extractall(
                repository_path / ("anyimage_base" if edition == "base" else "anyimage")
            )
    script = tmp_path / "check.py"
    script.write_text(
        """
import importlib
import importlib.abc
import sys
import os
from pathlib import Path
from unittest.mock import Mock
from types import SimpleNamespace
import numpy as np
import scipy.ndimage
import scipy.interpolate
import scipy.optimize
from materialyoucolor.quantize import QuantizeCelebi
import bpy

package_root = (Path(__file__).parent / 'second_repo' / 'anyimage_base').resolve()
def audit_readonly_package(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        path = Path(os.fsdecode(args[0])).resolve()
        if path.is_relative_to(package_root) and args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT):
            raise PermissionError(f'Read-only installation: {path}')
sys.addaudithook(audit_readonly_package)

class RejectAI(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'blendjob', 'onnxruntime', 'torch', 'server'} or '.server' in fullname or fullname.endswith('.runtime'):
            raise AssertionError(f'Base imported AI code: {fullname}')

blocker = RejectAI()
sys.meta_path.insert(0, blocker)
base = importlib.import_module('second_repo.anyimage_base')
bpy.context.preferences.system.use_online_access = False
base.register()
settings = bpy.context.scene.anyimage_settings
assert settings.cutout_edge_length > 0
assert not hasattr(settings, 'cutout_generate_normal')
assert not hasattr(base.AnyImagePreferences, 'storage_root')
assert 'blendjob' not in sys.modules
image = bpy.data.images.new('Base source', width=4, height=4, alpha=True)
image.pixels.foreach_set(np.ones(4 * 4 * 4, dtype=np.float32))
source = bpy.data.objects.new('Base source', None)
source.empty_display_type = 'IMAGE'
source.data = image
bpy.context.collection.objects.link(source)
bpy.context.view_layer.objects.active = source
source.select_set(True)
shape_object = importlib.import_module('second_repo.anyimage_base.operators.cutout_tool.object')
mesh = SimpleNamespace(vertices=np.array([[-1, 0, -1], [1, 0, -1], [1, 0, 1], [-1, 0, 1]]),
                       faces=[(0, 1, 2, 3)], uv=np.array([[0, 0], [1, 0], [1, 1], [0, 1]]), balloon=np.zeros(4))
for shape in ('FLAT', 'SOLID'):
    result = shape_object.create_shape_object(bpy.context, source, shape, (0, 0, 4, 4), mesh, color_image=image)
    assert len(result.data.vertices) == 4
    assert result.modifiers[0].node_group.name == 'O Image Cutout'
bpy.context.view_layer.objects.active = result
assert bpy.ops.anyimage.bake_mesh() == {'FINISHED'}
bpy.context.view_layer.objects.active = source
assert bpy.ops.anyimage.convert_to_plane() == {'FINISHED'}
base.unregister()
sys.meta_path.remove(blocker)
full = importlib.import_module('first_repo.anyimage')
# The bpy wheel has no application event loop. Test real RNA registration while
# replacing the server polling timer, whose lifecycle has separate unit coverage.
full.runtime.enable = Mock()
first, second = (full, base) if sys.argv[1] == 'full' else (base, full)
first.register()
selection = next(cls for cls in first.CLASSES if getattr(cls, 'bl_idname', '') == 'anyimage.select_cutout_selection')
assert bpy.types.Operator.bl_rna_get_subclass_py(selection.bl_rna.identifier) is selection
assert selection.show_shape_menu.__module__.endswith('.ai_interaction' if first is full else '.interaction')
assert hasattr(bpy.context.scene.anyimage_settings, 'cutout_generate_normal') == (first is full)
poll_starts = full.runtime.enable.call_count
original = bpy.context.scene.anyimage_settings.bl_rna.as_pointer()
try:
    second.register()
except RuntimeError as error:
    assert 'already enabled' in str(error)
else:
    raise AssertionError('Second edition was enabled')
second.unregister()
assert full.runtime.enable.call_count == poll_starts
assert bpy.context.scene.anyimage_settings.bl_rna.as_pointer() == original
first.unregister()
assert not hasattr(bpy.types.Scene, 'anyimage_settings')
second.register()
assert hasattr(bpy.context.scene.anyimage_settings, 'cutout_generate_normal') == (second is full)
second.unregister()
assert not hasattr(bpy.types.Scene, 'anyimage_settings')
print('Edition isolation verified')
""",
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    for suffix in ("RESOURCES", "CONFIG", "SCRIPTS", "EXTENSIONS", "DATAFILES"):
        directory = tmp_path / "blender-user" / suffix.lower()
        directory.mkdir(parents=True, exist_ok=True)
        environment["BLENDER_USER_" + suffix] = str(directory)
    result = subprocess.run(
        [sys.executable, str(script), first],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        timeout=90,
    )
    assert result.returncode == 0, f"Exit {result.returncode}: {result.stdout}{result.stderr}"
    assert "Edition isolation verified" in result.stdout


def test_pack_selects_editions_and_platforms():
    with (
        patch.object(pack.subprocess, "run"),
        patch.object(pack, "build_all", return_value=[]) as build,
    ):
        pack.main(["--platform", "windows-x64"])
        build.assert_called_once_with(("full", "base"), ("windows-x64",))
    with (
        patch.object(pack.subprocess, "run"),
        patch.object(pack, "build_all", return_value=[]) as build,
    ):
        pack.main(["--edition", "base"])
        build.assert_called_once_with(("base",), pack.PLATFORMS)
    with pytest.raises(SystemExit):
        pack.main(["--local", "--edition", "base"])


def test_base_source_list_rejects_missing_files(tmp_path):
    with pytest.raises(RuntimeError, match="Missing edition source"):
        edition_sources(tmp_path, "base")
