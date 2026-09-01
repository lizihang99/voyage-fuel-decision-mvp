from decimal import Decimal
from dataclasses import replace
import unittest
from unittest.mock import patch

from voyage_fuel.calculator import calculate_voyage as calculate_single_voyage
from voyage_fuel.case_calculator import (
    calculate_decision_case,
    calculate_parsed_decision_case,
)
from voyage_fuel.contracts import CandidateInput, DecisionCaseInput, Issue, ParsedDecisionCase
from voyage_fuel.factors import get_builtin_factor
from voyage_fuel.models import FuelComponent, FuelFactor
from voyage_fuel.json_io import parse_decision_case


def _component(path_id: str, price: str | None, *, qualification: str | None = None) -> FuelComponent:
    if qualification is None:
        qualification = "ASSUMED_ELIGIBLE" if path_id == "UCO_FAME" else "NOT_DEMONSTRATED"
    return FuelComponent(
        get_builtin_factor(path_id),
        None if price is None else Decimal(price),
        eligible_biomass_fraction=Decimal("1") if path_id == "UCO_FAME" else Decimal("0"),
        qualification_status=qualification,
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


class CaseCalculatorTests(unittest.TestCase):
    def test_preserves_candidate_order_and_deduplicates_shared_b0(self):
        request = _case(
            CandidateInput("uco-1", _component("UCO_FAME", "1000"), specified_blend_ratios=(Decimal("0.2"),)),
            CandidateInput("lng-1", _component("LNG_OTTO_MEDIUM_SPEED", "850"), specified_blend_ratios=(Decimal("0.1"),)),
        )

        result = calculate_decision_case(request)

        self.assertEqual([item.candidate_id for item in result.candidate_results], ["uco-1", "lng-1"])
        self.assertIsNotNone(result.baseline_scenario)
        assert result.baseline_scenario is not None
        self.assertEqual(result.baseline_scenario.ratio, Decimal("0"))
        self.assertTrue(all(
            item.voyage_result is not None
            and item.voyage_result.scenarios[0].physical_energy_mj == result.baseline_scenario.physical_energy_mj
            for item in result.candidate_results
        ))
        self.assertTrue(all(
            scenario.execution_status == "EXECUTION_CONDITIONS_PENDING"
            for item in result.candidate_results
            if item.voyage_result is not None
            for scenario in item.voyage_result.scenarios
        ))
        self.assertEqual(sum(scenario.scenario_id == "B0" for scenario in result.scenarios), 1)
        self.assertGreater(len(result.scenarios), 1)
        self.assertTrue(result.recommendations)
        self.assertEqual(result.candidate_results[0].voyage_result.economics.comparison_status, "COMPARABLE")
        self.assertEqual(result.candidate_results[1].voyage_result.economics.comparison_status, "COMPARABLE")

    def test_invalid_candidate_is_projected_without_blocking_valid_candidate(self):
        payload = {
            "reportYear": 2026,
            "departurePort": "CNSHG",
            "arrivalPort": "NLRTM",
            "adjacentValidPortOfCallConfirmed": True,
            "currency": "EUR",
            "baseline": {"pathId": "MDO", "massTonnes": "100", "pricePerTonne": "700"},
            "euaPricePerTCO2e": "80",
            "candidates": [
                {"candidateId": "uco-1", "pathId": "UCO_FAME", "pricePerTonne": "1000"},
                {"candidateId": "bad-lng", "pathId": "LNG_OTTO_MEDIUM_SPEED", "specifiedBlendRatios": ["1.2"]},
            ],
        }

        result = calculate_parsed_decision_case(parse_decision_case(payload))

        self.assertEqual([item.candidate_id for item in result.candidate_results], ["uco-1", "bad-lng"])
        self.assertEqual(result.candidate_results[0].calculation_status, "COMPARABLE")
        self.assertIsNotNone(result.candidate_results[0].voyage_result)
        self.assertEqual(result.candidate_results[1].calculation_status, "BLOCKED")
        self.assertIsNone(result.candidate_results[1].voyage_result)
        self.assertEqual(result.candidate_results[1].issues[0].candidate_id, "bad-lng")
        self.assertEqual(len(result.issues), 1)
        self.assertEqual(result.issues[0].candidate_id, "bad-lng")

    def test_missing_prices_keep_candidate_calculable_with_domain_results(self):
        result = calculate_decision_case(_case(
            CandidateInput("uco-no-price", _component("UCO_FAME", None)),
            eua=None,
        ))

        candidate = result.candidate_results[0]
        self.assertEqual(candidate.calculation_status, "CALCULABLE")
        self.assertIsNotNone(candidate.voyage_result)
        assert candidate.voyage_result is not None
        self.assertIsNotNone(candidate.voyage_result.scenarios[0].eu_ets)
        self.assertIsNotNone(candidate.voyage_result.scenarios[0].fuel_eu)
        self.assertEqual(candidate.voyage_result.economics.comparison_status, "CALCULABLE")

    def test_invalid_port_blocks_case_before_candidate_results(self):
        request = DecisionCaseInput(
            report_year=2026,
            departure_port="ZZZZZ",
            arrival_port="NLRTM",
            adjacent_valid_port_of_call_confirmed=True,
            currency="EUR",
            baseline_component=_component("MDO", "700"),
            baseline_mass_tonnes=Decimal("100"),
            eua_price_per_tco2e=Decimal("80"),
            candidates=(CandidateInput("uco-1", _component("UCO_FAME", "1000")),),
        )

        result = calculate_decision_case(request)

        self.assertIsNone(result.baseline_scenario)
        self.assertEqual(result.candidate_results, ())
        self.assertTrue(result.issues[0].blocking)
        self.assertEqual(result.issues[0].scope, "CASE")
        self.assertEqual(result.issues[0].code, "PORT_NOT_FOUND")

    def test_malformed_methane_factor_blocks_only_that_candidate(self):
        base_factor = get_builtin_factor("LNG_OTTO_MEDIUM_SPEED")
        malformed_factor = FuelFactor(
            path_id=base_factor.path_id,
            lcv_mj_per_g=base_factor.lcv_mj_per_g,
            wt_t_g_per_mj=base_factor.wt_t_g_per_mj,
            cf_co2_g_per_g=base_factor.cf_co2_g_per_g,
            cf_ch4_g_per_g=base_factor.cf_ch4_g_per_g,
            cf_n2o_g_per_g=base_factor.cf_n2o_g_per_g,
            rwd=base_factor.rwd,
            cslip_percent=None,
            methane_slip_applicable=True,
            factor_status=base_factor.factor_status,
            csf_ch4_g_per_g=base_factor.csf_ch4_g_per_g,
        )
        result = calculate_decision_case(_case(
            CandidateInput("uco-1", _component("UCO_FAME", "1000")),
            CandidateInput("bad-lng", FuelComponent(malformed_factor, Decimal("850"))),
        ))

        self.assertEqual(result.candidate_results[0].calculation_status, "COMPARABLE")
        self.assertEqual(result.candidate_results[1].calculation_status, "BLOCKED")
        self.assertIsNone(result.candidate_results[1].voyage_result)
        self.assertEqual(result.candidate_results[1].issues[0].scope, "CANDIDATE")

    def test_inconsistent_candidate_b0_blocks_the_entire_case(self):
        request = _case(CandidateInput("uco-1", _component("UCO_FAME", "1000")))

        def inconsistent_candidate_b0(voyage_request):
            result = calculate_single_voyage(voyage_request)
            if voyage_request.candidate_component.factor.path_id != "UCO_FAME":
                return result
            mismatched_b0 = replace(
                result.scenarios[0],
                physical_energy_mj=result.scenarios[0].physical_energy_mj + Decimal("1"),
            )
            return replace(result, scenarios=(mismatched_b0, *result.scenarios[1:]))

        parse_issue = Issue(
            code="INVALID_BLEND_RATIO",
            scope="CANDIDATE",
            field="candidates[1].specifiedBlendRatios[0]",
            blocking=True,
            message="ratio must be within the blend cap",
            candidate_id="bad-lng",
        )
        with patch(
            "voyage_fuel.case_calculator.calculate_voyage",
            side_effect=inconsistent_candidate_b0,
        ):
            result = calculate_decision_case(request, initial_issues=(parse_issue,))

        self.assertIsNone(result.baseline_scenario)
        self.assertEqual(result.candidate_results, ())
        self.assertEqual(result.scenarios, ())
        self.assertEqual(result.recommendations, ())
        self.assertEqual(len(result.issues), 2)
        self.assertEqual(result.issues[0].code, "INCONSISTENT_BASELINE")
        self.assertTrue(result.issues[0].blocking)
        self.assertEqual(result.issues[1], parse_issue)


if __name__ == "__main__":
    unittest.main()
