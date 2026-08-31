from decimal import Decimal
import unittest

from voyage_fuel.factors import get_builtin_factor


class FactorRegressions(unittest.TestCase):
    def test_uco_default_factor_is_estimated(self):
        factor = get_builtin_factor("UCO_FAME")
        self.assertEqual(factor.factor_status, "ESTIMATED")
        self.assertEqual(factor.wt_t_g_per_mj, Decimal("14.9") - Decimal("2.834") / Decimal("0.037"))


if __name__ == "__main__":
    unittest.main()
