import unittest
from decimal import Decimal

from voyage_fuel.constraints import calculate_constraints
from voyage_fuel.factors import get_builtin_factor
from voyage_fuel.models import FuelComponent, ScopeRates


class ConstraintTests(unittest.TestCase):
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

    def test_vector_g_constraint_bounds(self):
        result = calculate_constraints(
            report_year=2026, baseline_mass_tonnes=Decimal("100"),
            baseline=self.baseline, candidate=self.candidate, scope=self.scope,
            candidate_supply_tonnes=Decimal("10"), incremental_budget=Decimal("5000"),
            max_blend_ratio=Decimal("0.30"), baseline_energy_mj=Decimal("4270000"),
            eua_price_per_tco2e=Decimal("80"),
        )
        self.assertAlmostEqual(float(result.x_budget), 0.1330109107323719, places=12)
        self.assertAlmostEqual(float(result.x_supply), 0.09868269008550959, places=12)
        self.assertAlmostEqual(float(result.x_cap), 0.09868269008550959, places=12)
        self.assertAlmostEqual(float(result.x_target_min_unconstrained), 0.022130676682982508, places=15)
        self.assertEqual(result.x_target_min, result.x_target_min_unconstrained)
        self.assertEqual(result.x_max_improvement, result.x_cap)
        self.assertEqual(result.x_cost_min, Decimal("0"))

    def test_target_is_unreachable_when_cap_is_below_minimum(self):
        result = calculate_constraints(
            report_year=2026, baseline_mass_tonnes=Decimal("100"),
            baseline=self.baseline, candidate=self.candidate, scope=self.scope,
            candidate_supply_tonnes=Decimal("1"), incremental_budget=None,
            max_blend_ratio=Decimal("0.01"), baseline_energy_mj=Decimal("4270000"),
            eua_price_per_tco2e=Decimal("80"),
        )
        self.assertEqual(result.target_status, "TARGET_UNREACHABLE_UNDER_CONSTRAINTS")
        self.assertGreater(result.x_target_min_unconstrained, result.x_cap)
        self.assertIsNone(result.x_target_min_cost)
        self.assertIn("TARGET_UNREACHABLE_UNDER_CONSTRAINTS", result.warning_codes)

    def test_budget_without_prices_is_warning_and_supply_still_applies(self):
        baseline = FuelComponent(get_builtin_factor("MGO"), None)
        candidate = FuelComponent(get_builtin_factor("UCO_FAME"), None,
                                  eligible_biomass_fraction=Decimal("1"),
                                  qualification_status="ASSUMED_ELIGIBLE")
        result = calculate_constraints(
            report_year=2026, baseline_mass_tonnes=Decimal("100"),
            baseline=baseline, candidate=candidate, scope=self.scope,
            candidate_supply_tonnes=Decimal("10"), incremental_budget=Decimal("5000"),
            max_blend_ratio=Decimal("0.30"), baseline_energy_mj=Decimal("4270000"),
            eua_price_per_tco2e=None,
        )
        self.assertIsNone(result.x_budget)
        self.assertEqual(result.x_cap, result.x_supply)
        self.assertIn("BUDGET_UNAVAILABLE_WITHOUT_PRICES", result.warning_codes)

    def test_fueleu_not_applicable_does_not_search_target(self):
        result = calculate_constraints(
            report_year=2024, baseline_mass_tonnes=Decimal("100"),
            baseline=self.baseline, candidate=self.candidate, scope=ScopeRates(
                Decimal("0.5"), Decimal("0.4"), Decimal("0.2"), None, False),
            candidate_supply_tonnes=None, incremental_budget=None,
            max_blend_ratio=Decimal("1"), baseline_energy_mj=Decimal("4270000"),
            eua_price_per_tco2e=None,
        )
        self.assertEqual(result.target_status, "TARGET_NOT_APPLICABLE")
        self.assertIsNone(result.x_target_min_unconstrained)
        self.assertIn("TARGET_NOT_APPLICABLE", result.warning_codes)

    def test_target_no_solution_still_reports_maximum_improvement_boundary(self):
        candidate = FuelComponent(get_builtin_factor("HFO"), Decimal("1000"))
        result = calculate_constraints(
            report_year=2026, baseline_mass_tonnes=Decimal("100"),
            baseline=self.baseline, candidate=candidate, scope=self.scope,
            candidate_supply_tonnes=None, incremental_budget=None,
            max_blend_ratio=Decimal("1"), baseline_energy_mj=Decimal("4270000"),
            eua_price_per_tco2e=Decimal("80"),
        )

        self.assertEqual(result.target_status, "TARGET_NO_SOLUTION")
        self.assertEqual(result.x_max_improvement, Decimal("0"))


if __name__ == "__main__":
    unittest.main()
