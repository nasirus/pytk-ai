import unittest

from pytk_ai.filters import filter_output
from pytk_ai.plan import plan_command


class FiltersPackagesTests(unittest.TestCase):
    def test_pip_list_summarizes_table_output(self):
        stdout = """Package           Version
----------------- -------
certifi           2023.11.17
requests          2.31.0
urllib3           2.1.0
"""
        result = filter_output(
            "pip list",
            stdout,
            "",
            0,
            plan=plan_command("pip list"),
        )
        self.assertEqual(result.filter_name, "pip.list")
        self.assertIn("pip list: 3 packages", result.output)
        self.assertIn("certifi (2023.11.17)", result.output)

    def test_pip_outdated_summarizes_json_output(self):
        stdout = """[
  {"name": "requests", "version": "2.31.0", "latest_version": "2.32.0"},
  {"name": "pytest", "version": "7.4.0", "latest_version": "8.0.0"}
]"""
        result = filter_output(
            "uv pip list --outdated --format json",
            stdout,
            "",
            0,
            plan=plan_command("uv pip list --outdated --format json"),
        )
        self.assertEqual(result.filter_name, "pip.outdated")
        self.assertIn("pip outdated: 2 packages", result.output)
        self.assertIn("requests: 2.31.0 -> 2.32.0", result.output)

    def test_pip_list_freeze_output_falls_back_to_raw_output(self):
        stdout = """certifi==2023.11.17
requests==2.31.0
urllib3==2.1.0
"""
        result = filter_output(
            "pip list --format freeze",
            stdout,
            "",
            0,
            plan=plan_command("pip list --format freeze"),
        )
        self.assertEqual(result.filter_name, "pip.list")
        self.assertEqual(result.output, stdout.strip())

    def test_uv_sync_short_circuits_up_to_date(self):
        stdout = """Resolved 42 packages in 123ms
Audited 42 packages in 0.05ms
"""
        result = filter_output(
            "uv sync",
            stdout,
            "",
            0,
            plan=plan_command("uv sync"),
        )
        self.assertEqual(result.filter_name, "uv.sync")
        self.assertEqual(result.output, "uv sync: ok (up to date)")

    def test_npm_list_summarizes_dependency_tree(self):
        stdout = """demo@1.0.0 /repo
├── react@18.2.0
├── typescript@5.4.2
└── zod@3.23.8
"""
        result = filter_output(
            "npm list",
            stdout,
            "",
            0,
            plan=plan_command("npm list"),
        )
        self.assertEqual(result.filter_name, "npm.list")
        self.assertIn("npm list: 3 dependencies", result.output)
        self.assertIn("react (18.2.0)", result.output)

    def test_pnpm_list_summarizes_json_output(self):
        stdout = """{
  "name": "demo",
  "version": "1.0.0",
  "dependencies": {
    "react": {"version": "18.2.0"},
    "vitest": {"version": "2.1.0"}
  }
}"""
        result = filter_output(
            "pnpm list --json",
            stdout,
            "",
            0,
            plan=plan_command("pnpm list --json"),
        )
        self.assertEqual(result.filter_name, "pnpm.list")
        self.assertIn("pnpm list: 2 dependencies", result.output)
        self.assertIn("vitest (2.1.0)", result.output)

    def test_bundle_install_keeps_installed_gems_and_summary(self):
        stdout = """Fetching gem metadata from https://rubygems.org/.........
Resolving dependencies...
Using rake 13.1.0
Installing rspec 3.13.0
Installing simplecov 0.22.0
Bundle complete! 85 Gemfile dependencies, 202 gems now installed.
"""
        result = filter_output(
            "bundle install",
            stdout,
            "",
            0,
            plan=plan_command("bundle install"),
        )
        self.assertEqual(result.filter_name, "bundle.install")
        self.assertIn("bundle install: complete", result.output)
        self.assertIn("Installed gems: 2", result.output)
        self.assertIn("rspec 3.13.0", result.output)

    def test_prisma_generate_extracts_counts(self):
        stdout = """Prisma schema loaded from prisma/schema.prisma

✔ Generated Prisma Client (v5.12.0) to ./node_modules/@prisma/client in 120ms

Generated 14 models, 2 enums, 1 types for Prisma Client
"""
        result = filter_output(
            "npx prisma generate",
            stdout,
            "",
            0,
            plan=plan_command("npx prisma generate"),
        )
        self.assertEqual(result.filter_name, "prisma.generate")
        self.assertIn("prisma generate: client generated", result.output)
        self.assertIn("models: 14, enums: 2, types: 1", result.output)
        self.assertIn("output: @prisma/client", result.output)

    def test_package_manager_failures_keep_raw_output(self):
        stderr = """npm ERR! code ELSPROBLEMS
npm ERR! invalid: react@18.2.0 /repo/node_modules/react
"""
        result = filter_output(
            "npm list",
            "",
            stderr,
            1,
            plan=plan_command("npm list"),
        )
        self.assertEqual(result.filter_name, "npm.list")
        self.assertIn("ELSPROBLEMS", result.output)
        self.assertIn("invalid: react@18.2.0", result.output)
