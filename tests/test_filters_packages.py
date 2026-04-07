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

    def test_uv_sync_short_circuits_checked_output(self):
        stderr = """Resolved 24 packages in 0.68ms
Checked 22 packages in 0.24ms
"""
        result = filter_output(
            "uv sync",
            "",
            stderr,
            0,
            plan=plan_command("uv sync"),
        )
        self.assertEqual(result.filter_name, "uv.sync")
        self.assertEqual(result.output, "uv sync: ok (up to date)")

    def test_uv_pip_install_strips_download_chatter(self):
        stdout = """  Downloading requests-2.31.0-py3-none-any.whl (62.6 kB)
  Using cached certifi-2023.11.17-py3-none-any.whl (162 kB)
  Preparing packages...
Installed 5 packages in 23ms
 + certifi==2023.11.17
 + charset-normalizer==3.3.2
 + idna==3.6
 + requests==2.31.0
 + urllib3==2.1.0
"""
        result = filter_output(
            "uv pip install requests",
            stdout,
            "",
            0,
            plan=plan_command("uv pip install requests"),
        )
        self.assertEqual(result.filter_name, "uv.pip-install")
        self.assertNotIn("Downloading", result.output)
        self.assertIn("Installed 5 packages in 23ms", result.output)
        self.assertIn("+ requests==2.31.0", result.output)

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

    def test_pnpm_outdated_summarizes_json_output(self):
        stdout = """{
  "react": {"current": "18.2.0", "wanted": "18.3.0", "latest": "19.0.0"},
  "zod": {"current": "3.23.8", "wanted": "3.23.8", "latest": "3.24.0"}
}"""
        result = filter_output(
            "pnpm outdated --format json",
            stdout,
            "",
            0,
            plan=plan_command("pnpm outdated --format json"),
        )
        self.assertEqual(result.filter_name, "pnpm.outdated")
        self.assertIn("pnpm outdated: 2 packages", result.output)
        self.assertIn("react: 18.2.0 -> 18.3.0 (latest 19.0.0)", result.output)

    def test_pnpm_install_keeps_summary_and_changes(self):
        stdout = """Progress: resolved 1, reused 0, downloaded 0, added 0
Packages: +2
dependencies:
+ react 18.2.0
+ zod 3.23.8

Done in 1.2s using pnpm v10.0.0
"""
        result = filter_output(
            "pnpm install",
            stdout,
            "",
            0,
            plan=plan_command("pnpm install"),
        )
        self.assertEqual(result.filter_name, "pnpm.install")
        self.assertNotIn("Progress:", result.output)
        self.assertIn("Packages: +2", result.output)
        self.assertIn("+ react 18.2.0", result.output)

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

    def test_bundle_update_routes_to_update_summary(self):
        stdout = """Fetching gem metadata from https://rubygems.org/.........
Resolving dependencies...
Using rake 13.1.0
Fetching rspec 3.14.0 (was 3.13.0)
Installing rspec 3.14.0 (was 3.13.0)
Bundle updated!
"""
        result = filter_output(
            "bundle update rspec",
            stdout,
            "",
            0,
            plan=plan_command("bundle update rspec"),
        )
        self.assertEqual(result.filter_name, "bundle.update")
        self.assertIn("bundle update: updated", result.output)

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

    def test_prisma_migrate_dev_summarizes_schema_changes(self):
        stdout = """Applying migration 20260128_add_sessions

CREATE TABLE \"Session\" (
  \"id\" TEXT NOT NULL,
  \"userId\" TEXT NOT NULL,
  FOREIGN KEY (\"userId\") REFERENCES \"User\"(\"id\")
);

CREATE INDEX \"session_status_idx\" ON \"Session\"(\"status\");

Your database is now in sync with your schema.
"""
        result = filter_output(
            "npx prisma migrate dev --name add_sessions",
            stdout,
            "",
            0,
            plan=plan_command("npx prisma migrate dev --name add_sessions"),
        )
        self.assertEqual(result.filter_name, "prisma.migrate-dev")
        self.assertIn("prisma migrate dev", result.output)
        self.assertIn("migration: 20260128_add_sessions", result.output)
        self.assertIn("changes: +1 tables", result.output)

    def test_prisma_migrate_status_summarizes_counts(self):
        stdout = """Database schema is up to date!
2 applied migrations found
1 pending migration found
Last common migration: 20260128_add_sessions
"""
        result = filter_output(
            "prisma migrate status",
            stdout,
            "",
            0,
            plan=plan_command("prisma migrate status"),
        )
        self.assertEqual(result.filter_name, "prisma.migrate-status")
        self.assertIn("prisma migrate status: 2 applied, 1 pending", result.output)
        self.assertIn("latest: 20260128_add_sessions", result.output)

    def test_prisma_migrate_deploy_summarizes_migration_count(self):
        stdout = """2 migrations found in prisma/migrations

Applying migration `20260128_add_sessions`
Applying migration `20260201_add_audit_log`

The following migration(s) have been applied:
"""
        result = filter_output(
            "pnpm prisma migrate deploy",
            stdout,
            "",
            0,
            plan=plan_command("pnpm prisma migrate deploy"),
        )
        self.assertEqual(result.filter_name, "prisma.migrate-deploy")
        self.assertEqual(result.output, "prisma migrate deploy: 2 migrations")

    def test_prisma_db_push_summarizes_counts(self):
        stdout = """Prisma schema loaded from prisma/schema.prisma
Your database is now in sync with your Prisma schema.

CREATE TABLE \"Post\" (
  \"id\" TEXT NOT NULL
);
ALTER TABLE \"User\" ADD COLUMN \"nickname\" TEXT;
CREATE INDEX \"post_author_idx\" ON \"Post\"(\"authorId\");
"""
        result = filter_output(
            "prisma db push",
            stdout,
            "",
            0,
            plan=plan_command("prisma db push"),
        )
        self.assertEqual(result.filter_name, "prisma.db-push")
        self.assertIn("prisma db push: schema pushed", result.output)
        self.assertIn("tables: 1, columns: 1, indexes: 1", result.output)

    def test_npm_run_strips_boilerplate(self):
        stdout = """> demo@1.0.0 build
> next build

npm WARN deprecated inflight@1.0.6: This module is not supported
npm notice New major version of npm available!

Creating an optimized production build...
Build completed
"""
        result = filter_output(
            "npm run build",
            stdout,
            "",
            0,
            plan=plan_command("npm run build"),
        )
        self.assertEqual(result.filter_name, "npm.run")
        self.assertNotIn("npm WARN", result.output)
        self.assertNotIn("demo@1.0.0", result.output)
        self.assertIn("Build completed", result.output)

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
