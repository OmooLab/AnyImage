from tests.support.paths import PROJECT_ROOT
import tomllib
import unittest

from tools.docs import documentation_command
from tools.docs import documentation_version


MKDOCS_FILE = PROJECT_ROOT / "mkdocs.yml"
DOCS_ROOT = PROJECT_ROOT / "docs"


def project_config():
    return tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )


class DocumentationContentTest(unittest.TestCase):
    def test_navigation_references_existing_markdown_files(self):
        referenced_files = []
        for line in MKDOCS_FILE.read_text(encoding="utf-8").splitlines():
            value = line.rsplit(":", 1)[-1].strip().removeprefix("- ").strip()
            if value.endswith(".md"):
                referenced_files.append(value)

        self.assertTrue(referenced_files)
        for relative_path in referenced_files:
            with self.subTest(relative_path=relative_path):
                self.assertTrue((DOCS_ROOT / relative_path).is_file())


class DocumentationCommandTest(unittest.TestCase):
    def test_documentation_version_omits_the_patch(self):
        project_version = project_config()["project"]["version"]
        major_minor = ".".join(project_version.split(".")[:2])

        self.assertEqual(
            documentation_version(),
            f"{major_minor}.x",
        )

    def test_build_writes_the_multi_version_site_locally(self):
        self.assertEqual(
            documentation_command("build"),
            ("mike", "deploy", "--update-aliases", documentation_version(), "latest"),
        )
        self.assertNotIn("--push", documentation_command("build"))

    def test_dev_serves_the_current_documentation_with_hot_reload(self):
        self.assertEqual(
            documentation_command("dev"),
            ("mkdocs", "serve"),
        )

    def test_deploy_publishes_the_version_series_as_latest(self):
        self.assertEqual(
            documentation_command("deploy"),
            (
                "mike",
                "deploy",
                "--update-aliases",
                "--push",
                "--allow-empty",
                "--remote",
                "omoolab",
                documentation_version(),
                "latest",
            ),
        )

    def test_project_exposes_the_docs_command(self):
        self.assertEqual(
            project_config()["project"]["scripts"]["docs"],
            "tools.docs:main",
        )


if __name__ == "__main__":
    unittest.main()
