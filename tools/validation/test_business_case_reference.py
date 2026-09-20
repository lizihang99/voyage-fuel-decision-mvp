"""Hand-derived reference-engine anchors; no production code or fixtures."""

import copy
from decimal import Decimal, localcontext
from fractions import Fraction
import json
import unittest

from tools.validation.business_case_reference import (
    calculate_reference,
    derive_issues,
    encode,
    envelope,
    ledger,
    reviewed_issues,
)


def factor(path="HFO", **overrides):
    value = dict(
        path_id=path, lcv="0.0405", wtt="13.5", co2="3.114",
        ch4="0.00005", n2o="0.00018", slip=None, methane=False,
        rwd="1", biomass="0", factor_status="FIXED",
        qualification="NOT_DEMONSTRATED", mode="STATIC",
        equipment_id="ALL_ICE", source_ids=["HAND_ANCHOR"],
    )
    value.update(overrides)
    return value


def uco(**overrides):
    value = factor(
        "UCO_FAME", lcv="0.037", wtt="-61.694595", co2="2.834",
        mode="BIO_E", e="14.9", biomass="1",
        qualification="ASSUMED_ELIGIBLE", factor_status="ESTIMATED",
    )
    value.update(overrides)
    return value


def case(baseline=None, candidate=None, mass="1", year=2025, scope="1",
         **candidate_options):
    return {
        "id": "hand",
        "request": {
            "reportYear": year, "currency": "EUR",
            "baseline": {
                "pathId": "baseline", "massTonnes": mass, "pricePerTonne": "600",
            },
            "euaPricePerTCO2e": "80",
            "candidates": [{
                "candidateId": "c", "pathId": "candidate",
                "pricePerTonne": "1000", "allowsPureUse": True,
                **candidate_options,
            }],
        },
        "snapshot": {
            "scope": {
                "geo": "1", "surrender": {2024: "0.4", 2025: "0.7"}.get(year, "1"),
                "fueleu": None if year == 2024 else scope,
            },
            "baseline": baseline or factor(),
            "candidates": {"c": candidate or uco()},
        },
        "expected_issues": [], "expected_http_status": 200,
    }


def q(value):
    return Fraction(value)


