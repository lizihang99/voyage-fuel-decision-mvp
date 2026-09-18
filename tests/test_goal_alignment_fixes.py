import csv
import io
from pathlib import Path
import unittest

from fastapi.testclient import TestClient
from pypdf import PdfReader

from voyage_fuel.case_calculator import calculate_decision_case
from voyage_fuel.json_io import parse_decision_case
from voyage_fuel.reports import decision_case_to_csv, decision_case_to_pdf
from voyage_fuel.web import app


def payload(*, candidates=None, year=2026, include_prices=True):
    baseline = {"pathId": "MDO", "massTonnes": "100"}
    if include_prices:
        baseline["pricePerTonne"] = "700"
    return {
        "reportYear": year,
        "departurePort": "CNSHG",
        "arrivalPort": "NLRTM",
        "adjacentValidPortOfCallConfirmed": True,
        "currency": "EUR",
        "baseline": baseline,
        "euaPricePerTCO2e": "80" if include_prices else None,
        "candidates": [{
            "candidateId": "uco",
            "pathId": "UCO_FAME",
            "pricePerTonne": "1000" if include_prices else None,
            "specifiedBlendRatios": ["0.2"],
            "maxBlendRatio": "0.3",
        }] if candidates is None else candidates,
    }


class GoalAlignmentFixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_calculate_returns_snapshot_and_exports_require_that_snapshot(self):
        calculated = self.client.post("/api/calculate", json=payload())
        self.assertEqual(calculated.status_code, 200)
        snapshot_id = calculated.json()["result_snapshot_id"]

        missing = self.client.post("/api/export/csv", json=payload())
        self.assertEqual(missing.status_code, 409)
        self.assertEqual(missing.json()["issues"][0]["code"], "RESULT_SNAPSHOT_REQUIRED")

        exported = self.client.post("/api/export/csv", json={
            "resultSnapshotId": snapshot_id,
            "calculatedResult": {"model_cost": "client forged value"},
        })
        self.assertEqual(exported.status_code, 200)
        self.assertIn("scenario", exported.text)
        self.assertNotIn("client forged value", exported.text)

    def test_empty_candidate_case_returns_b0_without_new_energy_recommendations(self):
        parsed = parse_decision_case(payload(candidates=[]))
        self.assertIsNotNone(parsed.request)
        result = calculate_decision_case(parsed.request, parsed.issues)
        self.assertIsNotNone(result.baseline_scenario)
        self.assertEqual([row.scenario_id for row in result.scenarios], ["B0"])
        self.assertEqual(result.candidate_results, ())
        self.assertEqual(result.recommendations, ())
        self.assertIsNone(result.decision_summary)

        response = self.client.post("/api/calculate", json=payload(candidates=[]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["scenario_id"] for row in response.json()["scenarios"]], ["B0"])

    def test_case_exports_expose_candidate_break_even_thresholds(self):
        parsed = parse_decision_case(payload())
        result = calculate_decision_case(parsed.request, parsed.issues)
        rows = list(csv.DictReader(io.StringIO(decision_case_to_csv(result))))
        threshold = next(row for row in rows if row["record_type"] == "candidate_economics")
        self.assertEqual(threshold["candidate_id"], "uco")
        self.assertTrue(threshold["pc_break_even"])
        self.assertTrue(threshold["pe_break_even_status"])

        text = "\n".join(page.extract_text() or "" for page in PdfReader(
            io.BytesIO(decision_case_to_pdf(result))
        ).pages)
        self.assertIn("Candidate fuel break-even price", text)
        self.assertIn("EUA break-even price", text)

    def test_public_result_carries_reasons_for_key_null_fields(self):
        parsed = parse_decision_case(payload(year=2024, include_prices=False))
        result = calculate_decision_case(parsed.request, parsed.issues)
        self.assertEqual(
            result.field_reasons["scenarios.B0.result.eu_ets.eua_cost"],
            "EUA_PRICE_NOT_PROVIDED",
        )
        self.assertEqual(
            result.field_reasons["scenarios.B0.result.fuel_eu.target_g_per_mj"],
            "NOT_YET_APPLICABLE",
        )
        self.assertEqual(
            result.field_reasons["candidate_results.uco.economics.pc_break_even"],
            "PRICE_REQUIRED_FOR_COMPARISON",
        )

        rows = list(csv.DictReader(io.StringIO(decision_case_to_csv(result))))
        self.assertTrue(any(
            row["record_type"] == "field_reason"
            and row["reason_code"] == "EUA_PRICE_NOT_PROVIDED"
            for row in rows
        ))

    def test_page_uses_explicit_candidate_mass_share_wording(self):
        root = Path(__file__).parents[1]
        source = (
            (root / "src/voyage_fuel/templates/index.html").read_text(encoding="utf-8")
            + (root / "src/voyage_fuel/static/app.js").read_text(encoding="utf-8")
        )
        for label in (
            "候选燃料质量占比",
            "最大候选燃料质量占比",
            "指定候选燃料质量占比",
            "推荐候选燃料质量占比",
        ):
            self.assertIn(label, source)


if __name__ == "__main__":
    unittest.main()
