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
            "scenario-comparison-table", "conditional-recommendations",
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


if __name__ == "__main__":
    unittest.main()
