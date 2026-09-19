from tests.support.paths import PROJECT_ROOT
import tomllib
import unittest


MANIFEST_PATH = PROJECT_ROOT / "src" / "anyimage" / "blender_manifest.toml"


class ExtensionManifestTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = tomllib.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_declares_modern_extension_metadata(self):
        self.assertEqual(self.manifest["schema_version"], "1.0.0")
        self.assertEqual(self.manifest["id"], "anyimage")
        self.assertEqual(self.manifest["type"], "add-on")

    def test_declares_required_environment_permissions(self):
        self.assertEqual(
            set(self.manifest["permissions"]),
            {"network", "files"},
        )
