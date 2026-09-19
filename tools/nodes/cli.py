import argparse
import importlib.util
import subprocess
import sys
import webbrowser
from pathlib import Path
from tempfile import mkdtemp


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def run(command):
    print("+", subprocess.list2cmdline([str(part) for part in command]), flush=True)
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def require_bpy():
    if importlib.util.find_spec("bpy") is None:
        raise RuntimeError(
            "bpy is required; run with: uv run --group blender node-group ..."
        )


def run_module(module_name, arguments=()):
    run((sys.executable, "-m", module_name, *arguments))


def main():
    parser = argparse.ArgumentParser(description="Build, check, or preview node groups.")
    commands = parser.add_subparsers(dest="command")
    for name, help_text in (
        ("build", "Build assets, validate them, and run tests"),
        ("check", "Validate saved assets and run tests"),
        ("preview", "Preview node groups from current source"),
    ):
        command = commands.add_parser(name, help=help_text)
        if name == "preview":
            command.add_argument("--output", type=Path, help="Output HTML path; defaults to a temporary directory")
            command.add_argument("--no-open", action="store_true", help="Save without opening a browser")
            command.add_argument("--fragment", action="store_true", help="Save an HTML fragment without opening it")
        else:
            command.add_argument("--skip-tests", action="store_true", help="Skip pytest, keeping asset validation")
    options = parser.parse_args()
    if options.command is None:
        parser.print_help()
        return
    require_bpy()
    if options.command == "preview":
        output = (options.output or Path(mkdtemp(prefix="anyimage-node-preview-")) / "nodes.html").resolve()
        arguments = ["--output", str(output)]
        if options.fragment:
            arguments.append("--fragment")
        run_module("tools.nodes.preview.export", arguments)
        print(output)
        if not options.no_open and not options.fragment:
            webbrowser.open(output.as_uri())
        return
    modules = ("tools.nodes.build", "tools.nodes.check") if options.command == "build" else ("tools.nodes.check",)
    for module_name in modules:
        run_module(module_name)
    if not options.skip_tests:
        run((sys.executable, "-m", "pytest", "tests/nodes", "tests/tools/nodes"))


if __name__ == "__main__":
    main()
