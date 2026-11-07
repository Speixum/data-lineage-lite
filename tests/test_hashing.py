"""hashing 模块测试：分块文件哈希、表格规范化哈希、不可序列化降级。"""

import hashlib
import os
import tempfile
import unittest

from lineage import hashing
from lineage.errors import LineageError


class HashFileTests(unittest.TestCase):
    """文件哈希：稳定性、敏感性与异常路径。"""

    def test_sha256_bytes_has_prefix(self) -> None:
        digest = hashing.sha256_bytes(b"lineage")
        self.assertEqual(digest, "sha256:" + hashlib.sha256(b"lineage").hexdigest())

    def test_hash_file_chunking_is_stable(self) -> None:
        payload = bytes(range(256)) * 37
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "blob.bin")
            with open(path, "wb") as handle:
                handle.write(payload)
            expected = "sha256:" + hashlib.sha256(payload).hexdigest()
            for chunk_size in (1, 7, 1024, hashing.CHUNK_SIZE):
                self.assertEqual(hashing.hash_file(path, chunk_size), expected)

    def test_hash_file_missing_raises_ascii_error(self) -> None:
        with self.assertRaises(LineageError) as ctx:
            hashing.hash_file("no/such/file.csv")
        message = str(ctx.exception)
        self.assertIn("file not found", message)
        message.encode("ascii")  # 错误信息必须是纯 ASCII

    def test_hash_file_directory_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(LineageError):
                hashing.hash_file(tmp)

    def test_hash_file_rejects_bad_chunk_size(self) -> None:
        with self.assertRaises(LineageError):
            hashing.hash_file(__file__, chunk_size=0)


class TableHashTests(unittest.TestCase):
    """表格哈希：列序无关、行序有关、跨表示一致。"""

    def test_column_order_does_not_matter(self) -> None:
        left = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
        right = [{"b": "x", "a": 1}, {"b": "y", "a": 2}]
        self.assertEqual(hashing.hash_table(left), hashing.hash_table(right))

    def test_row_order_matters(self) -> None:
        left = [{"a": 1}, {"a": 2}]
        right = [{"a": 2}, {"a": 1}]
        self.assertNotEqual(hashing.hash_table(left), hashing.hash_table(right))

    def test_value_change_changes_hash(self) -> None:
        before = [{"a": 1}, {"a": 2}]
        after = [{"a": 1}, {"a": 3}]
        self.assertNotEqual(hashing.hash_table(before), hashing.hash_table(after))

    def test_columnar_dict_matches_records(self) -> None:
        columnar = {"a": [1, 2], "b": ["x", "y"]}
        records = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
        self.assertEqual(hashing.hash_table(columnar), hashing.hash_table(records))

    def test_matrix_rows_match_records(self) -> None:
        matrix = [[1, "x"], [2, "y"]]
        records = [{"c0": 1, "c1": "x"}, {"c0": 2, "c1": "y"}]
        self.assertEqual(hashing.hash_table(matrix), hashing.hash_table(records))

    def test_ragged_rows_are_padded_with_none(self) -> None:
        ragged = [{"a": 1}, {"b": 2}]
        padded = [{"a": 1, "b": None}, {"a": None, "b": 2}]
        self.assertEqual(hashing.hash_table(ragged), hashing.hash_table(padded))

    def test_nan_cell_is_stable(self) -> None:
        one = [{"a": float("nan")}]
        two = [{"a": float("nan")}]
        self.assertEqual(hashing.hash_table(one), hashing.hash_table(two))

    def test_unstable_hash_shape(self) -> None:
        digest = hashing.unstable_hash(object())
        self.assertRegex(digest, r"^unstable:[A-Za-z_][A-Za-z0-9_]*#[0-9a-f]{8}$")


class SnapshotTests(unittest.TestCase):
    """params 快照与输入/输出指纹。"""

    def test_table_becomes_summary(self) -> None:
        snapshot, unstable = hashing.json_snapshot([{"a": 1}, {"a": 2}])
        self.assertEqual(snapshot, {"<table>": ["a"], "<rows>": 2})
        self.assertFalse(unstable)

    def test_unserialisable_object_is_unstable(self) -> None:
        snapshot, unstable = hashing.json_snapshot(object())
        self.assertTrue(unstable)
        self.assertIsInstance(snapshot, str)
        self.assertIn("object", snapshot)

    def test_nested_snapshot_keeps_structure(self) -> None:
        snapshot, unstable = hashing.json_snapshot({"n": 1, "items": [1, "two"]})
        self.assertEqual(snapshot, {"n": 1, "items": [1, "two"]})
        self.assertFalse(unstable)

    def test_fingerprint_of_value_has_hash(self) -> None:
        entry = hashing.fingerprint_object(42)
        self.assertEqual(entry["ref"], "<return>")
        self.assertEqual(entry["kind"], "value")
        self.assertTrue(str(entry["hash"]).startswith("sha256:"))

    def test_fingerprint_of_table_has_profile(self) -> None:
        entry = hashing.fingerprint_object([{"a": 1}, {"a": None}])
        self.assertEqual(entry["kind"], "table")
        self.assertEqual(entry["fingerprint"]["rows"], 2)
        self.assertEqual(entry["fingerprint"]["cols"], 1)

    def test_fingerprint_of_file_has_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "data.csv")
            with open(path, "wb") as handle:
                handle.write(b"a,b\n1,2\n")
            entry = hashing.fingerprint_object(path, ref="path")
            self.assertEqual(entry["kind"], "file")
            self.assertEqual(entry["bytes"], 8)
            self.assertEqual(entry["hash"], hashing.hash_file(path))


if __name__ == "__main__":
    unittest.main()
