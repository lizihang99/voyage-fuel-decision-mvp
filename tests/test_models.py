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

    def test_voyage_input_rejects_ratio_outside_maximum(self):
        with self.assertRaises(ValueError):
            from voyage_fuel.models import VoyageInput

            VoyageInput(
                report_year=2025,
                departure_port="CNSHG",
                arrival_port="NLRTM",
                baseline_component=FuelComponent(FuelFactor(
                    path_id="B",
                    lcv_mj_per_g=Decimal("0.04"),
                    wt_t_g_per_mj=Decimal("1"),
                    cf_co2_g_per_g=Decimal("1"),
                    cf_ch4_g_per_g=Decimal("0"),
                    cf_n2o_g_per_g=Decimal("0"),
                    rwd=Decimal("1"),
                    cslip_percent=None,
                    methane_slip_applicable=False,
                    factor_status="FIXED",
                ), Decimal("1")),
                baseline_mass_tonnes=Decimal("1"),
                candidate_component=FuelComponent(FuelFactor(
                    path_id="C",
                    lcv_mj_per_g=Decimal("0.04"),
                    wt_t_g_per_mj=Decimal("1"),
                    cf_co2_g_per_g=Decimal("1"),
                    cf_ch4_g_per_g=Decimal("0"),
                    cf_n2o_g_per_g=Decimal("0"),
                    rwd=Decimal("1"),
                    cslip_percent=None,
                    methane_slip_applicable=False,
                    factor_status="FIXED",
                ), Decimal("1")),
                eua_price_per_tco2e=None,
                specified_blend_ratios=(Decimal("0.6"),),
                max_blend_ratio=Decimal("0.5"),
            )


if __name__ == "__main__":
    unittest.main()
