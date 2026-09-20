"""Browser tests for the contextual teaching guide view."""
import copy
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
from business_case_surfaces import validate_exports


class TeachingGuideViewTests(BrowserAppMixin, unittest.TestCase):
    def test_loaded_example_shows_contextual_notes_and_toggle_does_not_recalculate(self):
        context, page = self.new_page()
        try:
            page.goto(self.base_url + "/?view=workbench", wait_until="networkidle")
            page.locator("#try-examples").click()
            with page.expect_response(lambda response: response.url.endswith("/api/calculate")):
                page.locator('[data-example="basic"]').click()
            page.wait_for_function("!document.getElementById('export-csv').disabled")

            self.assertEqual(page.locator("#case-form #teaching-guide-toggle").count(), 0)
            toggle = page.locator("#teaching-guide-toggle")
            self.assertTrue(toggle.is_checked())
            self.assertEqual(page.locator("[data-guide-note]").count(), 3)
            self.assertEqual(page.locator('[data-guide-active="true"]').count(), 1)
            self.assertIn("这一例看什么", page.locator("#teaching-guide-intro").inner_text())
            self.assertIn("合成数据与资格假设，仅供示例", page.locator("#teaching-guide-intro").inner_text())

            toggle.uncheck()
            self.assertEqual(page.locator("[data-guide-note]").count(), 0)
            self.assertEqual(page.locator('[data-guide-active="true"]').count(), 0)
            self.assertFalse(page.locator("#export-csv").is_disabled())

            toggle.check()
            self.assertEqual(page.locator("[data-guide-note]").count(), 3)
            self.assertFalse(page.locator("#export-csv").is_disabled())
        finally:
            context.close()

    def test_modified_example_removes_notes_until_the_example_is_reloaded(self):
        context, page = self.new_page()
        try:
            page.goto(self.base_url + "/?view=workbench", wait_until="networkidle")
            page.locator("#try-examples").click()
            with page.expect_response(lambda response: response.url.endswith("/api/calculate")):
                page.locator('[data-example="comparison"]').click()
            page.wait_for_function("!document.getElementById('export-csv').disabled")
            self.assertEqual(page.locator("[data-guide-note]").count(), 5)

            hvo = page.locator(".candidate-row").filter(
                has=page.locator('[data-field="candidateId"][value="hvo"]')
            )
            hvo.locator('[data-field="candidateSupplyTonnes"]').fill("0")
            self.assertEqual(page.locator("[data-guide-note]").count(), 0)
            self.assertEqual(page.locator('[data-guide-active="true"]').count(), 0)
            self.assertTrue(page.locator("#export-csv").is_disabled())
        finally:
            context.close()

    def test_guide_module_failure_does_not_block_normal_calculation(self):
        context = self.browser.new_context(
            viewport={"width": 1440, "height": 900},
            accept_downloads=True,
        )
        page = context.new_page()
        try:
            page.route(
                "**/static/teaching-guide-view.mjs",
                lambda route: route.abort(),
            )
            page.goto(self.base_url + "/?view=workbench", wait_until="networkidle")
            page.locator("#try-examples").click()
            with page.expect_response(
                lambda response: response.url.endswith("/api/calculate")
            ):
                page.locator('[data-example="basic"]').click()
            page.wait_for_function("!document.getElementById('export-csv').disabled")
            self.assertEqual(page.locator("[data-guide-note]").count(), 0)
            self.assertTrue(page.locator("#teaching-guide-toggle").is_hidden())
            self.assertFalse(page.locator("#export-pdf").is_disabled())
            self.assertIn(
                "已完成",
                page.locator("#workbench-status").inner_text(),
            )
        finally:
            context.close()

    def test_guide_does_not_overflow_at_320px(self):
        context, page = self.new_page(width=320, height=740)
        try:
            page.goto(self.base_url + "/?view=workbench", wait_until="networkidle")
            page.locator("#try-examples").click()
            with page.expect_response(
                lambda response: response.url.endswith("/api/calculate")
            ):
                page.locator('[data-example="comparison"]').click()
            page.wait_for_function("!document.getElementById('export-csv').disabled")
            self.assertFalse(
                page.evaluate(
                    "document.documentElement.scrollWidth > document.documentElement.clientWidth"
                )
            )
            self.assertTrue(
                page.locator('[data-guide-note="comparison-supply"]').is_visible()
            )
        finally:
            context.close()

    def test_workbench_exposes_semantic_guide_anchors(self):
        context, page = self.new_page()
        try:
            page.goto(self.base_url + "/?view=workbench", wait_until="networkidle")
            page.locator("#try-examples").click()
            with page.expect_response(lambda response: response.url.endswith("/api/calculate")):
                page.locator('[data-example="basic"]').click()
            for anchor in ("cost-breakdown", "ghgi", "fueleu-balance"):
                with self.subTest(example="basic", anchor=anchor):
                    self.assertGreater(
                        page.locator(f'[data-guide-anchor~="{anchor}"]').count(),
                        0,
                    )

            page.locator("#try-examples").click()
            with page.expect_response(lambda response: response.url.endswith("/api/calculate")):
                page.locator('[data-example="comparison"]').click()
            for anchor in ("goals", "detail-charts", "supply-uco-limited"):
                with self.subTest(example="comparison", anchor=anchor):
                    self.assertGreater(
                        page.locator(f'[data-guide-anchor~="{anchor}"]').count(),
                        0,
                    )
            self.assertEqual(
                page.locator(
                    '[data-guide-anchor~="supply-uco-limited"]'
                    '[data-guide-candidate-id="uco-limited"]'
                ).count(),
                1,
            )
            self.assertEqual(page.locator(".teaching-guide-anchor-slot").count(), 0)
        finally:
            context.close()

    def test_view_mounts_one_active_note_per_anchor_and_destroys_cleanly(self):
        context, page = self.new_page()
        try:
            page.goto(self.base_url + "/?view=workbench", wait_until="networkidle")
            result = page.evaluate("""async () => {
                const module = await import("/static/teaching-guide-view.mjs");
                const root = document.createElement("div");
                root.innerHTML = `
                    <section data-guide-anchor="cost-breakdown"><p>成本区域</p></section>
                    <section data-guide-anchor="ghgi"><p>GHGI区域</p></section>
                `;
                document.body.append(root);
                const view = module.createTeachingGuideView({ root });
                const state = { phase: "ready", visible: true };
                const notes = [
                    { id: "basic-cost", anchor: "cost-breakdown", title: "成本", text: "成本说明" },
                    { id: "basic-ghgi", anchor: "ghgi", title: "GHGI", text: "<img src=x onerror=window.__guideXss=1>" },
                    { id: "missing", anchor: "missing-anchor", title: "缺失", text: "不应显示" },
                ];

                view.render({ state, notes });
                const firstCount = root.querySelectorAll("[data-guide-note]").length;
                const firstActive = root.querySelectorAll('[data-guide-active="true"]').length;
                const xssImages = root.querySelectorAll("[data-guide-note] img").length;
                const xssFlag = Boolean(window.__guideXss);

                view.render({ state, notes });
                const secondCount = root.querySelectorAll("[data-guide-note]").length;

                view.render({ state: { ...state, visible: false }, notes });
                const hiddenCount = root.querySelectorAll("[data-guide-note]").length;

                view.destroy();
                const destroyedCount = root.querySelectorAll("[data-guide-note]").length;
                const destroyedActive = root.querySelectorAll("[data-guide-active]").length;
                root.remove();

                return {
                    firstCount,
                    firstActive,
                    xssImages,
                    xssFlag,
                    secondCount,
                    hiddenCount,
                    destroyedCount,
                    destroyedActive,
                };
            }""")
            self.assertEqual(result["firstCount"], 2)
            self.assertEqual(result["firstActive"], 1)
            self.assertEqual(result["xssImages"], 0)
            self.assertFalse(result["xssFlag"])
            self.assertEqual(result["secondCount"], 2)
            self.assertEqual(result["hiddenCount"], 0)
            self.assertEqual(result["destroyedCount"], 0)
            self.assertEqual(result["destroyedActive"], 0)
        finally:
            context.close()

    def test_hidden_details_anchor_mounts_a_visible_note_outside_details(self):
        context, page = self.new_page()
        try:
            page.goto(self.base_url + "/?view=workbench", wait_until="networkidle")
            result = page.evaluate("""async () => {
                const module = await import("/static/teaching-guide-view.mjs");
                const root = document.createElement("div");
                root.innerHTML = `
                    <details id="closed-guide" class="workbench-section">
                        <summary>用量限制与价格影响</summary>
                        <section data-guide-anchor="supply-uco-limited">
                            <p>折叠内容</p>
                        </section>
                    </details>
                `;
                document.body.append(root);
                const view = module.createTeachingGuideView({ root });
                view.render({
                    state: { visible: true },
                    notes: [{
                        id: "comparison-supply",
                        anchor: "supply-uco-limited",
                        title: "供应限制",
                        text: "说明应保持可见",
                    }],
                });
                const note = root.querySelector('[data-guide-note="comparison-supply"]');
                const details = root.querySelector("#closed-guide");
                const result = {
                    noteVisible: Boolean(note && note.getClientRects().length),
                    noteOutsideDetails: Boolean(note && note.parentElement === root),
                    activeOnDetails: details.dataset.guideActive === "true",
                };
                view.destroy();
                root.remove();
                return result;
            }""")
            self.assertTrue(result["noteVisible"])
            self.assertTrue(result["noteOutsideDetails"])
            self.assertTrue(result["activeOnDetails"])
        finally:
            context.close()


