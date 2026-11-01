"""Expose project packages and isolate Blender from the user's installation."""
import os
import sys
from tempfile import TemporaryDirectory

from tests.support.paths import PROJECT_ROOT

sys.path[:0] = [str(PROJECT_ROOT / "src"), str(PROJECT_ROOT / "src/anyimage")]


def pytest_configure(config):
    """Select an empty user directory before test collection imports bpy."""
    directory = TemporaryDirectory(prefix="anyimage-blender-")
    os.environ["BLENDER_USER_RESOURCES"] = directory.name
    config.add_cleanup(directory.cleanup)
