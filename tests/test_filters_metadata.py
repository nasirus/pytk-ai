import importlib.util
import sys
import unittest
from unittest import mock

from pytk_ai.filters import filter_output
from pytk_ai.filters import base as filters_base
from pytk_ai.plan import plan_command
from pytk_ai.runner import run_command


class FilterMetadataTests(unittest.TestCase):
    def test_filter_output_attaches_metrics_and_policy(self):
        result = filter_output(
            "git add src/app.py",
            "",
            "",
            0,
            plan=plan_command("git add src/app.py"),
        )
        self.assertEqual(result.filter_name, "git.add")
        self.assertIsNotNone(result.metrics)
        self.assertIsNotNone(result.policy)
        self.assertEqual(result.policy.summary_scope, "success-only")
        self.assertEqual(result.policy.usage_mode_behavior, "same-output")
        self.assertEqual(result.metrics.usage_mode, "interactive")
        self.assertEqual(result.metrics.raw.tokens, 0)
        self.assertGreaterEqual(result.metrics.filtered.tokens, 1)
        self.assertLessEqual(result.metrics.saved_tokens, 0)

    def test_filter_output_preserves_failure_stream_order_in_metrics(self):
        result = filter_output(
            "cargo test",
            "stdout detail\n",
            "stderr detail\n",
            101,
            plan=plan_command("cargo test"),
        )
        self.assertIsNotNone(result.metrics)
        self.assertEqual(result.metrics.raw.lines, 2)
        self.assertGreaterEqual(
            result.metrics.raw.tokens, result.metrics.filtered.tokens
        )

    def test_run_command_records_usage_mode_in_result(self):
        result = run_command(
            f"{sys.executable} -c \"print('hello')\"",
            usage_mode="hook",
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIsNotNone(result.filter_metrics)
        self.assertEqual(result.filter_metrics.usage_mode, "hook")
        self.assertIsNotNone(result.filter_policy)
        self.assertEqual(result.filter_policy.usage_mode_behavior, "same-output")

    def test_build_filter_policy_is_both(self):
        result = filter_output(
            "cargo build",
            "Compiling app v0.1.0 (/tmp/app)\nFinished dev [unoptimized + debuginfo] target(s) in 1.23s\n",
            "",
            0,
            plan=plan_command("cargo build"),
        )
        self.assertEqual(result.filter_name, "cargo.build")
        self.assertIsNotNone(result.policy)
        self.assertEqual(result.policy.summary_scope, "both")

    def test_token_estimator_label_matches_available_backend(self):
        filters_base._load_token_encoder.cache_clear()
        self.addCleanup(filters_base._load_token_encoder.cache_clear)
        expected = (
            "cl100k_base"
            if importlib.util.find_spec("tiktoken") is not None
            else "chars/4-estimate"
        )
        self.assertEqual(filters_base.token_estimator_label(), expected)

    def test_estimate_tokens_falls_back_without_tiktoken(self):
        filters_base._load_token_encoder.cache_clear()
        self.addCleanup(filters_base._load_token_encoder.cache_clear)
        with mock.patch(
            "builtins.__import__", side_effect=ImportError("tiktoken unavailable")
        ):
            self.assertEqual(filters_base.token_estimator_label(), "chars/4-estimate")
            self.assertEqual(filters_base.estimate_tokens("abcd"), 1)
            self.assertEqual(filters_base.estimate_tokens("abcdefgh"), 2)
