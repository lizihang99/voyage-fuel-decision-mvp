import unittest
from decimal import Decimal

from voyage_fuel.economics import (
    build_economics,
    calculate_candidate_break_even_price,
    calculate_eua_break_even_price,
)
from voyage_fuel.calculator import calculate_voyage
from voyage_fuel.factors import get_builtin_factor
from voyage_fuel.models import FuelComponent, ScopeRates
from voyage_fuel.models import VoyageInput


class EconomicsTests(unittest.TestCase):
    def setUp(self):
        self.baseline = FuelComponent(get_builtin_factor("MGO"), Decimal("600"))
        self.candidate = FuelComponent(
            get_builtin_factor("UCO_FAME"), Decimal("1000"),
            eligible_biomass_fraction=Decimal("1"), qualification_status="ASSUMED_ELIGIBLE",
        )
        self.scope = ScopeRates(
            eu_ets_scope_rate=Decimal("0.5"), eu_ets_surrender_rate=Decimal("1"),
            eu_ets_effective_rate=Decimal("0.5"), fuel_eu_scope_rate=Decimal("0.5"),
            fuel_eu_applicable=True,
        )

    def test_vector_g_break_even_prices(self):
        pc = calculate_candidate_break_even_price(
            2026, self.baseline, self.candidate, self.scope, Decimal("80"),
        )
        pe = calculate_eua_break_even_price(
            2026, self.baseline, self.candidate, self.scope,
        )
        self.assertLess(abs(pc - Decimal("630.76546135831381733")), Decimal("1e-18"))
        self.assertLess(abs(pe.value - Decimal("346.45311859774705762")), Decimal("1e-18"))
        self.assertEqual(pe.status, "FINITE_NON_NEGATIVE")

    def test_missing_price_hides_economic_thresholds(self):
        baseline = FuelComponent(get_builtin_factor("MGO"), None)
        candidate = FuelComponent(get_builtin_factor("UCO_FAME"), None)
        self.assertIsNone(calculate_candidate_break_even_price(
            2026, baseline, candidate, self.scope, Decimal("80"),
        ))
        result = calculate_eua_break_even_price(2026, baseline, candidate, self.scope)
        self.assertIsNone(result.value)
        self.assertEqual(result.status, "PRICE_REQUIRED_FOR_COMPARISON")

        request = VoyageInput(
            report_year=2026,
            departure_port="CNSHG",
            arrival_port="NLRTM",
            baseline_component=baseline,
            baseline_mass_tonnes=Decimal("100"),
            candidate_component=candidate,
            eua_price_per_tco2e=None,
        )
        voyage = calculate_voyage(request)
        self.assertIsNone(voyage.economics.pc_break_even)
        self.assertIsNone(voyage.economics.pe_break_even)
        self.assertEqual(voyage.economics.pe_break_even_status, "PRICE_REQUIRED_FOR_COMPARISON")

    def test_eua_threshold_classifies_degenerate_cases(self):
        equal_scope = ScopeRates(Decimal("0"), Decimal("1"), Decimal("0"), Decimal("0.5"), True)
        tied = calculate_eua_break_even_price(2026, self.baseline, self.candidate, equal_scope)
        self.assertEqual(tied.status, "NO_FINITE_POINT")

        same_price = FuelComponent(get_builtin_factor("MGO"), Decimal("600"))
        same_factor = FuelComponent(get_builtin_factor("MGO"), Decimal("600"))
        all_tie = calculate_eua_break_even_price(2026, same_price, same_factor, self.scope)
        self.assertEqual(all_tie.status, "ALL_PRICES_TIE")

    def test_voyage_exposes_compliance_value_without_changing_cost_order(self):
        request = VoyageInput(
            report_year=2026,
            departure_port="CNSHG",
            arrival_port="NLRTM",
            baseline_component=self.baseline,
            baseline_mass_tonnes=Decimal("100"),
            candidate_component=self.candidate,
            eua_price_per_tco2e=Decimal("80"),
            specified_blend_ratios=(Decimal("0.20"),),
            max_blend_ratio=Decimal("0.30"),
            candidate_allows_pure_use=True,
            compliance_improvement_value=Decimal("268.31901315986921862"),
        )
        result = calculate_voyage(request)
        b20 = next(row for row in result.scenarios if row.ratio == Decimal("0.20"))
        self.assertLess(abs(b20.compliance_improvement_tco2e - Decimal("28.27699157844080847")), Decimal("1e-15"))
        self.assertLess(abs(b20.reference_adjusted_cost - Decimal("73020.4")), Decimal("1e-12"))
        self.assertEqual(result.economics.cost_min_ratio, Decimal("0"))
        self.assertEqual(result.economics.cost_sorted_ratios[0], Decimal("0"))
        self.assertTrue(any(
            abs(point.value_star - Decimal("268.31901315986921862")) < Decimal("1e-15")
            for point in result.economics.switch_points
        ))


if __name__ == "__main__":
    unittest.main()
