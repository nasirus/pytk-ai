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
        self.assertIn("pip list: 28 packages", result.output)
        self.assertIn("Pygments (2.20.0)", result.output)
        self.assertIn("httpx (0.27.0)", result.output)
        self.assertIn("... +16 more packages", result.output)

    def test_pip_outdated_json(self):
        f, result = self._run("pip_outdated_json")
        self.assertEqual(result.filter_name, "pip.outdated")
        self.assertIn("pip outdated: 28 packages", result.output)
        self.assertIn("httpx: 0.24.1 -> 0.28.1", result.output)
        self.assertIn("pydantic: 2.0.3 -> 2.12.5", result.output)
        self.assertIn("... +13 more packages", result.output)

    def test_uv_sync_ok(self):
        f, result = self._run("uv_sync_ok")
        self.assertEqual(result.filter_name, "uv.sync")
        self.assertIn("Installed 22 packages in 14ms", result.output)
        self.assertIn("+ anyio==4.13.0", result.output)
        self.assertIn("+ httpx==0.27.0", result.output)
        self.assertIn("... +10 more packages", result.output)

    def test_npm_list(self):
        f, result = self._run("npm_list")
        self.assertEqual(result.filter_name, "npm.list")
        self.assertIn("npm list: 15 dependencies", result.output)
        self.assertIn("@testing-library/react (14.1.2)", result.output)
        self.assertIn("react (18.2.0)", result.output)
        self.assertIn("... +3 more dependencies", result.output)

    def test_npm_list_error(self):
        f, result = self._run("npm_list_error")
        self.assertEqual(result.filter_name, "npm.list")
        self.assertIn("ELSPROBLEMS", result.output)
        self.assertIn("UNMET DEPENDENCY react@18.2.0", result.output)
        self.assertIn("npm error missing: react@18.2.0", result.output)

    def test_pnpm_list_json(self):
        f, result = self._run("pnpm_list_json")
        self.assertEqual(result.filter_name, "pnpm.list")
        self.assertIn("pnpm list: 15 dependencies", result.output)
        self.assertIn("@testing-library/react (14.1.2)", result.output)
        self.assertIn("react (18.2.0)", result.output)
        self.assertIn("... +3 more dependencies", result.output)

    def test_bundle_install(self):
        f, result = self._run("bundle_install")
        self.assertEqual(result.filter_name, "bundle.install")
        self.assertIn("bundle install: complete", result.output)
        self.assertIn("Installed gems: 2", result.output)

    def test_prisma_generate(self):
        f, result = self._run("prisma_generate")
        self.assertEqual(result.filter_name, "prisma.generate")
        self.assertIn("prisma generate: client generated", result.output)
        self.assertIn("output: @prisma/client", result.output)

    def test_success_fixtures_reduce_output(self):
        for name in (
            "pip_list",
            "bundle_install",
            "prisma_generate",
            "npm_list",
            "uv_sync_ok",
        ):
            with self.subTest(name=name):
                f, result = self._run(name)
                raw = f["stdout"] or f["stderr"]
                self.assertLess(len(result.output), len(raw))
