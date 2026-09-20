import unittest
import json

from tests.e2e.test_mvp_flow import BrowserAppMixin


class WorkbenchFlowTests(BrowserAppMixin, unittest.TestCase):
    def new_workbench_page(self, width=1440, height=900):
        context, page = self.new_page(width=width, height=height)
        page.goto(self.base_url + "/?view=workbench", wait_until="networkidle")
        page.locator("#calculate-command").wait_for()
        page.wait_for_function("!document.getElementById('calculate-command').disabled")
        return context, page

    def test_workbench_calculates_and_switches_goal(self):
        context, page = self.new_workbench_page()
        try:
            self.fill_case(page, include_rfnbo=False)
            result = self.calculate(page, view="workbench")
            self.assertTrue(result["decision_summary"])
            page.locator("#workbench-root").wait_for(state="visible")
            page.locator("#workbench-status").filter(has_text="已完成").wait_for()
            page.locator("#workbench-goal-cards button").filter(has_text="达到 GHGI 参考线").click()
            page.locator("#workbench-scenario-table .workbench-scenario-row.selected").wait_for()
            page.locator("#workbench-selected-detail").filter(has_text="当前方案投入产出").wait_for()
            sensitivity = page.locator("#workbench-sensitivity")
            sensitivity.filter(has_text="用量限制与价格影响").wait_for()
            self.assertFalse(sensitivity.evaluate("(node) => node.open"))
            sensitivity.locator("summary").click()
            self.assertIn("什么价格更划算", page.locator("#workbench-sensitivity").inner_text())
            self.assertEqual(page.locator(".workbench-scatter .quadrant").count(), 4)
            self.assertGreater(page.locator(".workbench-scatter .plot-point").count(), 0)
            self.assertGreater(page.locator(".workbench-threshold-lanes").count(), 0)
            self.assertGreater(page.locator(".workbench-threshold-lanes .lane-threshold-point").count(), 0)
        finally:
            context.close()

    def test_workbench_desktop_keeps_net_change_visible_and_details_below_table(self):
        context, page = self.new_workbench_page(width=1440, height=900)
        try:
            self.fill_case(page, include_rfnbo=False)
            self.calculate(page, view="workbench")
            page.locator("#workbench-root").wait_for(state="visible")

            row = page.locator(".workbench-scenario-row[data-scenario-id='uco-quote-1@0.002']")
            row.click()
            change = row.locator(".change-up")
            change.wait_for(state="visible")

            table_scroll = page.locator(".workbench-table-scroll")
            table_rect = table_scroll.bounding_box()
            change_rect = change.bounding_box()
            detail_rect = page.locator("#workbench-selected-detail").bounding_box()
            assert table_rect is not None
            assert change_rect is not None
            assert detail_rect is not None

            self.assertLessEqual(
                table_scroll.evaluate("(node) => node.scrollWidth"),
                table_scroll.evaluate("(node) => node.clientWidth") + 1,
            )
            self.assertGreaterEqual(change_rect["x"], table_rect["x"])
            self.assertLessEqual(
                change_rect["x"] + change_rect["width"],
                table_rect["x"] + table_rect["width"],
            )
            self.assertLess(
                table_rect["y"] + table_rect["height"],
                detail_rect["y"],
            )
            self.assertEqual(
                change.evaluate("(node) => getComputedStyle(node).color"),
                "rgb(161, 43, 43)",
            )
        finally:
            context.close()

    def test_workbench_b0_only_keeps_base_result_and_disables_recommendations(self):
        context, page = self.new_workbench_page()
        try:
            self.choose_port(page, "#departure-port-search", "CNSHG")
            self.choose_port(page, "#arrival-port-search", "NLRTM")
            page.locator(".candidate-row .remove-candidate").click()
            result = self.calculate(page, view="workbench")
            self.assertEqual([row["scenario_id"] for row in result["scenarios"]], ["B0"])
            page.locator("#workbench-root").wait_for(state="visible")
            self.assertFalse(page.locator("#export-csv").is_disabled())
            page.locator("#workbench-sensitivity summary").click()
            self.assertIn("尚未添加替代燃料", page.locator("#workbench-sensitivity").inner_text())
            self.assertNotIn("B0-only", page.locator("#workbench-sensitivity").inner_text())
        finally:
            context.close()

    def test_blocked_candidate_shows_reasons_in_price_section(self):
        context, page = self.new_workbench_page()
        try:
            self.fill_case(page, include_rfnbo=False)
            page.locator(".candidate-row").first.locator('[data-field="pathId"]').evaluate(
                "select => { select.add(new Option('UNKNOWN_PATH', 'UNKNOWN_PATH')); select.value = 'UNKNOWN_PATH'; }"
            )
            result = self.calculate(page, view="workbench")
            self.assertEqual(result["candidate_results"][0]["calculation_status"], "BLOCKED")
            page.locator("#workbench-sensitivity summary").click()
            text = page.locator("#workbench-sensitivity").inner_text()
            self.assertIn("替代燃料暂时无法参与比较", text)
            self.assertNotIn("尚未添加替代燃料", text)
            for issue in result["candidate_results"][0]["issues"]:
                self.assertIn(issue["message"], text)
        finally:
            context.close()

    def test_workbench_mobile_has_no_horizontal_overflow(self):
        context, page = self.new_workbench_page(width=390, height=844)
        try:
            self.fill_case(page, include_rfnbo=False)
            self.calculate(page, view="workbench")
            page.locator("#workbench-root").wait_for(state="visible")
            overflow = page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
            self.assertFalse(overflow)
            self.assertEqual(page.locator("body[data-view='workbench'] .topbar").evaluate("(node) => getComputedStyle(node).position"), "static")
            self.assertGreater(page.locator(".workbench-scenario-card").count(), 0)
            self.assertGreater(page.locator(".workbench-delta-card").count(), 0)
            self.assertEqual(page.locator(".workbench-table-scroll").count(), 1)
            self.assertFalse(page.locator(".workbench-table-scroll").is_visible())
            visible_text = page.locator("#workbench-content").inner_text()
            self.assertIn("模型成本", visible_text)
            self.assertIn("相对 B0", visible_text)
        finally:
            context.close()

    def test_workbench_main_view_uses_business_labels(self):
        context, page = self.new_workbench_page()
        try:
            self.fill_case(page, include_rfnbo=False)
            self.calculate(page, view="workbench")
            page.locator("#workbench-root").wait_for(state="visible")
            visible_text = page.locator("#workbench-content").inner_text()
            self.assertNotIn("MODEL_COST_MINIMUM", visible_text)
            self.assertNotIn("CONSTRAINT_RESULT", visible_text)
            self.assertNotIn("TARGET_UNREACHABLE_UNDER_CONSTRAINTS", visible_text)
            self.assertIn("当前模型成本最低", visible_text)
            self.assertIn("执行条件待确认", visible_text)
            self.assertIn("核心结论", visible_text)
            self.assertIn("用量限制与价格影响", visible_text)
        finally:
            context.close()

    def test_workbench_percent_input_is_sent_as_mass_ratio(self):
        context, page = self.new_workbench_page()
        try:
            self.fill_case(page, include_rfnbo=False)
            row = page.locator(".candidate-row").first
            row.locator('[data-field="maxBlendRatio"]').fill("30")
            row.locator('[data-field="specifiedBlendRatios"]').fill("2.2130676682982508109")
            with page.expect_request(lambda request: request.url.endswith("/api/calculate")) as request_info:
                page.locator("#calculate-command").click()
            body = json.loads(request_info.value.post_data)
            candidate = body["candidates"][0]
            self.assertEqual(candidate["maxBlendRatio"], "0.3")
            self.assertEqual(candidate["specifiedBlendRatios"], ["0.022130676682982508109"])
        finally:
            context.close()

    def test_calculation_details_reuse_result_and_clear_on_edit(self):
        for width, height in ((1440, 900), (390, 844)):
            with self.subTest(width=width):
                context, page = self.new_workbench_page(width, height)
                try:
                    calls = []
                    page.on("request", lambda request: calls.append(request.url)
                            if request.url.endswith("/api/calculate") else None)
                    self.fill_case(page, include_rfnbo=False)
                    result = self.calculate(page, view="workbench")
                    details = page.locator("#calculation-details")
                    self.assertFalse(details.evaluate("(node) => node.open"))
                    details.locator("summary").click()
                    self.assertTrue(page.locator("#overview-metrics").is_visible())
                    self.assertEqual(details.locator("form, input, select").count(), 0)
                    details.get_by_role("tab", name="场景明细").click()
                    self.assertEqual(
                        page.locator("#scenario-comparison-table tbody tr").count(),
                        len(result["scenarios"]),
                    )
                    details.get_by_role("tab", name="计算依据").click()
                    self.assertTrue(page.locator("#calculation-basis").is_visible())
                    self.assertFalse(page.evaluate(
                        "document.documentElement.scrollWidth > document.documentElement.clientWidth"
                    ))
                    page.screenshot(path=f"output/calculation-details-{width}.png", full_page=True)
                    details.locator("summary").click()
                    details.locator("summary").focus()
                    page.keyboard.press("Enter")
                    self.assertTrue(details.evaluate("(node) => node.open"))
                    self.assertEqual(len(calls), 1)
                    page.locator("#baseline-mass").fill("101")
                    self.assertFalse(details.is_visible())
                    self.assertFalse(details.evaluate("(node) => node.open"))
                    self.assertNotIn("因子回溯", page.locator("#calculation-basis").inner_text())
                    self.assertTrue(page.locator("#export-csv").is_disabled())
                finally:
                    context.close()


if __name__ == "__main__":
    unittest.main()
