"""Bounded C-layer differential experiment. Writes data, never product code.

Run with PYTHONPATH including src and tmp/c-layer-deps.
Exit 2 means recorded differences; exit 1 means infrastructure error.
"""
import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime, timezone
from decimal import Decimal as D
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import importlib.metadata

import numpy
import scipy
from scipy.optimize import brentq

from c_layer_inputs import inputs
from c_layer_oracle import envelope, ledger, normalized, solve
from voyage_fuel.constraints import calculate_constraints
from voyage_fuel.economics import (
    calculate_candidate_break_even_price, calculate_eua_break_even_price,
    calculate_value_switch_points,
)
from voyage_fuel.calculator import calculate_voyage
from voyage_fuel.case_calculator import calculate_decision_case, calculate_parsed_decision_case
from voyage_fuel.json_io import parse_decision_case
from voyage_fuel.case_comparison import calculate_case_value_switch_points, metric_delta
from voyage_fuel.models import FuelComponent, FuelFactor, ScopeRates, VoyageInput
from voyage_fuel.contracts import CandidateInput, DecisionCaseInput, CaseScenario

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/validation/c-layer"
RECORDS = []
sys.stdout.reconfigure(encoding="utf-8")


def encode(obj):
    if isinstance(obj, F):
        return {"fraction": str(obj), "decimal": str(D(obj.numerator) / D(obj.denominator))}
    if isinstance(obj, D):
        return str(obj)
    if isinstance(obj, tuple):
        return list(obj)
    raise TypeError(type(obj).__name__)


def check(rec, field, expected, actual, features, evidence="INDEPENDENT_EXACT", tolerance="1e-24"):
    numeric = isinstance(expected, (F, D, float, int)) and not isinstance(expected, bool)
    error = None
    if numeric and actual is not None and not isinstance(actual, str):
        def dec(v):
            return D(v.numerator) / D(v.denominator) if isinstance(v, F) else D(str(v))
        error = abs(dec(expected) - dec(actual))
        limit = D(tolerance)
        matched = error <= limit
        result = "MATCH" if error == 0 else "MATCH_WITH_ROUNDING" if matched else "DIFFERENCE"
    else:
        matched = expected == actual
        result = "MATCH" if matched else "DIFFERENCE"
    rec["checks"].append(dict(field=field, expected=expected, actual=actual,
                              absolute_error=error, tolerance=tolerance if numeric else None,
                              features=features.split(), evidence=evidence, result=result))


def record(identifier, label, data=None):
    rec = dict(id=identifier, label=label, input=data, checks=[])
    RECORDS.append(rec)
    return rec


def component(fuel, name):
    f = FuelFactor(
        path_id=name, lcv_mj_per_g=D(fuel["lcv"]), wt_t_g_per_mj=D(fuel["wtt"]),
        cf_co2_g_per_g=D(fuel["co2"]), cf_ch4_g_per_g=D(fuel["ch4"]),
        cf_n2o_g_per_g=D(fuel["n2o"]), rwd=D(fuel["rwd"]),
        cslip_percent=D(fuel["slip"]), methane_slip_applicable=D(fuel["slip"]) != 0,
        factor_status="ESTIMATED", csf_ch4_g_per_g=D(1) if D(fuel["slip"]) else D(0),
    )
    return FuelComponent(f, None if fuel["price"] is None else D(fuel["price"]))


def scope(c):
    return ScopeRates(D(c["scope"]), D(c["surrender"]), D(c["scope"]) * D(c["surrender"]),
                      None if c["fueleu_scope"] is None else D(c["fueleu_scope"]),
                      c["year"] != 2024 and c["fueleu_scope"] not in (None, "0"))


def constraint_actual(c):
    return calculate_constraints(
        report_year=c["year"], baseline_mass_tonnes=D(c["mass"]),
        baseline=component(c["baseline"], "SYN_BASE"), candidate=component(c["candidate"], "SYN_CAND"),
        scope=scope(c), candidate_supply_tonnes=None if c["supply"] is None else D(c["supply"]),
        incremental_budget=None if c["budget"] is None else D(c["budget"]),
        max_blend_ratio=D(c["cap"]), eua_price_per_tco2e=None if c["eua"] is None else D(c["eua"]),
    )


