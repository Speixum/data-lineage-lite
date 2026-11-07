"""profile 模块测试：行数/列数/缺失率/重复行/类型推断。"""

import unittest

from lineage.profile import classify, infer_type, is_null, profile_table


class ProfileTableTests(unittest.TestCase):
    """表格质量指纹。"""

    def test_basic_metrics(self) -> None:
        rows = [
            {"name": "a", "age": 1},
            {"name": "b", "age": None},
            {"name": "a", "age": 1},
        ]
        profile = profile_table(rows)
        self.assertEqual(profile["rows"], 3)
        self.assertEqual(profile["cols"], 2)
        self.assertEqual(profile["columns"], ["name", "age"])
        self.assertEqual(profile["null_ratio"], 0.1667)
        self.assertEqual(profile["dup_rows"], 1)
        self.assertEqual(profile["types"], {"name": "str", "age": "int"})

    def test_columnar_input_matches_records(self) -> None:
        columnar = {"a": [1, None], "b": ["x", "y"]}
        records = [{"a": 1, "b": "x"}, {"a": None, "b": "y"}]
        self.assertEqual(profile_table(columnar), profile_table(records))

    def test_empty_table(self) -> None:
        profile = profile_table([])
        self.assertEqual(profile["rows"], 0)
        self.assertEqual(profile["null_ratio"], 0.0)

    def test_non_table_returns_zero_profile(self) -> None:
        profile = profile_table(42)
        self.assertEqual(profile["rows"], 0)
        self.assertEqual(profile["columns"], [])
        self.assertEqual(profile["types"], {})


class InferTypeTests(unittest.TestCase):
    """单列类型推断与缺失判定。"""

    def test_int_and_float_merge_to_float(self) -> None:
        self.assertEqual(infer_type([1, 2.5]), "float")

    def test_mixed_types(self) -> None:
        self.assertEqual(infer_type([1, "abc"]), "mixed")

    def test_all_null_is_empty(self) -> None:
        self.assertEqual(infer_type([None, ""]), "empty")

    def test_classify_common_values(self) -> None:
        self.assertEqual(classify(True), "bool")
        self.assertEqual(classify("12"), "int")
        self.assertEqual(classify("12.5"), "float")
        self.assertEqual(classify("2026-11-08"), "date")
        self.assertEqual(classify("2026-11-08T01:35:00"), "datetime")
        self.assertEqual(classify("hello"), "str")

    def test_is_null(self) -> None:
        self.assertTrue(is_null(None))
        self.assertTrue(is_null(""))
        self.assertFalse(is_null(" "))
        self.assertFalse(is_null(0))


if __name__ == "__main__":
    unittest.main()
