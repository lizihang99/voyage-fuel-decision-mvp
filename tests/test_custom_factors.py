import unittest
from decimal import Decimal

from voyage_fuel.custom_factors import resolve_custom_factor


def evidence(fields):
    return {
        field: [{
            "sourceId": f"SRC-{field.upper()}",
            "sourceType": "LAB_CERTIFICATE",
            "unit": unit,
            "verificationStatus": status,
        }]
        for field, (unit, status) in fields.items()
    }


class CustomFactorTests(unittest.TestCase):
    def emission_payload(self, methane=False):
        units = {
            "lcv": "MJ/gFuel", "wtT": "gCO2eq/MJ",
            "cfCO2": "gGHG/gFuel", "cfCH4": "gGHG/gFuel", "cfN2O": "gGHG/gFuel",
            "cslip": "%", "methaneSlipApplicable": "boolean",
            "rwd": "ratio", "eligibleBiomassFraction": "fraction",
        }
        payload = {
            "custom": True, "pathId": "CUSTOM_TEST", "equipmentId": "TEST",
            "wtTMode": "STATIC", "lcv": ".04", "wtT": "-10",
            "cfCO2": "3", "cfCH4": "0", "cfN2O": "0",
            "cslip": "2" if methane else "NA", "methaneSlipApplicable": methane,
            "rwd": "1", "eligibleBiomassFraction": "0",
        }
        if methane:
            for field in ("csfCO2", "csfCH4", "csfN2O"):
                payload[field] = "0"
                units[field] = "gGHG/gFuel"
        payload["sourceEvidence"] = evidence({key: (unit, "ESTIMATED") for key, unit in units.items()})
        return payload

    def test_emission_coefficients_reject_negative_and_nonfinite_values(self):
        for field in ("cfCO2", "cfCH4", "cfN2O", "csfCO2", "csfCH4", "csfN2O"):
            for value in ("-.1", "NaN", "sNaN", "Infinity", "-Infinity"):
                with self.subTest(field=field, value=value):
                    payload = self.emission_payload(methane=True)
                    payload[field] = value
                    with self.assertRaisesRegex(ValueError, "INVALID_EMISSION_FACTOR.*" + field):
                        resolve_custom_factor(payload)

    def test_zero_emissions_and_negative_wtt_remain_valid(self):
        payload = self.emission_payload(methane=True)
        for field in ("cfCO2", "cfCH4", "cfN2O", "csfCO2", "csfCH4", "csfN2O"):
            payload[field] = "0"
        factor = resolve_custom_factor(payload)
        self.assertEqual(factor.wt_t_g_per_mj, Decimal("-10"))
        self.assertEqual(factor.cf_co2_g_per_g, Decimal("0"))
        self.assertEqual(factor.csf_ch4_g_per_g, Decimal("0"))

    def test_na_combustion_factors_keep_existing_semantics(self):
        payload = self.emission_payload()
        payload.update(cfCO2="NA", cfCH4="NA", cfN2O="NA")
        factor = resolve_custom_factor(payload)
        self.assertEqual(factor.cf_co2_g_per_g, Decimal("0"))
        self.assertIn("cf_co2_g_per_g", factor.na_fields)
        self.assertIn("cf_ch4_g_per_g", factor.na_fields)
        self.assertIn("cf_n2o_g_per_g", factor.na_fields)

    def test_invalid_emissions_are_isolated_at_api_and_export_boundaries(self):
        from copy import deepcopy
        from fastapi.testclient import TestClient
        from tests.test_web_api import minimum_payload
        from voyage_fuel.web import app

        with TestClient(app, raise_server_exceptions=False) as client:
            for field in ("cfCO2", "cfCH4", "cfN2O", "csfCO2", "csfCH4", "csfN2O"):
                for value in ("-.1", "NaN", "Infinity"):
                    with self.subTest(field=field, value=value):
                        payload = minimum_payload()
                        invalid = self.emission_payload(methane=True)
                        invalid.update(candidateId="invalid", pricePerTonne="900")
                        invalid[field] = value
                        payload["candidates"].insert(0, invalid)
                        response = client.post("/api/calculate", json=payload)
                        self.assertEqual(response.status_code, 200)
                        result = response.json()
                        candidate = next(c for c in result["candidate_results"] if c["candidate_id"] == "invalid")
                        self.assertEqual(candidate["calculation_status"], "BLOCKED")
                        self.assertEqual(candidate["issues"][0]["code"], "INVALID_EMISSION_FACTOR")
                        self.assertIn(field, candidate["issues"][0]["message"])
                        self.assertIsNotNone(result["baseline_scenario"])
                        self.assertFalse(any(row["candidate_id"] == "invalid" for row in result["scenarios"]))
                        for endpoint in ("export/csv", "export/pdf"):
                            self.assertEqual(client.post("/api/" + endpoint, json=payload).status_code, 200)

                        bad_baseline = deepcopy(payload)
                        bad_baseline["baseline"] = {**invalid, "massTonnes": "100"}
                        for endpoint in ("calculate", "export/csv", "export/pdf"):
                            response = client.post("/api/" + endpoint, json=bad_baseline)
                            self.assertEqual(response.status_code, 422)
                            self.assertEqual(response.json()["issues"][0]["code"], "INVALID_EMISSION_FACTOR")

    def test_invalid_qualification_status_is_blocked(self):
        payload = {
            "pathId": "CUSTOM_MDO", "equipmentId": "CUSTOM_ENGINE", "lcv": "0.04",
            "wtTMode": "STATIC", "wtT": "10", "cfCO2": "3", "cfCH4": "0", "cfN2O": "0",
            "cslip": "NA", "methaneSlipApplicable": False, "rwd": "1",
            "eligibleBiomassFraction": "0", "qualificationStatus": "UNKNOWN",
            "sourceEvidence": evidence({
                "lcv": ("MJ/gFuel", "VERIFIED"), "wtT": ("gCO2eq/MJ", "VERIFIED"),
                "cfCO2": ("gGHG/gFuel", "VERIFIED"), "cfCH4": ("gGHG/gFuel", "VERIFIED"),
                "cfN2O": ("gGHG/gFuel", "VERIFIED"), "cslip": ("%", "VERIFIED"),
                "methaneSlipApplicable": ("boolean", "VERIFIED"), "rwd": ("ratio", "VERIFIED"),
                "eligibleBiomassFraction": ("fraction", "VERIFIED"),
            }),
        }
        with self.assertRaisesRegex(ValueError, "BLOCKED.*qualificationStatus"):
            resolve_custom_factor(payload)

    def test_rwd_two_is_blocked_for_non_rfnbo_mode(self):
        payload = {
            "pathId": "CUSTOM_MDO", "equipmentId": "CUSTOM_ENGINE", "lcv": "0.04",
            "wtTMode": "STATIC", "wtT": "10", "cfCO2": "3", "cfCH4": "0", "cfN2O": "0",
            "cslip": "NA", "methaneSlipApplicable": False, "rwd": "2",
            "eligibleBiomassFraction": "0", "qualificationStatus": "VERIFIED_ELIGIBLE",
            "sourceEvidence": evidence({
                "lcv": ("MJ/gFuel", "VERIFIED"), "wtT": ("gCO2eq/MJ", "VERIFIED"),
                "cfCO2": ("gGHG/gFuel", "VERIFIED"), "cfCH4": ("gGHG/gFuel", "VERIFIED"),
                "cfN2O": ("gGHG/gFuel", "VERIFIED"), "cslip": ("%", "VERIFIED"),
                "methaneSlipApplicable": ("boolean", "VERIFIED"), "rwd": ("ratio", "VERIFIED"),
                "eligibleBiomassFraction": ("fraction", "VERIFIED"),
            }),
        }
        with self.assertRaisesRegex(ValueError, "INVALID_RWD"):
            resolve_custom_factor(payload)

    def test_static_custom_factor_requires_and_keeps_field_evidence(self):
        payload = {
            "pathId": "CUSTOM_MDO",
            "equipmentId": "CUSTOM_ENGINE",
            "lcv": "0.04",
            "wtTMode": "STATIC",
            "wtT": "10",
            "cfCO2": "3",
            "cfCH4": "0",
            "cfN2O": "0",
            "cslip": "NA",
            "methaneSlipApplicable": False,
            "rwd": "1",
            "eligibleBiomassFraction": "0",
            "sourceEvidence": evidence({
                "lcv": ("MJ/gFuel", "VERIFIED"), "wtT": ("gCO2eq/MJ", "VERIFIED"),
                "cfCO2": ("gGHG/gFuel", "VERIFIED"), "cfCH4": ("gGHG/gFuel", "VERIFIED"),
                "cfN2O": ("gGHG/gFuel", "VERIFIED"), "cslip": ("%", "VERIFIED"),
                "methaneSlipApplicable": ("boolean", "VERIFIED"), "rwd": ("ratio", "VERIFIED"),
                "eligibleBiomassFraction": ("fraction", "VERIFIED"),
            }),
        }
        factor = resolve_custom_factor(payload)
        self.assertEqual(factor.factor_status, "VERIFIED")
        self.assertEqual(factor.wt_t_g_per_mj, Decimal("10"))
        self.assertIsNone(factor.cslip_percent)
        self.assertEqual(factor.na_fields, ("cslip_percent",))
        self.assertEqual(len(factor.source_evidence), 9)

    def test_missing_evidence_blocks_custom_factor(self):
        payload = {
            "pathId": "CUSTOM_MDO", "equipmentId": "CUSTOM_ENGINE", "lcv": "0.04",
            "wtTMode": "STATIC", "wtT": "10", "cfCO2": "3", "cfCH4": "0", "cfN2O": "0",
            "cslip": "NA", "methaneSlipApplicable": False, "rwd": "1",
            "eligibleBiomassFraction": "0",
            "sourceEvidence": evidence({"lcv": ("MJ/gFuel", "VERIFIED")}),
        }
        with self.assertRaisesRegex(ValueError, "BLOCKED.*sourceEvidence"):
            resolve_custom_factor(payload)

    def test_nonzero_slip_requires_slip_factors(self):
        payload = {
            "pathId": "CUSTOM_LNG", "equipmentId": "CUSTOM_ENGINE", "lcv": "0.05",
            "wtTMode": "STATIC", "wtT": "10", "cfCO2": "2.75", "cfCH4": "0", "cfN2O": "0",
            "cslip": "2", "methaneSlipApplicable": True, "rwd": "1",
            "eligibleBiomassFraction": "0",
            "sourceEvidence": evidence({
                "lcv": ("MJ/gFuel", "ESTIMATED"), "wtT": ("gCO2eq/MJ", "ESTIMATED"),
                "cfCO2": ("gGHG/gFuel", "ESTIMATED"), "cfCH4": ("gGHG/gFuel", "ESTIMATED"),
                "cfN2O": ("gGHG/gFuel", "ESTIMATED"), "cslip": ("%", "ESTIMATED"),
                "methaneSlipApplicable": ("boolean", "ESTIMATED"), "rwd": ("ratio", "ESTIMATED"),
                "eligibleBiomassFraction": ("fraction", "ESTIMATED"),
            }),
        }
        with self.assertRaisesRegex(ValueError, "BLOCKED.*csf"):
            resolve_custom_factor(payload)

    def test_custom_factor_keeps_equipment_and_field_evidence(self):
        payload = {
            "pathId": "CUSTOM_MDO", "equipmentId": "CUSTOM_ENGINE", "lcv": "0.04",
            "wtTMode": "STATIC", "wtT": "10", "cfCO2": "3", "cfCH4": "0", "cfN2O": "0",
            "cslip": "NA", "methaneSlipApplicable": False, "rwd": "1",
            "eligibleBiomassFraction": "0", "qualificationStatus": "VERIFIED_ELIGIBLE",
            "sourceEvidence": evidence({
                "lcv": ("MJ/gFuel", "VERIFIED"), "wtT": ("gCO2eq/MJ", "VERIFIED"),
                "cfCO2": ("gGHG/gFuel", "VERIFIED"), "cfCH4": ("gGHG/gFuel", "VERIFIED"),
                "cfN2O": ("gGHG/gFuel", "VERIFIED"), "cslip": ("%", "VERIFIED"),
                "methaneSlipApplicable": ("boolean", "VERIFIED"), "rwd": ("ratio", "VERIFIED"),
                "eligibleBiomassFraction": ("fraction", "VERIFIED"),
            }),
        }
        factor = resolve_custom_factor(payload)
        self.assertEqual(factor.equipment_id, "CUSTOM_ENGINE")
        self.assertEqual({item.field_name for item in factor.source_evidence}, {
            "lcv", "wtT", "cfCO2", "cfCH4", "cfN2O", "cslip",
            "methaneSlipApplicable", "rwd", "eligibleBiomassFraction",
        })


if __name__ == "__main__":
    unittest.main()
