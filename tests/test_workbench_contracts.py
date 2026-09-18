"""Contracts consumed by the decision workbench view."""

import unittest

from fastapi.testclient import TestClient

from tests.test_goal_alignment_fixes import payload
from voyage_fuel.web import app


class WorkbenchContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_b0_only_does_not_create_candidate_advice(self):
        response = self.client.post("/api/calculate", json=payload(candidates=[]))

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual([row["scenario_id"] for row in result["scenarios"]], ["B0"])
        self.assertEqual(result["recommendations"], [])
        self.assertIsNone(result["decision_summary"])
        self.assertTrue(result["result_snapshot_id"])

    def test_report_set_winner_and_continuous_improvement_boundary_are_distinct(self):
        # The continuous optimum is B100, but this candidate cannot be used at
        # 100%. The summary therefore reports the best existing report point,
        # while the candidate recommendation correctly remains unavailable.
        request = payload()
        request["candidates"][0]["maxBlendRatio"] = "1"
        request["candidates"][0]["candidateAllowsPureUse"] = False

        response = self.client.post("/api/calculate", json=request)

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(
            result["decision_summary"]["max_improvement_scenario_id"],
            "uco@0.2",
        )
        recommendation = next(
            row for row in result["recommendations"]
            if row["recommendation_id"] == "MAX_COMPLIANCE_IMPROVEMENT:uco"
        )
        self.assertEqual(recommendation["status"], "UNAVAILABLE")
        self.assertEqual(recommendation["reason"], "SCENARIO_UNAVAILABLE")
        constraints = result["candidate_results"][0]["voyage_result"]["constraints"]
        self.assertEqual(constraints["x_max_improvement"], "1")
        self.assertNotIn("uco@1", [row["scenario_id"] for row in result["scenarios"]])

    def test_target_winner_is_a_compliant_report_scenario(self):
        response = self.client.post("/api/calculate", json=payload())

        self.assertEqual(response.status_code, 200)
        result = response.json()
        scenario_id = result["decision_summary"]["target_min_cost_scenario_id"]
        scenario = next(row for row in result["scenarios"] if row["scenario_id"] == scenario_id)
        self.assertGreaterEqual(
            float(scenario["result"]["fuel_eu"]["compliance_balance_g"]),
            0,
        )


if __name__ == "__main__":
    unittest.main()
