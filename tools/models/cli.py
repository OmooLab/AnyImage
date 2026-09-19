"""Prepare AnyImage ONNX artifacts and upload them to OmooLab R2."""

import argparse
import hashlib
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = PROJECT_ROOT / "models"
MODEL_CACHE_DIR = PROJECT_ROOT / ".model-cache"
SOURCE_ROOT = PROJECT_ROOT / "src" / "anyimage"
sys.path.insert(0, str(SOURCE_ROOT))
from server.model_catalog import DOWNLOADABLE_MODELS

R2_REMOTE = "omoolab-r2:ai-models"
CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class BuildSpec:
    source_url: str
    source_filename: str
    source_size: int
    source_sha256: str
    exporter: str


@dataclass(frozen=True)
class ModelFile:
    key: str
    folder: str
    filename: str
    size: int
    sha256: str
    source_url: str = ""
    build: BuildSpec | None = None

    @property
    def destination(self):
        return MODELS_DIR / self.folder / self.filename

    @property
    def remote(self):
        return f"{R2_REMOTE}/{self.folder}/{self.filename}"


MODEL_BUILDS = {
    "REALESRGAN_GENERAL_WDN_X4V3": BuildSpec(
        source_url=(
            "https://github.com/xinntao/Real-ESRGAN/releases/download/"
            "v0.2.5.0/realesr-general-wdn-x4v3.pth"
        ),
        source_filename="realesr-general-wdn-x4v3.pth",
        source_size=4885111,
        source_sha256=(
            "1641f8c4464b9f097c9fdda5589273713f67cf59f3d909e0bd688f0cee269dca"
        ),
        exporter="realesrgan_wdn_x4",
    ),
}

ISOLATED_EXPORTERS = {
    "MOGE3_VITL": ("moge3_export.py", ()),
    "HAT_GAN_X4_SHARPER": ("hat_export.py", ()),
    "BIREFNET_LITE": ("birefnet_export.py", ("--variant", "lite")),
    "BIREFNET_HR_MATTING": ("birefnet_export.py", ("--variant", "hr-matting")),
}


def hf_url(repository, filename):
    return f"https://huggingface.co/{repository}/resolve/main/{filename}"


def catalog_model_files():
    files = []
    for key, model in DOWNLOADABLE_MODELS.items():
        for filename, size, sha256 in model.r2_files:
            source_url = ""
            if model.huggingface_repository:
                source_url = hf_url(model.huggingface_repository, filename)
            files.append(
                ModelFile(
                    key=key,
                    folder=model.r2_directory,
                    filename=filename,
                    size=size,
                    sha256=sha256,
                    source_url=source_url,
                    build=MODEL_BUILDS.get(key),
                )
            )
    return tuple(files)


MODEL_FILES = catalog_model_files()


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def verify_file(path, size, sha256):
    path = Path(path)
    if not path.is_file():
        return False
    if path.stat().st_size != size:
        raise RuntimeError(f"File has an unexpected size: {path}")
    if file_sha256(path) != sha256:
        raise RuntimeError(f"File has an unexpected SHA-256: {path}")
    return True


def download_file(url, destination, size, sha256):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f"{destination.name}.part")
    temporary.unlink(missing_ok=True)
    request = Request(url, headers={"User-Agent": "AnyImage model build"})
    print(f"Download: {url}")
    downloaded = 0
    digest = hashlib.sha256()
    try:
        with urlopen(request, timeout=60) as response, temporary.open("wb") as output:
            while chunk := response.read(CHUNK_SIZE):
                output.write(chunk)
                digest.update(chunk)
                downloaded += len(chunk)
                print(
                    f"\r  {downloaded / 1024**2:.1f} / {size / 1024**2:.1f} MiB",
                    end="",
                    flush=True,
                )
        print()
        if downloaded != size:
            raise RuntimeError(f"size mismatch: {downloaded} != {size}")
        if digest.hexdigest() != sha256:
            raise RuntimeError("SHA-256 mismatch")
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def prepare_source(build):
    source = MODEL_CACHE_DIR / build.source_filename
    if verify_file(source, build.source_size, build.source_sha256):
        return source
    download_file(
        build.source_url,
        source,
        build.source_size,
        build.source_sha256,
    )
    return source


def build_model(model):
    from tools.models.exports import export_model

    source = prepare_source(model.build)
    destination = model.destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f"{destination.name}.part")
    temporary.unlink(missing_ok=True)
    print(f"Build: {destination.relative_to(PROJECT_ROOT)}")
    try:
        export_model(model.build.exporter, source, temporary)
        verify_file(temporary, model.size, model.sha256)
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def prepare_model(model):
    if verify_file(model.destination, model.size, model.sha256):
        print(f"Skip existing: {model.destination.relative_to(PROJECT_ROOT)}")
        return
    if model.build:
        build_model(model)
        return
    if model.key in ISOLATED_EXPORTERS:
        model.destination.parent.mkdir(parents=True, exist_ok=True)
        exporter, arguments = ISOLATED_EXPORTERS[model.key]
        with TemporaryDirectory(prefix=f".{model.folder}-", dir=MODELS_DIR) as directory:
            subprocess.run(
                ["uv", "run", "--script", str(Path(__file__).with_name(exporter)),
                 *arguments, "--destination", directory],
                cwd=PROJECT_ROOT, check=True,
            )
            models = [item for item in MODEL_FILES if item.key == model.key]
            for item in models:
                if not verify_file(Path(directory) / item.filename, item.size, item.sha256):
                    raise RuntimeError(f"{model.key} export differs from the published catalog")
            for item in models:
                path = Path(directory) / item.filename
                destination = MODELS_DIR / item.folder / item.filename
                destination.parent.mkdir(parents=True, exist_ok=True)
                path.replace(destination)
        return
    if not model.source_url:
        raise RuntimeError(f"No upstream source or builder for {model.key}")
    download_file(
        model.source_url,
        model.destination,
        model.size,
        model.sha256,
    )


def upload_models(models=MODEL_FILES):
    executable = shutil.which("rclone")
    if executable is None:
        raise RuntimeError("rclone is not available on PATH")
    for model in models:
        print(f"Upload: {model.remote}")
        subprocess.run(
            [
                executable,
                "copyto",
                str(model.destination),
                model.remote,
                "--progress",
            ],
            cwd=PROJECT_ROOT,
            check=True,
        )


def parse_args():
    parser = argparse.ArgumentParser(description="Prepare models locally or sync them to R2.")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("prepare", help="Download or export models and verify them locally")
    commands.add_parser("sync", help="Prepare and verify all models, then upload them to R2")
    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
    return args


def main():
    args = parse_args()
    if args.command is None:
        return
    for model in MODEL_FILES:
        prepare_model(model)
    if args.command == "sync":
        upload_models()


if __name__ == "__main__":
    main()
