import tempfile
import unittest
from pathlib import Path

from pytk_ai.filters.system_tools import (
    render_env_output,
    render_json_output,
    render_log_output,
    render_smart_output,
    render_summary_output,
    summarize_dependency_directory,
    validate_json_extension,
)


class FiltersSystemToolsTests(unittest.TestCase):
    def test_validate_json_extension_rejects_toml(self):
        error = validate_json_extension("Cargo.toml")
        self.assertIsNotNone(error)
        self.assertIn("not a JSON file", error)
        self.assertIn("pytk-ai deps", error)

    def test_render_json_output_schema(self):
        output = render_json_output(
            '{"name":"demo","items":[{"id":1}],"url":"https://example.com"}',
            max_depth=3,
            schema_only=True,
        )
        self.assertIn("name: string", output)
        self.assertIn("items:", output)
        self.assertIn("url: url", output)

    def test_render_log_output_groups_repeated_errors(self):
        content = (
            "2024-01-01 10:00:00 ERROR: Connection failed to /api/server\n"
            "2024-01-01 10:00:01 ERROR: Connection failed to /api/server\n"
            "2024-01-01 10:00:02 WARN: Retrying connection\n"
        )
        output = render_log_output(content)
        self.assertIn("[error] 2 errors (1 unique)", output)
        self.assertIn("[x2]", output)
        self.assertIn("[WARNINGS]", output)

    def test_render_env_output_masks_sensitive_values(self):
        output = render_env_output(
            {
                "PATH": "/usr/bin:/bin:/usr/local/bin",
                "AWS_SECRET_ACCESS_KEY": "supersecretvalue",
                "PYTHONPATH": "/workspace",
            }
        )
        self.assertIn("PATH Variables:", output)
        self.assertIn("AWS_SECRET_ACCESS_KEY=su****ue", output)
        self.assertIn("PYTHONPATH=/workspace", output)

    def test_summarize_dependency_directory_collects_multiple_manifests(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "Cargo.toml").write_text(
                '[dependencies]\nserde = "1"\n[dev-dependencies]\ninsta = "1"\n',
                encoding="utf-8",
            )
            (root / "package.json").write_text(
                '{"name":"demo","version":"1.0.0","dependencies":{"react":"18.0.0"}}',
                encoding="utf-8",
            )
            raw, output = summarize_dependency_directory(root)
        self.assertIn("serde", raw)
        self.assertIn("Rust (Cargo.toml):", output)
        self.assertIn("Node.js (package.json):", output)

    def test_render_summary_output_detects_json(self):
        output = render_summary_output(
            "curl https://example.com", '{"items":[1,2]}', True
        )
        self.assertIn("[ok] Command: curl https://example.com", output)
        self.assertIn("JSON Output:", output)

    def test_render_smart_output_creates_two_line_summary(self):
        content = (
            "use anyhow::Result;\n"
            "pub struct Config { value: String }\n"
            "pub fn load_config() -> Result<Config> { todo!() }\n"
        )
        output = render_smart_output(content, "config.rs")
        lines = output.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn("Rust module", lines[0])
        self.assertIn("uses:", lines[1])
