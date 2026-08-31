from decimal import Decimal
import unittest

from voyage_fuel.factors import get_definition, resolve_factor, builtin_path_ids
from voyage_fuel.models import FuelComponent


FORMAL = {
    "HFO": ("A", "0.0405", "STATIC", "13.5", "3.114", "0.00005", "0.00018", None, False, "1"),
    "LFO": ("A", "0.041", "STATIC", "13.2", "3.151", "0.00005", "0.00018", None, False, "1"),
    "MDO": ("A", "0.0427", "STATIC", "14.4", "3.206", "0.00005", "0.00018", None, False, "1"),
    "MGO": ("A", "0.0427", "STATIC", "14.4", "3.206", "0.00005", "0.00018", None, False, "1"),
    "LNG_OTTO_MEDIUM_SPEED": ("A", "0.0491", "STATIC", "18.5", "2.750", "0", "0.00011", "3.1", True, "1"),
    "LNG_OTTO_SLOW_SPEED": ("A", "0.0491", "STATIC", "18.5", "2.750", "0", "0.00011", "1.7", True, "1"),
    "LNG_DIESEL_SLOW_SPEED": ("A", "0.0491", "STATIC", "18.5", "2.750", "0", "0.00011", "0.2", True, "1"),
    "LNG_LBSI": ("A", "0.0491", "STATIC", "18.5", "2.750", "0", "0.00011", "2.6", True, "1"),
    "METHANOL_NG": ("A", "0.0199", "STATIC", "31.3", "1.375", "0.00005", "0.00018", None, False, "1"),
    "H2_NG_FC": ("A", "0.12", "STATIC", "132", "0", "0", None, None, False, "1"),
    "H2_NG_ICE": ("A", "0.12", "STATIC", "132", "0", "0", "0.00018", None, False, "1"),
    "LPG_PROPANE": ("B", "0.046", "STATIC", "7.8", "3.000", "0.00005", "0.00018", None, False, "1"),
    "LPG_BUTANE": ("B", "0.046", "STATIC", "7.8", "3.030", "0.00005", "0.00018", None, False, "1"),
    "NH3_NG_FC": ("B", "0.0186", "STATIC", "121", "0", "0.00005", "0.00018", None, False, "1"),
    "NH3_NG_ICE": ("B", "0.0186", "STATIC", "121", "0", "0.00005", "0.00018", None, False, "1"),
    "BIOETHANOL": ("B", "0.027", "BIO_E", None, "1.913", "0.00005", "0.00018", None, False, "1"),
    "BIODIESEL": ("B", "0.037", "BIO_E", None, "2.834", "0.00005", "0.00018", None, False, "1"),
    "HVO": ("B", "0.044", "BIO_E", None, "3.115", "0.00005", "0.00018", None, False, "1"),
    "BIOLNG_OTTO_MS": ("B", "0.050", "BIO_E", None, "2.750", "0", "0.00011", "3.1", True, "1"),
    "BIOLNG_OTTO_SS": ("B", "0.050", "BIO_E", None, "2.750", "0", "0.00011", "1.7", True, "1"),
    "BIOLNG_DIESEL_SS": ("B", "0.050", "BIO_E", None, "2.750", "0", "0.00011", "0.2", True, "1"),
    "BIOLNG_LBSI": ("B", "0.050", "BIO_E", None, "2.750", "0", "0.00011", "2.6", True, "1"),
    "BIOMETHANOL": ("B", "0.020", "BIO_E", None, "1.375", "0.00005", "0.00018", None, False, "1"),
    "BIOH2_FC": ("B", "0.120", "CERTIFIED", None, "0", "0", "0", None, False, "1"),
    "BIOH2_ICE": ("B", "0.120", "CERTIFIED", None, "0", "0", "0.00018", None, False, "1"),
    "UCO_FAME": ("B", "0.037", "BIO_E", None, "2.834", "0.00005", "0.00018", None, False, "1"),
    "E_DIESEL": ("B", "0.0427", "RFNBO_E", None, "3.206", "0.00005", "0.00018", None, False, "1"),
    "E_METHANOL": ("B", "0.0199", "RFNBO_E", None, "1.375", "0.00005", "0.00018", None, False, "1"),
    "E_LNG_OTTO_MEDIUM_SPEED": ("B", "0.0491", "RFNBO_E", None, "2.750", "0", "0.00011", "3.1", True, "1"),
    "E_LNG_OTTO_SLOW_SPEED": ("B", "0.0491", "RFNBO_E", None, "2.750", "0", "0.00011", "1.7", True, "1"),
    "E_LNG_DIESEL_SLOW_SPEED": ("B", "0.0491", "RFNBO_E", None, "2.750", "0", "0.00011", "0.2", True, "1"),
    "E_LNG_LBSI": ("B", "0.0491", "RFNBO_E", None, "2.750", "0", "0.00011", "2.6", True, "1"),
    "E_H2_FC": ("B", "0.120", "RFNBO_E", None, "0", "0", "0", None, False, "1"),
    "E_H2_ICE": ("B", "0.120", "RFNBO_E", None, "0", "0", "0.00018", None, False, "1"),
    "E_NH3_FC": ("B", "0.0186", "RFNBO_E", None, "0", "0.00005", "0.00018", None, False, "1"),
    "E_NH3_ICE": ("B", "0.0186", "RFNBO_E", None, "0", "0.00005", "0.00018", None, False, "1"),
}


