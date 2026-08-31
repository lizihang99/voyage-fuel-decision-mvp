from decimal import Decimal
import unittest

from voyage_fuel.energy import baseline_energy_mj, blend_masses_tonnes, fuel_cost
from voyage_fuel.factors import get_builtin_factor
from voyage_fuel.models import FuelComponent


class EnergyTests(unittest.TestCase):
    def test_twenty_percent_uco_blend_preserves_mdo_baseline_energy(self):
        baseline = FuelComponent(get_builtin_factor("MDO"), Decimal("600"))
        candidate = FuelComponent(
            get_builtin_factor("UCO_FAME"), Decimal("1000"),
            eligible_biomass_fraction=Decimal("1"),
            qualification_status="ASSUMED_ELIGIBLE",
        )
        energy = baseline_energy_mj(Decimal("100"), baseline.factor)
        baseline_t, candidate_t = blend_masses_tonnes(energy, baseline, candidate, Decimal("0.20"))

        self.assertLess(abs(baseline_t - Decimal("82.19441770933589990")), Decimal("1e-17"))
        self.assertLess(abs(candidate_t - Decimal("20.54860442733397498")), Decimal("1e-17"))
        self.assertEqual(
            (baseline_t * Decimal("1000000") * baseline.factor.lcv_mj_per_g)
            + (candidate_t * Decimal("1000000") * candidate.factor.lcv_mj_per_g),
            energy,
        )

    def test_missing_price_keeps_cost_unknown(self):
        component = FuelComponent(get_builtin_factor("MDO"), None)
        self.assertIsNone(fuel_cost(Decimal("100"), component))


if __name__ == "__main__":
    unittest.main()
