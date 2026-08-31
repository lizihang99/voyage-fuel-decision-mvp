import unittest
from decimal import Decimal

from voyage_fuel.factors import builtin_path_ids, get_definition


class FactorCatalogTests(unittest.TestCase):
    def test_open_catalog_contains_exactly_36_paths_and_excludes_ops(self):
        ids = builtin_path_ids()
        self.assertEqual(len(ids), 36)
        self.assertNotIn("ELECTRICITY_OPS", ids)
        self.assertEqual(get_definition("LNG_OTTO_MS").equipment_id, "LNG_OTTO_MS")

    def test_definition_preserves_fixed_factor_values(self):
        definition = get_definition("HFO")
        self.assertEqual(definition.factor_level, "A")
        self.assertEqual(definition.wt_t_mode, "STATIC")
        self.assertEqual(definition.lcv_mj_per_g, Decimal("0.0405"))
        self.assertEqual(definition.wt_t_g_per_mj, Decimal("13.5"))

    def test_unknown_and_ops_paths_are_rejected(self):
        with self.assertRaises(KeyError):
            get_definition("ELECTRICITY_OPS")
        with self.assertRaises(KeyError):
            get_definition("missing")


if __name__ == "__main__":
    unittest.main()
