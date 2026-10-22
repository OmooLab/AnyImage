from tests.support.paths import PROJECT_ROOT
import tomllib
import unittest

from tools.docs import documentation_command
from tools.docs import documentation_version


def project_config():
    return tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )


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
                "github",
                documentation_version(),
                "latest",
            ),
        )

if __name__ == "__main__":
    unittest.main()
