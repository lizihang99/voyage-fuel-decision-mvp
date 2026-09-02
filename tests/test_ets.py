from decimal import Decimal
import unittest

from voyage_fuel.emissions import calculate_eu_ets
from voyage_fuel.models import FuelAmount, FuelComponent, FuelFactor
from voyage_fuel.ports import ScopeRates


def hfo_component(price="600"):
    return FuelComponent(
        FuelFactor(
            path_id="HFO",
            lcv_mj_per_g=Decimal("0.0405"),
            wt_t_g_per_mj=Decimal("13.5"),
            cf_co2_g_per_g=Decimal("3.114"),
            cf_ch4_g_per_g=Decimal("0.00005"),
            cf_n2o_g_per_g=Decimal("0.00018"),
            rwd=Decimal("1"),
            cslip_percent=None,
            methane_slip_applicable=False,
            factor_status="FIXED",
        ),
        Decimal(price),
    )


class EuEtsTests(unittest.TestCase):
    def test_non_biomass_path_cannot_claim_biomass_zero_rating(self):
        with self.assertRaisesRegex(ValueError, "INVALID_BIOMASS_FRACTION"):
            FuelComponent(
                hfo_component().factor,
                Decimal("600"),
                eligible_biomass_fraction=Decimal("1"),
                qualification_status="ASSUMED_ELIGIBLE",
            )

    def test_2024_only_co2_enters_surrender(self):
        result = calculate_eu_ets(
            2024,
            [FuelAmount(hfo_component(), Decimal("100"))],
            ScopeRates(Decimal("1"), Decimal("0.4"), Decimal("0.4"), Decimal("1"), True),
            Decimal("80"),
        )
        self.assertEqual(result.raw_co2_t, Decimal("311.4"))
        self.assertEqual(result.raw_ch4_t, Decimal("0.005"))
        self.assertEqual(result.raw_n2o_t, Decimal("0.018"))
        self.assertEqual(result.included_gases, ("CO2",))
        self.assertEqual(result.euas_required, Decimal("124.56"))
        self.assertEqual(result.eua_cost, Decimal("9964.8"))
        self.assertEqual(result.ets_scope_by_gas["CO2"], result.s_ets_effective)
        self.assertTrue(result.excluded_from_ets_surrender["CH4"])
        self.assertTrue(result.excluded_from_ets_surrender["N2O"])

    def test_2026_includes_ch4_and_n2o(self):
        result = calculate_eu_ets(
            2026,
            [FuelAmount(hfo_component(), Decimal("100"))],
            ScopeRates(Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1"), True),
            None,
        )
        self.assertEqual(result.included_gases, ("CO2", "CH4", "N2O"))
        self.assertEqual(result.eua_cost, None)
        self.assertEqual(result.euas_required, Decimal("311.4") + Decimal("28") * Decimal("0.005") + Decimal("265") * Decimal("0.018"))
        self.assertEqual(set(result.ets_scope_by_gas), {"CO2", "CH4", "N2O"})



if __name__ == "__main__":
    unittest.main()
