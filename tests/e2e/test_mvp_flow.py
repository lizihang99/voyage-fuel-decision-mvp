import os
import shutil
import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


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
            self.assertIn("1", page.locator("#scenario-comparison-table").inner_text())

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
            self.assertIn("record_type", csv_path.read_text(encoding="utf-8-sig"))
            with page.expect_download() as download_info:
                page.locator("#export-pdf").click()
            pdf_download = download_info.value
            pdf_path = ARTIFACTS / "desktop-result.pdf"
            pdf_download.save_as(pdf_path)
            self.assertGreater(pdf_path.stat().st_size, 1000)
            self.assertTrue(pdf_path.read_bytes().startswith(b"%PDF"))

            scenario_ids_before = [row["scenario_id"] for row in raw_before["scenarios"]]
            page.locator("#precision-price").fill("0")
            page.locator("#precision-ratio").fill("1")
            page.wait_for_timeout(100)
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
            overflow = page.evaluate("""() => {
              const root = document.documentElement;
              const intentional = [...document.querySelectorAll('.tabs, .table-scroll')]
                .some(el => el.scrollWidth > el.clientWidth);
              return { page: root.scrollWidth - root.clientWidth, intentional };
            }""")
            self.assertTrue(overflow["intentional"])
            self.assertLessEqual(overflow["page"], 100, f"unexpected page overflow: {overflow['page']}px")
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
            self.choose_port(page, "#departure-port-search", "CNSHG")
            self.choose_port(page, "#arrival-port-search", "NLRTM")
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