def run_constraints(c):
    rec = record(c["id"], c["label"], c)
    p = normalized(c)
    actual = constraint_actual(c)
    rec["production"] = asdict(actual)
    refs = {mode: solve(p, mode) for mode in ("cap", "target_min", "target_cost", "cost", "improvement")}
    refs["unconstrained_target"] = solve(p, "target_min", constrained=False)
    rec["reference"] = refs
    # Independent solver cross-checks use objective/feasibility; solver tie representative may differ.
    for name, ref in refs.items():
        if "solver_status" not in ref:
            continue
        solver_features = {
            "cap": "M07-F01 M07-F02 M07-F03",
            "target_min": "M07-F04 M07-F06",
            "target_cost": "M09-F06 M11-F04",
            "cost": "M11-F03",
            "improvement": "M07-F07 M11-F05",
            "unconstrained_target": "M07-F04 M07-F05",
        }[name]
        check(rec, f"oracle.{name}.feasible", ref["exact_ratio"] is not None,
              ref["solver_status"] == 0, solver_features, "SOLVER")
        if rec["checks"][-1]["result"] == "DIFFERENCE":
            rec["checks"][-1]["difference_kind"] = "SOLVER_PRECISION_LIMIT"
        if ref["exact_ratio"] is not None and ref["solver_ratio"] is not None:
            # Tie-aware comparison evaluates objective, not a selected point.
            sr = ref["solver_ratio"]
            if name in ("cost", "target_cost"):
                expected = ledger(c, ref["exact_ratio"])["cost"]
                observed = ledger(c, str(sr))["cost"]
                tol = max(D("1e-5"), abs(D(expected.numerator) / D(expected.denominator)) * D("1e-9"))
            elif name == "improvement":
                expected, observed = ledger(c, ref["exact_ratio"])["ghgi"], ledger(c, str(sr))["ghgi"]
                tol = D("1e-8")
            else:
                expected, observed, tol = ref["exact_ratio"], sr, D("1e-8")
            check(rec, f"oracle.{name}.objective", expected, observed,
                  solver_features, "SOLVER", str(tol))
    expected_cap = refs["cap"]["exact_ratio"]
    check(rec, "x_cap", expected_cap, actual.x_cap, "M07-F01 M07-F02 M07-F03 M07-F09")
    for field, keep, enabled in (
        ("x_supply", "supply", True),
        ("x_budget", "budget", p["kb"] is not None and p["kc"] is not None),
    ):
        isolated = dict(p, cap="1", supply=None, budget=None)
        isolated[keep] = p[keep]
        expected = solve(isolated, "cap")["exact_ratio"] if enabled else (
            F(1) if c["budget"] is None else None)
        check(rec, field, expected, getattr(actual, field),
              "M07-F02" if keep == "supply" else "M07-F03 M07-F08")
    applicable = c["year"] != 2024 and c["fueleu_scope"] not in (None, "0")
    unconstrained = refs["unconstrained_target"]["exact_ratio"] if applicable else None
    minimum = refs["target_min"]["exact_ratio"] if applicable else None
    status = ("TARGET_NOT_APPLICABLE" if not applicable else
              "TARGET_NO_SOLUTION" if unconstrained is None else
              "TARGET_UNREACHABLE_UNDER_CONSTRAINTS" if minimum is None else "TARGET_REACHABLE")
    check(rec, "target_status", status, actual.target_status, "M07-F04 M07-F05 M07-F06")
    check(rec, "x_target_min_unconstrained", unconstrained, actual.x_target_min_unconstrained, "M07-F04 M07-F06")
    check(rec, "x_target_min", minimum, actual.x_target_min, "M07-F04")
    for field, mode, active, features in (
        ("x_target_min_cost", "target_cost", applicable, "M11-F04 M09-F06"),
        ("x_max_improvement", "improvement", applicable, "M07-F07 M11-F05"),
        ("x_cost_min", "cost", True, "M11-F03"),
    ):
        check(rec, field, refs[mode]["exact_ratio"] if active else None, getattr(actual, field), features)
    missing_budget = c["budget"] is not None and (p["kb"] is None or p["kc"] is None)
    check(rec, "budget_warning", missing_budget, "BUDGET_UNAVAILABLE_WITHOUT_PRICES" in actual.warning_codes,
          "M07-F08", "CONTRACT")
    return rec


