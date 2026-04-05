import unittest

try:
    from tests.helpers import load_fixture
except ImportError:
    from helpers import load_fixture
from pytk_ai.filters import filter_output
from pytk_ai.plan import plan_command


class FixturesPackagesTests(unittest.TestCase):
    def _run(self, name):
        f = load_fixture("packages", name)
        result = filter_output(
            f["command"],
            f["stdout"],
            f["stderr"],
            f["exit_code"],
            plan=plan_command(f["command"]),
        )
        return f, result

    def test_pip_list(self):
        f, result = self._run("pip_list")
        self.assertEqual(result.filter_name, "pip.list")
        self.assertIn("pip list: 3 packages", result.output)
        self.assertIn("certifi (2023.11.17)", result.output)

    def test_pip_outdated_json(self):
        f, result = self._run("pip_outdated_json")
        self.assertEqual(result.filter_name, "pip.outdated")
        self.assertIn("pip outdated: 2 packages", result.output)

    def test_uv_sync_ok(self):
        f, result = self._run("uv_sync_ok")
        self.assertEqual(result.filter_name, "uv.sync")
        self.assertEqual(result.output, "uv sync: ok (up to date)")

    def test_npm_list(self):
        f, result = self._run("npm_list")
        self.assertEqual(result.filter_name, "npm.list")
        self.assertIn("npm list: 3 dependencies", result.output)
        self.assertIn("react (18.2.0)", result.output)

    def test_npm_list_error(self):
        f, result = self._run("npm_list_error")
        self.assertEqual(result.filter_name, "npm.list")
        self.assertIn("ELSPROBLEMS", result.output)

    def test_pnpm_list_json(self):
        f, result = self._run("pnpm_list_json")
        self.assertEqual(result.filter_name, "pnpm.list")
        self.assertIn("pnpm list: 2 dependencies", result.output)

    def test_bundle_install(self):
        f, result = self._run("bundle_install")
        self.assertEqual(result.filter_name, "bundle.install")
        self.assertIn("bundle install: complete", result.output)
        self.assertIn("Installed gems: 2", result.output)

    def test_prisma_generate(self):
        f, result = self._run("prisma_generate")
        self.assertEqual(result.filter_name, "prisma.generate")
        self.assertIn("prisma generate: client generated", result.output)
        self.assertIn("models: 14", result.output)

    def test_success_fixtures_reduce_output(self):
        for name in ("pip_list", "bundle_install", "prisma_generate"):
            with self.subTest(name=name):
                f, result = self._run(name)
                self.assertLess(len(result.output), len(f["stdout"]))
