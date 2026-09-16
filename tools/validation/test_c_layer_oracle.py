"""Small hand-computable anchors for the independent experimental oracle."""
import unittest
from fractions import Fraction as F
from c_layer_oracle import solve, envelope, ledger
from c_layer_inputs import inputs


class OracleTests(unittest.TestCase):
    def setUp(self):
        self.case = dict(lb="40000", lc="40000", gb="100", gc="80",
                         rb="1", rc="1", kb="600", kc="1000",
                         mass="100", cap="1", supply=None, budget=None, target="90")

    def test_minimum_target_half(self):
        r = solve(self.case, "target_min")
        self.assertEqual(r["exact_ratio"], F(1, 2))
        self.assertAlmostEqual(r["solver_ratio"], .5)

    def test_supply_boundary(self):
        self.case["supply"] = "25"
        self.assertEqual(solve(self.case, "cap")["exact_ratio"], F(1, 4))
        self.assertIsNone(solve(self.case, "target_min")["exact_ratio"])

    def test_budget_boundary(self):
        self.case["budget"] = "10000"
        self.assertEqual(solve(self.case, "cap")["exact_ratio"], F(1, 4))

    def test_already_compliant_worsening_cheap_candidate(self):
        self.case.update(gb="80", gc="100", kb="1000", kc="600")
        self.assertEqual(solve(self.case, "target_cost")["exact_ratio"], F(1, 2))

    def test_fractional_reward_objective(self):
        self.case.update(rc="2", gc="40")
        r = solve(self.case, "improvement")
        self.assertEqual(r["exact_ratio"], F(1))
        self.assertAlmostEqual(r["solver_ratio"], 1)

    def test_envelope_ignores_dominated_intersection(self):
        r = envelope([("a", F(0), F(0)), ("b", F(10), F(1)),
                      ("c", F(30), F(3)), ("dominated", F(100), F(2))])
        self.assertEqual([(v, a, b) for v, a, b in r], [(F(10), "a", "c")])

    def test_shared_b0_does_not_require_unused_candidate_price(self):
        c = inputs()["constraints"][20]
        self.assertEqual(ledger(c, 0)["cost"], F(72000))

    def test_extremely_close_switches_remain_distinct(self):
        lines = [("a", F(0), F(0)), ("b", F(1), F(1)),
                 ("c", F("2.0000000000000000000000000000001"), F(2))]
        self.assertEqual(len(envelope(lines)), 2)


if __name__ == "__main__":
    unittest.main()
