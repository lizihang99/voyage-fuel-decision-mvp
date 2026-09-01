import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import warnings

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.",
)

from fastapi.testclient import TestClient

from voyage_fuel.web import app


def minimum_payload():
    return {
        "reportYear": 2026,
        "departurePort": "CNSHG",
        "arrivalPort": "NLRTM",
        "adjacentValidPortOfCallConfirmed": True,
        "currency": "EUR",
        "baseline": {"pathId": "MDO", "massTonnes": "100", "pricePerTonne": "700"},
        "euaPricePerTCO2e": "80",
        "candidates": [
            {
                "candidateId": "uco-quote-1",
                "pathId": "UCO_FAME",
                "pricePerTonne": "1000",
                "specifiedBlendRatios": ["0.2"],
                "maxBlendRatio": "0.3",
            },
            {
                "candidateId": "lng-quote-1",
                "pathId": "LNG_OTTO_MEDIUM_SPEED",
                "pricePerTonne": "850",
                "specifiedBlendRatios": ["0.1"],
            },
        ],
    }


class WebApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_reports_service_availability(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_fuels_returns_only_the_open_36_path_catalog(self):
        response = self.client.get("/api/fuels")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["pathIds"]), 36)
        self.assertNotIn("ELECTRICITY_OPS", response.json()["pathIds"])

    def test_port_query_returns_matching_identity_rows_not_the_full_table(self):
        response = self.client.get("/api/ports", params={"q": "rotter"})

        self.assertEqual(response.status_code, 200)
        ports = response.json()["ports"]
        port = next(port for port in ports if port["unlocode"] == "NLRTM")
        self.assertEqual(port["portName"], "Rotterdam")
        self.assertEqual(port["euEtsStatus"], "IN_SCOPE")
        self.assertEqual(port["fuelEuStatus"], "IN_SCOPE")
        self.assertLess(len(ports), 10)

    def test_calculate_returns_shared_baseline_candidates_recommendations_and_decimal_strings(self):
        response = self.client.post("/api/calculate", json=minimum_payload())

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual([item["candidate_id"] for item in result["candidate_results"]], ["uco-quote-1", "lng-quote-1"])
        self.assertEqual([item["scenario_id"] for item in result["scenarios"]].count("B0"), 1)
        self.assertTrue(result["recommendations"])
        self.assertIn("provenance", result)
        self.assertIsInstance(result["baseline_scenario"]["physical_energy_mj"], str)

    def test_case_level_invalid_input_returns_structured_422_issues(self):
        payload = minimum_payload()
        payload["adjacentValidPortOfCallConfirmed"] = False

        response = self.client.post("/api/calculate", json=payload)

        self.assertEqual(response.status_code, 422)
        issue = response.json()["issues"][0]
        self.assertEqual(issue["scope"], "CASE")
        self.assertEqual(issue["code"], "PORT_OF_CALL_CONFIRMATION_REQUIRED")
        self.assertEqual(issue["field"], "adjacentValidPortOfCallConfirmed")

    def test_blocked_candidate_does_not_prevent_unaffected_candidate_calculation(self):
        payload = minimum_payload()
        payload["candidates"][0]["pathId"] = "UNKNOWN_PATH"

        response = self.client.post("/api/calculate", json=payload)

        self.assertEqual(response.status_code, 200)
        candidates = response.json()["candidate_results"]
        self.assertEqual(candidates[0]["calculation_status"], "BLOCKED")
        self.assertEqual(candidates[1]["calculation_status"], "COMPARABLE")
        self.assertEqual(response.json()["scenarios"][0]["scenario_id"], "B0")

    def test_calculate_creates_no_case_file_or_session_cookie(self):
        with TemporaryDirectory() as temporary_directory:
            original_directory = Path.cwd()
            try:
                os.chdir(temporary_directory)
                response = self.client.post("/api/calculate", json=minimum_payload())
            finally:
                os.chdir(original_directory)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(list(Path(temporary_directory).iterdir()), [])
            self.assertNotIn("set-cookie", response.headers)

    def test_export_csv_calculates_server_result_and_returns_auditable_csv(self):
        payload = minimum_payload()
        payload["calculatedResult"] = {"model_cost": "client forged value"}
        response = self.client.post("/api/export/csv", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.headers["content-type"])
        self.assertIn("attachment", response.headers.get("content-disposition", ""))
        self.assertIn("record_type", response.text)
        self.assertIn("scenario", response.text)
        self.assertNotIn("client forged value", response.text)

    def test_export_pdf_returns_complete_nonempty_pdf(self):
        response = self.client.post("/api/export/pdf", json=minimum_payload())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertIn("attachment", response.headers.get("content-disposition", ""))
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertGreater(len(response.content), 1000)

    def test_export_endpoints_preserve_structured_case_errors(self):
        payload = minimum_payload()
        payload["adjacentValidPortOfCallConfirmed"] = False
        for path in ("/api/export/csv", "/api/export/pdf"):
            response = self.client.post(path, json=payload)
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.json()["issues"][0]["code"], "PORT_OF_CALL_CONFIRMATION_REQUIRED")


if __name__ == "__main__":
    unittest.main()
