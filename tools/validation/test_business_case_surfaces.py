"""Independent export checks, fault injection, and screenshot-free browser tests."""

import copy
import csv
import io
import re
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from tools.validation.business_case_surfaces import validate_exports
from tests.e2e.test_mvp_flow import BrowserAppMixin


def hand_case(year=2026, zero_scope=False, blocked=False):
    def component(path, wtt, co2, price):
        fields = {
            "lcv": ("MJ/gFuel", ".04"), "wtT": ("gCO2eq/MJ", wtt),
            "cfCO2": ("gGHG/gFuel", co2), "cfCH4": ("gGHG/gFuel", "0"),
            "cfN2O": ("gGHG/gFuel", "0"), "cslip": ("%", "NA"),
            "methaneSlipApplicable": ("boolean", False), "rwd": ("ratio", "1"),
            "eligibleBiomassFraction": ("fraction", "0"),
        }
        return {
            "custom": True, "pathId": path, "equipmentId": "SURFACE_TEST",
            "wtTMode": "STATIC", "pricePerTonne": price,
            "qualificationStatus": "NOT_DEMONSTRATED",
            **{k: v for k, (_, v) in fields.items()},
            "sourceEvidence": {
                k: {"sourceId": "SYNTHETIC-SURFACE", "sourceType": "TEST",
                    "unit": unit, "verificationStatus": "ESTIMATED"}
                for k, (unit, _) in fields.items()
            },
        }

    def factor(path, wtt, co2):
        return dict(path_id=path, lcv=".04", wtt=wtt, co2=co2, ch4="0",
                    n2o="0", slip=None, methane=False, rwd="1", biomass="0",
                    factor_status="ESTIMATED", qualification="NOT_DEMONSTRATED",
                    mode="STATIC", equipment_id="SURFACE_TEST",
                    source_ids=["SYNTHETIC-SURFACE"])

    candidate = dict(component("clean", "35", "1", "1000"),
                     candidateId="clean", maxBlendRatio=".6",
                     candidateAllowsPureUse=False, specifiedBlendRatios=[".2"])
    issues = []
    if blocked:
        del candidate["cfCO2"]
        issues = [{"code": "MISSING_REQUIRED_FACTOR", "scope": "CANDIDATE",
                   "candidate_id": "clean"}]
    return {
        "id": "A-surface-hand", "family": "A", "compact": True,
        "request": {
            "reportYear": year, "departurePort": "CNSHG",
            "arrivalPort": "SGSIN" if zero_scope else "NLRTM",
            "adjacentValidPortOfCallConfirmed": True, "currency": "EUR",
            "baseline": dict(component("baseline", "25", "3", "600"),
                             massTonnes="100"),
            "euaPricePerTCO2e": "80", "candidates": [candidate],
        },
        "snapshot": {
            "scope": {"geo": "0" if zero_scope else ".5",
                      "surrender": {2024: ".4", 2025: ".7"}.get(year, "1"),
                      "fueleu": None if year == 2024 else "0" if zero_scope else ".5"},
            "baseline": factor("baseline", "25", "3"),
            "candidates": {} if blocked else {"clean": factor("clean", "35", "1")},
        },
        "expected_issues": issues, "expected_http_status": 200,
    }


def exports(client, case):
    response = client.post("/api/calculate", json=case["request"])
    if response.status_code != 200:
        raise AssertionError(response.text)
    actual = response.json()
    snapshot = {"resultSnapshotId": actual["result_snapshot_id"]}
    csv_response = client.post("/api/export/csv", json=snapshot)
    pdf_response = client.post("/api/export/pdf", json=snapshot)
    if csv_response.status_code != 200 or pdf_response.status_code != 200:
        raise AssertionError((csv_response.text, pdf_response.status_code))
    return actual, csv_response.text, pdf_response.content


def rewrite_csv(text, mutate):
    reader = csv.DictReader(io.StringIO(text))
    columns = reader.fieldnames
    rows = list(reader)
    mutate(rows)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


class ExportValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from voyage_fuel.web import app
        from tools.validation.business_case_reference import calculate_reference
        cls.client = TestClient(app)
        cls.case = hand_case()
        cls.expected = calculate_reference(cls.case)
        cls.actual, cls.csv_text, cls.pdf_bytes = exports(cls.client, cls.case)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def check(self, csv_text=None, pdf_bytes=None, actual=None):
        return validate_exports(
            self.case, self.expected, self.actual if actual is None else actual,
            self.csv_text if csv_text is None else csv_text,
            self.pdf_bytes if pdf_bytes is None else pdf_bytes,
        )

    def test_independent_values_match_real_snapshot_exports(self):
        result = self.check()
        self.assertEqual(result["differences"], [])
        self.assertGreater(result["assertions"], 300)

    def test_product_values_are_not_an_oracle(self):
        actual = copy.deepcopy(self.actual)
        for scenario in actual["scenarios"]:
            scenario["result"]["model_cost"] = "999999999"
            scenario["deltas"] = {}
            scenario["calculation_status"] = "WRONG"
        actual["field_reasons"] = {}
        self.assertEqual(self.check(actual=actual)["differences"], [])

    def test_csv_corruption_even_when_product_output_agrees_is_detected(self):
        actual = copy.deepcopy(self.actual)
        actual["scenarios"][0]["result"]["model_cost"] = "999"
        def mutate(rows):
            for row in rows:
                if row["scenario_id"] == "B0" and row["metric_name"] == "model_cost":
                    row["absolute"] = "999"
        result = self.check(rewrite_csv(self.csv_text, mutate), actual=actual)
        self.assertTrue(any("model_cost.absolute" in d["path"] for d in result["differences"]))

    def test_status_reason_and_missing_duplicate_metrics_are_detected(self):
        for mutation in ("status", "reason", "missing", "duplicate"):
            with self.subTest(mutation=mutation):
                def mutate(rows):
                    row = next(r for r in rows if r["record_type"] == "scenario"
                               and r["scenario_id"] == "B0" and r["metric_name"] == "ratio")
                    if mutation == "status":
                        row["constraint_status"] = "CONSTRAINT_INFEASIBLE"
                    elif mutation == "reason":
                        row["reason_code"] = ""
                    elif mutation == "missing":
                        rows.remove(row)
                    else:
                        rows.append(dict(row))
                self.assertTrue(self.check(rewrite_csv(self.csv_text, mutate))["differences"])

    def test_missing_decision_group_or_metric_and_case_scope_are_detected(self):
        for kind in ("group", "metric", "scope"):
            with self.subTest(kind=kind):
                def mutate(rows):
                    if kind == "scope":
                        next(r for r in rows if r["record_type"] == "case")["eu_ets_scope_rate"] = "1"
                    elif kind == "group":
                        rows[:] = [r for r in rows if r["record_type"] != "decision_summary"]
                    else:
                        rows.remove(next(r for r in rows if r["record_type"] == "decision_summary"))
                self.assertTrue(self.check(rewrite_csv(self.csv_text, mutate))["differences"])

    def test_missing_recommendation_switch_and_economics_records_are_detected(self):
        def mutate(rows):
            rows[:] = [
                row for row in rows
                if not (
                    row["record_type"] == "decision_summary"
                    and row.get("decision_type") != "BASELINE"
                )
                and row["record_type"] not in {
                    "switch_point", "recommendation", "economics", "candidate_economics",
                }
            ]
        result = self.check(rewrite_csv(self.csv_text, mutate))
        paths = " ".join(item["path"] for item in result["differences"])
        for fragment in ("decisions.required", "switch_points.count",
                         "recommendations", "economics"):
            self.assertIn(fragment, paths)

    def test_pdf_numeric_and_status_faults_are_detected_in_labelled_rows(self):
        from pypdf import PdfReader
        original = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(self.pdf_bytes)).pages)
        for text in (
            original.replace("72000.00", "99999.00"),
            re.sub(r"F\s*E\s*A\s*S\s*I\s*B\s*L\s*E", "CORRUPTED", original),
            original.replace("60000.00", "60000.01"),
        ):
            with self.subTest():
                self.assertNotEqual(text, original)
                with patch("tools.validation.business_case_surfaces._pdf_text", return_value=text):
                    self.assertTrue(self.check()["differences"])

    def test_null_values_reasons_and_blocked_candidate_keep_b0(self):
        from tools.validation.business_case_reference import calculate_reference
        for case in (hand_case(year=2024), hand_case(zero_scope=True), hand_case(blocked=True)):
            with self.subTest(year=case["request"]["reportYear"], snapshot=case["snapshot"]["scope"]):
                actual, csv_text, pdf_bytes = exports(self.client, case)
                expected = calculate_reference(case)
                result = validate_exports(case, expected, actual, csv_text, pdf_bytes)
                self.assertEqual(result["differences"], [])
                self.assertIn("B0", {row["scenario_id"] for row in actual["scenarios"]})
                if not case["snapshot"]["candidates"]:
                    continue
                def mutate(rows):
                    row = next(r for r in rows if r["record_type"] == "scenario"
                               and r["metric_name"] == "fueleu_ghgi_actual_g_per_mj")
                    row["absolute"] = "0"
                self.assertTrue(validate_exports(
                    case, expected, actual, rewrite_csv(csv_text, mutate), pdf_bytes
                )["differences"])
                def drop_reasons(rows):
                    rows[:] = [r for r in rows if r["record_type"] != "field_reason"]
                self.assertTrue(validate_exports(
                    case, expected, actual, rewrite_csv(csv_text, drop_reasons), pdf_bytes
                )["differences"])

    def test_malformed_exports_report_differences_instead_of_passing(self):
        result = self.check(csv_text="bad,column\n1,2\n", pdf_bytes=b"not a PDF")
        self.assertGreater(result["assertions"], 0)
        self.assertTrue(result["differences"])

    def test_missing_price_and_budget_preserve_null_and_unverified_status(self):
        from tools.validation.business_case_reference import calculate_reference
        case = hand_case()
        del case["request"]["candidates"][0]["pricePerTonne"]
        case["request"]["candidates"][0]["incrementalBudget"] = "100"
        expected = calculate_reference(case)
        actual, csv_text, pdf_bytes = exports(self.client, case)
        self.assertEqual(validate_exports(case, expected, actual, csv_text, pdf_bytes)["differences"], [])
        def mutate(rows):
            for row in rows:
                if row["record_type"] == "scenario" and row["candidate_id"] == "clean":
                    row["constraint_status"] = "FEASIBLE"
        checked = validate_exports(case, expected, actual, rewrite_csv(csv_text, mutate), pdf_bytes)
        self.assertTrue(any("constraint_status" in d["path"] for d in checked["differences"]))

    def test_case_level_block_requires_absent_exports_without_reading_actual(self):
        expected = {"baseline": None, "candidates": {}, "status": "BLOCKED"}
        result = validate_exports({}, expected, None, "", b"")
        self.assertEqual(result, {"assertions": 2, "differences": []})
        leaked = validate_exports({}, expected, None, self.csv_text, self.pdf_bytes)
        self.assertEqual(len(leaked["differences"]), 2)

    def test_baseline_price_missing_is_not_replaced_with_zero(self):
        from tools.validation.business_case_reference import calculate_reference
        case = hand_case()
        del case["request"]["baseline"]["pricePerTonne"]
        actual, csv_text, pdf_bytes = exports(self.client, case)
        result = validate_exports(case, calculate_reference(case), actual, csv_text, pdf_bytes)
        self.assertEqual(result["differences"], [])

    def test_wrong_nullable_reason_detected_in_csv_and_pdf(self):
        from tools.validation.business_case_reference import calculate_reference
        from pypdf import PdfReader
        case = hand_case(year=2024)
        actual, csv_text, pdf_bytes = exports(self.client, case)
        expected = calculate_reference(case)
        def mutate(rows):
            row = next(r for r in rows if r["record_type"] == "field_reason"
                       and r["metric_name"] == "scenarios.B0.result.fuel_eu.ghgi_actual_g_per_mj")
            row["reason_code"] = "OUT_OF_SCOPE"
        checked = validate_exports(case, expected, actual, rewrite_csv(csv_text, mutate), pdf_bytes)
        self.assertTrue(any(d["path"] == "csv.reasons.scenarios.B0.result.fuel_eu.ghgi_actual_g_per_mj"
                            for d in checked["differences"]))
        text = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf_bytes)).pages)
        corrupted = re.sub(r"N\s*O\s*T\s*_\s*Y\s*E\s*T\s*_\s*A\s*P\s*P\s*L\s*I\s*C\s*A\s*B\s*L\s*E",
                           "OUT_OF_SCOPE", text)
        self.assertNotEqual(corrupted, text)
        with patch("tools.validation.business_case_surfaces._pdf_text", return_value=corrupted):
            checked = validate_exports(case, expected, actual, csv_text, pdf_bytes)
        self.assertTrue(any(d["path"].startswith("pdf.reasons.") for d in checked["differences"]))

    def test_missing_b0_and_blocked_candidate_status_faults_are_detected(self):
        from tools.validation.business_case_reference import calculate_reference
        case = hand_case(blocked=True)
        expected = calculate_reference(case)
        actual, csv_text, pdf_bytes = exports(self.client, case)
        for kind in ("baseline", "blocked"):
            with self.subTest(kind=kind):
                def mutate(rows):
                    if kind == "baseline":
                        rows[:] = [r for r in rows if r["scenario_id"] != "B0"]
                    else:
                        for row in rows:
                            if row["record_type"] == "constraints":
                                row["calculation_status"] = "COMPARABLE"
                self.assertTrue(validate_exports(
                    case, expected, actual, rewrite_csv(csv_text, mutate), pdf_bytes
                )["differences"])


