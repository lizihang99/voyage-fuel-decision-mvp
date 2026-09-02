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


if __name__ == "__main__":
    unittest.main()