class TeachingGuideIndependentTests(BrowserAppMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reference = prepare_reference(ROOT / "tests" / "fixtures" / "business-cases")
        if reference["production_modules_loaded"]:
            raise AssertionError(reference["production_modules_loaded"])
        cls.reference_cases = {
            entry["case"]["id"]: entry for entry in reference["results"]
        }
        super().setUpClass()

    @staticmethod
    def fixture_request(case_id):
        path = ROOT / "tests" / "fixtures" / "business-cases" / case_id / "request.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def load_example(self, page, example):
        page.locator("#try-examples").click()
        with page.expect_response(
            lambda response: response.url.endswith("/api/calculate")
        ) as response_info:
            page.locator(f'[data-example="{example}"]').click()
        page.wait_for_function("!document.getElementById('export-csv').disabled")
        return response_info.value

    def assert_independent(self, case_id, actual):
        entry = self.reference_cases[case_id]
        report = validate_product_result(entry["case"], entry["expected"], actual)
        self.assertTrue(report["passed"], report["differences"][:10])

    def assert_independent_exports(self, page, case_id, actual):
        downloads = {}
        for export in ("csv", "pdf"):
            with page.expect_download() as download_info:
                page.locator(f"#export-{export}").click()
            downloads[export] = Path(download_info.value.path())
        entry = self.reference_cases[case_id]
        export_report = validate_exports(
            entry["case"],
            entry["expected"],
            actual,
            downloads["csv"].read_text(encoding="utf-8-sig"),
            downloads["pdf"].read_bytes(),
        )
        self.assertEqual(export_report["differences"], [])

    def test_basic_result_guide_and_exports_match_independent_reference(self):
        context, page = self.new_page()
        try:
            page.goto(self.base_url + "/?view=workbench", wait_until="networkidle")
            response = self.load_example(page, "basic")
            body = response.json()
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.request.post_data), self.fixture_request("A-2025"))
            self.assert_independent("A-2025", body)
            notes = page.locator("[data-guide-note]")
            self.assertEqual(notes.count(), 3)
            text = "\n".join(notes.all_inner_texts())
            self.assertIn("700000.00 EUR", text)
            self.assertIn("89768.00 EUR", text)
            self.assertIn("789768.00 EUR", text)
            self.assertIn("90.7674 gCO2eq/MJ", text)
            self.assertIn("-30.544320 tCO2e", text)

            self.assert_independent_exports(page, "A-2025", body)
        finally:
            context.close()

    def test_comparison_guide_uses_actual_result_and_rejects_mutations(self):
        context, page = self.new_page()
        try:
            page.goto(self.base_url + "/?view=workbench", wait_until="networkidle")
            response = self.load_example(page, "comparison")
            body = response.json()
            self.assert_independent("B-default", body)
            notes_text = "\n".join(page.locator("[data-guide-note]").all_inner_texts())
            self.assertIn("7.1026%", notes_text)
            self.assertIn("8099.32 EUR", notes_text)
            self.assertIn("70.0000%", notes_text)
            self.assertIn("供应限制下不可达", notes_text)
            self.assertIn("大宗UCO未设置供应量上限", notes_text)
            self.assert_independent_exports(page, "B-default", body)

            entry = self.reference_cases["B-default"]
            mutations = []
            winner = copy.deepcopy(body)
            winner["decision_summary"]["target_min_cost_scenario_id"] = "B0"
            mutations.append(("winner", winner))

            ratio = copy.deepcopy(body)
            target_id = ratio["decision_summary"]["target_min_cost_scenario_id"]
            next(row for row in ratio["scenarios"] if row["scenario_id"] == target_id)["result"]["ratio"] = "0.99"
            mutations.append(("ratio", ratio))

            amount = copy.deepcopy(body)
            amount["baseline_scenario"]["model_cost"] = "1"
            mutations.append(("amount", amount))

            supply = copy.deepcopy(body)
            next(
                candidate for candidate in supply["candidate_results"]
                if candidate["candidate_id"] == "uco-limited"
            )["voyage_result"]["constraints"]["target_status"] = "TARGET_REACHABLE"
            mutations.append(("supply", supply))

            for name, mutated in mutations:
                with self.subTest(mutation=name):
                    report = validate_product_result(
                        entry["case"], entry["expected"], mutated
                    )
                    self.assertFalse(report["passed"], name)
        finally:
            context.close()

    def test_browser_guide_follows_injected_winner_instead_of_frozen_copy(self):
        context, page = self.new_page()
        injected = {}

        def inject_winner(route):
            response = route.fetch()
            body = response.json()
            body["decision_summary"]["target_min_cost_scenario_id"] = "B0"
            injected.update(body)
            route.fulfill(
                status=response.status,
                content_type="application/json",
                body=json.dumps(body),
            )

        try:
            page.route("**/api/calculate", inject_winner)
            page.goto(self.base_url + "/?view=workbench", wait_until="networkidle")
            response = self.load_example(page, "comparison")
            self.assertEqual(response.json()["decision_summary"]["target_min_cost_scenario_id"], "B0")
            target_note = page.locator('[data-guide-note="comparison-target"]')
            self.assertIn("0.0000%", target_note.inner_text())
            self.assertIn("船用柴油", target_note.inner_text())
            report = validate_product_result(
                self.reference_cases["B-default"]["case"],
                self.reference_cases["B-default"]["expected"],
                injected,
            )
            self.assertFalse(report["passed"])
        finally:
            context.close()

    def test_guide_screenshots_are_captured_for_desktop_and_mobile(self):
        output = ROOT / "output" / "contextual-example-tutorial"
        output.mkdir(parents=True, exist_ok=True)
        desktop_context, desktop = self.new_page(width=1440, height=900)
        mobile_context, mobile = self.new_page(width=390, height=844)
        try:
            desktop.goto(self.base_url + "/?view=workbench", wait_until="networkidle")
            self.load_example(desktop, "basic")
            desktop.screenshot(
                path=str(output / "basic-guide-desktop.png"),
                full_page=True,
            )
            desktop.locator("#workbench-selected-detail").screenshot(
                path=str(output / "basic-guide-detail.png"),
            )

            mobile.goto(self.base_url + "/?view=workbench", wait_until="networkidle")
            self.load_example(mobile, "comparison")
            mobile.screenshot(
                path=str(output / "comparison-guide-mobile.png"),
                full_page=True,
            )
            mobile.locator('[data-guide-note="comparison-supply"]').screenshot(
                path=str(output / "comparison-guide-supply-mobile.png"),
            )
            self.assertFalse(
                mobile.evaluate(
                    "document.documentElement.scrollWidth > document.documentElement.clientWidth"
                )
            )
        finally:
            desktop_context.close()
            mobile_context.close()


if __name__ == "__main__":
    unittest.main()
