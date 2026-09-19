"""Expose the extension and standalone server packages to the test suite."""
import sys

# Import the pinned dependencies before bpy prepends Blender's extension
# site-packages, where a half-removed install can shadow the project's own scipy.
import scipy  # noqa: F401

from tests.support.paths import PROJECT_ROOT

sys.path[:0] = [str(PROJECT_ROOT / "src"), str(PROJECT_ROOT / "src/anyimage")]
