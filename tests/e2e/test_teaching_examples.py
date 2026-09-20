"""Browser contract tests for loading teaching inputs through the normal form."""
import json
from pathlib import Path
import sys
import unittest

from tests.e2e.test_mvp_flow import BrowserAppMixin, ROOT


VALIDATION_TOOLS = ROOT / "tools" / "validation"
if str(VALIDATION_TOOLS) not in sys.path:
    sys.path.insert(0, str(VALIDATION_TOOLS))

from business_case_assertions import validate_product_result
from business_case_runner import prepare_reference


class TeachingExampleBrowserTests(BrowserAppMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        reference = prepare_reference(ROOT / "tests/fixtures/business-cases")
        cls.reference_production_imports = reference["production_modules_loaded"]
        cls.reference_cases = {entry["case"]["id"]: entry for entry in reference["results"]}

    def page_for(self, view, width=1440):
        context, page = self.new_page(width=width)
        page.goto(self.base_url + f"/?view={view}", wait_until="networkidle")
        return context, page

    @staticmethod
    def fixture_request(case_id):
        return json.loads((ROOT / "tests/fixtures/business-cases" / case_id / "request.json").read_text(encoding="utf-8"))

    def assert_independent_result(self, case_id, actual):
        entry = self.reference_cases[case_id]
        report = validate_product_result(entry["case"], entry["expected"], actual)
        self.assertEqual(self.reference_production_imports, [])
        self.assertTrue(report["passed"], report["differences"][:10])

    def test_example_entry_is_available_in_both_views(self):
        for view in ("legacy", "workbench"):
            with self.subTest(view=view):
                context, page = self.page_for(view)
                try:
                    page.locator("#try-examples").wait_for(state="visible")
                    self.assertEqual(page.locator("#example-menu").count(), 1)
                finally:
                    context.close()

    def test_basic_example_uses_frozen_request_and_normal_calculation(self):
        context, page = self.page_for("workbench")
        try:
            page.locator("#try-examples").click()
            with page.expect_response(lambda response: response.url.endswith("/api/calculate")) as response_info:
                page.locator('[data-example="basic"]').click()
            response = response_info.value
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.request.post_data), self.fixture_request("A-2025"))
            self.assert_independent_result("A-2025", response.json())
            page.wait_for_function("!document.getElementById('export-csv').disabled")
            self.assertIn("合成示例", page.locator("#example-status").inner_text())
            self.assertIn("合成示例", page.locator("#example-result-status").inner_text())
            self.assertFalse(page.locator("#export-pdf").is_disabled())
        finally:
            context.close()

    def test_comparison_example_loads_six_candidates_without_mobile_overflow(self):
        context, page = self.page_for("workbench", width=390)
        try:
            page.locator("#try-examples").click()
            with page.expect_response(lambda response: response.url.endswith("/api/calculate")) as response_info:
                page.locator('[data-example="comparison"]').click()
            response = response_info.value
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.request.post_data), self.fixture_request("B-default"))
            self.assert_independent_result("B-default", response.json())
            page.wait_for_function("!document.getElementById('export-csv').disabled")
            self.assertEqual(page.locator(".candidate-row").count(), 6)
            self.assertFalse(page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"))
        finally:
            context.close()

    def test_modified_comparison_preserves_frozen_qualification_fields(self):
        context, page = self.page_for("workbench")
        try:
            page.locator("#try-examples").click()
            with page.expect_response(lambda response: response.url.endswith("/api/calculate")):
                page.locator('[data-example="comparison"]').click()
            hvo = page.locator(".candidate-row").filter(
                has=page.locator('[data-field="candidateId"][value="hvo"]')
            )
            hvo.locator('[data-field="candidateSupplyTonnes"]').fill("0")
            self.assertTrue(page.locator("#export-csv").is_disabled())
            self.assertIn("已修改", page.locator("#example-status").inner_text())
            with page.expect_response(lambda response: response.url.endswith("/api/calculate")) as response_info:
                page.locator("#calculate-command").click()
            actual = json.loads(response_info.value.request.post_data)
            self.assertEqual(actual, self.fixture_request("B-hvo-supply0"))
        finally:
            context.close()

    def test_builtin_and_custom_drafts_survive_mode_switch_and_rerender(self):
        context, page = self.page_for("legacy")
        try:
            row = page.locator(".candidate-row").first
            row.locator('[data-field="pathId"]').select_option("E_DIESEL")
            row.locator(".builtin-editor summary").click()
            row.locator('[data-field="builtinQualificationStatus"]').select_option("VERIFIED_ELIGIBLE")
            row.locator('[data-field="builtinE"]').fill("20")
            row.locator('[data-field="builtinEu"]').fill("3")
            row.locator('[data-field="candidateMode"]').select_option("custom")
            row.locator('[data-field="customFuelName"]').fill("Persistent custom draft")
            row.locator('[data-field="candidateMode"]').select_option("builtin")
            self.assertEqual(row.locator('[data-field="pathId"]').input_value(), "E_DIESEL")
            self.assertEqual(row.locator('[data-field="builtinQualificationStatus"]').input_value(), "VERIFIED_ELIGIBLE")
            self.assertEqual(row.locator('[data-field="builtinE"]').input_value(), "20")
            self.assertEqual(row.locator('[data-field="builtinEu"]').input_value(), "3")
            page.locator("#add-candidate").click()
            restored = page.locator(".candidate-row").first
            restored.locator('[data-field="candidateMode"]').select_option("custom")
            self.assertEqual(restored.locator('[data-field="customFuelName"]').input_value(), "Persistent custom draft")
            restored.locator('[data-field="candidateMode"]').select_option("builtin")
            self.assertEqual(restored.locator('[data-field="builtinEu"]').input_value(), "3")
        finally:
            context.close()

    def test_builtin_path_change_clears_old_qualification_draft(self):
        context, page = self.page_for("legacy")
        try:
            row = page.locator(".candidate-row").first
            row.locator('[data-field="pathId"]').select_option("E_DIESEL")
            row.locator(".builtin-editor summary").click()
            row.locator('[data-field="builtinQualificationStatus"]').select_option("VERIFIED_ELIGIBLE")
            row.locator('[data-field="builtinE"]').fill("20")
            row.locator('[data-field="builtinEu"]').fill("3")
            row.locator('[data-field="pathId"]').select_option("MDO")
            self.assertEqual(row.locator('[data-field="builtinQualificationStatus"]').input_value(), "NOT_DEMONSTRATED")
            self.assertEqual(row.locator('[data-field="builtinE"]').input_value(), "")
            self.assertEqual(row.locator('[data-field="builtinEu"]').input_value(), "")
        finally:
            context.close()

    def test_verified_builtin_rfnbo_submits_e_and_eu_without_draft_keys(self):
        context, page = self.page_for("legacy")
        try:
            self.choose_port(page, "#departure-port-search", "CNSHG")
            self.choose_port(page, "#arrival-port-search", "NLRTM")
            row = page.locator(".candidate-row").first
            row.locator('[data-field="candidateId"]').fill("verified-rfnbo")
            row.locator('[data-field="pathId"]').select_option("E_DIESEL")
            row.locator(".builtin-editor summary").click()
            row.locator('[data-field="pricePerTonne"]').fill("1600")
            row.locator('[data-field="specifiedBlendRatios"]').fill("0.05")
            row.locator('[data-field="builtinQualificationStatus"]').select_option("VERIFIED_ELIGIBLE")
            row.locator('[data-field="builtinE"]').fill("20")
            row.locator('[data-field="builtinEu"]').fill("3")
            with page.expect_response(lambda response: response.url.endswith("/api/calculate")) as response_info:
                page.locator("#calculate-command").click()
            candidate = json.loads(response_info.value.request.post_data)["candidates"][0]
            self.assertEqual(candidate["qualificationStatus"], "VERIFIED_ELIGIBLE")
            self.assertEqual(candidate["e"], "20")
            self.assertEqual(candidate["eu"], "3")
            self.assertNotIn("builtinDraft", candidate)
            self.assertNotIn("customDraft", candidate)
            self.assertNotIn("candidateMode", candidate)
        finally:
            context.close()

    def test_reloading_modified_example_requires_confirmation_and_cancel_preserves_state(self):
        context, page = self.page_for("workbench")
        try:
            page.locator("#try-examples").click()
            with page.expect_response(lambda response: response.url.endswith("/api/calculate")):
                page.locator('[data-example="basic"]').click()
            page.locator("#baseline-mass").fill("999")
            self.assertTrue(page.locator("#export-pdf").is_disabled())
            page.once("dialog", lambda dialog: dialog.dismiss())
            page.locator("#try-examples").click()
            page.locator('[data-example="basic"]').click()
            self.assertEqual(page.locator("#baseline-mass").input_value(), "999")
            self.assertIn("已修改", page.locator("#example-status").inner_text())

            page.once("dialog", lambda dialog: dialog.accept())
            page.locator("#try-examples").click()
            with page.expect_response(lambda response: response.url.endswith("/api/calculate")):
                page.locator('[data-example="basic"]').click()
            self.assertEqual(page.locator("#baseline-mass").input_value(), "1000")
            self.assertNotIn("已修改", page.locator("#example-status").inner_text())
        finally:
            context.close()

    def test_invalid_rfnbo_example_resource_is_rejected_before_form_replacement(self):
        context = self.browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        invalid = {
            "version": 1,
            "examples": {
                "basic": {
                    "name": "基础计算", "caseId": "A-2025", "synthetic": True,
                    "request": self.fixture_request("A-2025"),
                },
                "comparison": {
                    "name": "多燃料比较", "caseId": "B-default", "synthetic": True,
                    "request": self.fixture_request("B-default"),
                },
            },
        }
        invalid["examples"]["comparison"]["request"]["candidates"][4]["qualificationStatus"] = "VERIFIED_ELIGIBLE"
        invalid["examples"]["comparison"]["request"]["candidates"][4]["e"] = "20"
        try:
            page.route(
                "**/static/teaching-examples.json",
                lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(invalid)),
            )
            page.goto(self.base_url + "/?view=workbench", wait_until="networkidle")
            self.assertTrue(page.locator("#try-examples").is_disabled())
            self.assertIn("E 和 eu", page.locator("#example-error").inner_text())
            self.assertEqual(page.locator("#baseline-mass").input_value(), "100")
            self.assertEqual(page.locator(".candidate-row").count(), 1)
        finally:
            context.close()

    def test_example_menu_escape_restores_focus_on_mobile(self):
        context, page = self.page_for("workbench", width=390)
        try:
            page.locator("#try-examples").click()
            self.assertTrue(page.locator("#example-menu").is_visible())
            page.keyboard.press("Escape")
            self.assertTrue(page.locator("#example-menu").is_hidden())
            self.assertEqual(page.evaluate("document.activeElement.id"), "try-examples")
            self.assertFalse(page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"))
        finally:
            context.close()

    def test_failed_export_preserves_calculated_result_and_retry_state(self):
        context, page = self.page_for("workbench")
        try:
            page.locator("#try-examples").click()
            with page.expect_response(lambda response: response.url.endswith("/api/calculate")):
                page.locator('[data-example="basic"]').click()
            page.route(
                "**/api/export/csv",
                lambda route: route.fulfill(
                    status=500,
                    content_type="application/json",
                    body=json.dumps({"issues": [{
                        "code": "EXPORT_TEST_FAILURE", "scope": "CASE", "field": "export",
                        "blocking": True, "message": "synthetic export failure",
                    }]}),
                ),
            )
            page.locator("#export-csv").click()
            page.locator("#case-errors").filter(has_text="EXPORT_TEST_FAILURE").wait_for()
            self.assertFalse(page.locator("#export-csv").is_disabled())
            self.assertFalse(page.locator("#export-pdf").is_disabled())
            self.assertIn("已完成", page.locator("#workbench-status").inner_text())
        finally:
            context.close()


if __name__ == "__main__":
    unittest.main()
