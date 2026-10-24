"""Select shared source files and the root edition entry point."""

from pathlib import Path

EDITIONS = ("full", "base")
AI_PATHS = (
    "ai_menu.py",
    "ai_preferences.py",
    "ai_properties.py",
    "ai_translations.py",
    "ai_tools.py",
    "common/ai.py",
    "common/analysis_image.py",
    "common/coordinate.py",
    "common/geometry_image.py",
    "common/job_image.py",
    "common/server_location.py",
    "operators/ai_setup.py",
    "operators/convert_to_panorama",
    "operators/convert_to_plane/object.py",
    "operators/convert_to_plane/operators.py",
    "operators/cutout_tool/ai_interaction.py",
    "operators/cutout_tool/ai_shape.py",
    "operators/cutout_tool/ai_object.py",
    "operators/cutout_tool/ai_operators.py",
    "operators/remove_background",
    "operators/upscale.py",
    "panel.py",
    "runtime.py",
    "server",
)


def edition_sources(source, edition):
    """Map archive paths to shared source files and the root entry point."""
    if edition not in EDITIONS:
        raise ValueError(f"Unsupported edition: {edition}")
    if not (source / "__init__.py").is_file():
        raise RuntimeError(f"Missing edition source: {source / '__init__.py'}")
    files = {}
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        if not path.is_file() or any(
            part.startswith(".") or part == "__pycache__" for part in relative.parts
        ):
            continue
        if relative.parts[0] == "wheels" or path.name == "blender_manifest.toml":
            continue
        if path.suffix.startswith(".blend") and path.suffix != ".blend":
            continue
        if edition == "base":
            if relative == Path("__init_base__.py"):
                continue
            if any(relative == Path(name) or Path(name) in relative.parents for name in AI_PATHS):
                continue
            if relative == Path("__init__.py"):
                path = source / "__init_base__.py"
        files[relative] = path
    files[Path("LICENSE")] = source.parents[1] / "LICENSE"
    for path in files.values():
        if not path.is_file():
            raise RuntimeError(f"Missing edition source: {path}")
    return files