class BusinessCaseBrowserTests(BrowserAppMixin, unittest.TestCase):
    """No screenshots, recordings, tutorials, or persistent browser artifacts."""

    def assert_reference_rows(self, page, case, expected, actual):
        from tools.validation.business_case_reference import ledger
        from tools.validation.business_case_surfaces import _display, _metrics, _constraint
        rendered = {row[0]: row for row in self.scenario_rows(page)}
        self.assertIn("B0", rendered)
        for identity in actual["scenarios"]:
            sid, cid = identity["scenario_id"], identity.get("candidate_id")
            book = expected["baseline"] if cid is None else ledger(
                case, cid, identity["result"]["ratio"])
            values = _metrics(book, expected["baseline"])
            self.assertIn(sid, rendered)
            row = rendered[sid]
            for column, key, places, scale in (
                (3, "ratio", 4, 100), (4, "model_cost", 2, 1),
                (8, "fueleu_ghgi_actual_g_per_mj", 4, 1),
                (9, "fueleu_compliance_balance_t", 6, 1),
                (13, "fuel_cost", 2, 1), (19, "euas_required", 6, 1),
                (20, "eua_cost", 2, 1), (24, "fueleu_indicative_penalty_eur", 2, 1),
            ):
                observed = row[column].replace(",", "").replace("%", "").strip()
                self.assertEqual(observed, _display(values[key], places, scale), (sid, key))
            self.assertIn(_constraint(book), row[2])
            self.assertIn("EXECUTION_CONDITIONS_PENDING", row[2])
        if expected["baseline"]["fueleu"]["ghgi"] is None:
            self.assertEqual(rendered["B0"][8], "-")
            self.assertEqual(rendered["B0"][9], "-")
            self.assertIn(expected["baseline"]["fueleu"]["status"],
                          page.locator("#thresholds-content").inner_text())
        for cid, candidate in expected["candidates"].items():
            if candidate["status"] == "BLOCKED":
                self.assertFalse(any(row[1] == cid for row in rendered.values()))
                self.assertIn(cid, page.locator("#thresholds-content").inner_text())
                self.assertIn("BLOCKED", page.locator("#thresholds-content").inner_text())

    def fill_synthetic_form(self, page, case):
        request = case["request"]
        self.choose_port(page, "#departure-port-search", request["departurePort"])
        self.choose_port(page, "#arrival-port-search", request["arrivalPort"])
        page.locator("#report-year").fill(str(request["reportYear"]))
        page.locator("#baseline-mode").select_option("custom")
        editor = page.locator("#baseline-custom-editor")
        for field, value in (
            ("baselineCustomFuelName", "Synthetic Baseline"), ("baselineLcv", ".04"),
            ("baselineWtT", "25"), ("baselineCfCO2", "3"),
            ("baselineSourceId", "SYNTHETIC-SURFACE"),
        ):
            editor.locator(f'[data-field="{field}"]').fill(value)
        editor.locator('[data-field="baselineCfCH4ZeroEstimate"]').check()
        editor.locator('[data-field="baselineCfN2OZeroEstimate"]').check()
        page.locator("#baseline-mass").fill("100")
        page.locator("#baseline-price").fill("600")
        page.locator("#eua-price").fill("80")
        page.locator("#case-currency").select_option("EUR")
        row = page.locator(".candidate-row").first
        row.locator('[data-field="candidateMode"]').select_option("custom")
        for field, value in (
            ("candidateId", "clean"), ("customFuelName", "Synthetic Clean"),
            ("lcv", ".04"), ("wtT", "35"), ("cfCO2", "1"),
            ("sourceId", "SYNTHETIC-SURFACE"), ("pricePerTonne", "1000"),
            ("maxBlendRatio", ".6"), ("specifiedBlendRatios", ".2"),
        ):
            row.locator(f'[data-field="{field}"]').fill(value)
        row.locator('[data-field="cfCH4ZeroEstimate"]').check()
        row.locator('[data-field="cfN2OZeroEstimate"]').check()
        row.locator('[data-field="candidateAllowsPureUse"]').uncheck()

    def assert_browser_exports(self, page, case, expected, actual):
        snapshot = {"resultSnapshotId": actual["result_snapshot_id"]}
        csv_response = page.request.post(self.base_url + "/api/export/csv", data=snapshot)
        pdf_response = page.request.post(self.base_url + "/api/export/pdf", data=snapshot)
        self.assertEqual(csv_response.status, 200)
        self.assertEqual(pdf_response.status, 200)
        checked = validate_exports(case, expected, actual, csv_response.text(), pdf_response.body())
        self.assertEqual(checked["differences"], [], case["id"])

    def test_actual_form_entry_normal_2024_and_zero_scope(self):
        from tools.validation.business_case_reference import calculate_reference
        for case in (hand_case(), hand_case(year=2024), hand_case(zero_scope=True)):
            with self.subTest(year=case["request"]["reportYear"],
                              arrival=case["request"]["arrivalPort"]):
                context, page = self.new_page()
                try:
                    self.fill_synthetic_form(page, case)
                    actual = self.calculate(page)
                    expected = calculate_reference(case)
                    self.assert_reference_rows(page, case, expected, actual)
                    self.assert_browser_exports(page, case, expected, actual)
                    with page.expect_request("**/api/export/csv") as export_request:
                        with page.expect_download():
                            page.locator("#export-csv").click()
                    self.assertEqual(export_request.value.post_data_json["resultSnapshotId"],
                                     actual["result_snapshot_id"])
                finally:
                    context.close()

    def render_real_api_response(self, page, case):
        response = page.request.post(self.base_url + "/api/calculate", data=case["request"])
        self.assertEqual(response.status, case["expected_http_status"])
        actual = response.json()
        # API-injected rendering: this does not exercise the case's input widgets.
        page.route("**/api/calculate", lambda route: route.fulfill(status=response.status, json=actual))
        page.locator("#calculate-command").click()
        page.wait_for_function(
            "() => document.querySelector('#scenario-comparison-table tbody')"
            ".innerText.includes('B0')"
        )
        return actual

    def test_api_injected_compact_a_to_d_rendering_desktop_and_mobile(self):
        from tools.validation.business_case_inputs import cases
        from tools.validation.business_case_reference import calculate_reference
        available = cases()
        representatives = [
            next(c for c in available if c["family"] == family and c["compact"]
                 and c["expected_http_status"] == 200)
            for family in "ABCD"
        ]
        self.assertEqual({c["family"] for c in representatives}, set("ABCD"))
        for width in (1440, 390):
            for case in representatives:
                with self.subTest(case=case["id"], width=width):
                    context, page = self.new_page(width)
                    try:
                        actual = self.render_real_api_response(page, case)
                        expected = calculate_reference(case)
                        self.assert_reference_rows(page, case, expected, actual)
                        self.assert_browser_exports(page, case, expected, actual)
                    finally:
                        context.close()

    def test_api_injected_blocked_candidate_retains_baseline(self):
        from tools.validation.business_case_reference import calculate_reference
        case = hand_case(blocked=True)
        for width in (1440, 390):
            with self.subTest(width=width):
                context, page = self.new_page(width)
                try:
                    actual = self.render_real_api_response(page, case)
                    expected = calculate_reference(case)
                    self.assert_reference_rows(page, case, expected, actual)
                    self.assert_browser_exports(page, case, expected, actual)
                    self.assertTrue(page.locator("#export-csv").is_enabled())
                finally:
                    context.close()


if __name__ == "__main__":
    unittest.main()
