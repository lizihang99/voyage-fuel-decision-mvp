from decimal import Decimal
import unittest

from voyage_fuel.models import FuelComponent, FuelFactor


class ModelTests(unittest.TestCase):
    def test_factor_keeps_decimal_values_and_component_price(self):
        factor = FuelFactor(
            path_id="MDO",
            lcv_mj_per_g=Decimal("0.0427"),
            wt_t_g_per_mj=Decimal("14.4"),
            cf_co2_g_per_g=Decimal("3.206"),
            cf_ch4_g_per_g=Decimal("0.00005"),
            cf_n2o_g_per_g=Decimal("0.00018"),
            rwd=Decimal("1"),
            cslip_percent=None,
            methane_slip_applicable=False,
            factor_status="FIXED",
        )
        component = FuelComponent(factor=factor, price_per_tonne=Decimal("600"))
        self.assertEqual(component.factor.lcv_mj_per_g, Decimal("0.0427"))
        self.assertEqual(component.price_per_tonne, Decimal("600"))


if __name__ == "__main__":
    unittest.main()
