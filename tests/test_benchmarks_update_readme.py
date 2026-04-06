import unittest

from benchmarks.update_readme import format_benchmark_tables


class BenchmarkReadmeFormattingTests(unittest.TestCase):
    def test_format_benchmark_tables_includes_estimator_when_present(self):
        results = [
            {
                "category": "git",
                "name": "status_clean",
                "command": "git status",
                "filter_name": "git.status",
                "raw_tokens": 100,
                "filtered_tokens": 40,
                "saved_tokens": 60,
                "reduction_pct": 60.0,
                "token_estimator": "cl100k_base",
            }
        ]

        table = format_benchmark_tables(results)

        self.assertIn("Token estimator: `cl100k_base`", table)
