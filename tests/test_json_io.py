import json
import unittest
from decimal import Decimal

from voyage_fuel.json_io import calculate_voyage_json


class JsonIoTests(unittest.TestCase):
    def test_json_accepts_custom_factor_only_with_field_evidence(self):
        def ev(field, unit):
            return [{"sourceId": f"SRC-{field}", "sourceType": "LAB_CERTIFICATE", "unit": unit, "verificationStatus": "VERIFIED"}]
        payload = {
            "reportYear": 2026, "departurePort": "CNSHG", "arrivalPort": "NLRTM",
            "baseline": {"pathId": "CUSTOM_BASE", "custom": True, "massTonnes": "1", "pricePerTonne": "600",
                "equipmentId": "ENGINE", "lcv": "0.04", "wtTMode": "STATIC", "wtT": "10", "cfCO2": "3", "cfCH4": "0", "cfN2O": "0", "cslip": "NA", "methaneSlipApplicable": False, "rwd": "1", "eligibleBiomassFraction": "0",
                "sourceEvidence": {"lcv": ev("lcv", "MJ/gFuel"), "wtT": ev("wtT", "gCO2eq/MJ"), "cfCO2": ev("cfCO2", "gGHG/gFuel"), "cfCH4": ev("cfCH4", "gGHG/gFuel"), "cfN2O": ev("cfN2O", "gGHG/gFuel"), "cslip": ev("cslip", "%"), "methaneSlipApplicable": ev("methaneSlipApplicable", "boolean"), "rwd": ev("rwd", "ratio"), "eligibleBiomassFraction": ev("eligibleBiomassFraction", "fraction")}},
            "candidate": {"pathId": "MDO", "massTonnes": "1", "pricePerTonne": "700"},
            "euaPricePerTCO2e": "80",
        }
        result = json.loads(calculate_voyage_json(json.dumps(payload)))
        self.assertEqual(result["scenarios"][0]["eu_ets"]["included_gases"], ["CO2", "CH4", "N2O"])
        self.assertEqual(result["scenarios"][0]["fuel_eu"]["status"], "SURPLUS_ESTIMATE")
        self.assertEqual(result["baseline_factor"]["factor_status"], "VERIFIED")
        self.assertEqual(result["baseline_factor"]["source_evidence"][0]["source_id"], "SRC-lcv")

    def test_json_exposes_constraint_bounds_and_marks_infeasible_reference(self):
        payload = {
            "reportYear": 2026,
            "departurePort": "CNSHG",
            "arrivalPort": "NLRTM",
            "baseline": {"pathId": "MGO", "massTonnes": "100", "pricePerTonne": "600"},
            "candidate": {
                "pathId": "UCO_FAME", "pricePerTonne": "1000",
                "eligibleBiomassFraction": "1", "qualificationStatus": "ASSUMED_ELIGIBLE",
            },
            "euaPricePerTCO2e": "80",
            "candidateSupplyTonnes": "10",
            "incrementalBudget": "5000",
            "complianceImprovementValue": "268.31901315986921862",
            "maxBlendRatio": "0.30",
            "candidateAllowsPureUse": True,
        }
        result = json.loads(calculate_voyage_json(json.dumps(payload)))
        self.assertEqual(result["constraints"]["target_status"], "TARGET_REACHABLE")
        self.assertEqual(result["constraints"]["x_supply"], "0.098682690085509590940605500346660503813265541945921")
        self.assertEqual(result["economics"]["comparison_value"], "268.31901315986921862")
        self.assertLess(abs(Decimal(result["economics"]["pc_break_even"]) - Decimal("630.76546135831381733")), Decimal("1e-18"))
        b100 = next(row for row in result["scenarios"] if row["ratio"] == "1")
        self.assertEqual(b100["constraint_status"], "CONSTRAINT_INFEASIBLE")

    def test_json_round_trip_preserves_decimal_result_as_string(self):
        payload = {
            "reportYear": 2025,
            "departurePort": "CNSHG",
            "arrivalPort": "NLRTM",
            "baseline": {"pathId": "MDO", "massTonnes": "100", "pricePerTonne": "600"},
            "candidate": {"pathId": "UCO_FAME", "pricePerTonne": "1000", "eligibleBiomassFraction": "1", "qualificationStatus": "ASSUMED_ELIGIBLE"},
            "euaPricePerTCO2e": "80",
            "specifiedBlendRatios": ["0.20"],
            "maxBlendRatio": "1",
            "candidateAllowsPureUse": True,
        }
        result = json.loads(calculate_voyage_json(json.dumps(payload)))
        self.assertEqual(Decimal(result["baseline_energy_mj"]), Decimal("4270000"))
        ratios = [row["ratio"] for row in result["scenarios"]]
        self.assertEqual(ratios[:3], ["0", "0.20", "1"])
        self.assertIn("0.022130676682982508109158969772727924816074006340564", ratios)
        self.assertEqual(result["scenarios"][1]["execution_status"], "EXECUTION_CONDITIONS_PENDING")

    def test_json_resolves_rfnbo_qualification_inputs(self):
        payload = {
            "reportYear": 2025,
            "departurePort": "CNSHG",
            "arrivalPort": "NLRTM",
            "baseline": {"pathId": "MDO", "massTonnes": "1", "pricePerTonne": "600"},
            "candidate": {
                "pathId": "E_DIESEL", "pricePerTonne": "1000",
                "qualificationStatus": "ASSUMED_ELIGIBLE", "e": "28.2", "eu": "20",
            },
            "euaPricePerTCO2e": None,
            "candidateAllowsPureUse": True,
        }
        result = json.loads(calculate_voyage_json(json.dumps(payload)))
        self.assertEqual(result["scenarios"][1]["ratio"], "1")
        self.assertEqual(result["scenarios"][1]["fuel_eu"]["wt_t_intensity_g_per_mj"], "4.1")


if __name__ == "__main__":
    unittest.main()
