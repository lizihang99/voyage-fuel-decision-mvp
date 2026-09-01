from decimal import Decimal
import unittest

from voyage_fuel.case_calculator import calculate_decision_case, calculate_parsed_decision_case
from voyage_fuel.contracts import CandidateInput, DecisionCaseInput, Issue, ParsedDecisionCase
from voyage_fuel.factors import resolve_factor
from voyage_fuel.models import FuelComponent
from voyage_fuel.ports import calculate_scope_rates, load_port_table


class ProvenanceTests(unittest.TestCase):
    def test_case_contains_port_scope_and_factor_provenance(self):
        baseline = FuelComponent(resolve_factor("MDO"), Decimal("700"))
        candidate = FuelComponent(resolve_factor("E_DIESEL"), Decimal("900"))
        request = DecisionCaseInput(
            report_year=2026,
            departure_port="CNSHG",
            arrival_port="NLRTM",
            adjacent_valid_port_of_call_confirmed=True,
            currency="EUR",
            baseline_component=baseline,
            baseline_mass_tonnes=Decimal("100"),
            eua_price_per_tco2e=Decimal("80"),
            candidates=(CandidateInput("e-diesel", candidate),),
        )

        result = calculate_decision_case(request)
        provenance = result.provenance
        self.assertIsNotNone(provenance)
        assert provenance is not None
        self.assertEqual(provenance.calculation_spec_version, "2026-08-07")
        self.assertEqual(provenance.fuel_factor_version, "2026-08-31-audit")
        self.assertEqual(provenance.port_rule_version, "2026-07-23")
        self.assertEqual(provenance.departure.unlocode, "CNSHG")
        self.assertEqual(provenance.departure.port_name, "Shanghai Pt")
        self.assertEqual(provenance.departure.eu_ets_identity, "THIRD_COUNTRY")
        self.assertEqual(provenance.departure.fuel_eu_identity, "THIRD_COUNTRY")
        self.assertEqual(provenance.departure.rule_source_id, "PORT-02;ETS-01;FEU-01")
        self.assertEqual(provenance.departure.source_version, "UN/LOCODE 2025-1")
        self.assertEqual(provenance.arrival.unlocode, "NLRTM")
        self.assertEqual(provenance.arrival.port_name, "Rotterdam")
        self.assertEqual(provenance.eu_ets_reason, "ONE_IN_SCOPE")
        self.assertEqual(provenance.fuel_eu_reason, "ONE_IN_SCOPE")
        self.assertEqual(provenance.eu_ets_geographic_rate, Decimal("0.5"))
        self.assertEqual(provenance.eu_ets_surrender_rate, Decimal("1"))
        self.assertEqual(provenance.fuel_eu_rate, Decimal("0.5"))

        trace = provenance.factor_resolutions[-1]
        self.assertEqual(trace.requested_path_id, "E_DIESEL")
        self.assertEqual(trace.resolved_path_id, "MDO")
        self.assertEqual(trace.resolution_reason, "RFNBO_QUALIFICATION_NOT_DEMONSTRATED")
        self.assertEqual(trace.qualification_status, "NOT_DEMONSTRATED")
        self.assertEqual(trace.factor_status, "FIXED")
        self.assertEqual(len(provenance.source_ids), len(set(provenance.source_ids)))
        self.assertTrue(provenance.source_ids)

    def test_trace_preserves_explicitly_resolved_rfnbo_factor(self):
        baseline = FuelComponent(resolve_factor("MDO"), Decimal("700"))
        candidate_factor = resolve_factor(
            "E_DIESEL",
            qualification_status="ASSUMED_ELIGIBLE",
            e_value=Decimal("20"),
            eu_value=Decimal("5"),
        )
        candidate = FuelComponent(
            candidate_factor,
            Decimal("900"),
            qualification_status="ASSUMED_ELIGIBLE",
        )
        request = DecisionCaseInput(
            report_year=2026,
            departure_port="CNSHG",
            arrival_port="NLRTM",
            adjacent_valid_port_of_call_confirmed=True,
            currency="EUR",
            baseline_component=baseline,
            baseline_mass_tonnes=Decimal("100"),
            eua_price_per_tco2e=Decimal("80"),
            candidates=(CandidateInput("e-diesel", candidate),),
        )

        result = calculate_decision_case(request)
        assert result.provenance is not None
        trace = result.provenance.factor_resolutions[-1]
        self.assertEqual(trace.factor, candidate.factor)
        self.assertEqual(trace.factor.wt_t_g_per_mj, Decimal("15"))

    def test_unparsed_case_returns_unavailable_provenance_without_facts(self):
        result = calculate_parsed_decision_case(ParsedDecisionCase(
            request=None,
            issues=(Issue("INVALID_YEAR", "CASE", "reportYear", True, "invalid year"),),
        ))

        self.assertIsNotNone(result.provenance)
        assert result.provenance is not None
        self.assertEqual(result.provenance.status, "UNAVAILABLE")
        self.assertIsNone(result.provenance.departure)
        self.assertIsNone(result.provenance.arrival)
        self.assertEqual(result.provenance.factor_resolutions, ())
        self.assertEqual(result.provenance.source_ids, ())

    def test_case_error_returns_partial_provenance_without_port_facts(self):
        baseline = FuelComponent(resolve_factor("MDO"), Decimal("700"))
        request = DecisionCaseInput(
            report_year=2026,
            departure_port="ZZZZZ",
            arrival_port="NLRTM",
            adjacent_valid_port_of_call_confirmed=True,
            currency="EUR",
            baseline_component=baseline,
            baseline_mass_tonnes=Decimal("100"),
            eua_price_per_tco2e=Decimal("80"),
            candidates=(),
        )

        result = calculate_decision_case(request)

        self.assertIsNotNone(result.provenance)
        assert result.provenance is not None
        self.assertEqual(result.provenance.status, "PARTIAL")
        self.assertIsNone(result.provenance.departure)
        self.assertIsNone(result.provenance.arrival)
        self.assertEqual(result.provenance.factor_resolutions[0].factor, baseline.factor)

    def test_omr_fueleu_scope_records_special_rule_reason(self):
        table = load_port_table()
        omr_code = next(code for code, row in table.items() if row["fuelEuStatus"] == "OMR")
        rates = calculate_scope_rates(2026, omr_code, "CNSHG", table)

        self.assertEqual(rates.fuel_eu_scope_rate, Decimal("0.5"))
        self.assertEqual(rates.fuel_eu_reason, "OMR_SPECIAL_RULE")


if __name__ == "__main__":
    unittest.main()
