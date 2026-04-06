import unittest

from pytk_ai.filters import filter_output
from pytk_ai.plan import plan_command


class FiltersPsqlTests(unittest.TestCase):
    def test_psql_table_output_is_compacted(self):
        stdout = """ id | username    | email\n----+-------------+-------------------\n  1 | alice_smith | alice@example.com\n  2 | bob_jones   | bob@example.com\n(2 rows)\n"""
        result = filter_output(
            "psql -c 'select * from users'",
            stdout,
            "",
            0,
            plan=plan_command("psql -c 'select * from users'"),
        )
        self.assertEqual(result.filter_name, "psql")
        self.assertEqual(
            result.output,
            "id\tusername\temail\n1\talice_smith\talice@example.com\n2\tbob_jones\tbob@example.com",
        )

    def test_psql_expanded_output_is_compacted(self):
        stdout = """-[ RECORD 1 ]------\nid       | 1\nusername | alice_smith\nemail    | alice@example.com\n-[ RECORD 2 ]------\nid       | 2\nusername | bob_jones\nemail    | bob@example.com\n(2 rows)\n"""
        result = filter_output(
            "psql -x -c 'select * from users'",
            stdout,
            "",
            0,
            plan=plan_command("psql -x -c 'select * from users'"),
        )
        self.assertEqual(result.filter_name, "psql")
        self.assertEqual(
            result.output,
            "[1] id=1 username=alice_smith email=alice@example.com\n[2] id=2 username=bob_jones email=bob@example.com",
        )

    def test_psql_passthrough_keeps_non_table_output(self):
        result = filter_output(
            "psql -c 'copy users to stdout'",
            "COPY 5\n",
            "",
            0,
            plan=plan_command("psql -c 'copy users to stdout'"),
        )
        self.assertEqual(result.filter_name, "psql")
        self.assertEqual(result.output, "COPY 5")

    def test_psql_failures_keep_raw_output(self):
        stderr = 'ERROR:  relation "missing" does not exist\nLINE 1: select * from missing;\n'
        result = filter_output(
            "psql -c 'select * from missing'",
            "",
            stderr,
            1,
            plan=plan_command("psql -c 'select * from missing'"),
        )
        self.assertEqual(result.filter_name, "generic")
        self.assertIn('relation "missing" does not exist', result.output)
