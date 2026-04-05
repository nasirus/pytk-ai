import unittest

from pytk_ai.plan.scanner import scan_compound


class PlanScannerTests(unittest.TestCase):
    def test_scan_compound_splits_and_preserves_operators(self):
        segments, pipe = scan_compound("git status && pytest -q ; ls")
        self.assertEqual(
            segments,
            [("git status", "&&"), ("pytest -q", ";"), ("ls", None)],
        )
        self.assertIsNone(pipe)

    def test_scan_compound_ignores_operators_inside_quotes(self):
        segments, pipe = scan_compound("python -c \"print('a && b')\" && git status")
        self.assertEqual(
            segments,
            [("python -c \"print('a && b')\"", "&&"), ("git status", None)],
        )
        self.assertIsNone(pipe)

    def test_scan_compound_returns_pipe_remainder(self):
        segments, pipe = scan_compound("git log | head")
        self.assertEqual(segments, [("git log", "|")])
        self.assertEqual(pipe, "head")
