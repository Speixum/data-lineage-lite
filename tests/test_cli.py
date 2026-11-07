"""cli 测试：退出码、渲染输出、错误路径。"""

import contextlib
import io
import json
import os
import tempfile
import unittest

import lineage
from lineage import cli


def _save_run(tmp: str, name: str, path: str) -> None:
    with lineage.run(name) as current:
        @lineage.track("job")
        def job(rows):
            return rows

        job([{"a": 1}, {"a": None}])
    current.save(path)


class CliTests(unittest.TestCase):
    """命令行入口行为。"""

    def test_help_exits_zero(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                cli.main(["--help"])
        self.assertEqual(ctx.exception.code, 0)

    def test_no_subcommand_prints_help(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = cli.main([])
        self.assertEqual(code, 2)
        self.assertIn("usage:", buffer.getvalue())

    def test_render_mermaid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "run.json")
            _save_run(tmp, "demo", path)
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = cli.main(["render", path, "--format", "mermaid"])
            self.assertEqual(code, 0)
            self.assertIn("flowchart TD", buffer.getvalue())

    def test_diff_returns_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = os.path.join(tmp, "a.json")
            second = os.path.join(tmp, "b.json")
            _save_run(tmp, "a", first)
            _save_run(tmp, "b", second)
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = cli.main(["diff", first, second])
            self.assertEqual(code, 0)
            self.assertIn("summary: added=0", buffer.getvalue())

    def test_list_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _save_run(tmp, "one", os.path.join(tmp, "one.json"))
            _save_run(tmp, "two", os.path.join(tmp, "two.json"))
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = cli.main(["list", tmp, "--json"])
            self.assertEqual(code, 0)
            payload = json.loads(buffer.getvalue())
            self.assertEqual(sorted(item["name"] for item in payload), ["one", "two"])

    def test_missing_file_reports_error(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stderr(buffer):
            code = cli.main(["render", "no/such/file.json"])
        self.assertEqual(code, 1)
        self.assertIn("error:", buffer.getvalue())
        buffer.getvalue().encode("ascii")


if __name__ == "__main__":
    unittest.main()
