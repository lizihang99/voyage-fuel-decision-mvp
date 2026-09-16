import re
import unittest

from fastapi.testclient import TestClient

from voyage_fuel.web import app


class WebPageContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_root_serves_operational_calculator_with_stable_controls(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.text
        for element_id in (
            "report-year", "departure-port-search", "arrival-port-search",
            "adjacent-port-confirmation", "case-currency", "baseline-fuel",
            "baseline-mass", "baseline-price", "eua-price", "candidate-collection",
            "add-candidate", "calculate-command", "result-boundary-summary",
            "scenario-comparison-table", "new-energy-decision-summary",
            "conditional-recommendations",
            "calculation-basis", "display-precision", "export-csv", "export-pdf",
        ):
            self.assertRegex(html, rf'id=["\']{re.escape(element_id)}["\']')
        self.assertIn("/static/app.js", html)
        self.assertIn("/static/styles.css", html)

    def test_static_assets_are_available_and_js_uses_structured_issues(self):
        script = self.client.get("/static/app.js")
        stylesheet = self.client.get("/static/styles.css")
        self.assertEqual(script.status_code, 200)
        self.assertEqual(stylesheet.status_code, 200)
        source = script.text
        for field in ("issue.code", "issue.field", "issue.blocking", "issue.message"):
            self.assertIn(field, source)
        self.assertNotRegex(source, r'parseInt\s*\([^)]*message|match\s*\([^)]*message')

    def test_page_handles_failed_calculation_and_export_without_stale_results(self):
        source = self.client.get("/static/app.js").text
        self.assertIn("function clearResults()", source)
        self.assertIn("state.result = null", source)
        self.assertRegex(source, r"catch \(error\) \{ clearResults\(\);")
        self.assertIn('code: "EXPORT_ERROR"', source)

    def test_candidate_issues_are_deduplicated_and_match_candidate_id(self):
        source = self.client.get("/static/app.js").text
        self.assertIn("function issueIdentity(issue)", source)
        self.assertIn("function uniqueIssues(issues = [])", source)
        self.assertIn("issue.candidate_id", source)
        self.assertIn('[data-field="candidateId"]', source)

    def test_candidate_legend_is_direct_first_child_of_fieldset(self):
        html = self.client.get("/").text
        self.assertRegex(html, r"<fieldset>\s*<legend>候选燃料报价</legend>")

    def test_advanced_custom_fuel_form_exposes_minimal_factor_contract(self):
        html = self.client.get("/").text
        source = self.client.get("/static/app.js").text
        for field in (
            'data-field="candidateMode"',
            'data-field="customFuelName"',
            'data-field="customFuelType"',
            'data-field="wtTMode"',
            'data-field="lcv"',
            'data-field="wtT"',
            'data-field="cfCO2"',
            'data-field="cfCH4"',
            'data-field="cfN2O"',
            'data-field="cfCH4ZeroEstimate"',
            'data-field="cfN2OZeroEstimate"',
            'data-field="methaneSlipApplicable"',
            'data-field="qualificationStatus"',
            'data-field="sourceId"',
            'data-field="sourceType"',
            'data-field="verificationStatus"',
        ):
            self.assertIn(field, source)
        self.assertIn("sourceEvidence", source)
        self.assertIn("CUSTOM_NON_METHANE", source)
        self.assertIn("RFNBO_E", source)
        self.assertIn("RFNBO 资格未确认", html + source)
        self.assertIn("certified-warning", source)

    def test_page_declares_complete_result_contract_and_decimal_string_formatter(self):
        html = self.client.get("/").text
        source = self.client.get("/static/app.js").text
        for element_id in (
            "port-identity-details", "scenario-detail-table", "ets-fueleu-detail",
            "economics-summary", "switch-points", "baseline-mode", "baseline-custom-editor",
        ):
            self.assertRegex(html, rf'id=[\"\']{re.escape(element_id)}[\"\']')
        for field in (
            "formatDecimalString", "formatField", "physical_energy_mj", "fuel_cost",
            "raw_co2_t", "raw_ch4_t", "raw_n2o_t", "included_gases",
            "excluded_from_ets_surrender", "wt_t_intensity_g_per_mj", "tt_w_intensity_g_per_mj",
            "target_g_per_mj", "indicative_penalty_eur", "compliance_improvement_tco2e",
            "equipment_id", "source_evidence", "EXECUTION_CONDITIONS_PENDING",
        ):
            self.assertIn(field, source)

    def test_new_energy_decision_summary_contract_is_present(self):
        html = self.client.get("/").text
        source = self.client.get("/static/app.js").text
        for label in (
            "新能源决策摘要", "新增燃料成本", "EU ETS 成本节省",
            "净成本变化", "推荐新能源用量", "推荐混兑比例",
        ):
            self.assertIn(label, html + source)
        for field in ("decision_summary", "scenario_deltas", "function renderNewEnergyDecisionSummary"):
            self.assertIn(field, source)

    def test_page_evidence_panel_exposes_field_metadata_and_values(self):
        source = self.client.get("/static/app.js").text
        for field in (
            "item.source_type", "item.unit", "item.verification_status",
            "factor.e_g_per_mj", "factor.eu_g_per_mj", "trace.eligible_biomass_fraction",
        ):
            self.assertIn(field, source)

    def test_baseline_advanced_editor_exposes_same_custom_factor_contract(self):
        html = self.client.get("/").text
        source = self.client.get("/static/app.js").text
        for field in (
            'data-field="baselineMode"', 'data-field="baselineCustomFuelName"',
            'data-field="baselineLcv"', 'data-field="baselineWtT"',
            'data-field="baselineCfCO2"', 'data-field="baselineCfCH4"',
            'data-field="baselineCfN2O"', 'data-field="baselineSourceId"',
            'data-field="baselineSourceType"', 'data-field="baselineVerificationStatus"',
        ):
            self.assertIn(field, html + source)
        self.assertIn("baselineCustom", source)


if __name__ == "__main__":
    unittest.main()
