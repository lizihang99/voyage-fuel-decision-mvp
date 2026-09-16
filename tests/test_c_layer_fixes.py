"""Regression cases from the independent C-layer experiment, not mirrored formulas."""
from dataclasses import replace
from decimal import Decimal as D
from fractions import Fraction as F
import unittest

from voyage_fuel.calculator import calculate_voyage
from voyage_fuel.case_calculator import calculate_decision_case
from voyage_fuel.case_comparison import build_recommendations, build_case_scenarios
from voyage_fuel.constraints import calculate_constraints
from voyage_fuel.contracts import CandidateInput, DecisionCaseInput, CandidateResult
from voyage_fuel.models import FuelFactor, FuelComponent, ScopeRates, VoyageInput
from voyage_fuel.models import FuelAmount
from voyage_fuel.emissions import calculate_fueleu
from voyage_fuel.economics import calculate_value_switch_points
from voyage_fuel.case_comparison import calculate_case_value_switch_points
from voyage_fuel.contracts import CaseScenario


def component(name, ghgi, price):
    return FuelComponent(
        FuelFactor(name, D(".04"), D(ghgi) - D("75"), D("3"), D(0), D(0),
                   D(1), None, False, "ESTIMATED"), D(price))


def request(baseline=None, candidate=None, cap="1", price="400"):
    return VoyageInput(
        2026, "CNSHG", "NLRTM", baseline or component("base", "80", "1000"), D(100),
        candidate or component("candidate", "100", price), D(80),
        specified_blend_ratios=(D(".25"),) if D(cap) >= D(".25") else (),
        max_blend_ratio=D(cap), candidate_allows_pure_use=True)


def constraints(req):
    return calculate_constraints(
        report_year=req.report_year, baseline_mass_tonnes=req.baseline_mass_tonnes,
        baseline=req.baseline_component, candidate=req.candidate_component,
        scope=ScopeRates(D(".5"), D(1), D(".5"), D(".5"), True),
        candidate_supply_tonnes=req.candidate_supply_tonnes, incremental_budget=req.incremental_budget,
        max_blend_ratio=req.max_blend_ratio, eua_price_per_tco2e=req.eua_price_per_tco2e)


class TargetIntervalFixTests(unittest.TestCase):
    def test_cheaper_worsening_candidate_has_target_upper_bound(self):
        actual = constraints(request())
        self.assertEqual(actual.x_target_min, D(0))
        self.assertEqual(actual.x_target_min_cost, D(".46684"))
        self.assertEqual(actual.x_cost_min, D(1))  # Unconditional cost objective is unchanged.

    def test_report_contains_target_upper_optimum(self):
        result = calculate_voyage(request())
        point = next((s for s in result.scenarios if s.ratio == D(".46684")), None)
        self.assertIsNotNone(point)
        self.assertGreaterEqual(point.fuel_eu.compliance_balance_g, 0)
        self.assertEqual(point.model_cost, D("83989.6"))

    def test_existing_constraint_cap_inside_target_interval_wins(self):
        self.assertEqual(constraints(request(cap=".4")).x_target_min_cost, D(".4"))

    def test_baseline_exactly_at_target_worsening_candidate_keeps_zero(self):
        req = request(baseline=component("base", "89.3368", "1000"))
        self.assertEqual(constraints(req).x_target_min_cost, D(0))

    def test_more_expensive_worsening_candidate_keeps_b0(self):
        self.assertEqual(constraints(request(price="1500")).x_target_min_cost, D(0))

    def test_case_target_recommendation_is_compliant(self):
        req = request()
        case = DecisionCaseInput(2026, "CNSHG", "NLRTM", True, "EUR",
                                 req.baseline_component, D(100), D(80),
                                 (CandidateInput("candidate", req.candidate_component, allows_pure_use=True),))
        result = calculate_decision_case(case)
        rec = next(r for r in result.recommendations if r.recommendation_id == "TARGET_MIN_COST:candidate")
        row = next(r for r in result.scenarios if r.scenario_id == rec.scenario_id)
        self.assertEqual(row.result.ratio, D(".46684"))
        self.assertGreaterEqual(row.result.fuel_eu.compliance_balance_g, 0)
        self.assertEqual(result.economics.target_min_cost_scenario_id, rec.scenario_id)

    def test_recommendation_defensively_rejects_noncompliant_stale_ratio(self):
        result = calculate_voyage(request())
        bad = replace(result, constraints=replace(result.constraints, x_target_min_cost=D(1)))
        candidate = CandidateResult("candidate", "COMPARABLE", bad, ())
        rows = build_case_scenarios(result.scenarios[0], (candidate,))
        rec = next(r for r in build_recommendations(rows, (candidate,))
                   if r.recommendation_id == "TARGET_MIN_COST:candidate")
        self.assertEqual(rec.status, "UNAVAILABLE")
        self.assertIsNone(rec.scenario_id)

    def test_priced_cheaper_candidate_does_not_emit_forbidden_b100(self):
        req = replace(request(candidate=component("candidate", "60", "400")), candidate_allows_pure_use=False)
        result = calculate_voyage(req)
        self.assertNotIn(D(1), [s.ratio for s in result.scenarios])

    def test_case_recommendations_never_reference_forbidden_b100(self):
        req = request(candidate=component("candidate", "60", "400"))
        case = DecisionCaseInput(2026, "CNSHG", "NLRTM", True, "EUR",
                                 req.baseline_component, D(100), D(80),
                                 (CandidateInput("candidate", req.candidate_component,
                                                 specified_blend_ratios=(D(".25"),), allows_pure_use=False),))
        result = calculate_decision_case(case)
        self.assertNotIn("candidate@1", [r.scenario_id for r in result.scenarios])
        self.assertTrue(all(r.scenario_id != "candidate@1" for r in result.recommendations))


