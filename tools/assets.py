"""Build and copy Blender node assets."""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description="构建 Blender 节点资产并复制到插件目录。")
    parser.parse_args(argv)
    try:
        subprocess.run(["omoonodes", "build"], cwd=PROJECT_ROOT, check=True)
        destination = PROJECT_ROOT / "src/anyimage/assets/O_AnyImage.blend"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PROJECT_ROOT / "dist/b45/O_AnyImage/O_AnyImage.blend", destination)
    except subprocess.CalledProcessError as error:
        return error.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
