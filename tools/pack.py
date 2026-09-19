import argparse
import platform as host_platform
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = PROJECT_ROOT / "src" / "anyimage"
DIST_DIR = PROJECT_ROOT / "dist"
PYTHON_TARGETS = {
    "3.11": "numpy>=1.26,<2.0",
    "3.13": "numpy>=2.1,<3.0",
}
# Resolve NumPy for dependency compatibility, but use Blender's runtime copy.
BLENDER_PROVIDED_PACKAGES = frozenset({"numpy"})


@dataclass(frozen=True)
class Platform:
    pip_platform: str


PLATFORM_CONFIGS = {
    "windows-x64": Platform(pip_platform="win_amd64"),
    "macos-arm64": Platform(pip_platform="macosx_12_0_arm64"),
    "linux-x64": Platform(pip_platform="manylinux2014_x86_64"),
}
PLATFORMS = tuple(PLATFORM_CONFIGS)


def require_node_asset():
    """Fail before packaging when the generated node asset is absent."""
    asset_path = SOURCE_DIR / "assets" / "O_AnyImage.blend"
    if not asset_path.is_file():
        raise RuntimeError(
            "Node asset is missing; run: uv run --group blender node-group build"
        )


def project_dependencies():
    """Return Extension wheel requirements declared by the project."""
    project = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]
    return project.get("dependencies", [])


def download_wheels(platform, destination):
    """Download default dependencies as wheels for one target platform."""
    dependencies = project_dependencies()
    if not dependencies:
        return []
    config = PLATFORM_CONFIGS[platform]
    # Blender supplies NumPy; resolve against each runtime's compatible range.
    dependencies = [
        dependency
        for dependency in dependencies
        if re.split(r"[\s\[<>=!~;@]", dependency, maxsplit=1)[0]
        .lower().replace("_", "-") not in BLENDER_PROVIDED_PACKAGES
    ]
    wheels_by_name = {}
    shared_constraints = destination / "shared-constraints.txt"
    for python_version, numpy_requirement in PYTHON_TARGETS.items():
        target_directory = destination / python_version
        target_directory.mkdir()
        command = [
            sys.executable,
            "-m",
            "pip",
            "download",
            *dependencies,
            numpy_requirement,
            "--dest",
            str(target_directory),
            "--only-binary=:all:",
            f"--python-version={python_version}",
            "--implementation=cp",
            f"--platform={config.pip_platform}",
        ]
        if shared_constraints.exists():
            command.extend(["--constraint", str(shared_constraints)])
        subprocess.run(command, check=True)
        wheels = extension_wheels(sorted(target_directory.glob("*.whl")))
        if not wheels:
            raise RuntimeError(
                f"No wheels downloaded for {platform}, Python {python_version}"
            )
        if not shared_constraints.exists():
            shared_constraints.write_text(
                "\n".join(
                    "==".join(wheel.name.split("-")[:2])
                    for wheel in wheels
                    if wheel.name.endswith("-none-any.whl")
                ),
                encoding="utf-8",
            )
        for wheel in wheels:
            wheels_by_name[wheel.name] = wheel
    return [wheels_by_name[name] for name in sorted(wheels_by_name)]


def extension_wheels(wheels):
    """Exclude distributions supplied by the supported Blender runtime."""
    return [
        wheel
        for wheel in wheels
        if wheel.name.split("-", 1)[0].lower().replace("_", "-")
        not in BLENDER_PROVIDED_PACKAGES
    ]


def current_platform():
    target = {
        ("Windows", "amd64"): "windows-x64",
        ("Darwin", "arm64"): "macos-arm64",
        ("Linux", "x86_64"): "linux-x64",
    }.get((host_platform.system(), host_platform.machine().lower()))
    if target is None:
        raise ValueError("Unsupported host platform; specify --platform explicitly")
    return target


