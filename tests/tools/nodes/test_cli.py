from tests.support.paths import PROJECT_ROOT
import importlib.util
import subprocess
from unittest.mock import patch
import pytest


SCRIPT_PATH = PROJECT_ROOT / "tools" / "nodes" / "cli.py"


def load_launcher():
    specification = importlib.util.spec_from_file_location(
        "node_asset_launcher",
        SCRIPT_PATH,
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_commands_require_the_blender_group(monkeypatch):
    launcher = load_launcher()
    monkeypatch.setattr("sys.argv", ["node-group", "check"])
    with patch.object(launcher.importlib.util, "find_spec", return_value=None):
        with pytest.raises(RuntimeError, match="--group blender"):
            launcher.main()


@pytest.mark.parametrize("arguments,commands", [
    (["build"], [
        ("tools.nodes.build", ()),
        ("tools.nodes.check", ()),
        ("pytest", ("tests/nodes", "tests/tools/nodes")),
    ]),
    (["check", "--skip-tests"], [("tools.nodes.check", ())]),
    (["preview", "--fragment"], [
        ("tools.nodes.preview.export", "preview"),
    ]),
])
def test_commands_dispatch_requested_work(monkeypatch, tmp_path, arguments, commands):
    launcher = load_launcher()
    output = tmp_path / "node groups.html"
    command = ["node-group", *arguments]
    if arguments[0] == "preview":
        command += ["--output", str(output)]
    monkeypatch.setattr("sys.argv", command)
    with (
        patch.object(launcher, "require_bpy"),
        patch.object(launcher, "run_module") as run_module,
        patch.object(launcher, "run") as run,
        patch.object(launcher.webbrowser, "open") as open_browser,
    ):
        launcher.main()
    if arguments[0] == "preview":
        run_module.assert_called_once_with(
            "tools.nodes.preview.export",
            ["--output", str(output), "--fragment"],
        )
        open_browser.assert_not_called()
    else:
        expected_modules = [item[0] for item in commands if item[0] != "pytest"]
        assert [call.args[0] for call in run_module.call_args_list] == expected_modules
    if any(item[0] == "pytest" for item in commands):
        run.assert_called_once_with(
            (
                launcher.sys.executable,
                "-m",
                "pytest",
                "tests/nodes",
                "tests/tools/nodes",
            )
        )
    else:
        run.assert_not_called()


def test_module_failure_stops_later_steps(monkeypatch):
    launcher = load_launcher()
    monkeypatch.setattr("sys.argv", ["node-group", "build"])
    with (
        patch.object(launcher, "require_bpy"),
        patch.object(
            launcher,
            "run_module",
            side_effect=subprocess.CalledProcessError(1, "build"),
        ) as run_module,
        patch.object(launcher, "run") as run,
    ):
        with pytest.raises(subprocess.CalledProcessError):
            launcher.main()
    run_module.assert_called_once_with("tools.nodes.build")
    run.assert_not_called()
