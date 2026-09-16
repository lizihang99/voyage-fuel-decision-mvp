import os
import csv
import json
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
        ranked = [(int(row[10]), row[0], float(row[4].replace(",", ""))) for row in rows if row[10].isdigit()]
        self.assertGreaterEqual(len(ranked), 3)
        self.assertEqual([rank for rank, _, _ in sorted(ranked)], list(range(1, len(ranked) + 1)))
        expected = sorted(
            ((float(item["result"]["model_cost"]), item["scenario_id"]) for item in raw_result["scenarios"] if item.get("current_model_cost_rank") is not None),
            key=lambda item: (item[0], item[1]),
        )
        self.assertEqual([scenario_id for _, scenario_id in expected], [scenario_id for _, scenario_id, _ in sorted(ranked)])

class MVPFlowTests(BrowserAppMixin, unittest.TestCase):
    def test_complete_result_contract_is_visible_across_result_panels(self):
        context, page = self.new_page()
        try:
            self.fill_case(page, include_rfnbo=False)
            self.calculate(page)
            overview = page.locator("#overview-panel").inner_text()
            self.assertIn("Shanghai Pt", overview)
            self.assertIn("Rotterdam", overview)
            self.assertIn("THIRD_COUNTRY", overview)
            self.assertIn("IN_SCOPE", overview)
            self.assertIn("EU ETS CO2", overview)
            self.assertIn("FuelEU WtT", overview)
            self.assertIn("相对 B0", overview)
            for label in ("新能源决策摘要", "新增燃料成本", "EU ETS 成本节省", "净成本变化", "推荐新能源用量", "推荐混兑比例"):
                self.assertIn(label, overview)

            page.get_by_role("tab", name="Scenarios").click()
            scenarios = page.locator("#scenarios-panel").inner_text()
            for label in ("燃料质量", "物理能源", "燃料成本", "EU ETS CH4", "EU ETS N2O", "纳入气体", "排除气体", "EUAs", "EUA 成本", "FuelEU TtW", "指示性罚款"):
                self.assertIn(label, scenarios)

            page.get_by_role("tab", name="Thresholds").click()
            thresholds = page.locator("#thresholds-panel").inner_text()
            for label in ("目标", "预算", "供应量", "最大混合比例", "最大改善比例"):
                self.assertIn(label, thresholds)

            page.get_by_role("tab", name="Evidence").click()
            evidence = page.locator("#evidence-panel").inner_text()
            for label in ("设备", "因子模式", "因子状态", "资格", "来源 ID", "ETS effective rate"):
                self.assertIn(label, evidence)
            self.assertIn("EXECUTION_CONDITIONS_PENDING", overview)
        finally:
            context.close()

    def test_baseline_advanced_custom_mode_submits_minimal_factor_payload(self):
        context, page = self.new_page()
        try:
            self.choose_port(page, "#departure-port-search", "CNSHG")
            self.choose_port(page, "#arrival-port-search", "NLRTM")
            page.locator("#case-currency").select_option("EUR")
            page.locator("#baseline-mode").select_option("custom")
            editor = page.locator("#baseline-custom-editor")
            self.assertTrue(editor.is_visible())
            editor.locator('[data-field="baselineCustomFuelName"]').fill("Baseline Custom Fuel")
            editor.locator('[data-field="baselineLcv"]').fill("0.04")
            editor.locator('[data-field="baselineWtT"]').fill("10")
            editor.locator('[data-field="baselineCfCO2"]').fill("3")
            editor.locator('[data-field="baselineCfCH4ZeroEstimate"]').check()
            editor.locator('[data-field="baselineCfN2OZeroEstimate"]').check()
            editor.locator('[data-field="baselineSourceId"]').fill("BASE-SUP-1")
            page.locator("#baseline-mass").fill("100")
            page.locator("#baseline-price").fill("700")
            page.locator("#eua-price").fill("80")
            self.fill_candidate(page, 0, candidate_id="uco", path_id="UCO_FAME", price="1000", ratio="0.2")
            with page.expect_response(lambda response: response.url.endswith("/api/calculate") and response.request.method == "POST") as response_info:
                page.locator("#calculate-command").click()
            response = response_info.value
            self.assertEqual(response.status, 200)
            request_payload = json.loads(response.request.post_data)
            baseline = request_payload["baseline"]
            self.assertTrue(baseline["custom"])
            self.assertTrue(baseline["pathId"].startswith("CUSTOM_BASELINE"))
            self.assertEqual(baseline["equipmentId"], "CUSTOM_NON_METHANE")
            self.assertEqual(baseline["cslip"], "NA")
            self.assertEqual(baseline["cfCH4"], "0")
            self.assertEqual(baseline["cfN2O"], "0")
            self.assertEqual(baseline["sourceEvidence"]["lcv"][0]["sourceId"], "BASE-SUP-1")
        finally:
            context.close()

    def test_custom_fuel_form_builds_minimal_backend_factor_payload(self):
        context, page = self.new_page()
        try:
            self.choose_port(page, "#departure-port-search", "CNSHG")
            self.choose_port(page, "#arrival-port-search", "NLRTM")
            page.locator("#case-currency").select_option("EUR")
            page.locator("#baseline-fuel").select_option("MDO")
            page.locator("#baseline-mass").fill("100")
            page.locator("#baseline-price").fill("700")
            page.locator("#eua-price").fill("80")

            row = page.locator(".candidate-row").first
            row.locator('[data-field="candidateMode"]').select_option("custom")
            self.assertTrue(row.locator(".custom-editor").is_visible())
            self.assertFalse(row.locator('[data-field="cslip"]').is_visible())
            self.assertFalse(row.locator('[data-field="csfCO2"]').is_visible())

            row.locator('[data-field="candidateId"]').fill("custom-waste-oil")
            row.locator('[data-field="customFuelName"]').fill("Waste Oil")
            row.locator('[data-field="lcv"]').fill("0.04")
            row.locator('[data-field="wtT"]').fill("10")
            row.locator('[data-field="cfCO2"]').fill("3")
            row.locator('[data-field="cfCH4ZeroEstimate"]').check()
            row.locator('[data-field="cfN2OZeroEstimate"]').check()
            row.locator('[data-field="pricePerTonne"]').fill("900")
            row.locator('[data-field="specifiedBlendRatios"]').fill("0.2")
            row.locator('[data-field="sourceId"]').fill("SUP-123")

            with page.expect_response(lambda response: response.url.endswith("/api/calculate") and response.request.method == "POST") as response_info:
                page.locator("#calculate-command").click()
            response = response_info.value
            self.assertEqual(response.status, 200)
            result = response.json()
            self.assertEqual(result["candidate_results"][0]["calculation_status"], "COMPARABLE")
            self.assertEqual(result["candidate_results"][0]["voyage_result"]["candidate_factor"]["factor_status"], "ESTIMATED")
            body = json.loads(response.request.post_data)
            custom = body["candidates"][0]
            self.assertTrue(custom["custom"])
            self.assertEqual(custom["pathId"], custom["customPathId"])
            self.assertTrue(custom["pathId"].startswith("CUSTOM_FUEL_"))
            self.assertEqual(custom["equipmentId"], "CUSTOM_NON_METHANE")
            self.assertEqual(custom["cslip"], "NA")
            self.assertFalse(custom["methaneSlipApplicable"])
            self.assertEqual(custom["rwd"], "1")
            self.assertEqual(custom["eligibleBiomassFraction"], "0")
            self.assertEqual(custom["cfCH4"], "0")
            self.assertEqual(custom["cfN2O"], "0")
            self.assertEqual(custom["sourceEvidence"]["lcv"][0]["sourceId"], "SUP-123")
            self.assertEqual(custom["sourceEvidence"]["cfCH4"][0]["verificationStatus"], "ESTIMATED")
            page.locator("#result-run-status").filter(has_text="已完成").wait_for()
        finally:
            context.close()

    def test_unqualified_custom_rfnbo_is_locked_to_non_rfnbo_mode(self):
        context, page = self.new_page()
        try:
            row = page.locator(".candidate-row").first
            row.locator('[data-field="candidateMode"]').select_option("custom")
            row.locator('[data-field="customProfile"]').select_option("rfnbo")
            row.locator('[data-field="wtTMode"]').select_option("RFNBO_E")
            self.assertTrue(row.locator('[data-field="rfnbo-warning"]').is_visible())
            self.assertEqual(row.locator('[data-field="wtTMode"]').input_value(), "STATIC")
            self.assertFalse(row.locator('[data-field="e"]').is_visible())
            self.assertTrue(row.locator('[data-field="wtT"]').is_visible())
        finally:
            context.close()

    def test_unqualified_custom_biofuel_keeps_bio_e_formula(self):
        context, page = self.new_page()
        try:
            self.choose_port(page, "#departure-port-search", "CNSHG")
            self.choose_port(page, "#arrival-port-search", "NLRTM")
            page.locator("#baseline-fuel").select_option("MDO")
            page.locator("#baseline-mass").fill("100")
            page.locator("#baseline-price").fill("700")
            page.locator("#eua-price").fill("80")
            row = page.locator(".candidate-row").first
            row.locator('[data-field="candidateMode"]').select_option("custom")
            row.locator('[data-field="customFuelName"]').fill("Unqualified Biofuel")
            row.locator('[data-field="customProfile"]').select_option("biofuel")
            row.locator('[data-field="wtTMode"]').select_option("BIO_E")
            self.assertEqual(row.locator('[data-field="wtTMode"]').input_value(), "BIO_E")
            row.locator('[data-field="lcv"]').fill("0.037")
            row.locator('[data-field="e"]').fill("14.9")
            row.locator('[data-field="cfCO2"]').fill("2.834")
            row.locator('[data-field="cfCH4ZeroEstimate"]').check()
            row.locator('[data-field="cfN2OZeroEstimate"]').check()
            row.locator('[data-field="pricePerTonne"]').fill("900")
            row.locator('[data-field="specifiedBlendRatios"]').fill("0.2")
            row.locator('[data-field="sourceId"]').fill("BIO-SUP-1")
            with page.expect_response(lambda response: response.url.endswith("/api/calculate") and response.request.method == "POST") as response_info:
                page.locator("#calculate-command").click()
            response = response_info.value
            self.assertEqual(response.status, 200)
            result = response.json()
            self.assertEqual(result["candidate_results"][0]["calculation_status"], "COMPARABLE")
            self.assertEqual(result["candidate_results"][0]["voyage_result"]["candidate_factor"]["factor_status"], "ESTIMATED")
            body = json.loads(response.request.post_data)
            custom = body["candidates"][0]
            self.assertEqual(custom["wtTMode"], "BIO_E")
            self.assertEqual(custom["eligibleBiomassFraction"], "0")
        finally:
            context.close()

    def test_custom_candidate_path_ids_are_unique_for_duplicate_names(self):
        context, page = self.new_page()
        try:
            self.choose_port(page, "#departure-port-search", "CNSHG")
            self.choose_port(page, "#arrival-port-search", "NLRTM")
            page.locator("#baseline-fuel").select_option("MDO")
            page.locator("#baseline-mass").fill("100")
            page.locator("#baseline-price").fill("700")
            page.locator("#eua-price").fill("80")
            for index in range(2):
                if index:
                    page.locator("#add-candidate").click()
                row = page.locator(".candidate-row").nth(index)
                row.locator('[data-field="candidateMode"]').select_option("custom")
                row.locator('[data-field="customFuelName"]').fill("Same Name Fuel")
            with page.expect_response(lambda response: response.url.endswith("/api/calculate") and response.request.method == "POST") as response_info:
                page.locator("#calculate-command").click()
            response = response_info.value
            self.assertEqual(response.status, 200)
            body = json.loads(response.request.post_data)
            path_ids = [candidate["pathId"] for candidate in body["candidates"]]
            self.assertEqual(len(path_ids), len(set(path_ids)))
        finally:
            context.close()

    def test_generated_candidate_ids_stay_unique_after_remove_and_add(self):
        context, page = self.new_page()
        try:
            page.locator("#add-candidate").click()
            page.locator(".candidate-row").first.locator(".remove-candidate").click()
            page.locator("#add-candidate").click()
            candidate_ids = page.locator('[data-field="candidateId"]').evaluate_all("inputs => inputs.map(input => input.value)")
            self.assertEqual(len(candidate_ids), len(set(candidate_ids)))
        finally:
            context.close()

    def test_qualified_custom_rfnbo_shows_rule_defined_rwd(self):
        context, page = self.new_page()
        try:
            row = page.locator(".candidate-row").first
            row.locator('[data-field="candidateMode"]').select_option("custom")
            row.locator('[data-field="customProfile"]').select_option("rfnbo")
            row.locator('[data-field="qualificationStatus"]').select_option("ASSUMED_ELIGIBLE")
            row.locator('[data-field="wtTMode"]').select_option("RFNBO_E")
            rwd = row.locator('[data-field="rwd"]')
            self.assertTrue(rwd.is_visible())
            self.assertEqual(rwd.input_value(), "2")
            self.assertTrue(rwd.is_editable() is False)
        finally:
            context.close()

    def test_custom_gas_shows_slip_factors_only_for_nonzero_cslip(self):
        context, page = self.new_page()
        try:
            row = page.locator(".candidate-row").first
            row.locator('[data-field="candidateMode"]').select_option("custom")
            row.locator('[data-field="customFuelType"]').select_option("gas")
            self.assertTrue(row.locator('[data-field="cslip"]').is_visible())
            self.assertFalse(row.locator('[data-field="csfCO2"]').is_visible())
            row.locator('[data-field="cslip"]').fill("1.5")
            self.assertTrue(row.locator('[data-field="csfCO2"]').is_visible())
            self.assertTrue(row.locator('[data-field="csfCH4"]').is_visible())
            self.assertTrue(row.locator('[data-field="csfN2O"]').is_visible())
        finally:
            context.close()

    def test_custom_gas_can_explicitly_disable_methane_slip(self):
        context, page = self.new_page()
        try:
            self.choose_port(page, "#departure-port-search", "CNSHG")
            self.choose_port(page, "#arrival-port-search", "NLRTM")
            page.locator("#baseline-fuel").select_option("MDO")
            page.locator("#baseline-mass").fill("100")
            page.locator("#baseline-price").fill("700")
            page.locator("#eua-price").fill("80")
            row = page.locator(".candidate-row").first
            row.locator('[data-field="candidateMode"]').select_option("custom")
            row.locator('[data-field="customFuelType"]').select_option("gas")
            self.assertEqual(row.locator('[data-field="methaneSlipApplicable"]').count(), 1)
            row.locator('[data-field="methaneSlipApplicable"]').select_option("false")
            self.assertFalse(row.locator('[data-field="cslip"]').is_visible())
            self.assertFalse(row.locator('[data-field="csfCO2"]').is_visible())
            row.locator('[data-field="customFuelName"]').fill("Gaseous Hydrogen")
            row.locator('[data-field="lcv"]').fill("0.12")
            row.locator('[data-field="wtT"]').fill("132")
            row.locator('[data-field="cfCO2"]').fill("0")
            row.locator('[data-field="cfCH4ZeroEstimate"]').check()
            row.locator('[data-field="cfN2OZeroEstimate"]').check()
            row.locator('[data-field="pricePerTonne"]').fill("1200")
            row.locator('[data-field="specifiedBlendRatios"]').fill("0.2")
            row.locator('[data-field="sourceId"]').fill("H2-SUP-1")
            with page.expect_response(lambda response: response.url.endswith("/api/calculate") and response.request.method == "POST") as response_info:
                page.locator("#calculate-command").click()
            response = response_info.value
            self.assertEqual(response.status, 200)
            body = json.loads(response.request.post_data)
            custom = body["candidates"][0]
            self.assertEqual(custom["equipmentId"], "CUSTOM_GAS")
            self.assertFalse(custom["methaneSlipApplicable"])
            self.assertEqual(custom["cslip"], "NA")
        finally:
            context.close()

    def test_custom_editor_state_survives_candidate_collection_rerender(self):
        context, page = self.new_page()
        try:
            row = page.locator(".candidate-row").first
            stable_path_id = row.get_attribute("data-custom-path-id")
            row.locator('[data-field="candidateMode"]').select_option("custom")
            row.locator('[data-field="customFuelName"]').fill("Persistent Fuel")
            row.locator('[data-field="customProfile"]').select_option("biofuel")
            row.locator('[data-field="cfCH4ZeroEstimate"]').check()
            page.locator("#add-candidate").click()
            restored = page.locator(".candidate-row").first
            self.assertEqual(restored.locator('[data-field="candidateMode"]').input_value(), "custom")
            self.assertEqual(restored.locator('[data-field="customFuelName"]').input_value(), "Persistent Fuel")
            self.assertEqual(restored.locator('[data-field="customProfile"]').input_value(), "biofuel")
            self.assertTrue(restored.locator('[data-field="cfCH4ZeroEstimate"]').is_checked())
            self.assertTrue(restored.locator(".custom-editor").is_visible())
            self.assertEqual(restored.get_attribute("data-custom-path-id"), stable_path_id)
        finally:
            context.close()

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
                [(row[0], row[10]) for row in scenario_rows_before_precision],
                [(row[0], row[10]) for row in scenario_rows_after_precision],
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