def run_prices(c, index):
    rec = record(f"C-EC-{index:02d}", c["label"], c)
    b, cand, sc = component(c["baseline"], "SYN_BASE"), component(c["candidate"], "SYN_CAND"), scope(c)
    pe = None if c["eua"] is None else D(c["eua"])
    pc_actual = calculate_candidate_break_even_price(c["year"], b, cand, sc, pe)
    pe_actual = calculate_eua_break_even_price(c["year"], b, cand, sc)
    full = all(v is not None for v in (c["baseline"]["price"], c["candidate"]["price"], c["eua"]))
    if not full:
        check(rec, "pc_missing_price", None, pc_actual, "M08-F07", "CONTRACT")
        return
    # Two positive blends; roots derived from independently evaluated costs at prices 0 and 1.
    pc_roots = []
    for ratio in (F(1, 5), F(4, 5)):
        def delta_price(price):
            return ledger(c, ratio, candidate_price=price)["cost"] - ledger(c, 0, candidate_price=price)["cost"]
        intercept = delta_price(0)
        slope = delta_price(1) - intercept
        root = -intercept / slope
        pc_roots.append(root)
        check(rec, f"pc_ratio_{ratio}", root, pc_actual, "M08-F02")
        if root >= 0:
            upper = max(1., float(root) * 2 + 1)
            numerical = brentq(lambda p: float(delta_price(str(p))), 0, upper, xtol=1e-10)
            check(rec, f"pc_brent_{ratio}", root, numerical, "M08-F02", "SOLVER", "1e-7")
            check(rec, f"pc_substitution_{ratio}", F(0), delta_price(root), "M08-F02")
            check(rec, f"pc_sides_{ratio}", True, delta_price(root + 1) > 0 and delta_price(root - 1) < 0,
                  "M08-F02")
    check(rec, "pc_blend_invariance", pc_roots[0], pc_roots[1], "M08-F02")
    def delta_eua(price):
        return ledger(c, F(1, 2), eua_price=price)["cost"] - ledger(c, 0, eua_price=price)["cost"]
    intercept, slope = delta_eua(0), delta_eua(1) - delta_eua(0)
    root = None if slope == 0 else -intercept / slope
    status = ("ALL_PRICES_TIE" if slope == 0 and intercept == 0 else
              "NO_FINITE_POINT" if slope == 0 else "NEGATIVE_THRESHOLD" if root < 0 else "FINITE_NON_NEGATIVE")
    check(rec, "pe_status", status, pe_actual.status, "M08-F03")
    check(rec, "pe_value", root if root is not None and root >= 0 else None, pe_actual.value, "M08-F03")
    if root is not None and root >= 0:
        numerical = brentq(lambda p: float(delta_eua(str(p))), 0, max(1., float(root) * 2 + 1), xtol=1e-10)
        check(rec, "pe_brent", root, numerical, "M08-F03", "SOLVER", "1e-7")
        check(rec, "pe_substitution", F(0), delta_eua(root), "M08-F03")
        check(rec, "pe_sides", True, delta_eua(root + 1) * delta_eua(root - 1) < 0, "M08-F03")


def voyage(c):
    return calculate_voyage(VoyageInput(
        report_year=c["year"], departure_port="CNSHG", arrival_port="NLRTM",
        baseline_component=component(c["baseline"], "SYN_BASE"), baseline_mass_tonnes=D(c["mass"]),
        candidate_component=component(c["candidate"], "SYN_CAND"),
        eua_price_per_tco2e=None if c["eua"] is None else D(c["eua"]),
        specified_blend_ratios=(D(c["cap"]) / 2,), max_blend_ratio=D(c["cap"]),
        candidate_allows_pure_use=True,
        candidate_supply_tonnes=None if c["supply"] is None else D(c["supply"]),
        incremental_budget=None if c["budget"] is None else D(c["budget"]),
    ))


