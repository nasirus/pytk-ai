import unittest

from pytk_ai.filters import filter_output
from pytk_ai.plan import plan_command


class FiltersGitHubApiTests(unittest.TestCase):
    def test_gh_pr_list_summarizes_default_table(self):
        stdout = """Showing 2 of 2 open pull requests in octo/repo
#128 Add GitHub filter\tfeature/gh\tabout 2 hours ago
#127 Fix planner coverage\tmain\tabout 1 day ago
"""
        result = filter_output(
            "gh pr list",
            stdout,
            "",
            0,
            plan=plan_command("gh pr list"),
        )
        self.assertEqual(result.filter_name, "gh.pr.list")
        self.assertIn("gh pr list: 2 pull requests", result.output)
        self.assertIn("#128 | Add GitHub filter", result.output)
        self.assertNotIn("Showing 2 of 2", result.output)

    def test_gh_pr_view_filters_markdown_noise(self):
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
            "gh pr view 128",
            stdout,
            "",
            0,
            plan=plan_command("gh pr view 128"),
        )
        self.assertEqual(result.filter_name, "gh.pr.view")
        self.assertIn("gh pr view: [RFC] Add GitHub and API filters", result.output)
        self.assertIn("Reviewers: bob", result.output)
        self.assertIn("Implements the remaining filters.", result.output)
        self.assertIn("```json", result.output)
        self.assertNotIn("hidden", result.output)
        self.assertNotIn("[![CI]", result.output)

    def test_gh_issue_list_summarizes_default_table(self):
        stdout = """Showing 2 of 2 open issues in octo/repo
#91 Fix raw fallback\tbug\tabout 1 hour ago
#90 Tighten planner matching\tenhancement\tabout 1 day ago
"""
        result = filter_output(
            "gh issue list",
            stdout,
            "",
            0,
            plan=plan_command("gh issue list"),
        )
        self.assertEqual(result.filter_name, "gh.issue.list")
        self.assertIn("gh issue list: 2 issues", result.output)
        self.assertIn("#91 | Fix raw fallback", result.output)

    def test_gh_run_list_summarizes_default_table(self):
        stdout = """STATUS  TITLE               WORKFLOW   BRANCH  EVENT  ID          ELAPSED  AGE
completed  success  CI      main    push    987654321   2m10s    about 1 hour ago
completed  failure  Tests   phase6  pull_request  987654320  4m20s  about 2 hours ago
"""
        result = filter_output(
            "gh run list",
            stdout,
            "",
            0,
            plan=plan_command("gh run list"),
        )
        self.assertEqual(result.filter_name, "gh.run.list")
        self.assertIn("gh run list: 2 runs", result.output)
        self.assertIn("completed | success | CI", result.output)
        self.assertNotIn("STATUS  TITLE", result.output)

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