def prepare_local_dependencies(platform):
    """Synchronize local wheels and Manifest after a successful download."""
    if platform not in PLATFORMS:
        raise ValueError(f"Unsupported platform: {platform}")
    with tempfile.TemporaryDirectory() as directory:
        wheels = download_wheels(platform, Path(directory))
        manifest = manifest_for_platform(platform, wheels)
        destination = SOURCE_DIR / "wheels"
        destination.mkdir(exist_ok=True)
        for wheel in wheels:
            shutil.copy2(wheel, destination / wheel.name)
        selected = {wheel.name for wheel in wheels}
        for wheel in destination.glob("*.whl"):
            if wheel.name not in selected:
                wheel.unlink()
        manifest_path = SOURCE_DIR / "blender_manifest.toml"
        temporary_manifest = manifest_path.with_suffix(".toml.tmp")
        temporary_manifest.write_text(manifest, encoding="utf-8")
        temporary_manifest.replace(manifest_path)
    return sorted(destination.glob("*.whl"))


def manifest_for_platform(platform, wheels):
    """Return manifest text for one platform and its downloaded wheels."""
    wheels = extension_wheels(wheels)
    text = (SOURCE_DIR / "blender_manifest.toml").read_text(encoding="utf-8")
    lines = text.splitlines()
    table_start = next(
        (i for i, line in enumerate(lines) if line.startswith("[")),
        len(lines),
    )
    head = lines[:table_start]
    tail = lines[table_start:]
    head = [
        line
        for line in head
        if not line.strip().startswith(("platforms =", "wheels ="))
    ]
    insert_at = next(
        (
            i + 1
            for i, line in enumerate(head)
            if line.strip().startswith("blender_version_min")
        ),
        len(head),
    )
    head.insert(insert_at, f'platforms = ["{platform}"]')
    wheel_names = ", ".join(f'"./wheels/{wheel.name}"' for wheel in wheels)
    head.insert(insert_at + 1, f"wheels = [{wheel_names}]")
    return "\n".join(head + tail) + "\n"


def _build_extension(platform, wheels):
    require_node_asset()
    wheels = extension_wheels(wheels)
    manifest_text = manifest_for_platform(platform, wheels)
    manifest = tomllib.loads(manifest_text)
    output_path = DIST_DIR / (
        f"{manifest['name']}.v{manifest['version']}.{platform}.zip"
    )
    DIST_DIR.mkdir(exist_ok=True)
    with ZipFile(output_path, "w", ZIP_DEFLATED) as archive:
        for source_path in sorted(SOURCE_DIR.rglob("*")):
            if not source_path.is_file():
                continue
            if "__pycache__" in source_path.parts:
                continue
            if (
                source_path.suffix.startswith(".blend")
                and source_path.suffix != ".blend"
            ):
                continue
            relative_path = source_path.relative_to(SOURCE_DIR)
            if relative_path.parts[0] == "wheels":
                continue
            if source_path.name == "blender_manifest.toml":
                continue
            archive.write(source_path, relative_path)
        archive.writestr("blender_manifest.toml", manifest_text)
        for wheel in wheels:
            archive.write(wheel, Path("wheels") / wheel.name)
    return output_path


def build_extension(platform):
    if platform not in PLATFORMS:
        raise ValueError(f"Unsupported platform: {platform}")
    with tempfile.TemporaryDirectory() as directory:
        wheels = download_wheels(platform, Path(directory))
        return _build_extension(platform, wheels)


def build_all():
    return [build_extension(platform) for platform in PLATFORMS]


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Pack Blender extensions or prepare local dependencies"
    )
    parser.add_argument(
        "-l",
        "--local",
        action="store_true",
        help="Update source wheels and Manifest for local testing",
    )
    parser.add_argument(
        "-p",
        "--platform",
        choices=PLATFORMS,
        help="Build one platform; --local defaults to this computer",
    )
    args = parser.parse_args(argv)
    if args.local:
        platform = args.platform or current_platform()
        wheels = prepare_local_dependencies(platform)
        print(
            f"Prepared {len(wheels)} wheels for {platform} in {SOURCE_DIR / 'wheels'}"
        )
        print(f"Updated {SOURCE_DIR / 'blender_manifest.toml'}")
        return
    extension_paths = [build_extension(args.platform)] if args.platform else build_all()
    for extension_path in extension_paths:
        size_mib = extension_path.stat().st_size / (1024 * 1024)
        print(f"Built {extension_path} ({size_mib:.2f} MiB)")


if __name__ == "__main__":
    main()