DEFAULTS = {
    "LPG_PROPANE": ("0.046", "7.8", "3.000", "0.00005", "0.00018", "0"),
    "LPG_BUTANE": ("0.046", "7.8", "3.030", "0.00005", "0.00018", "0"),
    "NH3_NG_FC": ("0.0186", "121", "0", "0.00005", "0.00018", "0"),
    "NH3_NG_ICE": ("0.0186", "121", "0", "0.00005", "0.00018", "0"),
    "BIOETHANOL": ("0.02685", "20", "1.913", "0.00005", "0.00018", "0"),
    "BIODIESEL": ("0.037", "20", "2.834", "0.00005", "0.00018", "0"),
    "HVO": ("0.044", "15", "3.115", "0.00005", "0.00018", "0"),
    "BIOLNG_OTTO_MS": ("0.0491", "10", "2.750", "0", "0.00011", "3.1"),
    "BIOLNG_OTTO_SS": ("0.0491", "10", "2.750", "0", "0.00011", "1.7"),
    "BIOLNG_DIESEL_SS": ("0.0491", "10", "2.750", "0", "0.00011", "0.2"),
    "BIOLNG_LBSI": ("0.0491", "10", "2.750", "0", "0.00011", "2.6"),
    "BIOMETHANOL": ("0.01986", "18", "1.375", "0.00005", "0.00018", "0"),
    "BIOH2_FC": ("0.120", "25", "0", "0", "0", "0"),
    "BIOH2_ICE": ("0.120", "25", "0", "0", "0.00002", "0"),
    "UCO_FAME": ("0.037", None, "2.834", "0.00005", "0.00018", "0"),
    "E_DIESEL": ("0.0427", "3", "3.206", "0.00005", "0.00018", "0"),
    "E_METHANOL": ("0.0199", "3", "1.375", "0.00005", "0.00018", "0"),
    "E_LNG_OTTO_MEDIUM_SPEED": ("0.0491", "2", "2.750", "0", "0.00011", "3.1"),
    "E_LNG_OTTO_SLOW_SPEED": ("0.0491", "2", "2.750", "0", "0.00011", "1.7"),
    "E_LNG_DIESEL_SLOW_SPEED": ("0.0491", "2", "2.750", "0", "0.00011", "0.2"),
    "E_LNG_LBSI": ("0.0491", "2", "2.750", "0", "0.00011", "2.6"),
    "E_H2_FC": ("0.120", "1", "0", "0", "0", "0"),
    "E_H2_ICE": ("0.120", "1", "0", "0", "0.00002", "0"),
    "E_NH3_FC": ("0.0186", "2", "0", "0", "0.0001", "0"),
    "E_NH3_ICE": ("0.0186", "2", "0", "0", "0.0005", "0"),
}


