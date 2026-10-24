"""Validate release archives with Blender's bundled extension validator."""

import argparse
import hashlib
import subprocess
import sys
import tomllib
from pathlib import Path
from zipfile import ZipFile

from tools.editions import EDITIONS, edition_sources
from tools.pack import DIST_DIR, PLATFORMS, PROJECT_ROOT, SOURCE_DIR


def validate_archives(paths):
    import bpy

    version = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]["version"]
    validator = Path(bpy.utils.system_resource("SCRIPTS")) / "addons_core/bl_pkg/cli/blender_ext.py"
    asset_digest = None
    for path in paths:
        with ZipFile(path) as archive:
            manifest = tomllib.loads(archive.read("blender_manifest.toml").decode())
            edition = {"anyimage": "full", "anyimage_base": "base"}[manifest["id"]]
            name = "AnyImage Base" if edition == "base" else "AnyImage"
            (platform,) = manifest["platforms"]
            if (
                manifest["name"] != name
                or manifest["version"] != version
                or platform not in PLATFORMS
            ):
                raise ValueError(f"Unexpected manifest: {path}")
            if path.name != f"{name.replace(' ', '_')}.v{version}.{platform}.zip":
                raise ValueError(f"Unexpected archive name: {path}")
            sources = edition_sources(SOURCE_DIR, edition)
            expected = (
                {p.as_posix() for p in sources}
                | {"blender_manifest.toml"}
                | {p.removeprefix("./") for p in manifest["wheels"]}
            )
            if set(archive.namelist()) != expected:
                raise ValueError(f"Unexpected archive contents: {path}")
            for relative, source in sources.items():
                if archive.read(relative.as_posix()) != source.read_bytes():
                    raise ValueError(f"Stale source in archive: {path}: {relative}")
            if edition == "base":
                if "network" in manifest.get("permissions", {}) or any(
                    Path(wheel).name.lower().startswith(("blendjob-", "onnx", "torch-"))
                    for wheel in manifest["wheels"]
                ):
                    raise ValueError(f"AI dependency or permission in Base: {path}")
            digest = hashlib.sha256(archive.read("assets/O_AnyImage.blend")).digest()
            if asset_digest is not None and digest != asset_digest:
                raise ValueError("Edition node assets differ")
            asset_digest = digest
        subprocess.run([sys.executable, str(validator), "validate", str(path)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="*", type=Path)
    args = parser.parse_args()
    version = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]["version"]
    paths = args.archives or [
        DIST_DIR
        / f"{'AnyImage_Base' if edition == 'base' else 'AnyImage'}.v{version}.{platform}.zip"
        for platform in PLATFORMS
        for edition in EDITIONS
    ]
    validate_archives(paths)


if __name__ == "__main__":
    main()