class PhysicsAnchors(unittest.TestCase):
    def test_a_mass_space_energy_conservation(self):
        c = case(factor(lcv="0.04"), factor(lcv="0.05"), mass="100")
        result = ledger(c, "c", "0.25")
        self.assertEqual(q(result["physical"]["total_mass_t"]), Fraction(1600, 17))
        self.assertEqual(q(result["physical"]["baseline_mass_t"]), Fraction(1200, 17))
        self.assertEqual(q(result["physical"]["candidate_mass_t"]), Fraction(400, 17))
        self.assertEqual(result["physical"]["energy_mj"], "4000000")
        self.assertEqual(
            sum(q(x["energy_mj"]) for x in result["components"]), 4000000
        )

    def test_b_fueleu_hfo_lng_bio_rfnbo_and_fossil_fallback(self):
        lng = factor(
            "LNG", lcv="0.0491", wtt="18.5", co2="2.75", ch4="0",
            n2o="0.00011", slip="3.1", methane=True,
        )
        ediesel = factor(
            "E_DIESEL", lcv="0.0427", co2="3.206", mode="RFNBO_E",
            e="20", eu="73.2", wtt="999", rwd="2",
            qualification="VERIFIED_ELIGIBLE", factor_status="VERIFIED",
        )
        mdo = factor("MDO", lcv="0.0427", wtt="14.4", co2="3.206")
        for f, expected in [
            (factor(), "-97499.6"), (lng, "6573.06"),
            (uco(), "2699271.6"), (ediesel, "3320056.36"), (mdo, "-61088.64"),
        ]:
            with self.subTest(path=f["path_id"]):
                s = ledger(case(baseline=f), None, 0)
                self.assertEqual(q(s["fueleu"]["balance_g"]), q(expected))
        s = ledger(case(baseline=ediesel), None, 0)
        self.assertEqual(s["fueleu"]["denominator_mj"], "85400")
        self.assertEqual(q(s["fueleu"]["wtt_intensity"]), q("-26.6"))
        self.assertEqual(q(s["ets"]["raw_by_gas_t"]["CO2"]), q("3.206"))
        s = ledger(case(baseline=lng), None, 0)
        self.assertEqual(q(s["components"][0]["ttw_mass_eq"]), q("3.47151382"))

    def test_c_half_scope_changes_balance_not_intensity(self):
        c = case(mass="775/810", scope="0.5")
        half = ledger(c, "c", "0.5")
        self.assertEqual(q(half["physical"]["total_mass_t"]), 1)
        self.assertEqual(half["physical"]["energy_mj"], "38750")
        self.assertEqual(half["fueleu"]["scoped_energy_mj"], "19375")
        self.assertEqual(half["fueleu"]["balance_g"], "650443")
        c["snapshot"]["scope"]["fueleu"] = "1"
        full = ledger(c, "c", "0.5")
        self.assertEqual(full["fueleu"]["ghgi"], half["fueleu"]["ghgi"])
        self.assertEqual(full["fueleu"]["balance_g"], "1300886")

    def test_d_deficit_penalty_and_2030_target(self):
        c = case(factor(lcv="0.041", wtt="100", co2="0", ch4="0", n2o="0"),
                 mass="1000")
        s = ledger(c, None, 0)
        self.assertEqual(q(s["fueleu"]["target"]), q("89.3368"))
        self.assertEqual(s["fueleu"]["balance_g"], "-437191200")
        self.assertEqual(q(s["fueleu"]["penalty_eur"]), q("255916.8"))
        self.assertEqual(s["fueleu"]["classification"], "DEFICIT_ESTIMATE")
        c["snapshot"]["scope"]["fueleu"] = "0.5"
        self.assertEqual(q(ledger(c, None, 0)["fueleu"]["penalty_eur"]), q("127958.4"))
        c["request"]["reportYear"] = 2030
        self.assertEqual(q(ledger(c, None, 0)["fueleu"]["target"]), q("85.6904"))

    def test_ets_methane_slip_year_gases_and_single_scope(self):
        lng = factor(
            "LNG", lcv="0.0491", wtt="18.5", co2="2.75", ch4="0",
            n2o="0.00011", slip="3.1", methane=True,
        )
        for year, expected in [(2024, "1065.9"), (2025, "1865.325"),
                               (2026, "3560.99635")]:
            s = ledger(case(lng, mass="1000", year=year), None, 0)
            self.assertEqual(q(s["ets"]["euas"]), q(expected))
            self.assertEqual(q(s["ets"]["raw_by_gas_t"]["CO2"]), q("2664.75"))
            self.assertEqual(s["ets"]["raw_by_gas_t"]["CH4"], "31")
            self.assertEqual(q(s["ets"]["raw_by_gas_t"]["N2O"]), q("0.10659"))
            self.assertEqual(q(s["ets"]["raw_co2e_t"]), q("3560.99635"))
        c = case(lng, mass="1000", year=2025)
        c["snapshot"]["scope"]["geo"] = "0.5"
        self.assertEqual(q(ledger(c, None, 0)["ets"]["euas"]), q("932.6625"))

    def test_biomass_only_reduces_ets_co2(self):
        unqualified = ledger(case(uco(biomass="0"), year=2026), None, 0)
        qualified = ledger(case(uco(), year=2026), None, 0)
        self.assertEqual(q(unqualified["ets"]["euas"]), q("2.8831"))
        self.assertEqual(q(qualified["ets"]["euas"]), q("0.0491"))
        self.assertEqual(qualified["fueleu"], unqualified["fueleu"])
        self.assertEqual(qualified["fueleu"]["penalty_eur"], "0")
        mixed = ledger(case(factor(), uco(), year=2026), "c", "0.5")
        self.assertGreater(q(mixed["ets"]["raw_by_gas_t"]["CO2"]), 0)

    def test_non_methane_slip_gas_only_affects_fueleu(self):
        f = factor(
            lcv="0.04", wtt="0", co2="2", ch4="0", n2o="0",
            slip="10", csf_co2="3", csf_ch4="0", csf_n2o="0",
        )
        s = ledger(case(f, year=2026), None, 0)
        self.assertEqual(s["ets"]["euas"], "2")
        self.assertEqual(q(s["fueleu"]["ghgi"]), q("52.5"))

    def test_zero_scope_and_2024_nulls_have_reasons(self):
        for year, scope, status in [
            (2024, None, "NOT_YET_APPLICABLE"), (2026, "0", "OUT_OF_SCOPE")
        ]:
            c = case(year=year, scope=scope)
            c["snapshot"]["scope"]["geo"] = "0"
            del c["request"]["euaPricePerTCO2e"]
            s = ledger(c, None, 0)
            for field in ("ghgi", "balance_g", "balance_t", "penalty_eur"):
                self.assertIsNone(s["fueleu"][field])
                self.assertEqual(s["null_reasons"]["fueleu." + field], status)
            for field in ("target", "denominator_mj"):
                self.assertIsNone(s["fueleu"][field])
                self.assertEqual(s["null_reasons"]["fueleu." + field], status)
            self.assertEqual(s["fueleu"]["scoped_energy_mj"], "0")
            self.assertEqual(s["components"][0]["denominator_mj"], "40500")
            self.assertEqual(s["ets"]["euas"], "0")
            self.assertIsNone(s["costs"]["eua"])

    def test_delta_signs_and_zero_baseline(self):
        c = case(factor(co2="0", ch4="0", n2o="0"), year=2026)
        s = ledger(c, "c", "0.2")
        self.assertIsNone(s["percent_deltas"]["euas"])
        self.assertEqual(s["null_reasons"]["percent_deltas.euas"], "ZERO_BASELINE")
        self.assertEqual(
            q(s["deltas"]["model_cost"]),
            q(s["deltas"]["fuel_cost"]) + q(s["deltas"]["eua_cost"]),
        )
        self.assertEqual(q(s["costs"]["eua_savings"]), -q(s["deltas"]["eua_cost"]))

    def test_rfnbo_reward_only_changes_denominator_and_uses_physical_balance_energy(self):
        b = factor(lcv="1", wtt="100", co2="0", ch4="0", n2o="0")
        c = factor(lcv="1", wtt="20", co2="0", ch4="0", n2o="0", rwd="2")
        s = ledger(case(b, c, mass="10", year=2026), "c", "0.5")
        self.assertEqual(s["physical"]["energy_mj"], "10000000")
        self.assertEqual(s["fueleu"]["denominator_mj"], "15000000")
        self.assertEqual(s["fueleu"]["wtt_numerator_g"], "600000000")
        self.assertEqual(s["fueleu"]["ghgi"], "40")
        self.assertEqual(s["fueleu"]["balance_g"], "493368000")
        self.assertEqual(s["deltas"]["balance_t"], "600")

    def test_each_missing_price_preserves_physics_and_nulls_its_cost(self):
        full = case(year=2026)
        expected = ledger(full, "c", "0.2")
        for owner, key, null_field in [
            ("baseline", "pricePerTonne", "fuel"),
            ("candidate", "pricePerTonne", "fuel"),
            ("request", "euaPricePerTCO2e", "eua"),
        ]:
            with self.subTest(owner=owner):
                c = copy.deepcopy(full)
                container = (c["request"]["baseline"] if owner == "baseline"
                             else c["request"]["candidates"][0] if owner == "candidate"
                             else c["request"])
                del container[key]
                s = ledger(c, "c", "0.2")
                self.assertEqual(s["physical"], expected["physical"])
                self.assertEqual(s["ets"], expected["ets"])
                self.assertEqual(s["fueleu"], expected["fueleu"])
                self.assertIsNone(s["costs"][null_field])
                self.assertIsNone(s["costs"]["model"])
                self.assertEqual(s["status"], "CALCULABLE")

    def test_na_gas_is_retained_as_zero_in_applicable_mrv_arithmetic(self):
        s = ledger(case(factor(co2="0", ch4="0", n2o=None), year=2026), None, 0)
        self.assertEqual(s["ets"]["raw_by_gas_t"]["N2O"], "0")

    def test_only_positive_mass_components_contribute_evidence_status(self):
        c = case(factor(factor_status="ESTIMATED"), uco(factor_status="VERIFIED"))
        self.assertEqual(ledger(c, "c", "0")["factor_status"], "ESTIMATED")
        self.assertEqual(ledger(c, "c", "0.5")["factor_status"], "ESTIMATED")
        pure = ledger(c, "c", "1")
        self.assertEqual(pure["factor_status"], "VERIFIED")
        self.assertEqual(len(pure["components"]), 1)
        self.assertEqual(pure["components"][0]["path_id"], "UCO_FAME")


