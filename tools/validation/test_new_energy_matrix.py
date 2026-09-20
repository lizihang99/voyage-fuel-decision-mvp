"""Expanded boundary/portfolio matrix plus relations independent of formulas."""
from copy import deepcopy
from decimal import Decimal as D
from fractions import Fraction as F
import unittest

from fastapi.testclient import TestClient
from c_layer_inputs import decimal
from new_energy_matrix import expanded_cases, expanded_portfolios
from new_energy_reference import hand_case, business_values, optimal_references, custom_payload
from test_new_energy_cross_validation import IndependentDecisionAssertions, request
from voyage_fuel.case_calculator import calculate_decision_case
from voyage_fuel.web import app


class ExpandedDecisionTests(IndependentDecisionAssertions, unittest.TestCase):
    def test_expanded_type_matrix_against_independent_reference(self):
        for case in expanded_cases():
            with self.subTest(id=case["id"], category=case["category"], label=case["label"]):
                self.assert_case([case], calculate_decision_case(request([case])))

    def test_portfolios_of_two_three_five_and_eight_candidates(self):
        for cases in expanded_portfolios():
            with self.subTest(portfolio=cases[0]["id"], candidates=len(cases)):
                original = calculate_decision_case(request(cases))
                self.assert_case(cases, original)
                reversed_result = calculate_decision_case(request(list(reversed(cases))))
                self.assert_case(list(reversed(cases)), reversed_result)
                for field in ("cost_min_scenario_id", "target_min_cost_scenario_id", "max_improvement_scenario_id"):
                    self.assertEqual(getattr(original.decision_summary, field), getattr(reversed_result.decision_summary, field))

    def test_voyage_scaling_preserves_optimal_ratios(self):
        case = hand_case()
        case.update(supply="40", budget="12800")
        original = calculate_decision_case(request([case]))
        original_rows = {row.scenario_id: row for row in original.scenarios}
        for scale in (".000001", ".01", "10", "10000"):
            with self.subTest(scale=scale):
                scaled = deepcopy(case)
                for field in ("mass", "supply", "budget"):
                    scaled[field] = decimal(F(case[field]) * F(scale))
                result = calculate_decision_case(request([scaled]))
                self.assert_case([scaled], result)
                for field in ("cost_min_scenario_id", "target_min_cost_scenario_id", "max_improvement_scenario_id"):
                    self.assertEqual(getattr(original.decision_summary, field), getattr(result.decision_summary, field))
                for row in result.scenarios:
                    before = original_rows[row.scenario_id]
                    for field in ("candidate_mass_tonnes", "baseline_mass_tonnes", "physical_energy_mj", "fuel_cost", "model_cost"):
                        self.close(getattr(row.result, field), F(getattr(before.result, field)) * F(scale), "scale " + field)
                    self.close(row.result.fuel_eu.ghgi_actual_g_per_mj,
                               before.result.fuel_eu.ghgi_actual_g_per_mj, "scale intensity")

    def test_price_scaling_preserves_choices_and_physical_results(self):
        case = hand_case()
        case.update(budget="12800", supply="40")
        original = calculate_decision_case(request([case]))
        for scale in (".01", "2", "1000"):
            with self.subTest(scale=scale):
                scaled = deepcopy(case)
                for component in ("baseline", "candidate"):
                    scaled[component]["price"] = decimal(F(case[component]["price"]) * F(scale))
                for field in ("eua", "budget"):
                    scaled[field] = decimal(F(case[field]) * F(scale))
                result = calculate_decision_case(request([scaled]))
                self.assert_case([scaled], result)
                self.assertEqual([r.scenario_id for r in result.scenarios], [r.scenario_id for r in original.scenarios])
                for before, after in zip(original.scenarios, result.scenarios):
                    self.close(after.result.candidate_mass_tonnes, before.result.candidate_mass_tonnes, "price scaling mass")
                    self.close(after.result.model_cost, F(before.result.model_cost) * F(scale), "price scaling cost")

    def test_budget_and_supply_relaxation_cannot_worsen_objective(self):
        for field, values in (("supply", ("0", "10", "26.658", "40", "100")),
                              ("budget", ("0", "3200", "8530.56", "12800", "32000"))):
            previous_improvement = None
            previous_target_cost = None
            for value in values:
                case = hand_case()
                case[field] = value
                result = calculate_decision_case(request([case]))
                self.assert_case([case], result)
                rows = {r.scenario_id: r.result for r in result.scenarios}
                improvement = rows[result.decision_summary.max_improvement_scenario_id].fuel_eu.compliance_balance_t
                if previous_improvement is not None:
                    self.assertGreaterEqual(improvement, previous_improvement)
                previous_improvement = improvement
                target_id = result.decision_summary.target_min_cost_scenario_id
                if previous_target_cost is not None:
                    self.assertIsNotNone(target_id)
                    self.assertLessEqual(rows[target_id].model_cost, previous_target_cost)
                if target_id is not None:
                    previous_target_cost = rows[target_id].model_cost

    def test_reference_highs_for_expanded_well_scaled_cases(self):
        for case in expanded_cases():
            if case["category"] not in (
                "price_reversal", "carbon_price_reversal", "energy_density",
                "simultaneous_constraints", "year_scope", "target_topology",
            ):
                continue
            for mode, ref in optimal_references(case).items():
                if ref is None or "solver_status" not in ref:
                    continue
                with self.subTest(id=case["id"], mode=mode):
                    self.assertEqual(ref["exact_ratio"] is not None, ref["solver_status"] == 0)
                    if ref["exact_ratio"] is not None:
                        exact = business_values(case, ref["exact_ratio"])
                        observed = business_values(case, str(ref["solver_ratio"]))
                        metric = "fueleu_ghgi_actual_g_per_mj" if mode == "improvement" else "model_cost"
                        self.close(observed[metric], exact[metric], "matrix HiGHS objective", "1e-5")

    def test_api_invalid_candidate_is_isolated_from_valid_decisions(self):
        mutations = (
            {"maxBlendRatio": "1.1"}, {"candidateSupplyTonnes": "-1"},
            {"incrementalBudget": "-1"}, {"pricePerTonne": "-1"},
            {"lcv": "0"}, {"rwd": "2"}, {"sourceEvidence": {}},
            {"cfCO2": "-.1"}, {"cfCH4": "-.1"}, {"cfN2O": "-.1"},
        )
        with TestClient(app) as client:
            for change in mutations:
                with self.subTest(change=change):
                    payload = custom_payload([hand_case()])
                    invalid = deepcopy(payload["candidates"][0])
                    invalid.update(change, candidateId="invalid")
                    payload["candidates"].insert(0, invalid)
                    response = client.post("/api/calculate", json=payload)
                    self.assertEqual(response.status_code, 200)
                    result = response.json()
                    blocked = next(c for c in result["candidate_results"] if c["candidate_id"] == "invalid")
                    self.assertEqual(blocked["calculation_status"], "BLOCKED")
                    self.assertTrue(any(issue["blocking"] for issue in blocked["issues"]))
                    self.assertEqual(result["decision_summary"]["cost_min_scenario_id"], "B0")
                    self.assertEqual(result["decision_summary"]["target_min_cost_scenario_id"], "clean@0.26658")
                    self.assertEqual(result["decision_summary"]["max_improvement_scenario_id"], "clean@0.6")
                    target = next(r["result"] for r in result["scenarios"] if r["scenario_id"] == "clean@0.26658")
                    self.assertEqual(D(target["candidate_mass_tonnes"]), D("26.658"))
                    self.assertEqual(D(target["model_cost"]), D("80530.56"))
                    self.assertFalse(any(r["candidate_id"] == "invalid" for r in result["scenarios"]))

    def test_api_rejects_case_wide_invalid_inputs(self):
        with TestClient(app) as client:
            for variant in ("year", "zero_mass", "negative_eua", "confirmation", "duplicate_ids"):
                with self.subTest(variant=variant):
                    payload = custom_payload([hand_case()])
                    if variant == "year":
                        payload["reportYear"] = 2031
                    elif variant == "zero_mass":
                        payload["baseline"]["massTonnes"] = "0"
                    elif variant == "negative_eua":
                        payload["euaPricePerTCO2e"] = "-1"
                    elif variant == "confirmation":
                        payload["adjacentValidPortOfCallConfirmed"] = False
                    elif variant == "duplicate_ids":
                        payload["candidates"].append(deepcopy(payload["candidates"][0]))
                    response = client.post("/api/calculate", json=payload)
                    self.assertEqual(response.status_code, 422)
                    self.assertTrue(response.json()["issues"])
                    for endpoint in ("export/csv", "export/pdf"):
                        response = client.post("/api/" + endpoint, json=payload)
                        self.assertEqual(response.status_code, 409)
                        self.assertEqual(response.json()["issues"][0]["code"], "RESULT_SNAPSHOT_REQUIRED")

    def test_api_accepts_baseline_only_case_and_exports_its_snapshot(self):
        with TestClient(app) as client:
            payload = custom_payload([hand_case()])
            payload["candidates"] = []
            response = client.post("/api/calculate", json=payload)
            self.assertEqual(response.status_code, 200)
            result = response.json()
            self.assertIsNone(result["decision_summary"])
            self.assertEqual(result["scenarios"][0]["scenario_id"], "B0")
            export = {"resultSnapshotId": result["result_snapshot_id"]}
            for endpoint in ("export/csv", "export/pdf"):
                self.assertEqual(client.post("/api/" + endpoint, json=export).status_code, 200)

    def test_api_missing_prices_retain_physical_results_and_explain_limits(self):
        with TestClient(app) as client:
            for missing in ("baseline", "candidate", "eua"):
                with self.subTest(missing=missing):
                    payload = custom_payload([hand_case()])
                    if missing == "eua":
                        payload["euaPricePerTCO2e"] = None
                    elif missing == "baseline":
                        payload["baseline"]["pricePerTonne"] = None
                    else:
                        payload["candidates"][0]["pricePerTonne"] = None
                    response = client.post("/api/calculate", json=payload)
                    self.assertEqual(response.status_code, 200)
                    result = response.json()
                    self.assertEqual(result["candidate_results"][0]["calculation_status"], "CALCULABLE")
                    target_rec = next(r for r in result["recommendations"] if r["recommendation_id"] == "TARGET_MIN_COST:clean")
                    self.assertEqual(target_rec["reason"], "PRICE_REQUIRED_FOR_COMPARISON")
                    self.assertEqual(target_rec["status"], "UNAVAILABLE")
                    summary = result["decision_summary"]
                    self.assertIsNone(summary["target_min_cost_scenario_id"])
                    self.assertEqual(summary["max_improvement_scenario_id"], "clean@0.6")
                    maximum = next(r["result"] for r in result["scenarios"] if r["scenario_id"] == "clean@0.6")
                    self.assertEqual(D(maximum["candidate_mass_tonnes"]), D("60"))
                    self.assertEqual(D(maximum["fuel_eu"]["ghgi_actual_g_per_mj"]), D("76"))
                    self.assertIsNone(maximum["model_cost"])


if __name__ == "__main__":
    unittest.main()
