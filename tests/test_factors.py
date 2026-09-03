import unittest
from decimal import Decimal

from voyage_fuel.factors import builtin_path_ids, get_builtin_factor, get_definition


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

    def test_builtin_evidence_uses_fixed_status_for_regulatory_path(self):
        factor = get_builtin_factor("MDO")
        statuses = {record.field_name: record.verification_status for record in factor.source_evidence}
        self.assertEqual(statuses["lcv"], "FIXED")
        self.assertEqual(statuses["wtT"], "FIXED")
        self.assertEqual(statuses["cfCO2"], "FIXED")
        self.assertEqual(statuses["eligibleBiomassFraction"], "FIXED")

    def test_builtin_default_evidence_uses_estimated_status_and_covers_biomass_field(self):
        factor = get_builtin_factor("BIODIESEL")
        statuses = {record.field_name: record.verification_status for record in factor.source_evidence}
        self.assertEqual(factor.factor_status, "ESTIMATED")
        self.assertEqual(statuses["lcv"], "ESTIMATED")
        self.assertEqual(statuses["wtT"], "ESTIMATED")
        self.assertEqual(statuses["cfCO2"], "FIXED")
        self.assertEqual(statuses["eligibleBiomassFraction"], "ESTIMATED")

    def test_unknown_and_ops_paths_are_rejected(self):
        with self.assertRaises(KeyError):
            get_definition("ELECTRICITY_OPS")
        with self.assertRaises(KeyError):
            get_definition("missing")


if __name__ == "__main__":
    unittest.main()
