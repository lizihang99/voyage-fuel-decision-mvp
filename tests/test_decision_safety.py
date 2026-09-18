"""Regressions for permission, feasibility, and report boundaries."""

import csv
import io
import unittest
from dataclasses import replace
from decimal import Decimal as D

from fastapi.testclient import TestClient
from pypdf import PdfReader

from voyage_fuel.calculator import calculate_voyage
from voyage_fuel.case_calculator import calculate_parsed_decision_case
from voyage_fuel.contracts import CandidateInput
from voyage_fuel.json_io import parse_decision_case
from voyage_fuel.web import app
from tests.test_c_layer_fixes import component, request
from tests.test_case_json_io import minimum_payload


class DecisionSafetyTests(unittest.TestCase):
    @staticmethod
    def export_payload(client, payload):
        calculated = client.post("/api/calculate", json=payload)
        return {"resultSnapshotId": calculated.json()["result_snapshot_id"]}

    def test_direct_contracts_reject_explicit_unpermitted_pure_use(self):
        req = request()
        with self.assertRaisesRegex(ValueError, "INVALID_BLEND_RATIO"):
            replace(req, candidate_allows_pure_use=False, specified_blend_ratios=(D(1),))
        with self.assertRaisesRegex(ValueError, "INVALID_BLEND_RATIO"):
            CandidateInput("bad", req.candidate_component, specified_blend_ratios=(D(1),))

    def test_all_automatic_endpoints_respect_pure_use_permission(self):
        # This candidate reaches the target only at exactly B100.
        req = replace(
            request(baseline=component("base", "95", "1000"),
                    candidate=component("candidate", "89.3368", "400")),
            candidate_allows_pure_use=False,
        )
        for extra in ({}, {"incremental_budget": D("1000000")},
                      {"candidate_supply_tonnes": D("1000000")}):
            with self.subTest(extra=extra):
                result = calculate_voyage(replace(req, **extra))
                self.assertNotIn(D(1), [s.ratio for s in result.scenarios])
                self.assertEqual(result.constraints.x_target_min, D(1))
        allowed = calculate_voyage(replace(req, candidate_allows_pure_use=True))
        self.assertIn(D(1), [s.ratio for s in allowed.scenarios])

    def test_pure_use_api_error_is_local_to_the_candidate(self):
        payload = minimum_payload()
        payload["candidates"][1]["specifiedBlendRatios"] = ["1"]
        with TestClient(app) as client:
            response = client.post("/api/calculate", json=payload)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertIsNotNone(result["baseline_scenario"])
        issues = [i for c in result["candidate_results"] for i in c["issues"]
                  if i["candidate_id"] == "lng-quote-1"]
        self.assertTrue(issues, "Unpermitted B100 must produce a candidate issue")
        issue = issues[0]
        self.assertEqual(issue["code"], "INVALID_BLEND_RATIO")
        self.assertEqual(issue["field"], "candidates[1].specifiedBlendRatios[0]")
        self.assertNotIn("lng-quote-1@1", [s["scenario_id"] for s in result["scenarios"]])

    def test_unpriced_budget_is_unverified_but_other_constraints_still_apply(self):
        req = replace(
            request(candidate=component("candidate", "60", "400")),
            baseline_component=replace(request().baseline_component, price_per_tonne=None),
            incremental_budget=D("1000"), max_blend_ratio=D(".5"),
            specified_blend_ratios=(D(".25"),), candidate_supply_tonnes=D("10"),
        )
        result = calculate_voyage(req)
        self.assertIn("BUDGET_UNAVAILABLE_WITHOUT_PRICES", result.constraints.warning_codes)
        for scenario in result.scenarios:
            if scenario.ratio == 0:
                self.assertEqual(scenario.constraint_status, "FEASIBLE")
            elif scenario.ratio > result.constraints.x_cap:
                self.assertEqual(scenario.constraint_status, "CONSTRAINT_INFEASIBLE")
            else:
                self.assertEqual(scenario.constraint_status, "CONSTRAINT_UNVERIFIED")

    def test_unverified_budget_excludes_candidate_from_recommendations_and_exports(self):
        payload = minimum_payload()
        payload["candidates"][0].update(
            pricePerTonne=None, incrementalBudget="1000", candidateSupplyTonnes=None)
        result = calculate_parsed_decision_case(parse_decision_case(payload))
        rec = next(r for r in result.recommendations
                   if r.recommendation_id == "MAX_COMPLIANCE_IMPROVEMENT:uco-quote-1")
        self.assertEqual(rec.status, "UNAVAILABLE")
        self.assertEqual(rec.reason, "BUDGET_UNAVAILABLE_WITHOUT_PRICES")
        self.assertFalse((result.economics.max_improvement_scenario_id or "").startswith("uco-"))
        with TestClient(app) as client:
            export_payload = self.export_payload(client, payload)
            rows = list(csv.DictReader(io.StringIO(
                client.post("/api/export/csv", json=export_payload).text)))
            pdf = client.post("/api/export/pdf", json=export_payload).content
        uco_rows = [r for r in rows if r["record_type"] == "scenario"
                    and r["candidate_id"] == "uco-quote-1"]
        self.assertTrue(uco_rows)
        self.assertTrue(all(r["constraint_status"] == "CONSTRAINT_UNVERIFIED" for r in uco_rows))
        pdf_text = "".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)
        self.assertIn("CONSTRAINT_UNVERIFIED", "".join(pdf_text.split()))

    def test_non_eur_reports_keep_penalty_currency_separate(self):
        payload = minimum_payload()
        payload["currency"] = "USD"
        with TestClient(app) as client:
            export_payload = self.export_payload(client, payload)
            pdf = client.post("/api/export/pdf", json=export_payload).content
            rows = list(csv.DictReader(io.StringIO(
                client.post("/api/export/csv", json=export_payload).text)))
        pdf_text = "".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)
        self.assertIn("No currency conversion", pdf_text)
        self.assertIn("Indicative penalty equivalent (EUR)", " ".join(pdf_text.split()))
        penalty_rows = [r for r in rows if r.get("metric_name") == "fueleu_indicative_penalty_eur"]
        self.assertTrue(penalty_rows)
        self.assertTrue(all(r["currency"] == "USD" and r["value_currency"] == "EUR"
                            for r in penalty_rows))


if __name__ == "__main__":
    unittest.main()
