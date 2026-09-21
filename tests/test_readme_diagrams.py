"""Keep generated handoff diagrams aligned with their source and product scope."""

from pathlib import Path
import runpy
import unittest
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
DIAGRAMS = ROOT / "docs" / "diagrams"
NS = {"svg": "http://www.w3.org/2000/svg"}


class ReadmeDiagramTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builders = runpy.run_path(str(ROOT / "tools/diagrams/generate_diagrams.py"))

    def text(self, name):
        root = ET.parse(DIAGRAMS / f"{name}.svg").getroot()
        return "\n".join(node.text or "" for node in root.findall(".//svg:tspan", NS))

    def test_generated_files_match_source_and_readme_references(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for name in ("product-overview", "user-journey", "calculation-flow"):
            with self.subTest(diagram=name):
                actual = (DIAGRAMS / f"{name}.svg").read_text(encoding="utf-8")
                expected = self.builders["build_" + name.replace("-", "_")]()
                self.assertEqual(actual, expected)
                self.assertIn(f"(./docs/diagrams/{name}.svg)", readme)

    def test_each_diagram_has_accessible_title_description_and_viewbox(self):
        for path in DIAGRAMS.glob("*.svg"):
            with self.subTest(diagram=path.name):
                root = ET.parse(path).getroot()
                self.assertEqual(root.get("role"), "img")
                for element_id in root.get("aria-labelledby", "").split():
                    self.assertIsNotNone(root.find(f".//*[@id='{element_id}']"))
                self.assertTrue(root.find("svg:title", NS).text)
                self.assertTrue(root.find("svg:desc", NS).text)
                self.assertEqual(root.get("viewBox").split()[:3], ["0", "0", "1000"])

    def test_product_goals_and_boundaries_are_explicit(self):
        text = self.text("product-overview")
        for fragment in (
            "基准燃料（B0）", "有效挂靠港", "模型成本最低",
            "达到参考线的最低成本", "报告方案内最大合规改善",
            "不代表年度合规已完成",
        ):
            self.assertIn(fragment, text)
        self.assertNotIn("达标优先", text)
        self.assertNotIn("Port of Call", text)

    def test_journey_covers_both_entries_and_input_invalidation(self):
        text = self.text("user-journey")
        for fragment in (
            "自行填写", "试用示例（合成）", "没有候选也可只算基准",
            "自动填入示例条件并计算", "显示指引",
            "旧结果与导出入口失效", "需重新计算",
        ):
            self.assertIn(fragment, text)

    def test_calculation_separates_costs_and_support_from_main_flow(self):
        root = ET.parse(DIAGRAMS / "calculation-flow.svg").getroot()
        text = self.text("calculation-flow")
        self.assertEqual(len(root.findall(".//*[@data-connector='flow']")), 3)
        self.assertEqual(len(root.findall(".//*[@data-connector='support']")), 1)
        for fragment in (
            "同一能源需求", "各候选分别计算", "不把多个候选同时混兑",
            "模型成本 = 燃料成本 + EU ETS 配额成本",
            "FuelEU 指示性金额以欧元单列，不计入模型成本或预算",
            "规则与数据支撑", "不另设计算链路",
        ):
            self.assertIn(fragment, text)


if __name__ == "__main__":
    unittest.main()
