from decimal import Decimal
import unittest

from voyage_fuel.case_calculator import calculate_decision_case
from voyage_fuel.contracts import CandidateInput, DecisionCaseInput
from voyage_fuel.factors import resolve_factor
from voyage_fuel.models import FuelComponent


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


if __name__ == "__main__":
    unittest.main()
