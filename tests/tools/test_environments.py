import subprocess
import tomllib

from tests.support.paths import PROJECT_ROOT


def project_configuration():
    return tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )


def group_packages(configuration, name):
    groups = configuration["dependency-groups"]
    packages = set()
    for item in groups[name]:
        if isinstance(item, dict):
            packages.update(group_packages(configuration, item["include-group"]))
        else:
            packages.add(item.split("==", 1)[0].split(">=", 1)[0])
    return packages


def test_capability_groups_keep_ci_dependencies_small():
    configuration = project_configuration()
    groups = configuration["dependency-groups"]
    assert set(groups) == {"dev", "blender", "ai", "models", "docs"}
    ci_packages = group_packages(configuration, "dev") | group_packages(
        configuration, "blender"
    )
    assert ci_packages.isdisjoint(
        {"huggingface-hub", "onnx", "onnxruntime", "torch"}
    )


def test_ai_and_model_groups_own_their_runtime_dependencies():
    configuration = project_configuration()
    assert {"huggingface-hub", "onnxruntime"} <= group_packages(
        configuration, "ai"
    )
    assert {"onnx", "onnxruntime", "torch"} <= group_packages(
        configuration, "models"
    )


def test_workflows_run_the_regular_blender_suite():
    build_command = "uv run --group blender node-group build --skip-tests"
    test_command = (
        "uv run --group blender pytest tests/anyimage tests/nodes tests/tools"
    )
    for name in ("test.yml", "release.yml"):
        workflow = (PROJECT_ROOT / ".github" / "workflows" / name).read_text(
            encoding="utf-8"
        )
        assert build_command in workflow
        assert test_command in workflow
        assert workflow.index(build_command) < workflow.index(test_command)
        assert "BLENDER_BIN" not in workflow
        assert "download" not in workflow.lower()

    release = (PROJECT_ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )
    assert "uv run pack" in release


def test_generated_node_asset_is_ignored_and_untracked():
    asset = "src/anyimage/assets/O_AnyImage.blend"
    ignored = subprocess.run(
        ["git", "check-ignore", "--quiet", asset],
        cwd=PROJECT_ROOT,
        check=False,
    )
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", asset],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
    )
    assert ignored.returncode == 0
    assert tracked.returncode != 0
