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


if __name__ == "__main__":
    unittest.main()
