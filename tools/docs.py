"""Build and preview the versioned project documentation."""

import argparse
import subprocess
import tomllib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCUMENTATION_COMMANDS = {
    "dev": ("mkdocs", "serve"),
}
MIKE_DEPLOY_COMMAND = ("mike", "deploy", "--update-aliases")
DOCUMENTATION_REMOTE = "github"


def project_version():
    """Return the documentation version declared by the project."""
    project = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]
    return project["version"]


def documentation_version():
    """Return the major.minor series used for versioned documentation."""
    parts = project_version().split(".")
    if len(parts) < 2:
        raise ValueError("Project version must contain major and minor parts")
    return f"{parts[0]}.{parts[1]}.x"


def documentation_command(command):
    """Return the command line that runs one documentation subcommand."""
    if command == "build":
        # 本地构建多版本站点，只提交到本地 gh-pages 分支，不推送。
        return (*MIKE_DEPLOY_COMMAND, documentation_version(), "latest")
    if command == "deploy":
        # mike 在内容没有变化时不提交也不推送，--allow-empty 保证部署动作能到达远端。
        return (
            *MIKE_DEPLOY_COMMAND,
            "--push",
            "--allow-empty",
            "--remote",
            DOCUMENTATION_REMOTE,
            documentation_version(),
            "latest",
        )
    return DOCUMENTATION_COMMANDS[command]


def run(command):
    """Run one external command from the project root."""
    print("+", subprocess.list2cmdline([str(part) for part in command]), flush=True)
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def build_parser():
    parser = argparse.ArgumentParser(description="Build or preview the documentation.")
    commands = parser.add_subparsers(dest="command")

    commands.add_parser(
        "build",
        help="Build the current major.minor documentation locally",
    )
    commands.add_parser(
        "dev",
        help="Serve the current documentation with hot reload",
    )
    commands.add_parser(
        "deploy",
        help="Publish the current major.minor documentation and update latest",
    )
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return
    try:
        run(documentation_command(args.command))
    except KeyboardInterrupt:
        # 本地预览用 Ctrl+C 结束，不需要输出回溯。
        pass


if __name__ == "__main__":
    main()
