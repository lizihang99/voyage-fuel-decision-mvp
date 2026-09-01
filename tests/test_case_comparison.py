from decimal import Decimal
import unittest

from voyage_fuel.case_calculator import calculate_decision_case
from voyage_fuel.case_comparison import metric_delta
from voyage_fuel.contracts import CandidateInput, DecisionCaseInput
from voyage_fuel.factors import get_builtin_factor
from voyage_fuel.models import FuelComponent


def _component(path_id: str, price: str | None) -> FuelComponent:
    return FuelComponent(
        get_builtin_factor(path_id),
        None if price is None else Decimal(price),
        eligible_biomass_fraction=Decimal("1") if path_id == "UCO_FAME" else Decimal("0"),
        qualification_status="ASSUMED_ELIGIBLE" if path_id == "UCO_FAME" else "NOT_DEMONSTRATED",
    )


def _case(*candidates: CandidateInput, eua: str | None = "80") -> DecisionCaseInput:
    return DecisionCaseInput(
        report_year=2026,
        departure_port="CNSHG",
        arrival_port="NLRTM",
        adjacent_valid_port_of_call_confirmed=True,
        currency="EUR",
        baseline_component=_component("MDO", "700"),
        baseline_mass_tonnes=Decimal("100"),
        eua_price_per_tco2e=None if eua is None else Decimal(eua),
        candidates=tuple(candidates),
    )


