import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tests.support.blender import BlenderTestCase


class InputPreparationTest(BlenderTestCase):

    def test_packed_export_failure_removes_temporary_directory(self):
        for failure in (OSError("disk full"), None):
            with tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "export"
                output.mkdir()
                image = SimpleNamespace(file_format="OPEN_EXR", save=Mock(side_effect=failure))
                with patch.object(self.image_data.tempfile, "mkdtemp", return_value=str(output)):
                    with self.assertRaises(RuntimeError):
                        self.image_data.save_packed_image(image, None)
                self.assertEqual(image.file_format, "OPEN_EXR")
                self.assertFalse(output.exists())


    def test_animated_inputs_are_rejected_before_export(self):
        for source in ("MOVIE", "SEQUENCE"):
            with self.subTest(source=source), patch.object(self.image_data, "save_packed_image") as export:
                image = SimpleNamespace(source=source, packed_file=object())
                with self.assertRaisesRegex(RuntimeError, "Only still images"):
                    self.image_data.prepare_image_input(image, None)
                export.assert_not_called()
