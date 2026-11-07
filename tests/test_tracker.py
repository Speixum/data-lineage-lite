"""tracker 测试：装饰器、run 上下文、嵌套、线程隔离、失败记录。"""

import json
import os
import re
import tempfile
import threading
import unittest

import lineage
from lineage.io import load_lineage


def _decorated(step: str):
    """在当前 run 中记录一个简单步骤。"""
    @lineage.track(step)
    def step_func(value):
        return value
    return step_func


class TrackerTests(unittest.TestCase):
    """装饰器与 run 上下文的核心行为。"""

    def test_passthrough_without_run(self) -> None:
        calls = []

        @lineage.track("noop")
        def add(left, right):
            calls.append(1)
            return left + right

        self.assertEqual(add(1, 2), 3)
        self.assertEqual(len(calls), 1)
        self.assertIsNone(lineage.active_run())

    def test_success_node_fields(self) -> None:
        with lineage.run("demo") as current:
            @lineage.track("load")
            def load(rows):
                return rows

            result = load([{"a": 1}])
        self.assertEqual(result, [{"a": 1}])
        data = current.to_dict()
        self.assertEqual(data["schema"], "dataset-lineage/1.0")
        self.assertRegex(data["run_id"], r"^demo-[0-9]{8}T[0-9]{6}Z$")
        self.assertEqual(data["status"], "ok")
        self.assertIsNotNone(data["finished_at"])
        self.assertEqual(len(data["nodes"]), 1)
        node = data["nodes"][0]
        self.assertEqual(node["id"], "demo/load#01")
        self.assertEqual(node["step"], "load")
        self.assertEqual(node["seq"], 1)
        self.assertEqual(node["status"], "ok")
        self.assertIsNone(node["error"])
        self.assertFalse(node["unstable"])
        self.assertEqual(node["params"], {"rows": {"<table>": ["a"], "<rows>": 1}})
        self.assertEqual(node["inputs"][0]["ref"], "rows")
        self.assertEqual(node["outputs"][0]["ref"], "<return>")
        self.assertEqual(node["outputs"][0]["kind"], "table")
        self.assertTrue(node["outputs"][0]["hash"].startswith("sha256:"))
        self.assertGreaterEqual(node["duration_ms"], 0.0)
        self.assertEqual(data["env"].keys(), {"python", "platform", "cwd"})

    def test_failed_node_is_recorded_and_reraised(self) -> None:
        with self.assertRaises(ValueError):
            with lineage.run("boom") as current:
                @lineage.track("explode")
                def explode(value):
                    raise ValueError("bad value")

                explode(3)
        data = current.to_dict()
        self.assertEqual(data["status"], "failed")
        node = data["nodes"][0]
        self.assertEqual(node["status"], "failed")
        self.assertEqual(node["error"]["type"], "ValueError")
        self.assertEqual(node["error"]["message"], "bad value")
        self.assertTrue(node["error"]["traceback"])
        self.assertEqual(node["outputs"], [])

    def test_edges_chain_nodes(self) -> None:
        with lineage.run("chain") as current:
            @lineage.track("one")
            def one():
                return 1

            @lineage.track("two")
            def two(value):
                return value + 1

            self.assertEqual(two(one()), 2)
        data = current.to_dict()
        self.assertEqual(len(data["edges"]), 1)
        edge = data["edges"][0]
        self.assertEqual(edge["from"], "chain/one#01")
        self.assertEqual(edge["to"], "chain/two#02")
        self.assertEqual(edge["label"], "value")

    def test_nested_runs_share_store_and_prefix_ids(self) -> None:
        with lineage.run("outer") as outer:
            @lineage.track("prep")
            def prep():
                return 1

            prep()
            with lineage.run("inner") as inner:
                @lineage.track("work")
                def work():
                    return 2

                work()
        self.assertEqual([n["id"] for n in inner.to_dict()["nodes"]], ["outer/inner/work#01"])
        self.assertEqual(
            [n["id"] for n in outer.to_dict()["nodes"]],
            ["outer/prep#01", "outer/inner/work#01"],
        )

    def test_seq_is_scoped_per_run(self) -> None:
        with lineage.run("first") as one:
            _decorated("go")(1)
        with lineage.run("second") as two:
            _decorated("go")(2)
        first_node = one.to_dict()["nodes"][0]
        second_node = two.to_dict()["nodes"][0]
        self.assertEqual((first_node["id"], first_node["seq"]), ("first/go#01", 1))
        self.assertEqual((second_node["id"], second_node["seq"]), ("second/go#01", 1))

    def test_threads_are_isolated(self) -> None:
        captured = {}

        def worker(name: str) -> None:
            with lineage.run(name) as current:
                _decorated("job")(name)
            captured[name] = current.to_dict()["nodes"]

        threads = [threading.Thread(target=worker, args=(f"t{index}",)) for index in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(captured), ["t0", "t1"])
        for name, nodes in captured.items():
            self.assertEqual(len(nodes), 1)
            self.assertEqual(nodes[0]["id"], f"{name}/job#01")

    def test_empty_run_name_rejected(self) -> None:
        with self.assertRaises(ValueError):
            with lineage.run("   "):
                pass

    def test_unstable_argument_marks_node(self) -> None:
        class Opaque:
            pass

        with lineage.run("u") as current:
            _decorated("carry")(Opaque())
        node = current.to_dict()["nodes"][0]
        self.assertTrue(node["unstable"])
        self.assertTrue(node["outputs"][0]["hash"].startswith("unstable:Opaque#"))

    def test_save_and_reload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with lineage.run("persist") as current:
                _decorated("job")([{"a": 1}])
            path = current.save(os.path.join(tmp, "lineage.json"))
            self.assertTrue(os.path.isabs(path))
            data = load_lineage(path)
            self.assertEqual(data["name"], "persist")
            self.assertEqual(data["nodes"][0]["id"], "persist/job#01")
            with open(path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
            self.assertEqual(raw["schema"], "dataset-lineage/1.0")

    def test_summary_counts(self) -> None:
        with lineage.run("sum") as current:
            _decorated("job")(1)
        summary = current.summary()
        self.assertEqual(summary["nodes"], 1)
        self.assertEqual(summary["failed"], 0)
        self.assertEqual(summary["status"], "ok")


if __name__ == "__main__":
    unittest.main()