def run_envelope(data, template):
    rec = record(data["id"], data["label"], data)
    lines = [(name, F(cost), F(improvement)) for name, cost, improvement in data["lines"]]
    expected = envelope(lines)
    scenarios = tuple(replace(template, ratio=D(i) / D(10), model_cost=D(cost),
                              compliance_improvement_tco2e=D(improvement))
                      for i, (name, cost, improvement) in enumerate(data["lines"]))
    names = {s.ratio: data["lines"][i][0] for i, s in enumerate(scenarios)}
    single = [(p.value_star, names[p.from_ratio], names[p.to_ratio]) for p in calculate_value_switch_points(scenarios)]
    rows = tuple(CaseScenario(name, name, "COMPARABLE", s, {}) for (name, _, _), s in zip(lines, scenarios))
    multiple = [(p.value_star, p.from_scenario_id, p.to_scenario_id) for p in calculate_case_value_switch_points(rows)]
    rec["reference"] = expected
    for label, actual in (("single", single), ("case", multiple)):
        check(rec, label + ".switch_count", len(expected), len(actual), "M08-F05 M08-F06")
        for i, (exp, got) in enumerate(zip(expected, actual)):
            check(rec, f"{label}.{i}.value", exp[0], got[0], "M08-F05 M08-F06", tolerance="1e-40")
            check(rec, f"{label}.{i}.winners", exp[1:], got[1:], "M08-F06")
    rec["production"] = {"single": single, "case": multiple}


