import json
import unittest
from decimal import Decimal

from voyage_fuel.json_io import calculate_voyage_json


class JsonIoTests(unittest.TestCase):
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
        self.assertEqual([row["ratio"] for row in result["scenarios"]], ["0", "0.20", "1"])
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
