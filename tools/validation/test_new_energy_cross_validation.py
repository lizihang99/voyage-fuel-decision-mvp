"""Cross-check production decisions against independent mass-space optima.

Run with src, tools/validation and validation-only SciPy on PYTHONPATH.
This suite never computes expected values with production calculation helpers.
"""
import csv
import io
import unittest
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal as D
from fractions import Fraction as F

from c_layer_inputs import inputs
from c_layer_oracle import normalized, solve
from new_energy_reference import business_deltas, business_values, hand_case, optimal_references
from voyage_fuel.case_calculator import calculate_decision_case, calculate_parsed_decision_case
from voyage_fuel.contracts import CandidateInput, DecisionCaseInput
from voyage_fuel.json_io import parse_decision_case
from voyage_fuel.models import FuelComponent, FuelFactor
from voyage_fuel.reports import decision_case_to_csv


METRICS = (
    "fuel_cost", "eua_cost", "model_cost", "fueleu_ghgi_actual_g_per_mj",
    "fueleu_compliance_balance_t", "fueleu_indicative_penalty_eur",
)


def component(fuel, path):
    return FuelComponent(
        FuelFactor(
            path, D(fuel["lcv"]), D(fuel["wtt"]), D(fuel["co2"]),
            D(fuel["ch4"]), D(fuel["n2o"]), D(fuel["rwd"]), D(fuel["slip"]),
            D(fuel["slip"]) != 0, "ESTIMATED",
            csf_ch4_g_per_g=D(1) if D(fuel["slip"]) else D(0),
        ),
        None if fuel["price"] is None else D(fuel["price"]),
    )


def request(cases):
    first = cases[0]
    for case in cases:
        for field in ("baseline", "year", "scope", "surrender", "fueleu_scope", "mass", "eua"):
            if case[field] != first[field]:
                raise ValueError("Portfolio candidates must share a baseline: " + field)
    return DecisionCaseInput(
        report_year=first["year"],
        departure_port="NLRTM" if first["scope"] == "1" else "CNSHG",
        arrival_port={"0": "SGSIN", ".5": "NLRTM", "1": "DEHAM"}[first["scope"]],
        adjacent_valid_port_of_call_confirmed=True, currency="EUR",
        baseline_component=component(first["baseline"], "CROSS_BASE"),
        baseline_mass_tonnes=D(first["mass"]),
        eua_price_per_tco2e=None if first["eua"] is None else D(first["eua"]),
        candidates=tuple(
            CandidateInput(
                case["id"], component(case["candidate"], case["id"]),
                specified_blend_ratios=(D(case["cap"]) / 2,),
                max_blend_ratio=D(case["cap"]), allows_pure_use=True,
                supply_tonnes=None if case["supply"] is None else D(case["supply"]),
                incremental_budget=None if case["budget"] is None else D(case["budget"]),
            )
            for case in cases
        ),
    )


