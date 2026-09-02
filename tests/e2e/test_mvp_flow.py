import os
import csv
import shutil
import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
PYTHON = Path(os.environ.get("VOYAGE_FUEL_PYTHON", sys.executable))


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _browser_executable() -> str | None:
    configured = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
    if configured and Path(configured).exists():
        return configured
    chrome = shutil.which("chrome") or shutil.which("chromium")
    if chrome:
        return chrome
    candidates = sorted(Path(os.environ.get("LOCALAPPDATA", ""), "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
    return str(candidates[-1]) if candidates else None


class BrowserAppMixin:
    @classmethod
    def setUpClass(cls):
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        cls.port = _free_port()
        env = os.environ.copy()
        if not os.environ.get("VOYAGE_FUEL_USE_INSTALLED_PACKAGE"):
            env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
        cls.server = subprocess.Popen(
            [str(PYTHON), "-m", "voyage_fuel.web", "--host", "127.0.0.1", "--port", str(cls.port)],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        deadline = time.time() + 15
        import urllib.request
        while time.time() < deadline:
            try:
                if urllib.request.urlopen(cls.base_url + "/health", timeout=1).status == 200:
                    break
            except Exception:
                time.sleep(0.1)
        else:
            cls.server.kill()
            raise RuntimeError("voyage-fuel-web did not become healthy")
        cls.playwright = sync_playwright().start()
        executable = _browser_executable()
        launch_options = {"headless": True}
        if executable:
            launch_options["executable_path"] = executable
        cls.browser = cls.playwright.chromium.launch(**launch_options)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.terminate()
        try:
            cls.server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.server.kill()

    def new_page(self, width=1440, height=900):
        context = self.browser.new_context(viewport={"width": width, "height": height}, accept_downloads=True)
        page = context.new_page()
        page.goto(self.base_url + "/", wait_until="networkidle")
        page.locator("#baseline-fuel").wait_for()
        return context, page

    @staticmethod
    def choose_port(page, field_id, code):
        page.locator(field_id).fill(code)
        page.locator(f"{field_id.replace('-search', '-options')} .lookup-option").filter(has_text=code).first.click()

    @staticmethod
    def fill_candidate(page, index, *, candidate_id, path_id, price, ratio, max_ratio="1"):
        row = page.locator(".candidate-row").nth(index)
        row.locator('[data-field="candidateId"]').fill(candidate_id)
        row.locator('[data-field="pathId"]').select_option(path_id)
        row.locator('[data-field="pricePerTonne"]').fill(price)
        row.locator('[data-field="maxBlendRatio"]').fill(max_ratio)
        row.locator('[data-field="specifiedBlendRatios"]').fill(ratio)

    def fill_case(self, page, *, include_rfnbo=True):
        self.choose_port(page, "#departure-port-search", "CNSHG")
        self.choose_port(page, "#arrival-port-search", "NLRTM")
        page.locator("#case-currency").select_option("EUR")
        page.locator("#baseline-fuel").select_option("MDO")
        page.locator("#baseline-mass").fill("100")
        page.locator("#baseline-price").fill("700")
        page.locator("#eua-price").fill("80")
        self.fill_candidate(page, 0, candidate_id="uco-quote-1", path_id="UCO_FAME", price="1000", ratio="0.2", max_ratio="0.3")
        page.locator("#add-candidate").click()
        self.fill_candidate(page, 1, candidate_id="lng-quote-1", path_id="LNG_OTTO_MEDIUM_SPEED", price="850", ratio="0.1", max_ratio="0.5")
        if include_rfnbo:
            page.locator("#add-candidate").click()
            self.fill_candidate(page, 2, candidate_id="rfnbo-no-proof", path_id="E_DIESEL", price="900", ratio="0.1", max_ratio="0.2")

    def calculate(self, page):
        with page.expect_response(lambda response: response.url.endswith("/api/calculate") and response.request.method == "POST") as response_info:
            page.locator("#calculate-command").click()
        response = response_info.value
        self.assertEqual(response.status, 200)
        page.locator("#result-run-status").filter(has_text="已完成").wait_for()
        return response.json()

    @staticmethod
    def scenario_rows(page):
        return page.locator("#scenario-comparison-table tbody tr").evaluate_all(
            "rows => rows.map(row => [...row.cells].map(cell => cell.innerText.trim()))"
        )

    def assert_cost_ranking(self, page, raw_result):
        rows = self.scenario_rows(page)
        ranked = [(int(row[7]), row[0], float(row[4].replace(",", ""))) for row in rows if row[7].isdigit()]
        self.assertGreaterEqual(len(ranked), 3)
        self.assertEqual([rank for rank, _, _ in sorted(ranked)], list(range(1, len(ranked) + 1)))
        expected = sorted(
            ((float(item["result"]["model_cost"]), item["scenario_id"]) for item in raw_result["scenarios"] if item.get("current_model_cost_rank") is not None),
            key=lambda item: (item[0], item[1]),
        )
        self.assertEqual([scenario_id for _, scenario_id in expected], [scenario_id for _, scenario_id, _ in sorted(ranked)])

class MVPFlowTests(BrowserAppMixin, unittest.TestCase):
    def test_complete_desktop_and_mobile_flow(self):
        context, page = self.new_page()
        try:
            self.fill_case(page)
            raw_before = self.calculate(page)
            page.screenshot(path=str(ARTIFACTS / "desktop-results.png"), full_page=True)
            page.get_by_role("tab", name="Scenarios").click()
            body = page.locator("#scenarios-panel").inner_text()
            self.assertIn("B0", body)
            self.assertIn("uco-quote-1@0.2", body)
            self.assertIn("lng-quote-1@0.1", body)
            self.assertIn("EXECUTION_CONDITIONS_PENDING", body)
            self.assertIn("TARGET_REACHABLE", page.locator("#thresholds-panel").inner_text())
            self.assertRegex(page.locator("#thresholds-panel").inner_text(), r"目标最低成本比例")
            self.assertRegex(page.locator("#thresholds-panel").inner_text(), r"2\.2131%")
            scenario_rows_before_precision = self.scenario_rows(page)
            self.assertEqual(scenario_rows_before_precision[0][0], "B0")
            self.assert_cost_ranking(page, raw_before)

            page.get_by_role("tab", name="Evidence").click()
            evidence = page.locator("#evidence-panel").inner_text()
            self.assertIn("PORT-02", evidence)
            self.assertIn("FACTOR-CATALOG", evidence)
            self.assertIn("RFNBO_QUALIFICATION_NOT_DEMONSTRATED", evidence)

            with page.expect_download() as download_info:
                page.locator("#export-csv").click()
            csv_download = download_info.value
            csv_path = ARTIFACTS / "desktop-result.csv"
            csv_download.save_as(csv_path)
            self.assertGreater(csv_path.stat().st_size, 50)
            with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
                csv_rows = list(csv.DictReader(csv_file))
            self.assertIn("record_type", csv_rows[0])
            self.assertGreaterEqual(len(csv_rows), 10)
            self.assertEqual({row["record_type"] for row in csv_rows} & {"case", "port", "scenario"}, {"case", "port", "scenario"})
            case_row = next(row for row in csv_rows if row["record_type"] == "case")
            self.assertEqual(case_row["report_year"], "2026")
            self.assertEqual(case_row["departure_port"], "CNSHG")
            self.assertEqual(case_row["arrival_port"], "NLRTM")
            scenario_rows = [row for row in csv_rows if row["record_type"] == "scenario"]
            self.assertTrue({row["scenario_id"] for row in scenario_rows} >= {"B0", "uco-quote-1@0.2", "lng-quote-1@0.1"})
            self.assertTrue(any(row["execution_status"] == "EXECUTION_CONDITIONS_PENDING" for row in scenario_rows))
            with page.expect_download() as download_info:
                page.locator("#export-pdf").click()
            pdf_download = download_info.value
            pdf_path = ARTIFACTS / "desktop-result.pdf"
            pdf_download.save_as(pdf_path)
            self.assertGreater(pdf_path.stat().st_size, 1000)
            self.assertTrue(pdf_path.read_bytes().startswith(b"%PDF"))
            pdf_text = " ".join((page.extract_text() or "") for page in PdfReader(str(pdf_path)).pages)
            pdf_text = " ".join(pdf_text.split()).lower()
            self.assertIn("report year: 2026", pdf_text)
            self.assertIn("cnshg", pdf_text)
            self.assertIn("nlrtm", pdf_text)
            self.assertIn("b0", pdf_text)
            self.assertIn("uco-quote-1@0.2", pdf_text)
            self.assertIn("lng-quote-1@0.1", pdf_text)
            self.assertIn("execution_conditions_pending", pdf_text)
            self.assertIn("voyage-level proportional estimate", pdf_text)
            self.assertIn("not an annual legal penalty", pdf_text)

            scenario_ids_before = [row["scenario_id"] for row in raw_before["scenarios"]]
            page.locator("#precision-price").fill("0")
            page.locator("#precision-ratio").fill("1")
            page.wait_for_timeout(100)
            scenario_rows_after_precision = self.scenario_rows(page)
            self.assertEqual(
                [(row[0], row[7]) for row in scenario_rows_before_precision],
                [(row[0], row[7]) for row in scenario_rows_after_precision],
            )
            self.assert_cost_ranking(page, raw_before)
            api_after = page.request.post(self.base_url + "/api/calculate", data=page.evaluate("""() => ({
              reportYear: 2026, departurePort: 'CNSHG', arrivalPort: 'NLRTM', adjacentValidPortOfCallConfirmed: true,
              currency: 'EUR', baseline: {pathId: 'MDO', massTonnes: '100', pricePerTonne: '700'}, euaPricePerTCO2e: '80',
              candidates: [{candidateId:'uco-quote-1',pathId:'UCO_FAME',pricePerTonne:'1000',maxBlendRatio:'0.3',specifiedBlendRatios:['0.2']},
              {candidateId:'lng-quote-1',pathId:'LNG_OTTO_MEDIUM_SPEED',pricePerTonne:'850',maxBlendRatio:'0.5',specifiedBlendRatios:['0.1']},
              {candidateId:'rfnbo-no-proof',pathId:'E_DIESEL',pricePerTonne:'900',maxBlendRatio:'0.2',specifiedBlendRatios:['0.1']}]
            })""")).json()
            self.assertEqual(scenario_ids_before, [row["scenario_id"] for row in api_after["scenarios"]])
            self.assertEqual(raw_before["scenarios"], api_after["scenarios"])
            page.reload(wait_until="networkidle")
            self.assertEqual(page.locator("#result-run-status").inner_text(), "尚未计算")
            self.assertIn("暂无结果", page.locator("#overview-metrics").inner_text())
        finally:
            context.close()

        context, page = self.new_page(390, 844)
        try:
            self.fill_case(page, include_rfnbo=False)
            self.calculate(page)
            page.screenshot(path=str(ARTIFACTS / "mobile-results.png"), full_page=True)
            page.get_by_role("tab", name="Scenarios").click()
            page.locator("#scenarios-panel").wait_for()
            comparison_scroll = page.locator("#scenarios-panel .table-scroll").evaluate(
                "el => ({scrollWidth: el.scrollWidth, clientWidth: el.clientWidth})"
            )
            page.get_by_role("tab", name="Thresholds").click()
            threshold_scroll = page.locator("#thresholds-panel .table-scroll").evaluate(
                "el => ({scrollWidth: el.scrollWidth, clientWidth: el.clientWidth})"
            )
            self.assertGreater(comparison_scroll["scrollWidth"], comparison_scroll["clientWidth"])
            self.assertGreater(threshold_scroll["scrollWidth"], threshold_scroll["clientWidth"])
            overflow = page.evaluate("""() => {
              const root = document.documentElement;
              return root.scrollWidth - root.clientWidth;
            }""")
            self.assertEqual(overflow, 0, f"unexpected page overflow: {overflow}px")
            page.locator("#calculate-command").scroll_into_view_if_needed()
            box = page.locator("#calculate-command").bounding_box()
            self.assertIsNotNone(box)
            self.assertGreaterEqual(box["x"], 0)
            self.assertLessEqual(box["x"] + box["width"], 390)
            self.assertGreater(page.locator(".table-scroll").count(), 0)
        finally:
            context.close()

    def test_blocked_custom_candidate_does_not_hide_builtin_result(self):
        context, page = self.new_page()
        try:
            page.locator("#report-year").fill("2026")
            page.locator("#adjacent-port-confirmation").check()
            page.locator("#case-currency").select_option("EUR")
            self.choose_port(page, "#departure-port-search", "CNSHG")
            self.choose_port(page, "#arrival-port-search", "NLRTM")
            page.locator("#baseline-fuel").select_option("MDO")
            page.locator("#baseline-mass").fill("100")
            page.locator("#baseline-price").fill("700")
            page.locator("#eua-price").fill("80")
            self.fill_candidate(page, 0, candidate_id="custom-blocked", path_id="MDO", price="900", ratio="0.2")
            page.locator("#add-candidate").click()
            self.fill_candidate(page, 1, candidate_id="uco-ok", path_id="UCO_FAME", price="1000", ratio="0.2")
            # An unknown path is parsed as custom and blocked for missing evidence/fields.
            page.locator(".candidate-row").nth(0).locator('[data-field="pathId"]').evaluate("select => { const option = new Option('UNKNOWN_PATH', 'UNKNOWN_PATH'); select.add(option); select.value = 'UNKNOWN_PATH'; }")
            result = self.calculate(page)
            self.assertEqual(result["candidate_results"][0]["calculation_status"], "BLOCKED")
            self.assertEqual(result["candidate_results"][1]["calculation_status"], "COMPARABLE")
            self.assertIn("MISSING_REQUIRED_FACTOR", page.locator("#result-issues").inner_text())
            page.screenshot(path=str(ARTIFACTS / "desktop-blocked-candidate.png"), full_page=True)
        finally:
            context.close()


if __name__ == "__main__":
    unittest.main()
