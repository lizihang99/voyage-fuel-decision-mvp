"""Route and asset contracts for the decision workbench view."""

import unittest

from fastapi.testclient import TestClient

from voyage_fuel.web import app


class WorkbenchPageContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_root_still_defaults_to_legacy_view(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn('data-view="legacy"', response.text)
        self.assertNotIn('id="workbench-root"', response.text)

    def test_explicit_workbench_route(self):
        response = self.client.get("/", params={"view": "workbench"})

        self.assertEqual(response.status_code, 200)
        self.assertIn('data-view="workbench"', response.text)
        self.assertIn('id="workbench-root"', response.text)
        for hook in (
            'id="workbench-goal-cards"',
            'id="workbench-scenario-table"',
            'id="workbench-selected-detail"',
            'id="workbench-sensitivity"',
            'id="workbench-evidence"',
        ):
            self.assertIn(hook, response.text)
        self.assertIn("/static/workbench.css", response.text)
        source = self.client.get("/static/app.js").text
        self.assertIn('import("/static/workbench-view.mjs")', source)

    def test_explicit_legacy_route(self):
        response = self.client.get("/", params={"view": "legacy"})

        self.assertEqual(response.status_code, 200)
        self.assertIn('data-view="legacy"', response.text)
        self.assertIn('id="scenario-comparison-table"', response.text)

    def test_invalid_view_is_rejected(self):
        response = self.client.get("/", params={"view": "../legacy"})

        self.assertEqual(response.status_code, 422)

    def test_workbench_assets_are_available(self):
        for path in (
            "/static/workbench.css",
            "/static/workbench-view.mjs",
            "/static/workbench-model.mjs",
            "/static/workbench-charts.mjs",
            "/static/workbench-labels.mjs",
            "/static/display-values.mjs",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