class IndependentDecisionAssertions:
    def close(self, actual, expected, label, tolerance="1e-20"):
        if expected is None:
            self.assertIsNone(actual, label)
        else:
            self.assertIsNotNone(actual, label)
            self.assertLessEqual(abs(F(actual) - F(expected)), F(tolerance), label)

    def assert_case(self, cases, result):
        self.assertIsNotNone(result.baseline_scenario)
        self.assertFalse(any(issue.blocking for issue in result.issues), result.issues)
        by_id = {case["id"]: case for case in cases}
        baseline = business_values(cases[0], 0)
        rows = {row.scenario_id: row for row in result.scenarios}
        summary = result.decision_summary
        self.assertIsNotNone(summary)
        for row in result.scenarios:
            case = by_id[row.candidate_id] if row.candidate_id else cases[0]
            self.assertGreaterEqual(row.result.ratio, 0, row.scenario_id + ".ratio_nonnegative")
            self.assertLessEqual(row.result.ratio, 1, row.scenario_id + ".ratio_at_most_one")
            self.assertGreaterEqual(row.result.baseline_mass_tonnes, 0, row.scenario_id + ".baseline_mass_nonnegative")
            self.assertGreaterEqual(row.result.candidate_mass_tonnes, 0, row.scenario_id + ".candidate_mass_nonnegative")
            expected = business_values(case, row.result.ratio)
            for key in ("ratio", "baseline_mass_tonnes", "candidate_mass_tonnes", "physical_energy_mj"):
                self.close(getattr(row.result, key), expected[key], row.scenario_id + "." + key)
            actual = {
                "fuel_cost": row.result.fuel_cost,
                "eua_cost": row.result.eu_ets.eua_cost,
                "model_cost": row.result.model_cost,
                "fueleu_ghgi_actual_g_per_mj": row.result.fuel_eu.ghgi_actual_g_per_mj,
                "fueleu_compliance_balance_t": row.result.fuel_eu.compliance_balance_t,
                "fueleu_indicative_penalty_eur": row.result.fuel_eu.indicative_penalty_eur,
            }
            self.close(row.result.eu_ets.euas_required, expected["euas"], row.scenario_id + ".euas")
            for key in METRICS:
                label = row.scenario_id + "." + key
                self.close(actual[key], expected[key], label)
                delta = None if expected[key] is None or baseline[key] is None else expected[key] - baseline[key]
                self.close(summary.scenario_deltas[row.scenario_id][key].absolute, expected[key], label + ".absolute")
                self.close(summary.scenario_deltas[row.scenario_id][key].delta, delta, label + ".delta")

        references = {case["id"]: optimal_references(case) for case in cases}
        for candidate in result.candidate_results:
            case = by_id[candidate.candidate_id]
            applicable = case["year"] != 2024 and case["fueleu_scope"] not in (None, "0")
            unconstrained = solve(normalized(case), "target_min", constrained=False)
            constrained = solve(normalized(case), "target_min")
            status = (
                "TARGET_NOT_APPLICABLE" if not applicable else
                "TARGET_NO_SOLUTION" if unconstrained["exact_ratio"] is None else
                "TARGET_UNREACHABLE_UNDER_CONSTRAINTS" if constrained["exact_ratio"] is None else
                "TARGET_REACHABLE"
            )
            self.assertEqual(candidate.voyage_result.constraints.target_status, status)
            target_rec = next(rec for rec in result.recommendations
                              if rec.recommendation_id == "TARGET_MIN_COST:" + candidate.candidate_id)
            missing_prices = any(value is None for value in (
                case["baseline"]["price"], case["candidate"]["price"], case["eua"],
            ))
            if status != "TARGET_REACHABLE" or missing_prices:
                self.assertEqual(target_rec.status, "UNAVAILABLE")
                self.assertEqual(target_rec.reason, status if status != "TARGET_REACHABLE"
                                 else "PRICE_REQUIRED_FOR_COMPARISON", "target unavailability reason")
                if missing_prices:
                    self.assertIn("PRICE_REQUIRED_FOR_COMPARISON", target_rec.assumptions)
        for field, mode, metric in (
            ("cost_min_scenario_id", "cost", "model_cost"),
            ("target_min_cost_scenario_id", "target_cost", "model_cost"),
            ("max_improvement_scenario_id", "improvement", "fueleu_compliance_balance_t"),
        ):
            options = []
            if mode == "cost" and baseline["model_cost"] is not None:
                options.append(baseline[metric])
            if mode == "target_cost" and baseline["model_cost"] is not None and baseline["fueleu_compliance_balance_t"] is not None and baseline["fueleu_compliance_balance_t"] >= 0:
                options.append(baseline[metric])
            if mode == "improvement" and baseline[metric] is not None:
                options.append(baseline[metric])
            for case in cases:
                ref = references[case["id"]][mode]
                if ref is not None and ref["exact_ratio"] is not None:
                    options.append(business_values(case, ref["exact_ratio"])[metric])
            selected = getattr(summary, field)
            if not options:
                self.assertIsNone(selected, field)
                continue
            self.assertIn(selected, rows, field)
            winner = rows[selected]
            case = by_id[winner.candidate_id] if winner.candidate_id else cases[0]
            book = business_values(case, winner.result.ratio)
            expected = max(options) if mode == "improvement" else min(options)
            self.close(book[metric], expected, field + ".independent_optimum")
            self.assertLessEqual(F(winner.result.ratio), F(case["cap"]) + F("1e-40"), field)
            if case["supply"] is not None:
                self.assertLessEqual(book["candidate_mass_tonnes"], F(case["supply"]) + F("1e-20"), field)
            if case["budget"] is not None and book["model_cost"] is not None and baseline["model_cost"] is not None:
                self.assertLessEqual(book["model_cost"] - baseline["model_cost"], F(case["budget"]) + F("1e-20"), field)
            if mode == "target_cost":
                self.assertGreaterEqual(book["fueleu_compliance_balance_t"], -F("1e-20"), field)
        return references


