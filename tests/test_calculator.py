from decimal import Decimal
import unittest

from voyage_fuel.calculator import calculate_voyage
from voyage_fuel.models import FuelComponent, VoyageInput
from voyage_fuel.factors import get_builtin_factor


class CalculatorTests(unittest.TestCase):
    def test_voyage_returns_b0_and_requested_blend_with_common_energy(self):
        request = VoyageInput(
            report_year=2025,
            departure_port="CNSHG",
            arrival_port="NLRTM",
            baseline_component=FuelComponent(get_builtin_factor("MDO"), Decimal("600")),
            baseline_mass_tonnes=Decimal("100"),
            candidate_component=FuelComponent(
                get_builtin_factor("UCO_FAME"), Decimal("1000"), eligible_biomass_fraction=Decimal("1"),
                qualification_status="ASSUMED_ELIGIBLE"
            ),
            eua_price_per_tco2e=Decimal("80"),
            specified_blend_ratios=(Decimal("0.20"),),
            max_blend_ratio=Decimal("0.30"),
            candidate_allows_pure_use=True,
        )
        result = calculate_voyage(request)
        ratios = [scenario.ratio for scenario in result.scenarios]
        self.assertEqual(ratios[0:3], [Decimal("0"), Decimal("0.20"), Decimal("1")])
        self.assertIn(Decimal("0.30"), ratios)
        self.assertEqual(result.scenarios[0].baseline_mass_tonnes, Decimal("100"))
        self.assertEqual(result.scenarios[0].candidate_mass_tonnes, Decimal("0"))
        self.assertEqual(result.scenarios[0].physical_energy_mj, result.baseline_energy_mj)
        self.assertEqual(result.scenarios[1].physical_energy_mj, result.baseline_energy_mj)
        self.assertEqual(result.scenarios[1].execution_status, "EXECUTION_CONDITIONS_PENDING")
        self.assertIsNotNone(result.scenarios[1].eu_ets)
        self.assertIsNotNone(result.scenarios[1].fuel_eu)

    def test_duplicate_b0_ratio_is_emitted_once(self):
        request = VoyageInput(
            report_year=2025,
            departure_port="CNSHG",
            arrival_port="NLRTM",
            baseline_component=FuelComponent(get_builtin_factor("MDO"), Decimal("600")),
            baseline_mass_tonnes=Decimal("100"),
            candidate_component=FuelComponent(get_builtin_factor("UCO_FAME"), Decimal("1000")),
            eua_price_per_tco2e=None,
            specified_blend_ratios=(Decimal("0"), Decimal("0.20")),
        )
        result = calculate_voyage(request)
        self.assertEqual([scenario.ratio for scenario in result.scenarios], [Decimal("0"), Decimal("0.20"), Decimal("0.022130676682982508109158969772727924816074006340564")])

    def test_b100_is_not_emitted_when_candidate_pure_use_is_not_allowed(self):
        request = VoyageInput(
            report_year=2025,
            departure_port="CNSHG",
            arrival_port="NLRTM",
            baseline_component=FuelComponent(get_builtin_factor("MDO"), Decimal("600")),
            baseline_mass_tonnes=Decimal("100"),
            candidate_component=FuelComponent(get_builtin_factor("UCO_FAME"), Decimal("1000")),
            eua_price_per_tco2e=None,
            candidate_allows_pure_use=False,
        )
        result = calculate_voyage(request)
        self.assertEqual(
            [scenario.ratio for scenario in result.scenarios],
            [Decimal("0"), Decimal("0.022130676682982508109158969772727924816074006340564")],
        )

if __name__ == "__main__":
    unittest.main()