def run_cases(cases):
    for index, seed_case in enumerate(cases, start=1):
        c = deepcopy(seed_case)
        # This batch uses an actual CNSHG -> NLRTM route; freeze its expected rates.
        c.update(scope=".5", surrender="1", fueleu_scope=".5", year=2026)
        rec = record(f"C-CASE-{index:02d}", c["label"], c)
        good = component(c["candidate"], "SYN_CAND")
        candidates = (
            CandidateInput("candidate", good, specified_blend_ratios=(D(c["cap"]) / 2,),
                           max_blend_ratio=D(c["cap"]), allows_pure_use=True,
                           supply_tonnes=None if c["supply"] is None else D(c["supply"]),
                           incremental_budget=None if c["budget"] is None else D(c["budget"])),
            CandidateInput("dominated", replace(good, price_per_tonne=D("100000")), max_blend_ratio=D(".3")),
            CandidateInput("missing", replace(good, price_per_tonne=None), max_blend_ratio=D(".2")),
            CandidateInput("blocked", replace(good, factor=replace(good.factor, methane_slip_applicable=True,
                                                                  cslip_percent=None))),
        )
        request = DecisionCaseInput(2026, "CNSHG", "NLRTM", True, "EUR",
                                    component(c["baseline"], "SYN_BASE"), D(c["mass"]),
                                    None if c["eua"] is None else D(c["eua"]), candidates)
        result = calculate_decision_case(request)
        reverse = calculate_decision_case(replace(request, candidates=tuple(reversed(candidates))))
        alone = calculate_decision_case(replace(request, candidates=candidates[:1]))
        rec["production"] = asdict(result)
        statuses = {v.candidate_id: v.calculation_status for v in result.candidate_results}
        check(rec, "local_block", "BLOCKED", statuses["blocked"], "M09-F03", "CONTRACT")
        check(rec, "missing_price", "CALCULABLE", statuses["missing"], "M08-F07 M09-F02", "CONTRACT")
        check(rec, "shared_B0_count", 1, sum(row.scenario_id == "B0" for row in result.scenarios), "M09-F01", "CONTRACT")
        check(rec, "permutation", asdict(result.economics), asdict(reverse.economics),
              "M09-F05 M09-F06 M09-F07", "CONTRACT")
        clean = next(x.voyage_result for x in alone.candidate_results if x.candidate_id == "candidate")
        combined = next(x.voyage_result for x in result.candidate_results if x.candidate_id == "candidate")
        check(rec, "candidate_isolation", asdict(clean), asdict(combined), "M09-F02 M09-F03", "CONTRACT")
        b0 = ledger(c, 0)
        expected_rows = []
        boundary_rows = []
        for row in result.scenarios:
            row_case = deepcopy(c)
            if row.candidate_id == "dominated":
                row_case["candidate"]["price"] = "100000"
                row_case.update(cap=".3", budget=None, supply=None)
            elif row.candidate_id == "missing":
                row_case["candidate"]["price"] = None
                row_case.update(cap=".2", budget=None, supply=None)
            x = F(row.result.ratio)
            expected = ledger(row_case, x)
            if expected["balance"] is not None and abs(expected["balance"]) < F("1e-35"):
                boundary_rows.append(row.scenario_id)
                check(rec, f"{row.scenario_id}.exact_balance_sign",
                      (expected["balance"] > 0) - (expected["balance"] < 0),
                      (row.result.fuel_eu.compliance_balance_t > 0) -
                      (row.result.fuel_eu.compliance_balance_t < 0), "M09-F06 M11-F04")
                rec["checks"][-1]["exact_balance_t"] = expected["balance"]
                rec["checks"][-1]["production_balance_t"] = row.result.fuel_eu.compliance_balance_t
                if rec["checks"][-1]["result"] == "DIFFERENCE":
                    rec["checks"][-1]["difference_kind"] = "DECIMAL_BOUNDARY_SIGN"
            constraints = solve(normalized(row_case), "cap")
            cap = constraints["exact_ratio"]
            # A 1e-24 ratio neighbourhood is NOT used for exact goal sign checks.
            feasible = x <= cap or abs(x - cap) < F("1e-40")
            check(rec, f"{row.scenario_id}.feasible", feasible, row.result.constraint_status == "FEASIBLE",
                  "M07-F09 M09-F05")
            for key, actual in (("cost", row.result.model_cost), ("ghgi", row.result.fuel_eu.ghgi_actual_g_per_mj)):
                check(rec, f"{row.scenario_id}.{key}", expected[key], actual, "M08-F01 M09-F02")
            if row.candidate_id != "missing" or x != 0:
                delta = None if expected["cost"] is None or b0["cost"] is None else expected["cost"] - b0["cost"]
                check(rec, f"{row.scenario_id}.cost_delta", delta, row.deltas["model_cost"].delta, "M11-F01")
                pct = None if delta is None or b0["cost"] == 0 else delta / abs(b0["cost"]) * 100
                check(rec, f"{row.scenario_id}.cost_percent", pct, row.deltas["model_cost"].percent_delta, "M11-F02")
            improvement = expected["balance"] - b0["balance"]
            check(rec, f"{row.scenario_id}.improvement", improvement, row.result.compliance_improvement_tco2e,
                  "M08-F04 M09-F07 M11-F05")
            expected_rows.append((row, expected, feasible))
        ranked = sorted((row for row, expected, feasible in expected_rows if feasible and expected["cost"] is not None),
                        key=lambda r: (next(e["cost"] for rr, e, _ in expected_rows if rr is r), r.scenario_id))
        check(rec, "cost_ranking", [r.scenario_id for r in ranked],
              [r.scenario_id for r in sorted((r for r in result.scenarios if r.current_model_cost_rank is not None),
                                            key=lambda r: r.current_model_cost_rank)],
              "M08-F08 M09-F04 M09-F05 M11-F03")
        check(rec, "cost_winner", ranked[0].scenario_id if ranked else None,
              result.economics.cost_min_scenario_id, "M09-F04 M11-F03")
        # Check returned target winner satisfies exact target. Tiny Decimal goal
        # residual is recorded separately, never silently turned into compliance.
        target_rows = [(r, e) for r, e, feasible in expected_rows if feasible and e["cost"] is not None
                       and e["balance"] >= 0]
        winner = min(target_rows, key=lambda pair: (pair[1]["cost"], pair[0].scenario_id))[0] if target_rows else None
        check(rec, "fixed_set_target_winner", None if winner is None else winner.scenario_id,
              result.economics.target_min_cost_scenario_id, "M09-F05 M09-F06 M11-F04")
        improvement_rows = [(r, e) for r, e, feasible in expected_rows if feasible]
        best = max(improvement_rows, key=lambda pair: (pair[1]["balance"], pair[0].scenario_id))[0]
        check(rec, "max_improvement_winner", best.scenario_id, result.economics.max_improvement_scenario_id,
              "M09-F05 M09-F07 M11-F05")
        lp = solve(normalized(c), "target_cost")
        rec["continuous_target_reference"] = lp
        if lp["exact_ratio"] is not None:
            optimum = ledger(c, lp["exact_ratio"])["cost"]
            candidate_points = [(r, e) for r, e, feasible in expected_rows if feasible and r.candidate_id in (None, "candidate")
                                and e["cost"] is not None and e["balance"] >= 0]
            actual_best = min((e["cost"] for _, e in candidate_points), default=None)
            check(rec, "report_set_contains_continuous_target_optimum", optimum, actual_best,
                  "M07-F09 M09-F06 M11-F04")
        for recm in result.recommendations:
            if recm.status == "CONDITIONAL":
                check(rec, recm.recommendation_id + ".pending", True,
                      "EXECUTION_CONDITIONS_PENDING" in recm.assumptions,
                      "M11-F06", "CONTRACT")
                if recm.recommendation_id == "TARGET_MIN_COST:candidate" and recm.scenario_id:
                    rr = next(row for row in result.scenarios if row.scenario_id == recm.scenario_id)
                    check(rec, "target_recommendation_is_compliant", True, ledger(c, F(rr.result.ratio))["balance"] >= 0,
                          "M11-F04 M11-F06")
        check(rec, "no_overall_optimal", True,
              all(r.condition in {"CURRENT_MODEL_COST", "FUELEU_TARGET", "FUELEU_TARGET_MINIMUM_COST",
                                  "FUELEU_COMPLIANCE_IMPROVEMENT", "FUELEU_MAX_COMPLIANCE_IMPROVEMENT",
                                  "REFERENCE_ADJUSTED_COST_SENSITIVITY"} for r in result.recommendations),
              "M11-F07", "CONTRACT")
        # Preserve exact-sign failures, but identify their numerical origin.
        # Never silently reclassify a negative balance as compliant.
        if boundary_rows:
            for assertion in rec["checks"]:
                if assertion["result"] == "DIFFERENCE" and assertion["field"] in {
                    "fixed_set_target_winner", "report_set_contains_continuous_target_optimum",
                    "target_recommendation_is_compliant",
                } and rec["id"] != "C-CASE-04":
                    assertion["difference_kind"] = "DECIMAL_BOUNDARY_SIGN"
                    assertion["boundary_rows"] = boundary_rows
    # Test value sensitivity independently without making it the default cost.
    c = deepcopy(cases[0])
    v = voyage(c)
    from voyage_fuel.economics import build_economics
    econ, rows = build_economics(
        report_year=c["year"], baseline=component(c["baseline"], "SYN_BASE"),
        candidate=component(c["candidate"], "SYN_CAND"), scope=scope(c),
        eua_price_per_tco2e=D(c["eua"]), scenarios=v.scenarios, comparison_value=D("100"))
    rec = record("C-VALUE-01", "合规参考价值不改变默认成本排序", c)
    for row in rows:
        raw = ledger(c, F(row.ratio))
        imp = raw["balance"] - ledger(c, 0)["balance"]
        check(rec, f"{row.ratio}.adjusted_cost", raw["cost"] - 100 * imp,
              row.reference_adjusted_cost, "M08-F04")
    check(rec, "default_ranking_unchanged", v.economics.cost_sorted_ratios, econ.cost_sorted_ratios,
          "M08-F04 M08-F08 M11-F03", "CONTRACT")
    z = record("C-STATE-01", "零基准和缺值变化")
    for value, baseline, expected in ((D(5), D(0), (D(5), None, "ZERO_BASELINE")),
                                      (None, D(5), (None, None, None)),
                                      (D(-5), D(-10), (D(5), D(50), None))):
        actual = metric_delta(value, baseline)
        check(z, f"delta({value},{baseline})", expected,
              (actual.delta, actual.percent_delta, actual.reason_code), "M11-F01 M11-F02", "CONTRACT")


