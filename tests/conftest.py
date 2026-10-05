"""Expose the extension and standalone server packages to the test suite."""
import sys

# Import the pinned dependencies before bpy prepends Blender's extension
# site-packages, where a half-removed install can shadow the project's own scipy.
import scipy.ndimage  # noqa: F401
import scipy.interpolate  # noqa: F401
import scipy.optimize  # noqa: F401
from PIL import PngImagePlugin  # noqa: F401
from materialyoucolor.quantize import QuantizeCelebi  # noqa: F401

from tests.support.paths import PROJECT_ROOT

sys.path[:0] = [str(PROJECT_ROOT / "src"), str(PROJECT_ROOT / "src/anyimage")]