class NewEnergyCrossValidationTests(IndependentDecisionAssertions, unittest.TestCase):
    def test_reference_is_calibrated_to_literal_hand_calculation(self):
        case = hand_case()
        baseline = business_values(case, 0)
        self.assertEqual(baseline["physical_energy_mj"], 4000000)
        self.assertEqual(baseline["model_cost"], 72000)
        refs = optimal_references(case)
        self.assertEqual(refs["cost"]["exact_ratio"], 0)
        self.assertEqual(refs["target_cost"]["exact_ratio"], F(".26658"))
        self.assertEqual(refs["improvement"]["exact_ratio"], F(".6"))
        target = business_values(case, ".26658")
        self.assertEqual(target["candidate_mass_tonnes"], F("26.658"))
        self.assertEqual(target["fuel_cost"], F("70663.2"))
        self.assertEqual(target["eua_cost"], F("9867.36"))
        self.assertEqual(target["model_cost"], F("80530.56"))
        self.assertEqual(target["fueleu_compliance_balance_t"], 0)
        delta = business_deltas(case, ".26658")
        self.assertEqual(delta["fuel_cost"], F("10663.2"))
        self.assertEqual(delta["eua_cost"], F("-2132.64"))
        self.assertEqual(delta["model_cost"], F("8530.56"))
        self.assertEqual(delta["fueleu_compliance_balance_t"], F("21.3264"))

    def test_sixty_synthetic_cases_match_independent_optima_and_ledgers(self):
        cases = inputs()["constraints"]
        self.assertEqual(len(cases), 60)
        for case in cases:
            with self.subTest(case=case["id"], label=case["label"]):
                self.assert_case([case], calculate_decision_case(request([case])))

    def test_exact_and_highs_objectives_agree_away_from_subprecision_boundaries(self):
        for case in inputs()["constraints"]:
            # +/-1e-20 feasibility is tested by the exact reference, beyond LP tolerances.
            if case["id"] in ("C-LP-17", "C-LP-18"):
                continue
            for mode, ref in optimal_references(case).items():
                if ref is None or "solver_status" not in ref:
                    continue
                with self.subTest(case=case["id"], mode=mode):
                    self.assertEqual(ref["exact_ratio"] is not None, ref["solver_status"] == 0)
                    if ref["exact_ratio"] is not None:
                        exact = business_values(case, ref["exact_ratio"])
                        numerical = business_values(case, str(ref["solver_ratio"]))
                        metric = "fueleu_ghgi_actual_g_per_mj" if mode == "improvement" else "model_cost"
                        self.close(numerical[metric], exact[metric], "HiGHS objective", "1e-5")

    def test_multiple_candidates_are_compared_globally(self):
        expensive = hand_case()
        cheap = hand_case("500")
        cheap["id"] = "cheap"
        limited = hand_case("450", "10")
        limited["id"] = "limited"
        for cases in ([expensive, cheap], [limited, expensive, cheap], [cheap, limited, expensive]):
            with self.subTest(order=[c["id"] for c in cases]):
                result = calculate_decision_case(request(cases))
                self.assert_case(cases, result)
                winner = next(row for row in result.scenarios if row.scenario_id == result.decision_summary.cost_min_scenario_id)
                self.assertEqual(winner.candidate_id, "cheap")
                self.close(winner.result.ratio, ".6", "global cost ratio")

    def test_fixed_seed_multi_candidate_portfolios_match_independent_optima(self):
        template = hand_case()
        random_cases = inputs()["constraints"][28:]
        for index in range(0, 30, 3):
            cases = []
            for source in random_cases[index:index + 3]:
                case = deepcopy(template)
                for field in ("id", "candidate", "cap", "supply", "budget"):
                    case[field] = deepcopy(source[field])
                cases.append(case)
            with self.subTest(portfolio=index // 3 + 1):
                self.assert_case(cases, calculate_decision_case(request(cases)))

    def test_existing_builtin_snapshot_is_cross_checked_without_resolving_expected_factors(self):
        fixture = inputs()["builtin_reproduction"]
        parsed = parse_decision_case(fixture["payload"])
        self.assertIsNotNone(parsed.request)
        case = deepcopy(fixture["case"])
        case["id"] = "mgo"
        self.assert_case([case], calculate_parsed_decision_case(parsed))

    def test_csv_business_amounts_match_independent_values(self):
        for case in (hand_case(), hand_case("500"), hand_case(supply="10")):
            with self.subTest(price=case["candidate"]["price"], supply=case["supply"]):
                result = calculate_decision_case(request([case]))
                records = list(csv.DictReader(io.StringIO(decision_case_to_csv(result))))
                selected = [r for r in records if r["record_type"] == "decision_summary"]
                self.assertTrue(selected)
                for record in selected:
                    ratio = record["recommended_blend_ratio"]
                    absolute = business_values(case, ratio)
                    delta = business_deltas(case, ratio)
                    metric = {
                        "fuel_cost_delta": "fuel_cost", "eua_cost_savings": "eua_cost",
                        "model_cost_delta": "model_cost", "fueleu_ghgi_delta": "fueleu_ghgi_actual_g_per_mj",
                        "fueleu_balance_delta": "fueleu_compliance_balance_t",
                        "fueleu_penalty_delta": "fueleu_indicative_penalty_eur",
                    }[record["metric_name"]]
                    value = delta[metric]
                    if metric == "eua_cost" and value is not None:
                        value = -value
                    self.close(D(record["delta"]) if record["delta"] else None, value, "CSV " + metric)
                    self.close(D(record["absolute"]) if record["absolute"] else None, absolute[metric], "CSV absolute")
                    self.close(D(record["recommended_quantity_tonnes"]), absolute["candidate_mass_tonnes"], "CSV quantity")

    def test_cross_checks_detect_wrong_algorithm_outputs(self):
        cases = [hand_case()]
        result = calculate_decision_case(request(cases))
        wrong_winner = replace(result, decision_summary=replace(
            result.decision_summary, cost_min_scenario_id="clean@0.6",
        ))
        with self.assertRaisesRegex(AssertionError, "cost_min_scenario_id.independent_optimum"):
            self.assert_case(cases, wrong_winner)
        row = next(row for row in result.scenarios if row.scenario_id == "clean@0.6")
        for field, wrong in (("candidate_mass_tonnes", row.result.candidate_mass_tonnes + 1),
                             ("model_cost", row.result.model_cost + 100)):
            mutant_row = replace(row, result=replace(row.result, **{field: wrong}))
            mutant = replace(result, scenarios=tuple(
                mutant_row if item.scenario_id == row.scenario_id else item for item in result.scenarios
            ))
            with self.subTest(mutation=field):
                with self.assertRaisesRegex(AssertionError, field):
                    self.assert_case(cases, mutant)
        metric = result.decision_summary.scenario_deltas[row.scenario_id]["eua_cost"]
        deltas = {
            **result.decision_summary.scenario_deltas,
            row.scenario_id: {
                **result.decision_summary.scenario_deltas[row.scenario_id],
                "eua_cost": replace(metric, delta=metric.delta.copy_negate()),
            },
        }
        with self.assertRaisesRegex(AssertionError, "eua_cost.delta"):
            self.assert_case(cases, replace(result, decision_summary=replace(
                result.decision_summary, scenario_deltas=deltas,
            )))

    def test_cross_checks_reject_infeasible_ties_and_wrong_unavailable_reasons(self):
        case = hand_case()
        case["candidate"] = deepcopy(case["baseline"])
        result = calculate_decision_case(request([case]))
        row = result.scenarios[0]
        negative = replace(row, result=replace(
            row.result, ratio=D("-.1"), baseline_mass_tonnes=D("110"), candidate_mass_tonnes=D("-10"),
        ))
        with self.assertRaisesRegex(AssertionError, "ratio_nonnegative"):
            self.assert_case([case], replace(result, scenarios=(negative, *result.scenarios[1:])))

        for case in (hand_case(), dict(hand_case(), year=2024, surrender=".4", fueleu_scope=None)):
            case["candidate"]["price"] = None
            result = calculate_decision_case(request([case]))
            recs = tuple(
                replace(rec, reason="TARGET_NO_SOLUTION") if rec.recommendation_id.startswith("TARGET_MIN_COST:")
                else rec for rec in result.recommendations
            )
            with self.subTest(year=case["year"]):
                with self.assertRaisesRegex(AssertionError, "target unavailability reason"):
                    self.assert_case([case], replace(result, recommendations=recs))


if __name__ == "__main__":
    unittest.main()