def run_builtin(data):
    c = data["case"]
    result = calculate_parsed_decision_case(parse_decision_case(data["payload"]))
    rec = record(c["id"], c["label"], data)
    rec["production"] = asdict(result)
    actual = result.candidate_results[0].voyage_result
    # Freeze the shared A-layer inputs explicitly; this is not factor validation.
    for name, factor in (("baseline", actual.baseline_factor), ("candidate", actual.candidate_factor)):
        check(rec, f"{name}.snapshot", [D(c[name][k]) for k in ("lcv", "wtt", "co2", "ch4", "n2o", "rwd")],
              [factor.lcv_mj_per_g, factor.wt_t_g_per_mj, factor.cf_co2_g_per_g,
               factor.cf_ch4_g_per_g, factor.cf_n2o_g_per_g, factor.rwd],
              "M09-F02", "CONTRACT")
    ref = solve(normalized(c), "target_cost")
    rec["reference"] = ref
    check(rec, "target_min_cost_ratio", ref["exact_ratio"], actual.constraints.x_target_min_cost,
          "M09-F06 M11-F04")
    recommendation = next(x for x in result.recommendations if x.recommendation_id == "TARGET_MIN_COST:mgo")
    row = next(x for x in result.scenarios if x.scenario_id == recommendation.scenario_id)
    check(rec, "recommended_target_is_compliant", True, row.result.fuel_eu.compliance_balance_t >= 0,
          "M11-F04 M11-F06")
    rec["recommended_metrics"] = dict(ratio=row.result.ratio, ghgi=row.result.fuel_eu.ghgi_actual_g_per_mj,
                                       balance_t=row.result.fuel_eu.compliance_balance_t,
                                       cost=row.result.model_cost)
    rec["independent_optimum"] = ledger(c, ref["exact_ratio"])


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate-inputs", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    input_path = OUT / "inputs.json"
    if args.generate_inputs:
        input_path.write_text(json.dumps(inputs(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    data = json.loads(input_path.read_text(encoding="utf-8"))
    before = {str(p.relative_to(ROOT)): sha(p) for p in sorted((ROOT / "src/voyage_fuel").glob("*.py"))}
    for c in data["constraints"]:
        run_constraints(c)
    for i, c in enumerate(data["constraints"][:28], start=1):
        run_prices(c, i)
    template = voyage(data["constraints"][0]).scenarios[0]
    for c in data["envelope"]:
        run_envelope(c, template)
    run_cases([data["constraints"][i] for i in (0, 1, 6, 12, 15, 18, 20, 26)])
    run_builtin(data["builtin_reproduction"])
    after = {str(p.relative_to(ROOT)): sha(p) for p in sorted((ROOT / "src/voyage_fuel").glob("*.py"))}
    if before != after:
        raise RuntimeError("Production source changed during experiment")
    for rec in RECORDS:
        rec["result"] = "DIFFERENCE" if any(c["result"] == "DIFFERENCE" for c in rec["checks"]) else (
            "MATCH_WITH_ROUNDING" if any(c["result"] == "MATCH_WITH_ROUNDING" for c in rec["checks"]) else "MATCH")
    result = dict(
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        python=platform.python_version(), scipy=scipy.__version__, numpy=numpy.__version__,
        dependencies={name: importlib.metadata.version(name) for name in (
            "scipy", "numpy", "fastapi", "uvicorn", "jinja2", "reportlab",
            "starlette", "pydantic", "pydantic-core", "anyio")},
        git_head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        input_sha256=sha(input_path), production_sha256=before, production_unchanged=True,
        experiment_sha256={p.name: sha(p) for p in Path(__file__).parent.glob("*.py")},
        experiment_counts=dict(Counter(r["result"] for r in RECORDS)),
        assertion_counts=dict(Counter(c["result"] for r in RECORDS for c in r["checks"])),
        records=RECORDS,
    )
    (OUT / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=encode) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("experiment_counts", "assertion_counts", "production_unchanged")}, ensure_ascii=False))
    for rec in RECORDS:
        if rec["result"] == "DIFFERENCE":
            print(rec["id"], rec["label"], [(c["field"], str(c["expected"]), str(c["actual"]))
                                          for c in rec["checks"] if c["result"] == "DIFFERENCE"][:6])
    return 2 if result["experiment_counts"].get("DIFFERENCE") else 0


if __name__ == "__main__":
    sys.exit(main())