class CaseComparisonTests(unittest.TestCase):
    def test_projection_keeps_absolute_results_and_unrounded_decimal_deltas(self):
        result = calculate_decision_case(_case(
            CandidateInput("uco", _component("UCO_FAME", "1000"), specified_blend_ratios=(Decimal("0.2"),)),
            CandidateInput("lng", _component("LNG_OTTO_MEDIUM_SPEED", "850"), specified_blend_ratios=(Decimal("0.1"),)),
        ))

        b0 = next(scenario for scenario in result.scenarios if scenario.scenario_id == "B0")
        uco = next(scenario for scenario in result.scenarios if scenario.scenario_id == "uco@0.2")
        lng = next(scenario for scenario in result.scenarios if scenario.scenario_id == "lng@0.1")
        self.assertIsNone(b0.candidate_id)
        self.assertEqual(uco.candidate_id, "uco")
        self.assertEqual(lng.candidate_id, "lng")
        self.assertEqual(uco.result.execution_status, "EXECUTION_CONDITIONS_PENDING")
        self.assertEqual(uco.deltas["model_cost"].absolute, uco.result.model_cost)
        expected_delta = uco.result.model_cost - b0.result.model_cost
        self.assertEqual(uco.deltas["model_cost"].delta, expected_delta)
        self.assertEqual(
            uco.deltas["model_cost"].percent_delta,
            expected_delta / abs(b0.result.model_cost) * Decimal("100"),
        )

    def test_zero_baseline_metric_has_explicit_reason_without_division(self):
        delta = metric_delta(Decimal("1.25"), Decimal("0"))

        self.assertEqual(delta.absolute, Decimal("1.25"))
        self.assertEqual(delta.delta, Decimal("1.25"))
        self.assertIsNone(delta.percent_delta)
        self.assertEqual(delta.reason_code, "ZERO_BASELINE")

    def test_current_model_cost_ranking_only_contains_feasible_comparable_candidates(self):
        result = calculate_decision_case(_case(
            CandidateInput("uco", _component("UCO_FAME", "1000"), specified_blend_ratios=(Decimal("0.2"),)),
            CandidateInput("lng", _component("LNG_OTTO_MEDIUM_SPEED", "850"), specified_blend_ratios=(Decimal("0.1"),)),
            CandidateInput("limited", _component("UCO_FAME", "1000"), max_blend_ratio=Decimal("0.01"),
                           allows_pure_use=True),
        ))

        ranked = tuple(scenario for scenario in result.scenarios if scenario.current_model_cost_rank is not None)
        self.assertTrue(ranked)
        self.assertTrue(all(
            scenario.candidate_id is not None
            and scenario.calculation_status == "COMPARABLE"
            and scenario.result.constraint_status == "FEASIBLE"
            for scenario in ranked
        ))
        self.assertNotIn("limited@1", [scenario.scenario_id for scenario in ranked])
        self.assertEqual(
            sorted(scenario.current_model_cost_rank for scenario in ranked),
            list(range(1, len(ranked) + 1)),
        )
        current = next(item for item in result.recommendations if item.recommendation_id == "CURRENT_MODEL_COST_MIN")
        self.assertEqual(current.status, "CONDITIONAL")
        self.assertEqual(current.scenario_id, next(
            scenario.scenario_id for scenario in ranked if scenario.current_model_cost_rank == 1
        ))
        self.assertIn("EXECUTION_CONDITIONS_PENDING", current.assumptions)

    def test_recommendations_retain_target_status_and_switch_side_ids(self):
        result = calculate_decision_case(_case(
            CandidateInput(
                "uco", _component("UCO_FAME", "1000"), specified_blend_ratios=(Decimal("0.2"),),
                max_blend_ratio=Decimal("0.3"), allows_pure_use=True,
                compliance_improvement_value=Decimal("268.31901315986921862"),
            ),
            CandidateInput(
                "unreachable", _component("UCO_FAME", "1000"),
                max_blend_ratio=Decimal("0.01"), supply_tonnes=Decimal("1"),
            ),
        ))

        for recommendation_id in ("CURRENT_MODEL_COST_MIN", "TARGET_MIN_COST:uco", "MAX_COMPLIANCE_IMPROVEMENT:uco"):
            recommendation = next(item for item in result.recommendations if item.recommendation_id == recommendation_id)
            self.assertTrue(recommendation.condition)
            self.assertIsNotNone(recommendation.scenario_id)
            self.assertTrue(recommendation.reason)
            self.assertTrue(recommendation.assumptions)
            self.assertEqual(recommendation.status, "CONDITIONAL")

        unreachable = next(item for item in result.recommendations if item.recommendation_id == "TARGET_MIN_COST:unreachable")
        self.assertEqual(unreachable.status, "UNAVAILABLE")
        self.assertEqual(unreachable.reason, "TARGET_UNREACHABLE_UNDER_CONSTRAINTS")

        switches = tuple(item for item in result.recommendations if item.recommendation_id.startswith("REFERENCE_ADJUSTED_COST_SWITCH:uco:"))
        self.assertTrue(switches)
        self.assertTrue(all(
            item.from_scenario_id is not None and item.to_scenario_id is not None
            and (item.from_scenario_id == "B0" or item.from_scenario_id.startswith("uco@"))
            and item.to_scenario_id.startswith("uco@")
            for item in switches
        ))

    def test_missing_prices_leave_calculable_scenarios_and_unavailable_cost_recommendations(self):
        result = calculate_decision_case(_case(
            CandidateInput("uco", _component("UCO_FAME", None), allows_pure_use=True),
            eua=None,
        ))

        scenario = next(item for item in result.scenarios if item.scenario_id.startswith("uco@"))
        self.assertEqual(scenario.calculation_status, "CALCULABLE")
        self.assertEqual(scenario.result.execution_status, "EXECUTION_CONDITIONS_PENDING")
        self.assertIsNone(scenario.current_model_cost_rank)
        for recommendation_id in ("CURRENT_MODEL_COST_MIN", "TARGET_MIN_COST:uco"):
            recommendation = next(item for item in result.recommendations if item.recommendation_id == recommendation_id)
            self.assertEqual(recommendation.status, "UNAVAILABLE")
            self.assertIn("PRICE_REQUIRED_FOR_COMPARISON", recommendation.assumptions)

    def test_unreachable_target_keeps_feasible_maximum_compliance_improvement_conditional(self):
        result = calculate_decision_case(_case(
            CandidateInput(
                "unreachable", _component("UCO_FAME", "1000"),
                max_blend_ratio=Decimal("0.01"), supply_tonnes=Decimal("1"),
            ),
        ))

        recommendation = next(
            item for item in result.recommendations
            if item.recommendation_id == "MAX_COMPLIANCE_IMPROVEMENT:unreachable"
        )
        self.assertEqual(recommendation.status, "CONDITIONAL")
        self.assertEqual(recommendation.reason, "CONSTRAINT_RESULT")
        self.assertIsNotNone(recommendation.scenario_id)
        self.assertIn("TARGET_UNREACHABLE_UNDER_CONSTRAINTS", recommendation.assumptions)
        self.assertIn("EXECUTION_CONDITIONS_PENDING", recommendation.assumptions)

    def test_missing_prices_keep_feasible_maximum_compliance_improvement_conditional(self):
        result = calculate_decision_case(_case(
            CandidateInput("uco", _component("UCO_FAME", None), allows_pure_use=True),
            eua=None,
        ))

        recommendation = next(
            item for item in result.recommendations
            if item.recommendation_id == "MAX_COMPLIANCE_IMPROVEMENT:uco"
        )
        self.assertEqual(recommendation.status, "CONDITIONAL")
        self.assertEqual(recommendation.reason, "CONSTRAINT_RESULT")
        self.assertIsNotNone(recommendation.scenario_id)
        self.assertIn("CALCULABLE", recommendation.assumptions)
        self.assertNotIn("PRICE_REQUIRED_FOR_COMPARISON", recommendation.assumptions)

    def test_price_missing_unreachable_target_min_cost_keeps_both_limitations(self):
        result = calculate_decision_case(_case(
            CandidateInput(
                "unreachable", _component("UCO_FAME", None),
                max_blend_ratio=Decimal("0.01"), supply_tonnes=Decimal("1"),
            ),
            eua=None,
        ))

        recommendation = next(
            item for item in result.recommendations
            if item.recommendation_id == "TARGET_MIN_COST:unreachable"
        )
        self.assertEqual(recommendation.status, "UNAVAILABLE")
        self.assertEqual(recommendation.reason, "TARGET_UNREACHABLE_UNDER_CONSTRAINTS")
        self.assertIn("TARGET_UNREACHABLE_UNDER_CONSTRAINTS", recommendation.assumptions)
        self.assertIn("PRICE_REQUIRED_FOR_COMPARISON", recommendation.assumptions)


if __name__ == "__main__":
    unittest.main()
