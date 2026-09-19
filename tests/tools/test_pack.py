from tests.support.paths import PROJECT_ROOT
import importlib.util
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch


def load_pack():
    specification = importlib.util.spec_from_file_location(
        "anyimage_pack",
        PROJECT_ROOT / "tools" / "pack.py",
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class ArchiveContents:
    def __init__(self, path, records):
        self.files = {}
        records[path] = self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def write(self, source, target):
        self.files[Path(target).as_posix()] = None

    def writestr(self, target, value):
        self.files[target] = value.encode()

    def namelist(self):
        return list(self.files)

    def read(self, name):
        return self.files[name]


class ExtensionPackagingTest(unittest.TestCase):
    def test_rejects_missing_generated_node_asset(self):
        pack = load_pack()
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(pack, "SOURCE_DIR", Path(directory)):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "uv run --group blender node-group build",
                ):
                    pack._build_extension("windows-x64", [])

    def test_selects_platform_archive_contents_and_manifest(self):
        pack = load_pack()
        records = {}
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            wheel_path = directory_path / "blendjob-0.1.17-py3-none-any.whl"
            wheel_path.write_bytes(b"wheel")
            original_dist = pack.DIST_DIR
            pack.DIST_DIR = directory_path / "dist"
            try:
                with (
                    patch.object(pack, "download_wheels", return_value=[wheel_path]),
                    patch.object(pack, "ZipFile", side_effect=lambda path, *args: ArchiveContents(path, records)),
                ):
                    output_paths = pack.build_all()
            finally:
                pack.DIST_DIR = original_dist

            version = tomllib.loads(
                (pack.SOURCE_DIR / "blender_manifest.toml").read_text(encoding="utf-8")
            )["version"]
            self.assertEqual(
                {path.name for path in output_paths},
                {f"AnyImage.v{version}.{platform}.zip" for platform in pack.PLATFORMS},
            )
            for output_path in output_paths:
                platform = output_path.stem.split(".")[-1]
                with records[output_path] as archive:
                    names = set(archive.namelist())
                    manifest = archive.read("blender_manifest.toml").decode("utf-8")

                self.assertIn("__init__.py", names)
                self.assertIn("operators/clipboard_image/__init__.py", names)
                self.assertIn("operators/clipboard_image/operators.py", names)
                self.assertIn("operators/clipboard_image/actions.py", names)
                self.assertIn("operators/clipboard_image/clipboard.py", names)
                self.assertIn("blender_manifest.toml", names)
                self.assertNotIn("assets/O_AnyImage.blend1", names)
                for path in (
                    "common/__init__.py",
                    "common/ai.py",
                    "common/depth.py",
                    "common/image.py",
                    "common/material.py",
                    "common/node.py",
                    "common/object.py",
                    "common/selection.py",
                    "common/viewport.py",
                    "operators/cutout_tool/__init__.py",
                    "operators/cutout_tool/operators.py",
                    "operators/cutout_tool/interaction.py",
                    "operators/cutout_tool/geometry.py",
                    "operators/cutout_tool/mesh.py",
                    "operators/cutout_tool/tangle.py",
                    "licenses/tangle.txt",
                    "operators/cutout_tool/object.py",
                    "operators/cutout_tool/shape.py",
                    "operators/convert_to_plane/__init__.py",
                    "operators/convert_to_plane/object.py",
                    "operators/convert_to_plane/operators.py",
                    "operators/convert_to_plane/image_plane.py",
                    "operators/convert_to_panorama/__init__.py",
                    "operators/convert_to_panorama/operators.py",
                    "operators/convert_to_panorama/object.py",
                    "operators/frame_tool/__init__.py",
                    "operators/frame_tool/operators.py",
                    "operators/frame_tool/projection.py",
                    "operators/frame_tool/compositing.py",
                    "operators/mask_tool.py",
                    "operators/rectify_tool/__init__.py",
                    "operators/rectify_tool/operators.py",
                    "operators/rectify_tool/geometry.py",
                    "operators/rectify_tool/preview.py",
                    "operators/ai_setup.py",
                    "operators/remove_background.py",
                ):
                    self.assertIn(path, names)
                self.assertIn(
                    "assets/O_AnyImage.blend",
                    names,
                )
                self.assertIn("server/media/input.py", names)
                self.assertIn("common/depth.py", names)
                self.assertIn("server/models/geometry.py", names)
                self.assertIn("server/jobs/remove_background.py", names)
                self.assertIn("server/jobs/cutout.py", names)
                self.assertIn("server/jobs/depth_plane.py", names)
                self.assertIn("server/jobs/panorama.py", names)
                self.assertIn("server/geometry/panorama.py", names)
                self.assertIn("server/geometry/depth_texture.py", names)
                self.assertIn("server/geometry/prediction_artifacts.py", names)
                self.assertIn("server/geometry/normal_texture.py", names)
                self.assertIn("server/models/background.py", names)
                self.assertIn("server/models/moge.py", names)
                self.assertIn("server/model_catalog.py", names)
                self.assertIn("server/model_download.py", names)
                self.assertIn("server/models/onnx_ben2.py", names)
                self.assertIn("server/models/onnx_birefnet.py", names)
                self.assertIn("server/models/onnx_moge2.py", names)
                self.assertIn("server/models/onnx_moge3.py", names)
                self.assertIn("server/models/onnx_upscale.py", names)
                self.assertIn("server/models/upscale.py", names)
                self.assertIn("server/__init__.py", names)
                self.assertIn("operators/cutout_tool/polygon.py", names)
                self.assertIn("licenses/scikit-image.txt", names)
                self.assertIn(
                    "wheels/blendjob-0.1.17-py3-none-any.whl",
                    names,
                )
                self.assertNotIn("anyimage/__init__.py", names)
                self.assertIn(f'platforms = ["{platform}"]', manifest)
                self.assertNotIn(
                    "windows-x64" if platform != "windows-x64" else "macos-arm64",
                    manifest.split("platforms =", 1)[-1],
                )

    def test_reads_extension_dependencies_from_pyproject(self):
        pack = load_pack()
        self.assertEqual(
            pack.project_dependencies(),
            [
                "blendjob==0.1.17",
                "numpy>=1.26,<2.0",
                "scipy==1.15.3",
            ],
        )

    def test_manifest_includes_all_resolved_numerical_wheels(self):
        pack = load_pack()
        wheels = [
            Path(name)
            for name in (
                "blendjob-0.1.17-py3-none-any.whl",
                "numpy-1.26.4-cp311-cp311-win_amd64.whl",
                "scipy-1.15.3-cp311-cp311-win_amd64.whl",
            )
        ]
        manifest = tomllib.loads(pack.manifest_for_platform("windows-x64", wheels))
        self.assertEqual(
            set(manifest["wheels"]),
            {
                f"./wheels/{wheel.name}"
                for wheel in wheels
                if not wheel.name.startswith("numpy-")
            },
        )

    def test_downloads_both_python_versions_for_each_platform(self):
        pack = load_pack()
        records = {}
        for platform, config in pack.PLATFORM_CONFIGS.items():
            with self.subTest(platform=platform), tempfile.TemporaryDirectory() as directory:
                destination = Path(directory)

                def fake_run(command, check):
                    self.assertTrue(check)
                    target = Path(command[command.index("--dest") + 1])
                    tag = "cp" + target.name.replace(".", "")
                    if target.name == "3.13":
                        constraints = Path(command[command.index("--constraint") + 1])
                        self.assertEqual(
                            constraints.read_text(), "blendjob==0.1.17"
                        )
                    else:
                        self.assertNotIn("--constraint", command)
                    for name in (
                        "blendjob-0.1.17-py3-none-any.whl",
                        f"scipy-1.15.3-{tag}-{tag}-{config.pip_platform}.whl",
                        f"numpy-2.1.0-{tag}-{tag}-{config.pip_platform}.whl",
                    ):
                        (target / name).write_bytes(b"wheel")

                with patch.object(pack.subprocess, "run", side_effect=fake_run) as run:
                    wheels = pack.download_wheels(platform, destination)

                self.assertEqual(run.call_count, 2)
                for call, version, numpy_requirement in zip(
                    run.call_args_list,
                    ("3.11", "3.13"),
                    ("numpy>=1.26,<2.0", "numpy>=2.1,<3.0"),
                ):
                    command = call.args[0]
                    self.assertIn("blendjob==0.1.17", command)
                    self.assertNotIn(str(pack.SOURCE_DIR / "wheels"), command)
                    self.assertIn(f"--python-version={version}", command)
                    self.assertIn("--implementation=cp", command)
                    self.assertIn(f"--platform={config.pip_platform}", command)
                    self.assertEqual(
                        [value for value in command if value.startswith("numpy")],
                        [numpy_requirement],
                    )
                self.assertEqual(len(wheels), 3)
                self.assertEqual(
                    [wheel.name for wheel in wheels], sorted({wheel.name for wheel in wheels})
                )
                self.assertFalse(any(wheel.name.startswith("numpy-") for wheel in wheels))
                with (
                    patch.object(pack, "DIST_DIR", destination / "dist"),
                    patch.object(pack, "ZipFile", side_effect=lambda path, *args: ArchiveContents(path, records)),
                ):
                    output = pack._build_extension(platform, wheels)
                with records[output] as archive:
                    manifest = tomllib.loads(archive.read("blender_manifest.toml").decode())
                    expected = {f"wheels/{wheel.name}" for wheel in wheels}
                    self.assertEqual({name[2:] for name in manifest["wheels"]}, expected)
                    self.assertEqual(
                        {name for name in archive.namelist() if name.startswith("wheels/")},
                        expected,
                    )

    def test_empty_second_python_download_is_rejected(self):
        pack = load_pack()
        with tempfile.TemporaryDirectory() as directory:
            def fake_run(command, check):
                target = Path(command[command.index("--dest") + 1])
                if target.name == "3.11":
                    (target / "blendjob-0.1.17-py3-none-any.whl").write_bytes(b"wheel")

            with patch.object(pack.subprocess, "run", side_effect=fake_run):
                with self.assertRaisesRegex(RuntimeError, "Python 3.13"):
                    pack.download_wheels("windows-x64", Path(directory))

    def test_rejects_unknown_platform(self):
        pack = load_pack()
        with self.assertRaisesRegex(ValueError, "Unsupported platform"):
            pack.build_extension("windows-arm64")

    def test_platforms_match_manifest(self):
        pack = load_pack()
        manifest = tomllib.loads(
            (pack.SOURCE_DIR / "blender_manifest.toml").read_text(encoding="utf-8")
        )
        self.assertTrue(set(manifest["platforms"]) <= set(pack.PLATFORMS))
        self.assertEqual(
            set(pack.PLATFORMS),
            {"windows-x64", "macos-arm64", "linux-x64"},
        )

    def test_prepares_local_wheels_and_removes_stale_versions(self):
        pack = load_pack()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            manifest_path = source / "blender_manifest.toml"
            manifest_path.write_text(
                (pack.SOURCE_DIR / "blender_manifest.toml").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            destination = source / "wheels"
            destination.mkdir()
            (destination / "numpy-1.26.4-cp311-cp311-win_amd64.whl").write_bytes(
                b"numpy"
            )
            (destination / "scipy-1.14.0-cp311-cp311-win_amd64.whl").write_bytes(b"old")
            (destination / "notes.txt").write_text("keep", encoding="utf-8")
            wheel = root / "scipy-1.15.3-cp311-cp311-win_amd64.whl"
            wheel.write_bytes(b"new")
            with (
                patch.object(pack, "SOURCE_DIR", source),
                patch.object(pack, "download_wheels", return_value=[wheel]),
            ):
                result = pack.prepare_local_dependencies("windows-x64")
            self.assertEqual(result, [destination / wheel.name])
            self.assertEqual(result[0].read_bytes(), b"new")
            self.assertTrue((destination / "notes.txt").exists())
            manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["wheels"], [f"./wheels/{wheel.name}"])
            self.assertEqual(manifest["platforms"], ["windows-x64"])
            self.assertIn("permissions", manifest)

    def test_failed_download_keeps_local_dependencies_and_manifest(self):
        pack = load_pack()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            manifest = source / "blender_manifest.toml"
            manifest.write_bytes(b"original manifest")
            wheels = source / "wheels"
            wheels.mkdir()
            old = wheels / "old.whl"
            old.write_bytes(b"original wheel")
            def fake_run(command, check):
                target = Path(command[command.index("--dest") + 1])
                if target.name == "3.13":
                    raise RuntimeError("download failed")
                (target / "blendjob-0.1.17-py3-none-any.whl").write_bytes(b"wheel")

            with (
                patch.object(pack, "SOURCE_DIR", source),
                patch.object(pack.subprocess, "run", side_effect=fake_run),
            ):
                with self.assertRaisesRegex(RuntimeError, "download failed"):
                    pack.prepare_local_dependencies("windows-x64")
            self.assertEqual(manifest.read_bytes(), b"original manifest")
            self.assertEqual(old.read_bytes(), b"original wheel")

    def test_archive_excludes_blender_numpy(self):
        pack = load_pack()
        records = {}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wheel = root / "numpy-1.26.4-cp311-cp311-win_amd64.whl"
            wheel.write_bytes(b"numpy")
            with (
                patch.object(pack, "DIST_DIR", root / "dist"),
                patch.object(pack, "ZipFile", side_effect=lambda path, *args: ArchiveContents(path, records)),
            ):
                output = pack._build_extension("windows-x64", [wheel])
            with records[output] as archive:
                self.assertFalse(any("numpy-" in name for name in archive.namelist()))
                self.assertEqual(
                    tomllib.loads(archive.read("blender_manifest.toml").decode())[
                        "wheels"
                    ],
                    [],
                )

    def test_local_flag_defaults_to_host_and_does_not_build(self):
        pack = load_pack()
        with (
            patch.object(pack, "current_platform", return_value="windows-x64"),
            patch.object(
                pack, "prepare_local_dependencies", return_value=[]
            ) as prepare,
            patch.object(pack, "build_all") as build,
        ):
            pack.main(["-l"])
        prepare.assert_called_once_with("windows-x64")
        build.assert_not_called()

    def test_platform_flag_builds_one_platform(self):
        pack = load_pack()
        with tempfile.TemporaryDirectory() as directory:
            extension = Path(directory) / "AnyImage.v1.0.1.linux-x64.zip"
            extension.write_bytes(b"extension")
            with (
                patch.object(pack, "build_extension", return_value=extension) as build,
                patch.object(pack, "build_all") as build_all,
            ):
                pack.main(["-p", "linux-x64"])
            build.assert_called_once_with("linux-x64")
            build_all.assert_not_called()

    def test_default_command_builds_all_platforms(self):
        pack = load_pack()
        with tempfile.TemporaryDirectory() as directory:
            extension = Path(directory) / "AnyImage.v1.0.1.windows-x64.zip"
            extension.write_bytes(b"extension")
            with (
                patch.object(pack, "build_all", return_value=[extension]) as build_all,
                patch.object(pack, "build_extension") as build_extension,
            ):
                pack.main([])
            build_all.assert_called_once_with()
            build_extension.assert_not_called()

    def test_detects_supported_hosts(self):
        pack = load_pack()
        for system, machine, expected in (
            ("Windows", "AMD64", "windows-x64"),
            ("Darwin", "arm64", "macos-arm64"),
            ("Linux", "x86_64", "linux-x64"),
        ):
            with (
                patch.object(pack.host_platform, "system", return_value=system),
                patch.object(pack.host_platform, "machine", return_value=machine),
            ):
                self.assertEqual(pack.current_platform(), expected)


if __name__ == "__main__":
    unittest.main()
