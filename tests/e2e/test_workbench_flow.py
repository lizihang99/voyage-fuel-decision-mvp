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
            page.locator("#workbench-sensitivity").filter(has_text="敏感性与边界").wait_for()
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
            self.assertIn("B0-only", page.locator("#workbench-sensitivity").inner_text())
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
            self.assertIn("敏感性与边界", visible_text)
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


if __name__ == "__main__":
    unittest.main()
