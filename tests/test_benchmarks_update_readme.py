import json
import tempfile
import unittest
from pathlib import Path

from benchmarks.update_readme import format_benchmark_tables, load_results_document


class BenchmarkReadmeFormattingTests(unittest.TestCase):
    def test_load_results_document_rejects_non_v2_input(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "legacy.json"
            path.write_text(json.dumps([{"category": "git"}]))

            with self.assertRaisesRegex(ValueError, "JSON object"):
                load_results_document(path)

    def test_format_benchmark_tables_renders_side_by_side_comparison(self):
        document = {
            "schema_version": 2,
            "token_estimator": "cl100k_base",
            "rtk_version": "rtk 0.35.0",
            "results": [
                {
                    "engine": "pytk",
                    "status": "ok",
                    "benchmark_mode": "fixture",
                    "category": "git",
                    "name": "status_dirty",
                    "command": "git status",
                    "rewritten_command": "pytk-ai git status",
                    "filter_name": "git.status",
                    "raw_tokens": 100,
                    "filtered_tokens": 30,
                    "saved_tokens": 70,
                    "reduction_pct": 70.0,
                },
                {
                    "engine": "rtk",
                    "status": "ok",
                    "benchmark_mode": "rewrite-stub",
                    "category": "git",
                    "name": "status_dirty",
                    "command": "git status",
                    "rewritten_command": "rtk git status",
                    "filter_name": "rtk",
                    "raw_tokens": 100,
                    "filtered_tokens": 20,
                    "saved_tokens": 80,
                    "reduction_pct": 80.0,
                },
                {
                    "engine": "pytk",
                    "status": "ok",
                    "benchmark_mode": "fixture",
                    "category": "infra",
                    "name": "docker_compose_ps",
                    "command": "docker compose ps",
                    "rewritten_command": "pytk-ai docker compose ps",
                    "filter_name": "docker.compose.ps",
                    "raw_tokens": 60,
                    "filtered_tokens": 30,
                    "saved_tokens": 30,
                    "reduction_pct": 50.0,
                },
                {
                    "engine": "rtk",
                    "status": "unsupported",
                    "benchmark_mode": "unsupported",
                    "category": "infra",
                    "name": "docker_compose_ps",
                    "command": "docker compose ps",
                    "rewritten_command": "rtk docker compose ps",
                    "filter_name": "rtk",
                    "raw_tokens": 60,
                    "filtered_tokens": None,
                    "saved_tokens": None,
                    "reduction_pct": None,
                },
            ],
        }

        table = format_benchmark_tables(document)

        self.assertIn("Token estimator: `cl100k_base`", table)
        self.assertIn("Compared against `rtk 0.35.0`", table)
        self.assertIn("#### Scenario Comparison (Top 25)", table)
        self.assertIn("| git | 1 | 100 | 30 | 70.0% | 1/1 | 20 | 80.0% |", table)
        self.assertIn("| infra | 1 | 60 | 30 | 50.0% | 0/1 | 0 | 0.0% |", table)
        self.assertIn(
            "| git/status_dirty | `git status` | 100 | 30 | 70.0% | 20 | 80.0% | RTK +10.0pp |",
            table,
        )
