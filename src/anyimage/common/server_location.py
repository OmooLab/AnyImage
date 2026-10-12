"""Resolve AnyImage locations and inspect its required model files."""
from pathlib import Path

from ..runtime import runtime

from ..server.model_catalog import DEFAULT_MODEL_KEYS, get_downloadable_model


def server_root(location):
    if not str(location).strip():
        raise ValueError("Choose a Server Location")
    selected = Path(location).expanduser().resolve()
    root = next(
        (path for path in (selected, *selected.parents) if path.name.lower() == ".anyimage"),
        selected / ".anyimage",
    )
    if root.resolve() != root:
        raise ValueError("Choose a location with a regular .anyimage directory")
    return root


def inspect_installation(root):
    status = runtime.inspect_installation(root)
    missing = []
    for key in DEFAULT_MODEL_KEYS:
        model = get_downloadable_model(key)
        if not model_files_installed(root, model):
            missing.append(key)
    return {**status, "missing_models": tuple(missing)}


def model_files_installed(root, model):
    directory = Path(root) / "models" / model.directory_name
    try:
        return all((directory / name).stat().st_size == size for name, size, _checksum in model.files)
    except OSError:
        return False
