"""diff 测试：节点匹配、哈希变化、参数变化、质量漂移。"""

import unittest

from lineage.diff import diff_runs, format_text


def _node(step, seq, hash_value, rows=10, null_ratio=0.0, params=None, status="ok"):
    return {
        "id": f"demo/{step}#{seq:02d}",
        "step": step,
        "seq": seq,
        "status": status,
        "duration_ms": 1.0,
        "params": params or {},
        "inputs": [],
        "outputs": [
            {
                "ref": "<return>",
                "kind": "table",
                "hash": hash_value,
                "bytes": None,
                "fingerprint": {
                    "rows": rows,
                    "cols": 2,
                    "columns": ["a", "b"],
                    "null_ratio": null_ratio,
                    "dup_rows": 0,
                    "types": {"a": "int", "b": "str"},
                },
            }
        ],
        "error": None,
        "unstable": False,
    }


def _run(name, nodes, status="ok"):
    return {
        "schema": "dataset-lineage/1.0",
        "run_id": f"{name}-20261108T000000Z",
        "name": name,
        "status": status,
        "nodes": nodes,
        "edges": [],
    }


class DiffTests(unittest.TestCase):
    """两次 run 的节点级比较。"""

    def test_identical_runs(self) -> None:
        before = _run("a", [_node("load", 1, "sha256:aa"), _node("clean", 2, "sha256:bb")])
        after = _run("b", [_node("load", 1, "sha256:aa"), _node("clean", 2, "sha256:bb")])
        result = diff_runs(before, after)
        self.assertTrue(result["summary"]["identical"])
        self.assertEqual(result["summary"]["changed"], 0)
        self.assertEqual(result["summary"]["unchanged"], 2)

    def test_hash_change_is_detected(self) -> None:
        before = _run("a", [_node("clean", 1, "sha256:aa")])
        after = _run("b", [_node("clean", 1, "sha256:bb")])
        result = diff_runs(before, after)
        self.assertEqual(result["summary"]["changed"], 1)
        changed = result["changed"][0]
        self.assertEqual(changed["step"], "clean")
        self.assertTrue(changed["outputs"][0]["hash_changed"])
        self.assertEqual(changed["outputs"][0]["hash_before"], "sha256:aa")
        self.assertEqual(changed["outputs"][0]["hash_after"], "sha256:bb")

    def test_params_change_is_detected(self) -> None:
        before = _run("a", [_node("clean", 1, "sha256:aa", params={"fill": "median"})])
        after = _run("b", [_node("clean", 1, "sha256:aa", params={"fill": "zero"})])
        changed = diff_runs(before, after)["changed"][0]
        self.assertTrue(changed["params_changed"])
        self.assertEqual(changed["outputs"], [])

    def test_added_and_removed_nodes(self) -> None:
        before = _run("a", [_node("load", 1, "sha256:aa"), _node("clean", 2, "sha256:bb")])
        after = _run("b", [_node("clean", 1, "sha256:bb"), _node("publish", 2, "sha256:cc")])
        result = diff_runs(before, after)
        self.assertEqual([item["step"] for item in result["added"]], ["publish"])
        self.assertEqual([item["step"] for item in result["removed"]], ["load"])
        self.assertEqual(result["summary"]["added"], 1)
        self.assertEqual(result["summary"]["removed"], 1)

    def test_quality_drift(self) -> None:
        before = _run("a", [_node("clean", 1, "sha256:aa", rows=10, null_ratio=0.0)])
        after = _run("b", [_node("clean", 1, "sha256:bb", rows=12, null_ratio=0.05)])
        result = diff_runs(before, after)
        self.assertEqual(result["summary"]["quality_drift"], 1)
        drift = result["changed"][0]["outputs"][0]["drift"]
        self.assertTrue(drift["has_drift"])
        self.assertEqual(drift["rows"], [10, 12])
        self.assertEqual(drift["rows_delta"], 2)
        self.assertEqual(drift["null_ratio_delta"], 0.05)

    def test_status_change(self) -> None:
        before = _run("a", [_node("clean", 1, "sha256:aa")])
        after = _run("b", [_node("clean", 1, "sha256:aa", status="failed")], status="failed")
        result = diff_runs(before, after)
        self.assertEqual(result["summary"]["status_changed"], True)
        self.assertTrue(result["changed"][0]["status_changed"])

    def test_format_text_is_ascii_table(self) -> None:
        before = _run("a", [_node("clean", 1, "sha256:aa")])
        after = _run("b", [_node("clean", 1, "sha256:bb")])
        text = format_text(diff_runs(before, after))
        text.encode("ascii")
        self.assertIn("summary: added=0", text)
        self.assertIn("+---", text)
        self.assertIn("changed nodes:", text)


if __name__ == "__main__":
    unittest.main()
