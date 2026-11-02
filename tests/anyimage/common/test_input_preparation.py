import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tests.support.blender import BlenderTestCase


class InputPreparationTest(BlenderTestCase):

    def test_packed_image_export_saves_a_copy_and_restores_format(self):
        with tempfile.TemporaryDirectory() as directory:
            output_directory = Path(directory)
            calls = []

            class Image:
                file_format = "JPEG"

                def save(self, **options):
                    calls.append(options)
                    Path(options["filepath"]).write_bytes(b"raw image")

            image = Image()
            with patch.object(
                self.image_input.tempfile,
                "mkdtemp",
                return_value=str(output_directory),
            ):
                output = self.image_input.save_image_input(image)

            self.assertEqual(output, output_directory / "input.png")
            self.assertEqual(
                calls,
                [{"filepath": str(output), "save_copy": True}],
            )
            self.assertEqual(image.file_format, "JPEG")


    def test_packed_export_failure_removes_temporary_directory(self):
        for failure in (OSError("disk full"), None):
            with tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "export"
                output.mkdir()
                image = SimpleNamespace(file_format="OPEN_EXR", save=Mock(side_effect=failure))
                with patch.object(self.image_input.tempfile, "mkdtemp", return_value=str(output)):
                    with self.assertRaises(RuntimeError):
                        self.image_input.save_image_input(image)
                self.assertEqual(image.file_format, "OPEN_EXR")
                self.assertFalse(output.exists())


    def test_animated_inputs_are_rejected_before_export(self):
        for source in ("MOVIE", "SEQUENCE"):
            with self.subTest(source=source), patch.object(self.image_input, "save_image_input") as export:
                image = SimpleNamespace(source=source, packed_file=object())
                with self.assertRaisesRegex(RuntimeError, "Only still images"):
                    self.image_input.prepare_image_input(image)
                export.assert_not_called()
