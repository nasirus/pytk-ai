import unittest

from pytk_ai.filters import filter_output
from pytk_ai.filters.generic import filter_generic_output
from pytk_ai.filters.toml_fallback import apply_builtin_fallback
from pytk_ai.plan import plan_command


class FiltersGenericTests(unittest.TestCase):
    def test_generic_filter_removes_ansi_and_truncates(self):
        result = filter_generic_output(
            "echo test",
            "\x1b[31mred\x1b[0m\n1\n2\n3\n4",
            "",
            0,
            max_output_lines=3,
        )
        self.assertEqual(result.filter_name, "generic")
        self.assertNotIn("\x1b", result.output)
        self.assertIn("more lines omitted", result.output)

    def test_filter_output_uses_plan_hint_first(self):
        plan = plan_command("git status")
        result = filter_output(
            "git status",
            'On branch main\n  (use "git add" to track)\n',
            "",
            0,
            plan=plan,
        )
        self.assertEqual(result.filter_name, "git.status")
        self.assertNotIn('(use "git add"', result.output)

    def test_filter_output_falls_back_when_specific_filter_raises(self):
        plan = plan_command("git status")
        import pytk_ai.filters as filters_module

        original = filters_module._FILTERS["git"]
        try:

            def boom(*args, **kwargs):
                raise RuntimeError("boom")

            filters_module._FILTERS["git"] = boom
            result = filter_output("git status", "ok", "", 0, plan=plan)
        finally:
            filters_module._FILTERS["git"] = original

        self.assertEqual(result.filter_name, "generic")
        self.assertIn("filter failed", result.error)

    def test_filter_output_uses_builtin_toml_fallback_for_unknown_command(self):
        result = filter_output(
            "make all",
            "make[1]: Entering directory '/home/user'\ngcc -O2 foo.c\nmake[1]: Leaving directory '/home/user'\n",
            "",
            0,
        )
        self.assertEqual(result.filter_name, "toml.make")
        self.assertEqual(result.output, "gcc -O2 foo.c")

    def test_builtin_toml_fallback_applies_match_output_unless(self):
        fallback = apply_builtin_fallback(
            "rsync -av src/ dest/",
            "rsync: [sender] error\nerror in rsync protocol data stream (code 12)\nsent 100 bytes  received 200 bytes  60.00 bytes/sec\ntotal size is 1000  speedup is 3.33\n",
        )
        self.assertIsNotNone(fallback)
        self.assertEqual(fallback[0], "toml.rsync")
        self.assertEqual(
            fallback[1],
            "rsync: [sender] error\nerror in rsync protocol data stream (code 12)\ntotal size is 1000  speedup is 3.33",
        )

    def test_builtin_toml_fallback_applies_keep_lines_stage(self):
        fallback = apply_builtin_fallback(
            "java -jar app.jar",
            "2024-01-01 INFO Initializing Spring\n2024-01-01 INFO Tomcat started on port 8080\n2024-01-01 INFO Started MyApp in 3.2 seconds\n",
        )
        self.assertIsNotNone(fallback)
        self.assertEqual(fallback[0], "toml.spring-boot")
        self.assertEqual(
            fallback[1],
            "2024-01-01 INFO Tomcat started on port 8080\n2024-01-01 INFO Started MyApp in 3.2 seconds",
        )

    def test_builtin_toml_fallback_applies_truncate_and_line_cap(self):
        fallback = apply_builtin_fallback(
            "df -h",
            "Filesystem     1K-blocks   Used Available Use% Mounted on\n"
            + "x" * 100
            + "\n"
            + "\n".join(f"/dev/sd{i} 1 2 3 4% /mnt/{i}" for i in range(25)),
        )
        self.assertIsNotNone(fallback)
        self.assertEqual(fallback[0], "toml.df")
        self.assertIn("...", fallback[1].splitlines()[1])
        self.assertEqual(fallback[1].splitlines()[-1], "... (7 lines truncated)")

    def test_filter_output_uses_builtin_toml_fallback_for_df(self):
        result = filter_output(
            "df -h",
            "Filesystem     1K-blocks   Used Available Use% Mounted on\n" + "x" * 100,
            "",
            0,
        )
        self.assertEqual(result.filter_name, "toml.df")
        self.assertEqual(
            result.output,
            "Filesystem     1K-blocks   Used Available Use% Mounted on\n"
            + "x" * 77
            + "...",
        )

    def test_filter_output_uses_builtin_toml_fallback_for_du(self):
        result = filter_output(
            "du -sh .",
            "4.0K\t./src\n\n8.0K\t./tests\n16K\t.\n",
            "",
            0,
        )
        self.assertEqual(result.filter_name, "toml.du")
        self.assertEqual(result.output, "4.0K\t./src\n8.0K\t./tests\n16K\t.")

    def test_filter_output_uses_builtin_toml_fallback_for_ping(self):
        result = filter_output(
            "ping example.com",
            "PING example.com (93.184.216.34): 56 data bytes\n"
            "64 bytes from 93.184.216.34: icmp_seq=0 ttl=56 time=14.2 ms\n"
            "64 bytes from 93.184.216.34: icmp_seq=1 ttl=56 time=13.8 ms\n"
            "\n"
            "--- example.com ping statistics ---\n"
            "2 packets transmitted, 2 packets received, 0.0% packet loss\n"
            "round-trip min/avg/max/stddev = 13.8/14.0/14.2/0.2 ms\n",
            "",
            0,
        )
        self.assertEqual(result.filter_name, "toml.ping")
        self.assertEqual(
            result.output,
            "--- example.com ping statistics ---\n"
            "2 packets transmitted, 2 packets received, 0.0% packet loss\n"
            "round-trip min/avg/max/stddev = 13.8/14.0/14.2/0.2 ms",
        )

    def test_filter_output_uses_builtin_toml_fallback_for_ps(self):
        result = filter_output(
            "ps aux",
            "USER   PID %CPU %MEM COMMAND\n" + "u 1 0.0 0.0 " + "x" * 130,
            "",
            0,
        )
        self.assertEqual(result.filter_name, "toml.ps")
        self.assertEqual(
            result.output,
            "USER   PID %CPU %MEM COMMAND\nu 1 0.0 0.0 " + "x" * 105 + "...",
        )
