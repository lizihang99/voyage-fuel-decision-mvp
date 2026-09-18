from decimal import Decimal
import unittest

from voyage_fuel.contracts import CandidateInput, DecisionCaseInput, Issue
from voyage_fuel.factors import get_builtin_factor
from voyage_fuel.models import FuelComponent


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.baseline = FuelComponent(get_builtin_factor("MDO"), Decimal("700"))
        self.candidate = FuelComponent(get_builtin_factor("UCO_FAME"), Decimal("1000"))

    def test_case_requires_confirmed_adjacent_port_of_call(self):
        with self.assertRaisesRegex(ValueError, "PORT_OF_CALL_CONFIRMATION_REQUIRED"):
            DecisionCaseInput(
                report_year=2026, departure_port="CNSHG", arrival_port="NLRTM",
                adjacent_valid_port_of_call_confirmed=False, currency="EUR",
                baseline_component=self.baseline, baseline_mass_tonnes=Decimal("100"),
                eua_price_per_tco2e=Decimal("80"), candidates=(),
            )

    def test_case_rejects_report_year_outside_mvp_range(self):
        common = dict(
            departure_port="CNSHG", arrival_port="NLRTM",
            adjacent_valid_port_of_call_confirmed=True, currency="EUR",
            baseline_component=self.baseline, baseline_mass_tonnes=Decimal("100"),
            eua_price_per_tco2e=Decimal("80"), candidates=(self.candidate,),
        )
        for report_year in (2023, 2031):
            with self.subTest(report_year=report_year):
                with self.assertRaisesRegex(ValueError, "INVALID_YEAR"):
                    DecisionCaseInput(report_year=report_year, **common)

    def test_case_rejects_non_integer_report_year(self):
        with self.assertRaisesRegex(ValueError, "INVALID_YEAR"):
            DecisionCaseInput(
                report_year="2026", departure_port="CNSHG", arrival_port="NLRTM",
                adjacent_valid_port_of_call_confirmed=True, currency="EUR",
                baseline_component=self.baseline, baseline_mass_tonnes=Decimal("100"),
                eua_price_per_tco2e=Decimal("80"), candidates=(),
            )

    def test_case_accepts_mvp_report_year_endpoints(self):
        candidate = CandidateInput(candidate_id="candidate-1", component=self.candidate)
        common = dict(
            departure_port="CNSHG", arrival_port="NLRTM",
            adjacent_valid_port_of_call_confirmed=True, currency="EUR",
            baseline_component=self.baseline, baseline_mass_tonnes=Decimal("100"),
            eua_price_per_tco2e=Decimal("80"), candidates=(candidate,),
        )
        for report_year in (2024, 2030):
            with self.subTest(report_year=report_year):
                self.assertEqual(DecisionCaseInput(report_year=report_year, **common).report_year, report_year)

    def test_candidate_and_scenario_ids_are_stable(self):
        candidate = CandidateInput(
            candidate_id="uco-quote-1", component=self.candidate,
            specified_blend_ratios=(Decimal("0.20"),),
        )
        self.assertEqual(candidate.candidate_id, "uco-quote-1")
        self.assertEqual(candidate.scenario_id(Decimal("0.20")), "uco-quote-1@0.2")

    def test_issue_identifies_scope_candidate_and_field(self):
        issue = Issue(
            code="INVALID_BLEND_RATIO", scope="CANDIDATE", field="specifiedBlendRatios[0]",
            blocking=True, message="ratio must be between zero and one",
            candidate_id="uco-quote-1",
        )
        self.assertEqual(issue.candidate_id, "uco-quote-1")
        self.assertTrue(issue.blocking)

    def test_candidate_rejects_empty_id_and_invalid_constraints(self):
        with self.assertRaisesRegex(ValueError, "INVALID_CANDIDATE_ID"):
            CandidateInput(candidate_id="", component=self.candidate)
        with self.assertRaisesRegex(ValueError, "INVALID_BLEND_RATIO"):
            CandidateInput(
                candidate_id="uco-quote-1", component=self.candidate,
                specified_blend_ratios=(Decimal("0.6"),), max_blend_ratio=Decimal("0.5"),
            )

    def test_case_rejects_empty_currency_invalid_mass_and_duplicate_ids(self):
        candidate = CandidateInput(candidate_id="uco-quote-1", component=self.candidate)
        common = dict(
            report_year=2026, departure_port="CNSHG", arrival_port="NLRTM",
            adjacent_valid_port_of_call_confirmed=True, baseline_component=self.baseline,
            baseline_mass_tonnes=Decimal("100"), eua_price_per_tco2e=Decimal("80"),
        )
        with self.assertRaisesRegex(ValueError, "INVALID_CURRENCY"):
            DecisionCaseInput(currency="", candidates=(), **common)
        with self.assertRaisesRegex(ValueError, "INVALID_BASELINE_MASS"):
            DecisionCaseInput(currency="EUR", candidates=(), baseline_mass_tonnes=Decimal("0"), **{
                key: value for key, value in common.items() if key != "baseline_mass_tonnes"
            })
        with self.assertRaisesRegex(ValueError, "DUPLICATE_CANDIDATE_ID"):
            DecisionCaseInput(currency="EUR", candidates=(candidate, candidate), **common)

    def test_case_accepts_empty_candidate_collection_for_b0_only(self):
        case = DecisionCaseInput(
            report_year=2026, departure_port="CNSHG", arrival_port="NLRTM",
            adjacent_valid_port_of_call_confirmed=True, currency="EUR",
            baseline_component=self.baseline, baseline_mass_tonnes=Decimal("100"),
            eua_price_per_tco2e=Decimal("80"), candidates=(),
        )
        self.assertEqual(case.candidates, ())


if __name__ == "__main__":
    unittest.main()