class SearchAnchors(unittest.TestCase):
    def simple(self, **options):
        return case(
            factor(lcv="1", wtt="100", co2="0", ch4="0", n2o="0"),
            factor(lcv="1", wtt="0", co2="0", ch4="0", n2o="0"),
            mass="10", year=2026, **options,
        )

    def test_exact_constraint_vertices_and_all_report_roles(self):
        c = self.simple(
            maxBlendRatio="0.8", candidateSupplyTonnes="3",
            incrementalBudget="800", specifiedBlendRatios=["0.1", "0.1", "0.9"],
        )
        result = calculate_reference(c)["candidates"]["c"]
        bounds = result["constraints"]
        self.assertEqual(q(bounds["x_budget"]), q("0.2"))
        self.assertEqual(q(bounds["x_supply"]), q("0.3"))
        self.assertEqual(q(bounds["x_cap"]), q("0.2"))
        points = {q(p["ratio"]): p for p in result["report_points"]}
        self.assertEqual(set(points), {q("0"), q("0.1"), q("0.106632"), q("0.2"),
                                       q("0.3"), q("0.9"), q("1")})
        self.assertIn("CAP", points[q("0.2")]["roles"])
        self.assertIn("BUDGET_BOUNDARY", points[q("0.2")]["roles"])
        self.assertIn("MAX_IMPROVEMENT", points[q("0.2")]["roles"])
        self.assertEqual(points[q("0.3")]["scenario"]["constraint_status"],
                         "CONSTRAINT_INFEASIBLE")
        self.assertEqual(result["target"]["status"], "REACHABLE")
        self.assertEqual(q(result["optima"]["cost"]["objective"]), 6000)
        self.assertEqual(q(result["optima"]["target_cost"]["objective"]), q("6426.528"))

    def test_spec_g_unequal_lcv_supply_budget_target_and_break_even(self):
        c = case(
            factor("MGO", lcv="0.0427", wtt="14.4", co2="3.206"),
            uco(), mass="100", year=2026, scope="0.5",
            maxBlendRatio="0.3", candidateSupplyTonnes="10", incrementalBudget="5000",
        )
        c["snapshot"]["scope"]["geo"] = "0.5"
        result = calculate_reference(c)["candidates"]["c"]
        self.assertEqual(q(result["constraints"]["x_supply"]), Fraction(427, 4327))
        boundary = ledger(c, "c", result["constraints"]["x_cap"])
        self.assertEqual(boundary["physical"]["candidate_mass_t"], "10")
        target = ledger(c, "c", result["target"]["unconstrained_low"])
        self.assertEqual(target["fueleu"]["balance_g"], "0")
        self.assertEqual(
            q(result["break_even"]["candidate_price"]["value"]), Fraction(67334213, 106750)
        )
        self.assertEqual(result["break_even"]["eua_price"]["status"], "FINITE_NON_NEGATIVE")
        self.assertEqual(
            q(result["break_even"]["eua_price"]["value"]),
            Fraction(4100000000, 11834213),
        )

    def test_no_solution_still_reports_maximum_improvement(self):
        c = self.simple()
        c["snapshot"]["candidates"]["c"]["wtt"] = "95"
        r = calculate_reference(c)["candidates"]["c"]
        self.assertEqual(r["target"]["reason"], "TARGET_NO_SOLUTION")
        self.assertEqual(r["optima"]["max_improvement"]["representative_ratio"], "1")
        self.assertIn("MAX_IMPROVEMENT", r["report_points"][-1]["roles"])

    def test_target_unreachable_retains_bound_without_reporting_infeasible_target(self):
        result = calculate_reference(self.simple(maxBlendRatio="0.05"))
        r = result["candidates"]["c"]
        self.assertEqual(r["target"]["reason"], "TARGET_UNREACHABLE_UNDER_CONSTRAINTS")
        self.assertEqual(q(r["target"]["unconstrained_low"]), q("0.106632"))
        self.assertEqual(q(r["constraints"]["x_target_min_unconstrained"]), q("0.106632"))
        self.assertEqual(r["optima"]["target_cost"]["status"], "UNAVAILABLE")
        # SPEC 11.2's final definition uses the constrained intersection for
        # xTargetMin in 11.6; its separate unconstrained bound remains visible.
        self.assertFalse(any(q(p["ratio"]) == q("0.106632") for p in r["report_points"]))
        self.assertFalse(any("TARGET_MIN" in p["roles"] for p in r["report_points"]))
        self.assertIsNone(r["target"]["constrained_low"])
        self.assertIsNone(r["target"]["constrained_high"])
        for row in result["economics"]["ranking"] + result["economics"]["lines"]:
            if row["candidate_id"] == "c":
                self.assertLessEqual(q(row["ratio"]), q("0.05"))

    def test_cheap_dirty_candidate_cost_stops_at_target_upper_bound(self):
        c = self.simple(pricePerTonne="100", maxBlendRatio="0.8")
        c["snapshot"]["baseline"]["wtt"] = "80"
        c["snapshot"]["candidates"]["c"]["wtt"] = "100"
        r = calculate_reference(c)["candidates"]["c"]
        self.assertEqual(r["target"]["constrained_low"], "0")
        self.assertEqual(q(r["target"]["constrained_high"]), q("0.46684"))
        self.assertEqual(q(r["optima"]["target_cost"]["representative_ratio"]), q("0.46684"))
        self.assertEqual(r["optima"]["max_improvement"]["representative_ratio"], "0")
        self.assertIn(q("0.46684"), {q(p["ratio"]) for p in r["report_points"]})

    def test_flat_objectives_preserve_entire_tie_interval(self):
        c = self.simple(pricePerTonne="600", maxBlendRatio="0.75")
        c["snapshot"]["baseline"]["wtt"] = "80"
        c["snapshot"]["candidates"]["c"]["wtt"] = "80"
        r = calculate_reference(c)["candidates"]["c"]
        for name in ("cost", "target_cost", "max_improvement"):
            optimum = r["optima"][name]
            self.assertEqual(optimum["ratio_interval"], ["0", "3/4"])
            self.assertEqual(optimum["representative_ratio"], "0")

    def test_b100_permission_filters_every_role_without_epsilon(self):
        c = self.simple(allowsPureUse=False, pricePerTonne="100")
        r = calculate_reference(c)["candidates"]["c"]
        self.assertFalse(any(q(p["ratio"]) == 1 for p in r["report_points"]))
        self.assertEqual(r["constraints"]["x_cap"], "1")
        self.assertEqual(r["optima"]["cost"]["status"], "UNAVAILABLE")
        self.assertEqual(r["optima"]["cost"]["reason"], "PURE_USE_NOT_ALLOWED")
        self.assertEqual(r["optima"]["cost"]["objective"], "1000")
        self.assertFalse(r["optima"]["cost"]["attained"])

    def test_production_pure_permission_key_takes_precedence(self):
        c = self.simple(candidateAllowsPureUse=False, allowsPureUse=True)
        r = calculate_reference(c)["candidates"]["c"]
        self.assertNotIn(q("1"), {q(p["ratio"]) for p in r["report_points"]})
        c["request"]["candidates"][0].update(
            candidateAllowsPureUse=True, allowsPureUse=False
        )
        r = calculate_reference(c)["candidates"]["c"]
        self.assertIn(q("1"), {q(p["ratio"]) for p in r["report_points"]})

    def test_missing_prices_budget_unverified_and_known_violation_precedence(self):
        c = self.simple(incrementalBudget="100", maxBlendRatio="0.5")
        del c["request"]["candidates"][0]["pricePerTonne"]
        r = calculate_reference(c)
        cand = r["candidates"]["c"]
        self.assertEqual(cand["status"], "CALCULABLE")
        self.assertIsNone(cand["constraints"]["x_budget"])
        self.assertEqual(cand["constraints"]["budget_status"], "UNVERIFIED")
        self.assertEqual(ledger(c, "c", "0.1")["constraint_status"], "CONSTRAINT_UNVERIFIED")
        self.assertEqual(ledger(c, "c", "0.7")["constraint_status"], "CONSTRAINT_INFEASIBLE")
        self.assertEqual(ledger(c, "c", "0")["constraint_status"], "CONSTRAINT_FEASIBLE")
        self.assertEqual(cand["optima"]["max_improvement"]["status"], "UNAVAILABLE")
        self.assertEqual(r["economics"]["cost_minimum"]["winners"][0]["candidate_id"], None)
        self.assertEqual(r["economics"]["ranking"][0]["candidate_id"], None)

    def test_unverified_budget_keeps_mathematical_improvement_bound_separate(self):
        c = self.simple(incrementalBudget="100", maxBlendRatio="0.5")
        del c["request"]["candidates"][0]["pricePerTonne"]
        result = calculate_reference(c)
        candidate = result["candidates"]["c"]
        optimum = candidate["optima"]["max_improvement"]
        self.assertEqual(candidate["constraints"]["x_max_improvement"], "1/2")
        self.assertEqual(optimum["mathematical_ratio"], "1/2")
        self.assertEqual(optimum["mathematical_ratio_interval"], ["1/2", "1/2"])
        self.assertEqual(optimum["objective"], "500")
        self.assertIsNone(optimum["representative_ratio"])
        self.assertEqual(optimum["status"], "UNAVAILABLE")
        self.assertEqual(optimum["reason"], "BUDGET_UNAVAILABLE_WITHOUT_PRICES")
        self.assertNotIn("c", {
            w["candidate_id"] for w in result["economics"]["max_improvement"]["winners"]
        })
        for key in ("candidate_price", "eua_price"):
            self.assertEqual(candidate["break_even"][key]["status"], "UNAVAILABLE")
            self.assertEqual(candidate["break_even"][key]["reason"],
                             "PRICE_REQUIRED_FOR_COMPARISON")

    def test_mathematical_improvement_bound_is_not_always_cap(self):
        for candidate_wtt, expected_interval in [
            ("110", ["0", "0"]), ("100", ["0", "1/2"])
        ]:
            with self.subTest(candidate_wtt=candidate_wtt):
                c = self.simple(incrementalBudget="100", maxBlendRatio="0.5")
                c["snapshot"]["candidates"]["c"]["wtt"] = candidate_wtt
                del c["request"]["candidates"][0]["pricePerTonne"]
                candidate = calculate_reference(c)["candidates"]["c"]
                optimum = candidate["optima"]["max_improvement"]
                self.assertEqual(candidate["constraints"]["x_cap"], "1/2")
                self.assertEqual(candidate["constraints"]["x_max_improvement"], "0")
                self.assertEqual(optimum["mathematical_ratio_interval"], expected_interval)
                self.assertEqual(optimum["representative_ratio"], "0")
                self.assertEqual(optimum["ratio_interval"], ["0", "0"])

    def test_inapplicable_improvement_has_no_mathematical_bound(self):
        c = self.simple()
        c["snapshot"]["scope"]["fueleu"] = "0"
        candidate = calculate_reference(c)["candidates"]["c"]
        self.assertIsNone(candidate["constraints"]["x_max_improvement"])
        self.assertIsNone(candidate["optima"]["max_improvement"]["mathematical_ratio"])
        self.assertIsNone(
            candidate["optima"]["max_improvement"]["mathematical_ratio_interval"]
        )

    def test_missing_price_without_budget_keeps_physical_max_improvement(self):
        c = self.simple()
        del c["request"]["candidates"][0]["pricePerTonne"]
        r = calculate_reference(c)["candidates"]["c"]
        self.assertEqual(r["optima"]["max_improvement"]["status"], "AVAILABLE")
        self.assertEqual(r["optima"]["cost"]["reason"], "PRICE_REQUIRED_FOR_COMPARISON")
        self.assertIsNone(r["break_even"]["candidate_price"]["value"])

    def test_case_block_and_candidate_block_are_isolated(self):
        c = self.simple()
        c["request"]["adjacentValidPortOfCallConfirmed"] = False
        del c["snapshot"]
        r = calculate_reference(c)
        self.assertEqual(r["status"], "BLOCKED")
        self.assertIsNone(r["baseline"])
        self.assertEqual(r["candidates"], {})
        c = self.simple()
        del c["snapshot"]["candidates"]["c"]
        c["expected_issues"] = [
            {"code": "MISSING_REQUIRED_FACTOR", "scope": "CANDIDATE", "candidate_id": "c"}
        ]
        r = calculate_reference(c)
        self.assertIsNotNone(r["baseline"])
        self.assertEqual(r["candidates"]["c"]["status"], "BLOCKED")

    def test_derived_data_warnings_do_not_block_calculation_or_ledger(self):
        c = self.simple()
        del c["request"]["euaPricePerTCO2e"]
        c["request"]["candidates"][0]["incrementalBudget"] = "1000"
        r = calculate_reference(c)
        self.assertEqual(
            [(issue["code"], issue["scope"], issue["candidate_id"]) for issue in r["issues"]],
            [
                ("BUDGET_UNAVAILABLE_WITHOUT_PRICES", "CANDIDATE", "c"),
                ("PRICE_REQUIRED_FOR_COMPARISON", "CASE", None),
            ],
        )
        self.assertEqual(r["status"], "CALCULABLE")
        self.assertIsNotNone(r["baseline"])
        self.assertEqual(ledger(c, None, 0)["physical"]["energy_mj"], "10000000")
        self.assertEqual(ledger(c, "c", "0.2")["status"], "CALCULABLE")

    def test_real_case_blocker_takes_precedence_over_nonblocking_warning(self):
        c = self.simple()
        del c["request"]["euaPricePerTCO2e"]
        c["request"]["reportYear"] = 2031
        del c["snapshot"]
        self.assertEqual(calculate_reference(c)["status"], "BLOCKED")
        with self.assertRaises(ValueError):
            ledger(c, None, 0)

    def test_missing_unused_candidate_price_does_not_erase_known_b0_cost(self):
        c = self.simple()
        del c["request"]["candidates"][0]["pricePerTonne"]
        shared = ledger(c, None, 0)
        candidate_b0 = ledger(c, "c", 0)
        self.assertEqual(shared["costs"]["fuel"], "6000")
        self.assertEqual(candidate_b0["costs"]["fuel"], "6000")
        self.assertEqual(candidate_b0["costs"]["model"], "6000")
        self.assertEqual(shared["status"], "COMPARABLE")
        self.assertEqual(candidate_b0["status"], "CALCULABLE")

    def test_case_global_winners_include_baseline_and_candidate_ties(self):
        c = self.simple(pricePerTonne="600", maxBlendRatio="0.5")
        other = copy.deepcopy(c["request"]["candidates"][0])
        other["candidateId"] = "d"
        c["request"]["candidates"].append(other)
        c["snapshot"]["candidates"]["d"] = copy.deepcopy(c["snapshot"]["candidates"]["c"])
        r = calculate_reference(c)["economics"]
        self.assertEqual(r["cost_minimum"]["objective"], "6000")
        self.assertEqual({w["candidate_id"] for w in r["cost_minimum"]["winners"]},
                         {None, "c", "d"})
        self.assertEqual({w["candidate_id"] for w in r["max_improvement"]["winners"]},
                         {"c", "d"})

    def test_break_even_zero_scope_parallel_negative_and_all_ties(self):
        c = self.simple(pricePerTonne="600")
        r = calculate_reference(c)["candidates"]["c"]["break_even"]
        self.assertEqual(r["eua_price"]["status"], "ALL_PRICES_TIED")
        c["request"]["candidates"][0]["pricePerTonne"] = "1000"
        r = calculate_reference(c)["candidates"]["c"]["break_even"]
        self.assertEqual(r["eua_price"]["status"], "NO_FINITE_THRESHOLD")
        c["snapshot"]["scope"]["geo"] = "0"
        r = calculate_reference(c)["candidates"]["c"]["break_even"]
        self.assertEqual(r["eua_price"]["status"], "EUA_PRICE_IRRELEVANT")
        c = self.simple()
        c["snapshot"]["candidates"]["c"]["co2"] = "100"
        r = calculate_reference(c)["candidates"]["c"]["break_even"]
        self.assertEqual(r["candidate_price"]["status"], "NEGATIVE_THRESHOLD")
        self.assertEqual(r["eua_price"]["status"], "NEGATIVE_THRESHOLD")

    def test_zero_budget_supply_and_blend_cap_are_real_zero_constraints(self):
        for options in [
            {"incrementalBudget": "0"}, {"candidateSupplyTonnes": "0"},
            {"maxBlendRatio": "0"}, {"maxBlendRatio": 0},
        ]:
            with self.subTest(options=options):
                r = calculate_reference(self.simple(**options))["candidates"]["c"]
                self.assertEqual(r["constraints"]["x_cap"], "0")
                self.assertEqual(r["optima"]["max_improvement"]["representative_ratio"], "0")
                self.assertEqual(r["optima"]["cost"]["representative_ratio"], "0")
        c = self.simple(pricePerTonne="100", incrementalBudget="0")
        r = calculate_reference(c)["candidates"]["c"]
        self.assertEqual(r["constraints"]["x_budget"], "1")
        self.assertEqual(r["optima"]["cost"]["representative_ratio"], "1")

    def test_rfnbo_target_root_is_a_mass_space_vertex(self):
        c = self.simple()
        c["snapshot"]["candidates"]["c"].update(wtt="20", rwd="2")
        r = calculate_reference(c)["candidates"]["c"]
        self.assertEqual(q(r["target"]["unconstrained_low"]), Fraction(13329, 211671))
        at_target = ledger(c, "c", r["target"]["unconstrained_low"])
        self.assertEqual(at_target["fueleu"]["balance_g"], "0")
        self.assertEqual(r["optima"]["max_improvement"]["objective"], "900")

    def test_tiny_signed_residuals_are_never_rounded_to_target_in_reference(self):
        c = self.simple()
        c["snapshot"]["candidates"]["c"].update(wtt="20", rwd="2")
        target_ratio = Fraction(13329, 211671)
        scale = 10**60
        below = Fraction((target_ratio.numerator * scale) // target_ratio.denominator, scale)
        above = below + Fraction(1, scale)
        low = ledger(c, "c", below)
        high = ledger(c, "c", above)
        exact = ledger(c, "c", target_ratio)
        self.assertEqual(low["fueleu"]["classification"], "DEFICIT_ESTIMATE")
        self.assertEqual(high["fueleu"]["classification"], "SURPLUS_ESTIMATE")
        self.assertEqual(exact["fueleu"]["classification"], "ON_TARGET_ESTIMATE")
        self.assertLess(q(low["fueleu"]["balance_g"]), 0)
        self.assertGreater(q(low["fueleu"]["balance_g"]), -Fraction(1, 10**49))
        self.assertGreater(q(high["fueleu"]["balance_g"]), 0)
        self.assertLess(q(high["fueleu"]["balance_g"]), Fraction(1, 10**49))
        self.assertGreater(q(low["fueleu"]["penalty_eur"]), 0)
        self.assertEqual(high["fueleu"]["penalty_eur"], "0")
        material = ledger(c, "c", "0.05")
        self.assertLess(q(material["fueleu"]["balance_g"]), -1_000_000)
        self.assertEqual(material["fueleu"]["classification"], "DEFICIT_ESTIMATE")

    def test_target_at_one_and_zero_exactly_have_closed_boundaries(self):
        c = self.simple()
        c["snapshot"]["candidates"]["c"]["wtt"] = "89.3368"
        r = calculate_reference(c)["candidates"]["c"]
        self.assertEqual(r["target"]["unconstrained_low"], "1")
        self.assertEqual(r["target"]["constrained_high"], "1")
        self.assertEqual(r["optima"]["target_cost"]["representative_ratio"], "1")
        c["snapshot"]["baseline"]["wtt"] = "89.3368"
        c["snapshot"]["candidates"]["c"]["wtt"] = "100"
        r = calculate_reference(c)["candidates"]["c"]
        self.assertEqual(r["target"]["constrained_low"], "0")
        self.assertEqual(r["target"]["constrained_high"], "0")

    def test_case_sensitivity_uses_report_lines_and_not_penalty_or_value_in_cost(self):
        c = self.simple(maxBlendRatio="0.5", complianceImprovementValue="10")
        r = calculate_reference(c)
        self.assertEqual(r["economics"]["cost_minimum"]["objective"], "6000")
        half = ledger(c, "c", "0.5")
        self.assertEqual(half["costs"]["model"], "8000")
        self.assertEqual(half["costs"]["reference_adjusted"], "3000")
        self.assertEqual(
            [q(point["value"]) for point in r["economics"]["switch_points"]], [4]
        )
        self.assertEqual(r["economics"]["intervals"][0]["winners"], ["B0"])
        self.assertEqual(r["economics"]["intervals"][-1]["winners"], ["c@1/2"])

    def test_unqualified_frozen_factor_is_not_reinterpreted_from_path_name(self):
        c = self.simple()
        c["snapshot"]["candidates"]["c"].update(
            path_id="E_DIESEL", wtt="100", rwd="1", qualification="INELIGIBLE",
        )
        r = calculate_reference(c)["candidates"]["c"]
        self.assertEqual(r["target"]["reason"], "TARGET_NO_SOLUTION")
        self.assertEqual(r["optima"]["max_improvement"]["objective"], "0")

    def test_pure_use_tie_has_open_upper_endpoint_but_attained_minimum(self):
        c = self.simple(pricePerTonne="600", candidateAllowsPureUse=False)
        r = calculate_reference(c)["candidates"]["c"]
        self.assertEqual(r["optima"]["cost"]["ratio_interval"], ["0", "1"])
        self.assertFalse(r["optima"]["cost"]["upper_inclusive"])
        self.assertTrue(r["optima"]["cost"]["attained"])
        self.assertEqual(r["optima"]["cost"]["representative_ratio"], "0")

    def test_global_continuous_minimum_cannot_ignore_better_unattained_infimum(self):
        c = self.simple(pricePerTonne="100", candidateAllowsPureUse=False)
        r = calculate_reference(c)["economics"]
        self.assertEqual(r["cost_minimum"]["status"], "UNAVAILABLE")
        self.assertEqual(r["cost_minimum"]["reason"], "PURE_USE_NOT_ALLOWED")
        self.assertEqual(r["cost_minimum"]["objective"], "1000")
        self.assertEqual(r["cost_minimum"]["winners"], [])
        # Fixed report ranking remains meaningful despite the open feasible endpoint.
        self.assertGreater(len(r["ranking"]), 0)

    def test_global_attained_tie_beats_an_unattained_candidate_infimum(self):
        c = self.simple(pricePerTonne="100", candidateAllowsPureUse=False)
        other = copy.deepcopy(c["request"]["candidates"][0])
        other.update(candidateId="d", candidateAllowsPureUse=True)
        c["request"]["candidates"].append(other)
        c["snapshot"]["candidates"]["d"] = copy.deepcopy(c["snapshot"]["candidates"]["c"])
        result = calculate_reference(c)["economics"]["cost_minimum"]
        self.assertEqual(result["status"], "AVAILABLE")
        self.assertEqual(result["objective"], "1000")
        self.assertEqual([w["candidate_id"] for w in result["winners"]], ["d"])

    def test_missing_snapshot_without_issue_fails_closed(self):
        c = self.simple()
        del c["snapshot"]["candidates"]["c"]
        result = calculate_reference(c)
        self.assertIsNotNone(result["baseline"])
        self.assertEqual(result["candidates"]["c"]["status"], "BLOCKED")


class EnvelopeAndContract(unittest.TestCase):
    def test_lower_envelope_excludes_hidden_pair_crossings_and_preserves_ties(self):
        lines = [
            {"id": "a", "cost": "0", "improvement": "0"},
            {"id": "b", "cost": "10", "improvement": "1"},
            {"id": "c", "cost": "12", "improvement": "3"},
            {"id": "d", "cost": "12", "improvement": "3"},
        ]
        result = envelope(lines)
        self.assertEqual([p["value"] for p in result["switch_points"]], ["4"])
        self.assertEqual(result["switch_points"][0]["winners"], ["a", "c", "d"])
        self.assertEqual([i["winners"] for i in result["intervals"]],
                         [["a"], ["c", "d"]])
        self.assertEqual(result["intervals"][-1]["upper"], None)

    def test_envelope_keeps_arbitrarily_close_switches_and_zero_tie(self):
        eps = Fraction(1, 10**40)
        lines = [
            {"id": "a", "cost": 0, "improvement": 0},
            {"id": "b", "cost": 1, "improvement": 1},
            {"id": "c", "cost": 2 + eps, "improvement": 2},
        ]
        r = envelope(lines)
        self.assertEqual([q(p["value"]) for p in r["switch_points"]], [1, 1 + eps])
        r = envelope([
            {"id": "a", "cost": 0, "improvement": 0},
            {"id": "b", "cost": 0, "improvement": 1},
        ])
        self.assertEqual(r["switch_points"][0]["value"], "0")

    def test_encode_exact_numbers_and_decimal_context_independence(self):
        self.assertEqual(encode({"n": Fraction(2, 3), "d": Decimal("-0"),
                                 "i": 7, "b": True, "nil": None}),
                         {"n": "2/3", "d": "0", "i": "7", "b": True, "nil": None})
        c = case(specifiedBlendRatios=["0.2"])
        before = copy.deepcopy(c)
        with localcontext() as ctx:
            ctx.prec = 6
            low = calculate_reference(c)
        with localcontext() as ctx:
            ctx.prec = 50
            high = calculate_reference(c)
        self.assertEqual(low, high)
        self.assertEqual(c, before)
        json.dumps(low, allow_nan=False)

    def test_binary_float_inputs_are_rejected(self):
        c = case()
        with self.assertRaises((TypeError, ValueError)):
            ledger(c, "c", 0.2)

    def test_ratio_recheck_rejects_outside_domain_and_nonzero_b0(self):
        for candidate_id, ratio in [("c", "-0.1"), ("c", "1.01"), (None, "0.1")]:
            with self.subTest(candidate_id=candidate_id, ratio=ratio):
                with self.assertRaises(ValueError):
                    ledger(case(), candidate_id, ratio)

    def test_envelope_empty_and_identical_lines(self):
        self.assertEqual(envelope([]), {"switch_points": [], "intervals": []})
        result = envelope([
            {"id": "a", "cost": 10, "improvement": 2},
            {"id": "b", "cost": 10, "improvement": 2},
        ])
        self.assertEqual(result["switch_points"], [])
        self.assertEqual(result["intervals"],
                         [{"lower": "0", "upper": None, "winners": ["a", "b"]}])

    def test_all_frozen_issue_expectations_are_independently_derived(self):
        from business_case_inputs import cases
        for fixture in cases():
            with self.subTest(case=fixture["id"]):
                self.assertEqual(
                    derive_issues(fixture),
                    sorted(fixture["expected_issues"],
                           key=lambda issue: (issue["scope"],
                                              issue.get("candidate_id") or "",
                                              issue["code"])),
                )

    def test_tampered_issue_metadata_is_rejected(self):
        fixture = copy.deepcopy(case())
        fixture["synthetic"] = True
        fixture["id"] = "D-negative-test"
        fixture["expected_issues"] = [
            {"code": "WRONG_CODE", "scope": "CANDIDATE", "candidate_id": "c"}
        ]
        with self.assertRaisesRegex(ValueError, "independent derivation"):
            reviewed_issues(fixture)


if __name__ == "__main__":
    unittest.main()