class ExactBoundaryFixTests(unittest.TestCase):
    def unequal_request(self):
        baseline = component("base", "95", "600")
        candidate = FuelComponent(
            FuelFactor("candidate", D(".02"), D(10), D(1), D(0), D(0),
                       D(1), None, False, "ESTIMATED"), D(500))
        return request(baseline, candidate)

    def test_generated_minimum_is_on_compliant_side_in_exact_arithmetic(self):
        result = calculate_voyage(self.unequal_request())
        x = F(result.constraints.x_target_min)
        h = (1 - x) * F(".04") * (95 - F("89.3368")) + x * F(".02") * (60 - F("89.3368"))
        self.assertLessEqual(h, 0)
        point = next(s for s in result.scenarios if s.ratio == result.constraints.x_target_min)
        self.assertGreaterEqual(point.fuel_eu.compliance_balance_g, 0)

    def test_supplied_ratio_keeps_tiny_deficit_instead_of_on_target(self):
        req = self.unequal_request()
        x = D("0.27854177733183812390564441558952566448287394991048")
        result = calculate_voyage(replace(req, specified_blend_ratios=(x,)))
        point = next(s for s in result.scenarios if s.ratio == x)
        self.assertLess(point.fuel_eu.compliance_balance_g, 0)
        self.assertEqual(point.fuel_eu.status, "DEFICIT_ESTIMATE")
        self.assertNotEqual(result.constraints.x_target_min, x)

    def test_emitted_masses_preserve_exact_input_mass_ratio(self):
        result = calculate_voyage(self.unequal_request())
        point = next(s for s in result.scenarios if s.ratio == result.constraints.x_target_min)
        ratio = F(point.candidate_mass_tonnes) / (F(point.baseline_mass_tonnes) + F(point.candidate_mass_tonnes))
        self.assertEqual(ratio, F(point.ratio))

    def test_target_status_does_not_round_away_an_input_factor_difference(self):
        req = request()
        # Baseline and candidate have exactly the same GHGI just above target.
        precise_wtt = D("14.336800000000000000000000000000000000000000000000001")
        bad = replace(req.baseline_component, factor=replace(req.baseline_component.factor, wt_t_g_per_mj=precise_wtt))
        self.assertEqual(constraints(replace(req, baseline_component=bad, candidate_component=bad)).target_status,
                         "TARGET_NO_SOLUTION")

    def test_fueleu_preserves_tiny_nonzero_balance_from_exact_factor_inputs(self):
        req = request()
        factor = replace(req.baseline_component.factor,
                         wt_t_g_per_mj=D("14.336800000000000000000000000000000000000000000000001"))
        actual = calculate_fueleu(2026, (FuelAmount(replace(req.baseline_component, factor=factor), D(100)),), D(".5"))
        self.assertLess(actual.compliance_balance_g, 0)
        self.assertEqual(actual.status, "DEFICIT_ESTIMATE")

    def test_generated_upper_boundary_is_on_compliant_side(self):
        req = request(candidate=component("candidate", "101", "400"))
        actual = calculate_voyage(req)
        x = F(actual.constraints.x_target_min_cost)
        self.assertLessEqual((1 - x) * (80 - F("89.3368")) + x * (101 - F("89.3368")), 0)
        self.assertGreater(x, F(".44"))

    def test_small_rewarded_ratio_preserves_complement_digits(self):
        req = self.unequal_request()
        candidate = replace(req.candidate_component, factor=replace(req.candidate_component.factor, rwd=D(2)))
        result = calculate_voyage(replace(req, candidate_component=candidate))
        point = next(s for s in result.scenarios if s.ratio == result.constraints.x_target_min)
        self.assertEqual(F(point.candidate_mass_tonnes) /
                         (F(point.baseline_mass_tonnes) + F(point.candidate_mass_tonnes)), F(point.ratio))
        self.assertGreaterEqual(point.fuel_eu.compliance_balance_g, 0)


class CloseSwitchFixTests(unittest.TestCase):
    def lines(self):
        template = calculate_voyage(request()).scenarios[0]
        return tuple(replace(template, ratio=D(i) / 10, model_cost=D(cost),
                             compliance_improvement_tco2e=D(i))
                     for i, cost in enumerate(("0", "1", "2.0000000000000000000000000000001")))

    def test_single_candidate_preserves_two_close_switches(self):
        points = calculate_value_switch_points(self.lines())
        self.assertEqual([(p.from_ratio, p.to_ratio) for p in points], [(D(0), D(".1")), (D(".1"), D(".2"))])
        self.assertEqual([p.value_star for p in points], [D(1), D("1.0000000000000000000000000000001")])

    def test_case_preserves_two_close_switches(self):
        rows = tuple(CaseScenario(name, name, "COMPARABLE", s, {})
                     for name, s in zip(("a", "b", "c"), self.lines()))
        points = calculate_case_value_switch_points(rows)
        self.assertEqual([(p.from_scenario_id, p.to_scenario_id) for p in points], [("a", "b"), ("b", "c")])


if __name__ == "__main__":
    unittest.main()
