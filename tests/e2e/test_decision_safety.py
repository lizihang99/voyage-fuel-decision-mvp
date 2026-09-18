"""Browser regressions for result/input identity and public boundary labels."""

import unittest
from pathlib import Path

from playwright.sync_api import expect

from tests.e2e.test_mvp_flow import BrowserAppMixin


class DecisionSafetyBrowserTests(BrowserAppMixin, unittest.TestCase):
    def test_b0_only_page_calculates_and_exports_without_new_energy_recommendations(self):
        context, page = self.new_page()
        try:
            self.fill_case(page, include_rfnbo=False)
            page.locator(".remove-candidate").last.click()
            page.locator(".remove-candidate").last.click()
            result = self.calculate(page)
            self.assertEqual([row["scenario_id"] for row in result["scenarios"]], ["B0"])
            self.assertEqual(result["candidate_results"], [])
            self.assertEqual(result["recommendations"], [])
            self.assertIsNone(result["decision_summary"])
            expect(page.locator("#new-energy-decision-summary")).to_contain_text("暂无新能源决策结果")
            expect(page.locator("#port-identity-details")).to_contain_text("Shanghai Pt")
            expect(page.locator("#export-csv")).to_be_enabled()
            with page.expect_download():
                page.locator("#export-csv").click()
        finally:
            context.close()

    def test_initial_export_disabled_and_edits_invalidate_results(self):
        context, page = self.new_page()
        try:
            expect(page.locator("#export-csv")).to_be_disabled()
            self.fill_case(page, include_rfnbo=False)
            result = self.calculate(page)
            expect(page.locator("#export-csv")).to_be_enabled()
            page.locator("#baseline-mass").fill("110")
            expect(page.locator("#export-csv")).to_be_disabled()
            expect(page.locator("#result-run-status")).to_contain_text("输入已变更")
            expect(page.locator("#new-energy-decision-summary")).not_to_contain_text("推荐新能源用量")
            self.calculate(page)
            page.locator("#add-candidate").click()
            expect(page.locator("#export-pdf")).to_be_disabled()
            self.calculate(page)
            page.locator(".remove-candidate").last.click()
            expect(page.locator("#export-csv")).to_be_disabled()
        finally:
            context.close()

    def test_precision_does_not_invalidate_and_export_uses_calculated_inputs(self):
        context, page = self.new_page()
        try:
            self.fill_case(page, include_rfnbo=False)
            result = self.calculate(page)
            page.locator("#precision-mass").fill("6")
            expect(page.locator("#export-csv")).to_be_enabled()
            # No input event: exports must still use the successful input snapshot.
            page.locator("#baseline-mass").evaluate("el => { el.value = '999'; }")
            with page.expect_request("**/api/export/csv") as exported:
                with page.expect_download():
                    page.locator("#export-csv").click()
            body = exported.value.post_data_json
            self.assertEqual(body["resultSnapshotId"], result["result_snapshot_id"])
            self.assertNotIn("baseline", body)
            self.assertEqual(body["displayConfig"]["fuel_mass_decimals"], 6)
        finally:
            context.close()

    def test_old_success_or_failure_cannot_replace_new_calculation(self):
        context, page = self.new_page()
        try:
            self.fill_case(page, include_rfnbo=False)
            pending = []
            page.route("**/api/calculate", lambda route: pending.append(route))
            for old_status in (200, 422):
                with page.expect_request("**/api/calculate"):
                    page.locator("#calculate-command").click()
                page.locator("#baseline-mass").fill("110" if old_status == 200 else "120")
                with page.expect_request("**/api/calculate"):
                    page.locator("#calculate-command").click()
                self.assertEqual(len(pending), 2)
                old, new = pending
                newer_result = page.request.post(
                    self.base_url + "/api/calculate", data=new.request.post_data_json).json()
                new.fulfill(status=200, json=newer_result)
                expect(page.locator("#result-run-status")).to_contain_text("已完成")
                expected_metrics = page.locator("#overview-metrics").inner_text()
                if old_status == 200:
                    old_result = page.request.post(
                        self.base_url + "/api/calculate", data=old.request.post_data_json).json()
                else:
                    old_result = {"issues": [{"code": "OLD_FAILURE", "scope": "CASE",
                                              "field": "case", "message": "old", "blocking": True}]}
                old.fulfill(status=old_status, json=old_result)
                # Drain response handlers without relying on arbitrary sleeps.
                page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
                self.assertEqual(page.locator("#overview-metrics").inner_text(), expected_metrics)
                expect(page.locator("#result-run-status")).to_contain_text("已完成")
                expect(page.locator("#export-csv")).to_be_enabled()
                self.assertNotIn("OLD_FAILURE", page.locator("#case-errors").inner_text())
                pending.clear()
        finally:
            context.close()

    def test_edit_while_calculating_or_exporting_discards_stale_response(self):
        context, page = self.new_page()
        try:
            self.fill_case(page, include_rfnbo=False)
            pending = []
            page.route("**/api/calculate", lambda route: pending.append(route))
            with page.expect_request("**/api/calculate"):
                page.locator("#calculate-command").click()
            page.locator("#baseline-mass").fill("110")
            route = pending.pop()
            result = page.request.post(
                self.base_url + "/api/calculate", data=route.request.post_data_json).json()
            route.fulfill(status=200, json=result)
            page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
            expect(page.locator("#export-csv")).to_be_disabled()
            page.unroute("**/api/calculate")
            self.calculate(page)
            downloads = []
            page.on("download", lambda download: downloads.append(download))
            page.route("**/api/export/csv", lambda route: pending.append(route))
            with page.expect_request("**/api/export/csv"):
                page.locator("#export-csv").click()
            page.locator("#baseline-mass").fill("120")
            pending.pop().fulfill(status=200, content_type="text/csv", body="old,report\n")
            page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
            self.assertEqual(downloads, [])
            expect(page.locator("#export-csv")).to_be_disabled()
        finally:
            context.close()

    def test_business_blocked_response_cannot_be_exported(self):
        context, page = self.new_page()
        try:
            self.fill_case(page, include_rfnbo=False)
            page.locator("#departure-port-search").fill("ZZZZZ")
            with page.expect_response("**/api/calculate"):
                page.locator("#calculate-command").click()
            expect(page.locator("#result-run-status")).to_contain_text("阻断")
            expect(page.locator("#export-pdf")).to_be_disabled()
        finally:
            context.close()

    def test_currency_constraint_and_evidence_labels_across_viewports(self):
        for width, height in ((1440, 900), (390, 844)):
            with self.subTest(width=width):
                context, page = self.new_page(width, height)
                try:
                    self.fill_case(page, include_rfnbo=True)
                    page.locator("#case-currency").select_option("USD")
                    row = page.locator(".candidate-row").first
                    row.locator('[data-field="incrementalBudget"]').fill("1000")
                    row.locator('[data-field="pricePerTonne"]').fill("")
                    self.calculate(page)
                    self.assertIn("不换汇", page.locator("#currency-boundary-note").inner_text())
                    self.assertIn("EUR", page.locator("#ets-fueleu-detail").inner_text())
                    self.assertIn("未证明", page.locator("#catalog-qualification-note").inner_text())
                    page.get_by_role("tab", name="Scenarios").click()
                    self.assertIn("预算未验证", page.locator("#scenarios-panel").inner_text())
                    self.assertIn("CONSTRAINT_UNVERIFIED", page.locator("#scenarios-panel").inner_text())
                    page.get_by_role("tab", name="Thresholds").click()
                    self.assertIn("综合约束上限", page.locator("#thresholds-panel").inner_text())
                    page.get_by_role("tab", name="Evidence").click()
                    self.assertIn("不自动核验证书", page.locator("#evidence-panel").inner_text())
                    self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width)
                    out = Path(__file__).resolve().parents[2] / "output" / "safety"
                    out.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(out / f"evidence-{width}.png"), full_page=True)
                finally:
                    context.close()


if __name__ == "__main__":
    unittest.main()
