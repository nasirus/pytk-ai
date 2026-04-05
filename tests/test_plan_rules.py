import unittest

from pytk_ai.plan.rules import load_rules, match_rule, rule_filter_hint


class PlanRulesTests(unittest.TestCase):
    def test_load_rules_returns_data_from_json(self):
        rules = load_rules()
        self.assertGreater(len(rules), 0)
        self.assertTrue(any(rule.pytk_ai_cmd == "pytk-ai git" for rule in rules))

    def test_match_rule_finds_git_rule(self):
        rule = match_rule("git status")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.pytk_ai_cmd, "pytk-ai git")

    def test_rule_filter_hint_uses_pytk_ai_subcommand_name(self):
        rule = match_rule("pytest -q")
        self.assertIsNotNone(rule)
        self.assertEqual(rule_filter_hint(rule), "pytest")

    def test_match_rule_finds_generic_test_wrapper_rule(self):
        rule = match_rule("npm test")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.pytk_ai_cmd, "pytk-ai test")

    def test_match_rule_finds_cargo_test_rule_before_generic_cargo_rule(self):
        rule = match_rule("cargo test --lib")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.pytk_ai_cmd, "pytk-ai test")

    def test_match_rule_covers_file_commands(self):
        rule = match_rule("wc -l src/app.py")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.pytk_ai_cmd, "pytk-ai wc")

    def test_match_rule_covers_phase4_package_commands(self):
        rule = match_rule("uv sync")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.pytk_ai_cmd, "pytk-ai package")

        rule = match_rule("npx prisma generate")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.pytk_ai_cmd, "pytk-ai package")

    def test_match_rule_covers_phase5_infra_commands(self):
        rule = match_rule("docker ps")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.pytk_ai_cmd, "pytk-ai docker")

        rule = match_rule("kubectl get services")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.pytk_ai_cmd, "pytk-ai kubectl")

        rule = match_rule("aws ec2 describe-instances")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.pytk_ai_cmd, "pytk-ai aws")

        rule = match_rule("terraform validate")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.pytk_ai_cmd, "pytk-ai terraform")
