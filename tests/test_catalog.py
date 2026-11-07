"""catalog 测试：条目生成、聚合去重、卡片 markdown、读写校验。"""

import os
import tempfile
import unittest

import lineage
from lineage.catalog import (
    CATALOG_SCHEMA,
    build_catalog,
    card_markdown,
    load_catalog,
    make_entry,
    upsert,
    write_card,
    write_catalog,
)
from lineage.errors import LineageFormatError


def _publish_run(payload):
    """构造一次带表格输出的 run。"""
    with lineage.run("build") as current:
        @lineage.track("publish")
        def publish(rows):
            return rows

        publish(payload)
    return current.to_dict()


class CatalogEntryTests(unittest.TestCase):
    """条目与卡片内容。"""

    def test_make_entry_from_table_output(self) -> None:
        run = _publish_run([{"id": 1, "city": "beijing"}, {"id": 2, "city": None}])
        entry = make_entry(run, name="demo_users", version="1.2.0", license="CC-BY-4.0",
                           tasks=["analytics", "profiling"])
        self.assertEqual(entry["name"], "demo_users")
        self.assertEqual(entry["version"], "1.2.0")
        self.assertEqual(entry["rows"], 2)
        self.assertEqual(entry["cols"], 2)
        self.assertEqual(entry["columns"], ["id", "city"])
        self.assertEqual(entry["license"], "CC-BY-4.0")
        self.assertEqual(entry["tasks"], ["analytics", "profiling"])
        self.assertEqual(entry["source_step"], "publish")
        self.assertEqual(entry["status"], "ok")
        self.assertEqual(entry["card"], "cards/demo_users.md")
        self.assertTrue(str(entry["hash"]).startswith("sha256:"))
        self.assertEqual(entry["null_ratio"], 0.25)

    def test_make_entry_without_table_output(self) -> None:
        with lineage.run("value-only") as current:
            @lineage.track("compute")
            def compute():
                return 5

            compute()
        entry = make_entry(current.to_dict())
        self.assertIsNone(entry["rows"])
        self.assertEqual(entry["columns"], [])
        self.assertIsNone(entry["hash"])
        self.assertEqual(entry["license"], "internal-only")
        self.assertEqual(entry["tasks"], ["analytics"])

    def test_card_markdown_has_sections(self) -> None:
        run = _publish_run([{"id": 1, "city": "beijing"}])
        entry = make_entry(run, name="demo_users", tasks=["analytics"])
        text = card_markdown(entry)
        self.assertIn("# 数据集卡片：demo_users", text)
        self.assertIn("- 名称：", text)
        self.assertIn("- 版本：", text)
        self.assertIn("- 许可：", text)
        self.assertIn("- 适用任务：", text)
        self.assertIn("- 更新时间：", text)
        self.assertIn("| 列名 | 推断类型 |", text)
        self.assertIn("| city |", text)

    def test_card_markdown_without_columns(self) -> None:
        entry = {"name": "empty", "version": "0.1.0", "columns": []}
        text = card_markdown(entry)
        self.assertIn("（无字段信息：该 run 没有表格输出）", text)


class CatalogAggregationTests(unittest.TestCase):
    """catalog 聚合与落盘。"""

    def test_build_catalog_dedups_and_sorts(self) -> None:
        first = {"name": "b", "version": "1.0.0", "rows": 1}
        second = {"name": "a", "version": "1.0.0", "rows": 2}
        newer = {"name": "b", "version": "1.0.0", "rows": 3}
        catalog = build_catalog([first, second, newer])
        self.assertEqual(catalog["schema"], CATALOG_SCHEMA)
        self.assertEqual([item["name"] for item in catalog["datasets"]], ["a", "b"])
        self.assertEqual(catalog["datasets"][1]["rows"], 3)

    def test_upsert_keeps_existing_entries(self) -> None:
        base = build_catalog([{"name": "a", "version": "1.0.0"}])
        merged = upsert(base, {"name": "b", "version": "2.0.0"})
        self.assertEqual(len(merged["datasets"]), 2)
        self.assertEqual(len(base["datasets"]), 1)

    def test_write_and_load_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog = build_catalog([{"name": "a", "version": "1.0.0", "rows": 7}])
            path = write_catalog(os.path.join(tmp, "catalog.json"), catalog)
            loaded = load_catalog(path)
            self.assertEqual(loaded["datasets"][0]["rows"], 7)
            self.assertEqual(loaded["schema"], CATALOG_SCHEMA)

    def test_load_rejects_foreign_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "catalog.json")
            write_catalog(path, {"schema": "something-else/9", "datasets": []})
            with self.assertRaises(LineageFormatError):
                load_catalog(path)

    def test_write_card_creates_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            entry = {"name": "demo/users", "version": "1.0.0", "columns": ["id"]}
            path = write_card(os.path.join(tmp, "cards"), entry)
            self.assertTrue(os.path.isfile(path))
            self.assertTrue(os.path.basename(path).endswith(".md"))


if __name__ == "__main__":
    unittest.main()
