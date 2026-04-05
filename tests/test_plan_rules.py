import unittest

from ptk.plan.rules import load_rules, match_rule, rule_filter_hint


class PlanRulesTests(unittest.TestCase):
    def test_load_rules_returns_data_from_json(self):
        rules = load_rules()
        self.assertGreater(len(rules), 0)
        self.assertEqual(rules[0].ptk_cmd, "ptk git")

    def test_match_rule_finds_git_rule(self):
        rule = match_rule("git status")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.ptk_cmd, "ptk git")

    def test_rule_filter_hint_uses_ptk_subcommand_name(self):
        rule = match_rule("pytest -q")
        self.assertIsNotNone(rule)
        self.assertEqual(rule_filter_hint(rule), "pytest")