class FactorCatalogAuditTests(unittest.TestCase):
    def test_all_36_formal_path_fields_match_specification(self):
        self.assertEqual(set(builtin_path_ids()), set(FORMAL))
        for path_id, expected in FORMAL.items():
            definition = get_definition(path_id)
            level, lcv, mode, wt_t, co2, ch4, n2o, cslip, methane, rwd = expected
            self.assertEqual(definition.factor_level, level, path_id)
            self.assertEqual(definition.lcv_mj_per_g, Decimal(lcv), path_id)
            self.assertEqual(definition.wt_t_mode, mode, path_id)
            self.assertEqual(definition.wt_t_g_per_mj, None if wt_t is None else Decimal(wt_t), path_id)
            self.assertEqual(definition.cf_co2_g_per_g, Decimal(co2), path_id)
            self.assertEqual(definition.cf_ch4_g_per_g, Decimal(ch4), path_id)
            self.assertEqual(definition.cf_n2o_g_per_g, None if n2o is None else Decimal(n2o), path_id)
            self.assertEqual(definition.cslip_percent, None if cslip is None else Decimal(cslip), path_id)
            self.assertEqual(definition.methane_slip_applicable, methane, path_id)
            self.assertEqual(definition.rwd, Decimal(rwd), path_id)

    def test_all_b_level_default_snapshots_are_separate_from_formal_values(self):
        for path_id, expected in DEFAULTS.items():
            definition = get_definition(path_id)
            lcv, wt_t, co2, ch4, n2o, cslip = expected
            self.assertEqual(definition.default_lcv_mj_per_g, Decimal(lcv), path_id)
            self.assertEqual(definition.default_wt_t_g_per_mj, None if wt_t is None else Decimal(wt_t), path_id)
            self.assertEqual(definition.default_cf_co2_g_per_g, Decimal(co2), path_id)
            self.assertEqual(definition.default_cf_ch4_g_per_g, Decimal(ch4), path_id)
            self.assertEqual(definition.default_cf_n2o_g_per_g, Decimal(n2o), path_id)
            self.assertEqual(definition.default_cslip_percent, Decimal(cslip), path_id)

    def test_non_rfnbo_bio_defaults_do_not_mislabel_wtt_as_e(self):
        for path_id in (
            "BIOETHANOL", "BIODIESEL", "HVO", "BIOLNG_OTTO_MS", "BIOLNG_OTTO_SS",
            "BIOLNG_DIESEL_SS", "BIOLNG_LBSI", "BIOMETHANOL", "BIOH2_FC", "BIOH2_ICE",
        ):
            self.assertIsNone(get_definition(path_id).default_e_g_per_mj, path_id)
        self.assertEqual(get_definition("UCO_FAME").default_e_g_per_mj, Decimal("14.9"))

    def test_default_bio_estimates_use_snapshot_lcv_and_wtt(self):
        expected = {
            "BIOETHANOL": ("0.02685", "20"),
            "BIODIESEL": ("0.037", "20"),
            "HVO": ("0.044", "15"),
            "BIOLNG_OTTO_MS": ("0.0491", "10"),
            "BIOLNG_OTTO_SS": ("0.0491", "10"),
            "BIOLNG_DIESEL_SS": ("0.0491", "10"),
            "BIOLNG_LBSI": ("0.0491", "10"),
            "BIOMETHANOL": ("0.01986", "18"),
        }
        for path_id, (lcv, wt_t) in expected.items():
            factor = resolve_factor(path_id)
            self.assertEqual(factor.factor_status, "ESTIMATED", path_id)
            self.assertEqual(factor.lcv_mj_per_g, Decimal(lcv), path_id)
            self.assertEqual(factor.wt_t_g_per_mj, Decimal(wt_t), path_id)

    def test_explicit_bio_e_uses_formal_lcv_and_verified_requires_e(self):
        factor = resolve_factor("BIOETHANOL", qualification_status="ASSUMED_ELIGIBLE", e_value=Decimal("50"))
        self.assertEqual(factor.lcv_mj_per_g, Decimal("0.027"))
        self.assertEqual(factor.wt_t_g_per_mj, Decimal("50") - Decimal("1.913") / Decimal("0.027"))
        self.assertEqual(factor.factor_status, "ESTIMATED")
        with self.assertRaisesRegex(ValueError, "BLOCKED"):
            resolve_factor("BIOETHANOL", qualification_status="VERIFIED_ELIGIBLE")

    def test_qualified_hydrogen_and_ammonia_use_formal_emission_factors(self):
        hydrogen = resolve_factor("E_H2_ICE", qualification_status="ASSUMED_ELIGIBLE", e_value="28.2", eu_value="0")
        self.assertEqual(hydrogen.cf_n2o_g_per_g, Decimal("0.00018"))
        ammonia = resolve_factor("E_NH3_FC", qualification_status="ASSUMED_ELIGIBLE", e_value="28.2", eu_value="0")
        self.assertEqual(ammonia.cf_ch4_g_per_g, Decimal("0.00005"))
        self.assertEqual(ammonia.cf_n2o_g_per_g, Decimal("0.00018"))
        self.assertEqual(ammonia.cslip_percent, Decimal("0"))

    def test_verified_lpg_and_ammonia_use_recognized_cslip_without_verified_wtt(self):
        propane = resolve_factor(
            "LPG_PROPANE", qualification_status="VERIFIED_ELIGIBLE", cslip_percent=Decimal("0")
        )
        self.assertEqual(propane.factor_status, "VERIFIED")
        self.assertEqual(propane.cslip_percent, Decimal("0"))
        ammonia = resolve_factor(
            "NH3_NG_FC", qualification_status="VERIFIED_ELIGIBLE", cslip_percent=Decimal("0")
        )
        self.assertEqual(ammonia.factor_status, "VERIFIED")

    def test_every_open_path_has_a_default_calculable_resolution(self):
        for path_id in builtin_path_ids():
            factor = resolve_factor(path_id)
            self.assertTrue(factor.lcv_mj_per_g > 0, path_id)
            self.assertTrue(factor.wt_t_g_per_mj is not None, path_id)

    def test_na_and_rc_factor_semantics_are_not_collapsed_into_fixed_zero(self):
        hydrogen = resolve_factor("H2_NG_FC")
        self.assertIn("cf_n2o_g_per_g", hydrogen.na_fields)
        self.assertEqual(hydrogen.cf_n2o_g_per_g, Decimal("0"))
        self.assertEqual(hydrogen.cslip_semantics, "NA")

        propane_estimate = resolve_factor("LPG_PROPANE")
        self.assertEqual(propane_estimate.cslip_percent, Decimal("0"))
        self.assertEqual(propane_estimate.cslip_semantics, "SA")
        self.assertNotIn("cslip_percent", propane_estimate.na_fields)
        propane_verified = resolve_factor(
            "LPG_PROPANE", qualification_status="VERIFIED_ELIGIBLE", cslip_percent=Decimal("0")
        )
        self.assertEqual(propane_verified.cslip_semantics, "VERIFIED")

        bio_default = resolve_factor("BIOETHANOL")
        self.assertIsNone(bio_default.cslip_percent)
        self.assertEqual(bio_default.cslip_semantics, "NA")
        methane_default = resolve_factor("BIOLNG_OTTO_MS")
        self.assertEqual(methane_default.cslip_percent, Decimal("3.1"))
        self.assertEqual(methane_default.cslip_semantics, "FIXED")
        rfnbo_methane = resolve_factor(
            "E_LNG_OTTO_MS", qualification_status="ASSUMED_ELIGIBLE", e_value="28.2", eu_value="56.2"
        )
        self.assertEqual(rfnbo_methane.cslip_semantics, "FIXED")

    def test_rfnbo_non_methane_cslip_remains_na(self):
        factor = resolve_factor(
            "E_DIESEL", qualification_status="ASSUMED_ELIGIBLE", e_value="28.2", eu_value="73.2"
        )
        self.assertIsNone(factor.cslip_percent)
        self.assertEqual(factor.cslip_semantics, "NA")

    def test_all_rfnbo_paths_fallback_to_the_declared_fossil_equivalent(self):
        expected = {
            "E_DIESEL": "MDO",
            "E_METHANOL": "METHANOL_NG",
            "E_LNG_OTTO_MEDIUM_SPEED": "LNG_OTTO_MEDIUM_SPEED",
            "E_LNG_OTTO_SLOW_SPEED": "LNG_OTTO_SLOW_SPEED",
            "E_LNG_DIESEL_SLOW_SPEED": "LNG_DIESEL_SLOW_SPEED",
            "E_LNG_LBSI": "LNG_LBSI",
            "E_H2_FC": "H2_NG_FC",
            "E_H2_ICE": "H2_NG_ICE",
            "E_NH3_FC": "NH3_NG_FC",
            "E_NH3_ICE": "NH3_NG_ICE",
        }
        for path_id, fallback_path_id in expected.items():
            factor = resolve_factor(path_id)
            self.assertEqual(factor.path_id, fallback_path_id, path_id)
            self.assertEqual(factor.rwd, Decimal("1"), path_id)

    def test_all_rfnbo_assumed_and_verified_paths_use_formal_evaluation_fields(self):
        for path_id in (path for path in FORMAL if path.startswith("E_")):
            definition = get_definition(path_id)
            assumed_kwargs = {"e_value": Decimal("20"), "eu_value": definition.default_eu_g_per_mj}
            verified_kwargs = {"e_value": Decimal("20"), "eu_value": definition.default_eu_g_per_mj}
            if definition.cslip_required:
                assumed_kwargs["cslip_percent"] = Decimal("0")
                verified_kwargs["cslip_percent"] = Decimal("0")
            assumed = resolve_factor(path_id, qualification_status="ASSUMED_ELIGIBLE", **assumed_kwargs)
            self.assertEqual(assumed.path_id, path_id, path_id)
            self.assertEqual(assumed.factor_status, "ESTIMATED", path_id)
            self.assertEqual(assumed.rwd, Decimal("2"), path_id)
            verified = resolve_factor(path_id, qualification_status="VERIFIED_ELIGIBLE", **verified_kwargs)
            self.assertEqual(verified.path_id, path_id, path_id)
            self.assertEqual(verified.factor_status, "VERIFIED", path_id)
            self.assertEqual(verified.rwd, Decimal("2"), path_id)

    def test_assumed_qualification_keeps_certified_wtt_scenario_estimated(self):
        factor = resolve_factor(
            "BIOH2_FC", qualification_status="ASSUMED_ELIGIBLE", verified_wt_t=Decimal("12.4")
        )
        self.assertEqual(factor.factor_status, "ESTIMATED")
        self.assertEqual(factor.wt_t_g_per_mj, Decimal("12.4"))

    def test_verified_non_methane_path_keeps_cslip_as_na(self):
        factor = resolve_factor(
            "BIOETHANOL", qualification_status="VERIFIED_ELIGIBLE", e_value=Decimal("12.4")
        )
        self.assertEqual(factor.factor_status, "VERIFIED")
        self.assertIsNone(factor.cslip_percent)
        self.assertEqual(factor.cslip_semantics, "NA")

    def test_unproven_biomass_cannot_claim_an_eligible_fraction(self):
        with self.assertRaisesRegex(ValueError, "INVALID_BIOMASS_FRACTION"):
            FuelComponent(
                factor=resolve_factor("UCO_FAME"),
                price_per_tonne=Decimal("1000"),
                eligible_biomass_fraction=Decimal("1"),
                qualification_status="NOT_DEMONSTRATED",
            )


if __name__ == "__main__":
    unittest.main()
