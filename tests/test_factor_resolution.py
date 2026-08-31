from decimal import Decimal
import unittest

from voyage_fuel.factors import resolve_factor


class FactorResolutionTests(unittest.TestCase):
    def test_a_level_factor_is_fixed(self):
        factor = resolve_factor("HFO")
        self.assertEqual(factor.factor_status, "FIXED")
        self.assertEqual(factor.wt_t_g_per_mj, Decimal("13.5"))

    def test_uco_default_uses_bio_formula_and_is_estimated(self):
        factor = resolve_factor("UCO_FAME")
        self.assertEqual(factor.factor_status, "ESTIMATED")
        self.assertEqual(factor.wt_t_g_per_mj, Decimal("14.9") - Decimal("2.834") / Decimal("0.037"))

    def test_unqualified_rfnbo_falls_back_to_fossil_path(self):
        factor = resolve_factor("E_DIESEL", qualification_status="NOT_DEMONSTRATED")
        self.assertEqual(factor.path_id, "MDO")
        self.assertEqual(factor.factor_status, "FIXED")

    def test_assumed_rfnbo_uses_conservative_e_and_rwd_two(self):
        factor = resolve_factor(
            "E_DIESEL", qualification_status="ASSUMED_ELIGIBLE", e_value=Decimal("28.2"), eu_value=Decimal("20")
        )
        self.assertEqual(factor.factor_status, "ESTIMATED")
        self.assertEqual(factor.rwd, Decimal("2"))
        self.assertEqual(factor.wt_t_g_per_mj, Decimal("8.2"))

    def test_verified_rfnbo_requires_e_and_eu(self):
        with self.assertRaisesRegex(ValueError, "BLOCKED"):
            resolve_factor("E_DIESEL", qualification_status="VERIFIED_ELIGIBLE")

    def test_verified_lpg_requires_recognized_cslip(self):
        with self.assertRaisesRegex(ValueError, "BLOCKED"):
            resolve_factor("LPG_PROPANE", qualification_status="VERIFIED_ELIGIBLE")

    def test_lng_slip_is_device_specific(self):
        medium = resolve_factor("LNG_OTTO_MEDIUM_SPEED")
        slow = resolve_factor("LNG_OTTO_SLOW_SPEED")
        self.assertTrue(medium.methane_slip_applicable)
        self.assertEqual(medium.cslip_percent, Decimal("3.1"))
        self.assertEqual(slow.cslip_percent, Decimal("1.7"))


if __name__ == "__main__":
    unittest.main()
