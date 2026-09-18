from decimal import Decimal
import unittest

from voyage_fuel.emissions import calculate_fueleu
from voyage_fuel.factors import get_builtin_factor
from voyage_fuel.models import FuelAmount, FuelComponent, FuelFactor
from voyage_fuel.ports import calculate_scope_rates


class FuelEuTests(unittest.TestCase):
    def test_half_scope_keeps_ghgi_and_halves_compliance_balance(self):
        amounts = [
            FuelAmount(FuelComponent(get_builtin_factor("HFO"), Decimal("600")), Decimal("0.5")),
            FuelAmount(
                FuelComponent(get_builtin_factor("UCO_FAME"), Decimal("1000"), eligible_biomass_fraction=Decimal("1"), qualification_status="ASSUMED_ELIGIBLE"),
                Decimal("0.5"),
            ),
        ]
        result = calculate_fueleu(2025, amounts, Decimal("0.5"))
        self.assertLess(abs(result.physical_energy_mj - Decimal("38750")), Decimal("1e-20"))
        self.assertLess(abs(result.scoped_energy_mj - Decimal("19375")), Decimal("1e-20"))
        self.assertLess(abs(result.ghgi_actual_g_per_mj - Decimal("55.7655483870967741935483871")), Decimal("1e-24"))
        self.assertLess(abs(result.compliance_balance_g - Decimal("650443")), Decimal("1"))
        self.assertEqual(result.status, "SURPLUS_ESTIMATE")
        self.assertEqual(result.indicative_penalty_eur, Decimal("0"))

    def test_2024_has_no_fueleu_result(self):
        result = calculate_fueleu(
            2024,
            [FuelAmount(FuelComponent(get_builtin_factor("HFO"), Decimal("600")), Decimal("1"))],
            None,
        )
        self.assertEqual(result.status, "NOT_YET_APPLICABLE")
        self.assertIsNone(result.target_g_per_mj)
        self.assertIsNone(result.ghgi_actual_g_per_mj)
        self.assertIsNone(result.compliance_balance_g)
        self.assertIsNone(result.indicative_penalty_eur)

    def test_zero_scope_is_out_of_scope_without_compliance_metrics(self):
        result = calculate_fueleu(
            2025,
            [FuelAmount(FuelComponent(get_builtin_factor("HFO"), Decimal("600")), Decimal("1"))],
            Decimal("0"),
        )
        self.assertEqual(result.status, "OUT_OF_SCOPE")
        self.assertEqual(result.scoped_energy_mj, Decimal("0"))
        self.assertIsNone(result.target_g_per_mj)
        self.assertIsNone(result.ghgi_actual_g_per_mj)
        self.assertIsNone(result.compliance_balance_g)
        self.assertIsNone(result.indicative_penalty_eur)

    def test_vector_d_penalty_uses_deficit_and_actual_ghgi(self):
        factor = FuelFactor(
            path_id="TEST_100_GHGI",
            lcv_mj_per_g=Decimal("0.041"),
            wt_t_g_per_mj=Decimal("100"),
            cf_co2_g_per_g=Decimal("0"),
            cf_ch4_g_per_g=Decimal("0"),
            cf_n2o_g_per_g=Decimal("0"),
            rwd=Decimal("1"),
            cslip_percent=None,
            methane_slip_applicable=False,
            factor_status="FIXED",
        )
        result = calculate_fueleu(
            2025,
            [FuelAmount(FuelComponent(factor, Decimal("0")), Decimal("1000"))],
            Decimal("1"),
        )
        self.assertEqual(result.physical_energy_mj, Decimal("41000000"))
        self.assertEqual(result.ghgi_actual_g_per_mj, Decimal("100"))
        self.assertEqual(result.compliance_balance_g, Decimal("-437191200.0"))
        self.assertEqual(result.indicative_penalty_eur, Decimal("255916.80"))


if __name__ == "__main__":
    unittest.main()
