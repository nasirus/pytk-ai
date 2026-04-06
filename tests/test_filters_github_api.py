import json
import unittest

from pytk_ai.filters import filter_output
from pytk_ai.plan import plan_command


class FiltersGitHubApiTests(unittest.TestCase):
    def test_gh_pr_list_summarizes_json_output(self):
        stdout = """[{"number":128,"title":"Add GitHub filter","state":"OPEN","author":{"login":"mona"},"updatedAt":"2026-04-05T12:00:00Z"},{"number":127,"title":"Fix planner coverage","state":"MERGED","author":{"login":"hubot"},"updatedAt":"2026-04-04T12:00:00Z"}]"""
        result = filter_output(
            "gh pr list",
            stdout,
            "",
            0,
            plan=plan_command("gh pr list"),
        )
        self.assertEqual(result.filter_name, "gh.pr.list")
        self.assertEqual(
            result.output,
            "Pull Requests\n"
            "  [open] #128 Add GitHub filter (mona)\n"
            "  [merged] #127 Fix planner coverage (hubot)",
        )

    def test_gh_pr_view_summarizes_json_output(self):
        stdout = json.dumps(
            {
                "number": 128,
                "title": "[RFC] Add GitHub and API filters",
                "state": "OPEN",
                "author": {"login": "alice"},
                "body": '<!-- hidden -->\n[![CI](https://img.example/ci.svg)](https://example.com)\nImplements the remaining filters.\n\n```json\n{"keep":"value"}\n```\n',
                "url": "https://github.com/octo/repo/pull/128",
                "mergeable": "MERGEABLE",
                "reviews": {
                    "nodes": [
                        {"state": "APPROVED"},
                        {"state": "CHANGES_REQUESTED"},
                    ]
                },
                "statusCheckRollup": [
                    {"conclusion": "SUCCESS"},
                    {"state": "FAILURE"},
                ],
            }
        )
        result = filter_output(
            "gh pr view 128",
            stdout,
            "",
            0,
            plan=plan_command("gh pr view 128"),
        )
        self.assertEqual(result.filter_name, "gh.pr.view")
        self.assertIn("[open] PR #128: [RFC] Add GitHub and API filters", result.output)
        self.assertIn("alice", result.output)
        self.assertIn("OPEN | [ok]", result.output)
        self.assertIn("Reviews: 1 approved, 1 changes requested", result.output)
        self.assertIn("Checks: 1/2 passed", result.output)
        self.assertIn("[warn] 1 checks failed", result.output)
        self.assertIn("https://github.com/octo/repo/pull/128", result.output)
        self.assertIn("Implements the remaining filters.", result.output)
        self.assertIn("```json", result.output)
        self.assertNotIn("hidden", result.output)
        self.assertNotIn("[![CI]", result.output)

    def test_gh_issue_list_summarizes_json_output(self):
        stdout = """[{"number":91,"title":"Fix raw fallback","state":"OPEN","author":{"login":"mona"}},{"number":90,"title":"Tighten planner matching","state":"CLOSED","author":{"login":"hubot"}}]"""
        result = filter_output(
            "gh issue list",
            stdout,
            "",
            0,
            plan=plan_command("gh issue list"),
        )
        self.assertEqual(result.filter_name, "gh.issue.list")
        self.assertEqual(
            result.output,
            "Issues\n"
            "  [open] #91 Fix raw fallback\n"
            "  [closed] #90 Tighten planner matching",
        )

    def test_gh_run_list_summarizes_json_output(self):
        stdout = """[{"databaseId":987654321,"name":"CI","status":"completed","conclusion":"success","createdAt":"2026-04-05T12:00:00Z"},{"databaseId":987654320,"name":"Tests","status":"completed","conclusion":"failure","createdAt":"2026-04-05T11:00:00Z"}]"""
        result = filter_output(
            "gh run list",
            stdout,
            "",
            0,
            plan=plan_command("gh run list"),
        )
        self.assertEqual(result.filter_name, "gh.run.list")
        self.assertEqual(
            result.output,
            "Workflow Runs\n  [ok] CI [987654321]\n  [FAIL] Tests [987654320]",
        )

    def test_gh_pr_view_falls_back_to_text_summary_for_passthrough_modes(self):
        stdout = """[RFC] Add GitHub and API filters
Open
alice wants to merge 4 commits into main from phase-6
Reviewers: bob
Labels: enhancement
--
<!-- hidden -->
[![CI](https://img.example/ci.svg)](https://example.com)
Implements the remaining filters.

```json
{"keep":"value"}
```
"""
        result = filter_output(
            "gh pr view 128 --comments",
            stdout,
            "",
            0,
            plan=plan_command("gh pr view 128 --comments"),
        )
        self.assertEqual(result.filter_name, "gh.pr.view")
        self.assertIn("gh pr view: [RFC] Add GitHub and API filters", result.output)
        self.assertIn("Reviewers: bob", result.output)
        self.assertNotIn("hidden", result.output)

    def test_gh_repo_view_summarizes_json_output(self):
        stdout = """{"name":"ptk","owner":{"login":"nasirus"},"description":"Compact command output for LLM workflows","url":"https://github.com/nasirus/ptk","stargazerCount":42,"forkCount":7,"isPrivate":false}"""
        result = filter_output(
            "gh repo view",
            stdout,
            "",
            0,
            plan=plan_command("gh repo view"),
        )
        self.assertEqual(result.filter_name, "gh.repo.view")
        self.assertIn("gh repo view: nasirus/ptk", result.output)
        self.assertIn("public | 42 stars | 7 forks", result.output)
        self.assertIn("Compact command output for LLM workflows", result.output)

    def test_gh_api_preserves_response_body(self):
        stdout = '{"total_count":2,"items":[{"id":1},{"id":2}]}'
        result = filter_output(
            "gh api repos/nasirus/ptk/issues",
            stdout,
            "",
            0,
            plan=plan_command("gh api repos/nasirus/ptk/issues"),
        )
        self.assertEqual(result.filter_name, "gh.api")
        self.assertEqual(result.output, stdout)

    def test_curl_summarizes_large_json_as_schema(self):
        stdout = """{"name":"A very long user name here","count":42,"items":[{"id":1,"active":true}],"description":"A long description that would be noisier than the schema view"}"""
        result = filter_output(
            "curl https://api.example.com/users/1",
            stdout,
            "",
            0,
            plan=plan_command("curl https://api.example.com/users/1"),
        )
        self.assertEqual(result.filter_name, "curl")
        self.assertIn("name: string", result.output)
        self.assertIn("count: int", result.output)
        self.assertIn("[len=1]", result.output)

    def test_wget_success_strips_progress_noise(self):
        stderr = """--2026-04-05 12:00:00--  https://example.com/file.tar.gz
Resolving example.com (example.com)... 93.184.216.34
Saving to: 'file.tar.gz'

file.tar.gz         100%[===================>]   1.00K  --.-KB/s    in 0s

2026-04-05 12:00:00 (10.0 MB/s) - 'file.tar.gz' saved [1024/1024]
"""
        result = filter_output(
            "wget https://example.com/file.tar.gz",
            "",
            stderr,
            0,
            plan=plan_command("wget https://example.com/file.tar.gz"),
        )
        self.assertEqual(result.filter_name, "wget")
        self.assertEqual(
            result.output, "example.com/file.tar.gz ok | file.tar.gz | 1.0KB"
        )

    def test_wget_output_document_equals_uses_requested_filename(self):
        result = filter_output(
            "wget --output-document=result.txt https://example.com/data",
            "",
            "",
            0,
            plan=plan_command(
                "wget --output-document=result.txt https://example.com/data"
            ),
        )
        self.assertEqual(result.filter_name, "wget")
        self.assertEqual(result.output, "example.com/data ok | result.txt | ?")

    def test_curl_download_mode_preserves_success_output(self):
        stderr = (
            "100  1024  100  1024    0     0   2048      0 "
            "--:--:-- --:--:-- --:--:--  2048\n"
        )
        result = filter_output(
            "curl -O https://example.com/file.tar.gz",
            "",
            stderr,
            0,
            plan=plan_command("curl -O https://example.com/file.tar.gz"),
        )
        self.assertEqual(result.filter_name, "curl")
        self.assertIn("100  1024", result.output)

    def test_phase6_failures_preserve_actionable_output(self):
        stderr = "HTTP 404: Not Found\n"
        result = filter_output(
            "gh pr view 999",
            "",
            stderr,
            1,
            plan=plan_command("gh pr view 999"),
        )
        self.assertEqual(result.filter_name, "gh.pr.view")
        self.assertIn("HTTP 404: Not Found", result.output)

        html = "<html><title>404</title><body>missing</body></html>\n"
        result = filter_output(
            "curl https://api.example.com/missing",
            html,
            "",
            22,
            plan=plan_command("curl https://api.example.com/missing"),
        )
        self.assertEqual(result.filter_name, "curl")
        self.assertIn("<html>", result.output)

    def test_gh_generic_command_keeps_raw_output(self):
        stdout = "Logged in to github.com as nasirus\n"
        result = filter_output(
            "gh auth status",
            stdout,
            "",
            0,
            plan=plan_command("gh auth status"),
        )
        self.assertEqual(result.filter_name, "gh")
        self.assertEqual(result.output, stdout.rstrip())
