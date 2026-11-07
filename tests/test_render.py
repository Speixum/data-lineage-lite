"""render 测试：mermaid、dot、ASCII 文本树的结构。"""

import unittest

from lineage.render import FAILED_FILL, render, to_dot, to_mermaid, to_tree

RUN = {
    "schema": "dataset-lineage/1.0",
    "run_id": "demo-20261108T000000Z",
    "name": "demo",
    "status": "failed",
    "nodes": [
        {
            "id": "demo/a#01",
            "step": "a",
            "seq": 1,
            "status": "ok",
            "duration_ms": 1.0,
            "outputs": [
                {
                    "ref": "<return>",
                    "kind": "table",
                    "hash": "sha256:aa",
                    "fingerprint": {"rows": 2, "cols": 1, "null_ratio": 0.0},
                }
            ],
        },
        {
            "id": "demo/b#02",
            "step": "b",
            "seq": 2,
            "status": "failed",
            "duration_ms": 2.0,
            "outputs": [],
            "error": {"type": "ValueError", "message": "boom", "traceback": []},
        },
    ],
    "edges": [{"from": "demo/a#01", "to": "demo/b#02", "label": "table"}],
}


class MermaidTests(unittest.TestCase):
    """mermaid flowchart 结构。"""

    def test_header_and_nodes(self) -> None:
        text = to_mermaid(RUN)
        self.assertTrue(text.startswith("flowchart TD"))
        self.assertIn('n00["a <br/> ok <br/> 1.0ms"]', text)
        self.assertIn('n01["b <br/> FAILED <br/> 2.0ms"]', text)

    def test_edges_and_failed_class(self) -> None:
        text = to_mermaid(RUN)
        self.assertIn("n00 -->|table| n01", text)
        self.assertIn(f"classDef failed fill:{FAILED_FILL}", text)
        self.assertIn("class n01 failed", text)
        self.assertNotIn("class n00 failed", text)

    def test_render_dispatches(self) -> None:
        self.assertEqual(render(RUN, "mermaid"), to_mermaid(RUN))
        with self.assertRaises(ValueError):
            render(RUN, "svg")


class DotTests(unittest.TestCase):
    """graphviz dot 输出。"""

    def test_structure(self) -> None:
        text = to_dot(RUN)
        self.assertTrue(text.startswith('digraph "demo" {'))
        self.assertIn(f'fillcolor="{FAILED_FILL}"', text)
        self.assertIn('n00 -> n01 [label="table"];', text)
        self.assertTrue(text.rstrip().endswith("}"))


class TreeTests(unittest.TestCase):
    """纯 ASCII 文本树。"""

    def test_ascii_only(self) -> None:
        text = to_tree(RUN)
        text.encode("ascii")

    def test_branches_and_outputs(self) -> None:
        text = to_tree(RUN)
        self.assertIn("demo [failed] nodes=2 edges=1", text)
        self.assertIn("+-- 01 a [ok] (1.0 ms)", text)
        self.assertIn("+-- 02 b [FAILED] (2.0 ms)", text)
        self.assertIn("|-- <return> table sha256:aa rows=2 cols=1 null_ratio=0.0", text)
        self.assertIn("|-- ! ValueError: boom", text)


if __name__ == "__main__":
    unittest.main()
