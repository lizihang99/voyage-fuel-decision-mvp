"""Contract tests for the small set of distributable teaching inputs."""
import json
from pathlib import Path
import unittest

from fastapi.testclient import TestClient

from voyage_fuel.web import app


ROOT = Path(__file__).resolve().parents[1]
RESOURCE = ROOT / "src/voyage_fuel" / "static" / "teaching-examples.json"
FIXTURES = ROOT / "tests" / "fixtures" / "business-cases"


class TeachingExampleResourceTests(unittest.TestCase):
    def test_resource_contains_only_two_synthetic_requests_matching_frozen_cases(self):
        resource = json.loads(RESOURCE.read_text(encoding="utf-8"))
        self.assertEqual(resource["version"], 1)
        self.assertEqual(set(resource["examples"]), {"basic", "comparison"})
        for key, case_id in (("basic", "A-2025"), ("comparison", "B-default")):
            with self.subTest(example=key):
                example = resource["examples"][key]
                self.assertIsInstance(example["name"], str)
                self.assertTrue(example["name"].strip())
                self.assertEqual(example["caseId"], case_id)
                self.assertTrue(example["synthetic"])
                request = json.loads((FIXTURES / case_id / "request.json").read_text(encoding="utf-8"))
                self.assertEqual(example["request"], request)
                self.assertNotIn("expected", example)
                self.assertNotIn("result", example)

    def test_resource_requests_have_required_input_envelope(self):
        resource = json.loads(RESOURCE.read_text(encoding="utf-8"))
        for key, example in resource["examples"].items():
            with self.subTest(example=key):
                request = example["request"]
                self.assertEqual(
                    set(request),
                    {
                        "reportYear", "departurePort", "arrivalPort",
                        "adjacentValidPortOfCallConfirmed", "currency", "baseline",
                        "euaPricePerTCO2e", "candidates",
                    },
                )
                self.assertEqual(set(request["baseline"]), {"pathId", "massTonnes", "pricePerTonne"})
                self.assertIsInstance(request["candidates"], list)


class TeachingExampleGuideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_both_calculator_views_link_to_the_optional_guide(self):
        for view in ("legacy", "workbench"):
            with self.subTest(view=view):
                response = self.client.get("/", params={"view": view})
                self.assertEqual(response.status_code, 200)
                self.assertIn('href="/examples/guide"', response.text)
                self.assertIn('target="_blank"', response.text)
                self.assertIn('rel="noopener"', response.text)

    def test_guide_describes_two_examples_and_synthetic_boundaries(self):
        response = self.client.get("/examples/guide")
        self.assertEqual(response.status_code, 200)
        for text in (
            "基础计算", "多燃料比较", "合成输入", "1000 吨",
            "航次级 FuelEU/EU ETS 估算", "不代表真实认证", "不构成采购建议",
        ):
            self.assertIn(text, response.text)
        self.assertIn('href="/?view=workbench"', response.text)

    def test_guide_has_real_input_checklist_without_exercise(self):
        response = self.client.get("/examples/guide")
        self.assertEqual(response.status_code, 200)
        self.assertIn("开始自己的计算", response.text)
        for label in ("报告年份", "候选", "资格", "重新计算"):
            self.assertIn(label, response.text)
        for old_prompt in ("HVO 供应量改为 0", "完成练习", "下一步"):
            self.assertNotIn(old_prompt, response.text)


if __name__ == "__main__":
    unittest.main()
