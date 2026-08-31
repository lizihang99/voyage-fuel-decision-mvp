from decimal import Decimal
import unittest

from voyage_fuel.ports import calculate_scope_rates, load_port_table


class PortScopeTests(unittest.TestCase):
    def test_formal_table_and_eu_third_country_rates(self):
        table = load_port_table()
        self.assertEqual(len(table), 17519)
        rates = calculate_scope_rates(2025, "CNSHG", "NLRTM", table)
        self.assertEqual(rates.eu_ets_scope_rate, Decimal("0.5"))
        self.assertEqual(rates.eu_ets_surrender_rate, Decimal("0.7"))
        self.assertEqual(rates.eu_ets_effective_rate, Decimal("0.35"))
        self.assertEqual(rates.fuel_eu_scope_rate, Decimal("0.5"))

    def test_fueleu_is_not_applicable_before_2025(self):
        rates = calculate_scope_rates(2024, "CNSHG", "NLRTM")
        self.assertIsNone(rates.fuel_eu_scope_rate)
        self.assertFalse(rates.fuel_eu_applicable)

    def test_rejects_year_outside_mvp_range(self):
        with self.assertRaises(ValueError):
            calculate_scope_rates(2031, "CNSHG", "NLRTM")


if __name__ == "__main__":
    unittest.main()
