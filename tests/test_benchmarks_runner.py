import tempfile
import unittest
from pathlib import Path

from benchmarks.runner import (
    build_rtk_replay_plan,
    parse_rewritten_command,
    run_benchmarks,
)
from benchmarks.scenarios import Scenario


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body)
    path.chmod(0o755)


class BenchmarkRunnerTests(unittest.TestCase):
    def _make_fake_rtk(self, tmpdir: str, *, rewritten: str) -> Path:
        fake_rtk = Path(tmpdir) / "rtk"
        _write_executable(
            fake_rtk,
            f"""#!/usr/bin/env python3
import sys

args = sys.argv[1:]
if args == ["--version"]:
    print("rtk 9.9.9")
    raise SystemExit(0)
if args[:1] == ["rewrite"]:
    print({rewritten!r})
    raise SystemExit(0)
raise SystemExit(1)
""",
        )
        return fake_rtk

    def test_parse_rewritten_command_replaces_rtk_binary(self):
        argv = parse_rewritten_command("rtk git status", rtk_bin="/tmp/custom-rtk")
        self.assertEqual(argv, ["/tmp/custom-rtk", "git", "status"])

    def test_build_rtk_replay_plan_creates_temp_file_for_read_commands(self):
        scenario = Scenario(
            category="system",
            name="cat_tailwind",
            command="cat tailwind.config.js",
            exit_code=0,
            filter_name="read",
            fixture_path=Path("tests/fixtures/system/cat_tailwind"),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            fake_rtk = self._make_fake_rtk(
                tmpdir, rewritten="rtk read tailwind.config.js"
            )
            plan = build_rtk_replay_plan(scenario, rtk_bin=str(fake_rtk))
            try:
                self.assertEqual(plan.benchmark_mode, "rewrite-file")
                self.assertTrue((plan.workdir / "tailwind.config.js").exists())
            finally:
                plan.cleanup()

    def test_build_rtk_replay_plan_creates_temp_tree_for_find(self):
        scenario = Scenario(
            category="files",
            name="find_results",
            command="find . -name '*.py'",
            exit_code=0,
            filter_name="find",
            fixture_path=Path("tests/fixtures/files/find_results"),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            fake_rtk = self._make_fake_rtk(tmpdir, rewritten="rtk find . -name '*.py'")
            plan = build_rtk_replay_plan(scenario, rtk_bin=str(fake_rtk))
            try:
                self.assertEqual(plan.benchmark_mode, "rewrite-tree")
                self.assertTrue((plan.workdir / "src" / "jobs" / "worker.py").exists())
            finally:
                plan.cleanup()

    def test_run_benchmarks_emits_v2_document_for_pytk_only(self):
        document = run_benchmarks(category="generic", iterations=1, engines=("pytk",))

        self.assertEqual(document["schema_version"], 2)
        self.assertEqual(document["engines"], ["pytk"])
        self.assertEqual(document["iterations"], 1)
        self.assertEqual(len(document["results"]), 2)
        self.assertTrue(all(row["engine"] == "pytk" for row in document["results"]))

    def test_run_benchmarks_can_execute_fake_rtk_with_stubbed_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_rtk = Path(tmpdir) / "rtk"
            _write_executable(
                fake_rtk,
                """#!/usr/bin/env python3
import os
import subprocess
import sys

args = sys.argv[1:]
if args == ["--version"]:
    print("rtk 9.9.9")
    raise SystemExit(0)
if args[:1] == ["rewrite"]:
    print("rtk echo test")
    raise SystemExit(0)
if args[:1] == ["echo"]:
    cmd = subprocess.run(["echo", *args[1:]], env=os.environ.copy(), check=False)
    raise SystemExit(cmd.returncode)
raise SystemExit(1)
""",
            )

            document = run_benchmarks(
                category="generic",
                iterations=1,
                engines=("rtk",),
                rtk_bin=str(fake_rtk),
            )

        self.assertEqual(document["schema_version"], 2)
        self.assertEqual(document["rtk_version"], "rtk 9.9.9")
        printf_row = next(
            row
            for row in document["results"]
            if row["command"].startswith("printf '\\033[31mERROR\\033[0m build failed")
        )
        self.assertEqual(printf_row["engine"], "rtk")
        self.assertEqual(printf_row["status"], "ok")
        self.assertEqual(printf_row["benchmark_mode"], "rewrite-stub")
