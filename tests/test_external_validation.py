import json
import unittest
from decimal import Decimal
from pathlib import Path

from voyage_fuel.json_io import calculate_voyage_json


FIXTURE = Path(__file__).parent / "fixtures" / "external-validation-vectors.json"


class ExternalValidationVectorTests(unittest.TestCase):
    """Replay the hand-derived cross-project anchors recorded in the matrix."""

    @classmethod
    def setUpClass(cls):
        cls.vectors = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def assertDecimalClose(self, actual, expected, *, places="1e-24"):
        self.assertLess(
            abs(Decimal(str(actual)) - Decimal(expected)),
            Decimal(places),
        )

    def test_external_validation_vectors_match_recorded_anchors(self):
        for vector in self.vectors:
            with self.subTest(vector=vector["id"]):
                result = json.loads(calculate_voyage_json(vector["payload"]))
                expected = vector["expected"]
                self.assertDecimalClose(
                    result["baseline_energy_mj"], expected["baselineEnergyMJ"]
                )
                scenario = next(
                    item for item in result["scenarios"]
                    if item["ratio"] == vector["scenarioRatio"]
                )
                ets = scenario["eu_ets"]
                fuel_eu = scenario["fuel_eu"]
                self.assertDecimalClose(
                    scenario["physical_energy_mj"], expected["physicalEnergyMJ"]
                )
                for actual_key, expected_key in (
                    ("raw_co2_t", "rawCO2T"),
                    ("raw_ch4_t", "rawCH4T"),
                    ("raw_n2o_t", "rawN2OT"),
                    ("euas_required", "EUAs"),
                    ("eua_cost", "EUACost"),
                ):
                    self.assertDecimalClose(ets[actual_key], expected[expected_key])
                self.assertEqual(ets["included_gases"], expected["includedGases"])
                self.assertEqual(fuel_eu["status"], expected["fuelEUStatus"])
                for actual_key, expected_key in (
                    ("ghgi_actual_g_per_mj", "GHGI"),
                    ("target_g_per_mj", "target"),
                    ("compliance_balance_t", "complianceBalanceT"),
                    ("indicative_penalty_eur", "indicativePenaltyEUR"),
                ):
                    if expected_key in expected:
                        self.assertDecimalClose(fuel_eu[actual_key], expected[expected_key])

    def test_unqualified_rfnbo_anchor_keeps_fallback_trace(self):
        vector = next(item for item in self.vectors if item["id"] == "E4")
        result = json.loads(calculate_voyage_json(vector["payload"]))
        factor = result["candidate_factor"]
        expected = vector["expectedCandidateFactor"]
        self.assertEqual(factor["path_id"], expected["pathId"])
        self.assertEqual(factor["requested_path_id"], expected["requestedPathId"])
        self.assertEqual(factor["resolution_reason"], expected["resolutionReason"])


if __name__ == "__main__":
    unittest.main()
