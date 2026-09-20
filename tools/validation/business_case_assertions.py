"""Compare public product contracts with independently computed ledgers."""
from fractions import Fraction as F

from business_case_reference import ledger

# Much smaller than UI precision; only accommodates Decimal division rounding.
RELATIVE_TOLERANCE = F("1e-35")
ABSOLUTE_TOLERANCE = F("1e-35")
BOUNDARY_TOLERANCE = ABSOLUTE_TOLERANCE


def close(left, right):
    if left is None or right is None:
        return left is right
    try:
        a, b = F(left), F(right)
        return abs(a - b) <= ABSOLUTE_TOLERANCE + RELATIVE_TOLERANCE * max(abs(a), abs(b))
    except (ValueError, TypeError, ZeroDivisionError):
        return left == right


def boundary_close(left, right):
    try:
        return abs(F(left) - F(right)) <= BOUNDARY_TOLERANCE
    except (ValueError, TypeError):
        return left == right


def _boundary_projection(case, cid, expected_candidate, book):
    """Normalize status only for independently proven sub-ulp residuals."""
    point = next((p for p in expected_candidate["report_points"]
                  if boundary_close(p["ratio"], book["ratio"])), None)
    if not point or book["constraint_status"] != "CONSTRAINT_INFEASIBLE" \
            or point["scenario"]["constraint_status"] != "CONSTRAINT_FEASIBLE":
        return book
    candidate = next(c for c in case["request"]["candidates"] if c["candidateId"] == cid)
    excess = [F(book["ratio"]) - F(candidate.get("maxBlendRatio", "1"))]
    if candidate.get("candidateSupplyTonnes") is not None:
        excess.append(F(book["physical"]["candidate_mass_t"]) - F(candidate["candidateSupplyTonnes"]))
    if candidate.get("incrementalBudget") is not None:
        if book["deltas"]["model_cost"] is None:
            return book
        excess.append(F(book["deltas"]["model_cost"]) - F(candidate["incrementalBudget"]))
    if max(excess) <= ABSOLUTE_TOLERANCE:
        book["constraint_status"] = "CONSTRAINT_FEASIBLE"
    return book


def at(value, path):
    for part in path.split("."):
        value = value[part]
    return value


METRICS = {
    "ratio": "ratio",
    "baseline_mass_tonnes": "physical.baseline_mass_t",
    "candidate_mass_tonnes": "physical.candidate_mass_t",
    "physical_energy_mj": "physical.energy_mj",
    "fuel_cost": "costs.fuel",
    "eu_ets.raw_co2_t": "ets.raw_by_gas_t.CO2",
    "eu_ets.raw_ch4_t": "ets.raw_by_gas_t.CH4",
    "eu_ets.raw_n2o_t": "ets.raw_by_gas_t.N2O",
    "eu_ets.mrv_raw_co2e_t": "ets.raw_co2e_t",
    "eu_ets.ets_co2e_pre_scope_t": "ets.pre_scope_co2e_t",
    "eu_ets.euas_required": "ets.euas",
    "eu_ets.eua_cost": "costs.eua",
    "model_cost": "costs.model",
    "fuel_eu.physical_energy_mj": "physical.energy_mj",
    "fuel_eu.scoped_energy_mj": "fueleu.scoped_energy_mj",
    "fuel_eu.denominator_rwd_mj": "fueleu.denominator_mj",
    "fuel_eu.wt_t_intensity_g_per_mj": "fueleu.wtt_intensity",
    "fuel_eu.tt_w_intensity_g_per_mj": "fueleu.ttw_intensity",
    "fuel_eu.ghgi_actual_g_per_mj": "fueleu.ghgi",
    "fuel_eu.target_g_per_mj": "fueleu.target",
    "fuel_eu.compliance_balance_g": "fueleu.balance_g",
    "fuel_eu.compliance_balance_t": "fueleu.balance_t",
    "fuel_eu.indicative_penalty_eur": "fueleu.penalty_eur",
    "compliance_improvement_tco2e": "deltas.balance_t",
    "reference_adjusted_cost": "costs.reference_adjusted",
}

DELTA_KEYS = {
    "fuel_cost": "costs.fuel", "eua_cost": "costs.eua", "model_cost": "costs.model",
    "fueleu_ghgi_actual_g_per_mj": "fueleu.ghgi",
    "fueleu_compliance_balance_t": "fueleu.balance_t",
    "fueleu_indicative_penalty_eur": "fueleu.penalty_eur",
    "euas_required": "ets.euas", "ets_raw_co2_t": "ets.raw_by_gas_t.CO2",
    "ets_raw_ch4_t": "ets.raw_by_gas_t.CH4", "ets_raw_n2o_t": "ets.raw_by_gas_t.N2O",
}


class Checks:
    def __init__(self):
        self.assertions = 0
        self.differences = []

    def equal(self, path, expected, actual, numeric=False):
        self.assertions += 1
        matches = close(expected, actual) if numeric else expected == actual
        if not matches:
            self.differences.append({"path": path, "expected": expected, "actual": actual})

    def result(self):
        return {"assertions": self.assertions, "differences": self.differences,
                "passed": not self.differences}


def _scenario(check, prefix, expected, actual):
    for product_key, reference_key in METRICS.items():
        check.equal(prefix + "." + product_key, at(expected, reference_key),
                    at(actual, product_key), numeric=True)
    check.equal(prefix + ".included_gases", expected["ets"]["included_gases"],
                actual["eu_ets"]["included_gases"])
    status = expected["constraint_status"].replace("CONSTRAINT_FEASIBLE", "FEASIBLE")
    check.equal(prefix + ".constraint_status", status, actual["constraint_status"])
    classification = expected["fueleu"]["classification"] or expected["fueleu"]["status"]
    actual_classification = actual["fuel_eu"]["status"]
    # Exact rational factor derivation and finite Decimal factors can straddle
    # zero at the last digit. Only classify these sub-tolerance residues alike.
    balance = expected["fueleu"]["balance_g"]
    if balance is not None and abs(F(balance)) <= ABSOLUTE_TOLERANCE:
        check.equal(prefix + ".fuel_eu.status.at_boundary", True,
                    actual_classification in ("ON_TARGET_ESTIMATE", "SURPLUS_ESTIMATE", "DEFICIT_ESTIMATE")
                    and close(balance, actual["fuel_eu"]["compliance_balance_g"]))
    else:
        check.equal(prefix + ".fuel_eu.status", classification, actual_classification)
    check.equal(prefix + ".execution_status", "EXECUTION_CONDITIONS_PENDING",
                actual["execution_status"])


def _issue_keys(issues):
    return sorted((i["scope"], i.get("candidate_id") or "", i["code"]) for i in issues)

WARNINGS = {"PRICE_REQUIRED_FOR_COMPARISON", "BUDGET_UNAVAILABLE_WITHOUT_PRICES"}


def _matches_winner(row, winner):
    if row["candidate_id"] != winner["candidate_id"]:
        return False
    ratio = F(row["result"]["ratio"])
    interval = winner.get("ratio_interval")
    if interval is not None:
        low, high = map(F, interval)
        return low - ABSOLUTE_TOLERANCE <= ratio <= high + ABSOLUTE_TOLERANCE
    return close(ratio, winner.get("ratio", winner.get("representative_ratio")))


def validate_product_result(case, expected, actual):
    check = Checks()
    check.equal("issues", _issue_keys([i for i in case["expected_issues"] if i["code"] not in WARNINGS]),
                _issue_keys(actual.get("issues", [])))
    if expected["baseline"] is None:
        check.equal("baseline_scenario", None, actual.get("baseline_scenario"))
        check.equal("scenarios", [], actual.get("scenarios", []))
        return check.result()
    _scenario(check, "baseline", expected["baseline"], actual["baseline_scenario"])
    expected_candidates = expected["candidates"]
    actual_candidates = {c["candidate_id"]: c for c in actual["candidate_results"]}
    check.equal("candidate_ids", sorted(expected_candidates), sorted(actual_candidates))
    rows = actual["scenarios"]
    check.equal("B0_count", 1, sum(r["scenario_id"] == "B0" for r in rows))
    expected_rows = [(None, "0")] + [
        (cid, p["ratio"]) for cid, c in expected_candidates.items()
        for p in c["report_points"] if F(p["ratio"]) != 0]
    check.equal("case_report_point_count", len(expected_rows), len(rows))
    for cid, ratio in expected_rows:
        check.equal(f"case_report_point.{cid}@{ratio}", 1,
                    sum(row["candidate_id"] == cid and close(row["result"]["ratio"], ratio) for row in rows))
    for cid, ref in expected_candidates.items():
        if cid not in actual_candidates:
            continue
        candidate = actual_candidates[cid]
        check.equal(cid + ".status", ref["status"], candidate["calculation_status"])
        if ref["status"] == "BLOCKED":
            check.equal(cid + ".voyage", None, candidate["voyage_result"])
            check.equal(cid + ".rows", [], [r["scenario_id"] for r in rows if r["candidate_id"] == cid])
            continue
        voyage = candidate["voyage_result"]
        actual_points = voyage["scenarios"]
        points = ref["report_points"]
        check.equal(cid + ".report_point_count", len(points), len(actual_points))
        for point in points:
            matches = [p for p in actual_points if close(p["ratio"], point["ratio"])]
            check.equal(cid + ".report_point." + point["ratio"], 1, len(matches))
        for index, scenario in enumerate(actual_points):
            # Re-evaluate the actual returned ratio, not a rounded reference ratio.
            independent = ledger(case, cid, scenario["ratio"])
            request = next(c for c in case["request"]["candidates"] if c["candidateId"] == cid)
            if request.get("pricePerTonne") is None and F(scenario["ratio"]) == 0:
                # Candidate-local B0 economics are unavailable for an unpriced
                # quotation; the shared case B0 is independently checked above.
                independent["costs"]["fuel"] = independent["costs"]["model"] = None
            # Decimal projection of an exact boundary may land a few ulps on
            # the infeasible side. The reference report point identity and all
            # physics remain exact; permit only this documented boundary sign.
            independent = _boundary_projection(case, cid, ref, independent)
            _scenario(check, f"{cid}.scenario[{index}]", independent, scenario)
        for field in ("x_budget", "x_supply", "x_cap"):
            bound = ref["constraints"][field]
            check.equal(cid + ".constraints." + field, bound,
                        voyage["constraints"][field], numeric=True)
        check.equal(cid + ".target_status", ref["target"]["reason"] or "TARGET_REACHABLE",
                    voyage["constraints"]["target_status"])
        for reference, product in (("unconstrained_low", "x_target_min_unconstrained"),
                                    ("constrained_low", "x_target_min")):
            check.equal(cid + "." + product, ref["target"][reference],
                        voyage["constraints"][product], numeric=True)
        for name, product in (("cost", "x_cost_min"), ("target_cost", "x_target_min_cost"),
                              ("max_improvement", "x_max_improvement")):
            optimum = ref["optima"][name]
            ratio = voyage["constraints"][product]
            if name == "max_improvement":
                check.equal(cid + "." + product, ref["constraints"]["x_max_improvement"],
                            ratio, numeric=True)
            elif optimum["status"] == "UNAVAILABLE":
                check.equal(cid + "." + product, None, ratio)
            else:
                interval = optimum["ratio_interval"]
                allowed = ratio is not None and F(interval[0]) - ABSOLUTE_TOLERANCE <= F(ratio) <= F(interval[1]) + ABSOLUTE_TOLERANCE
                check.equal(cid + "." + product + ".optimal", True, allowed)
        economics = voyage["economics"]
        check.equal(cid + ".pc_break_even", ref["break_even"]["candidate_price"]["value"],
                    economics["pc_break_even"], numeric=True)
        check.equal(cid + ".pe_break_even", ref["break_even"]["eua_price"]["value"],
                    economics["pe_break_even"], numeric=True)
        threshold_status = ref["break_even"]["eua_price"]["status"]
        threshold_status = {"NO_FINITE_THRESHOLD": "NO_FINITE_POINT",
                            "ALL_PRICES_TIED": "ALL_PRICES_TIE",
                            "UNAVAILABLE": "PRICE_REQUIRED_FOR_COMPARISON"}.get(threshold_status, threshold_status)
        check.equal(cid + ".pe_break_even_status", threshold_status,
                    economics["pe_break_even_status"])
        local_recommendations = {r["recommendation_id"]: r for r in actual["recommendations"]}
        for kind, role in (("target_cost", "TARGET_MIN_COST"), ("max_improvement", "MAX_COMPLIANCE_IMPROVEMENT")):
            recommendation = local_recommendations.get(role + ":" + cid)
            check.equal(cid + "." + role + ".present", True, recommendation is not None)
            if recommendation is None:
                continue
            optimum = ref["optima"][kind]
            if optimum["status"] == "AVAILABLE":
                selected_id = recommendation["scenario_id"]
                selected = next((r for r in rows if r["scenario_id"] == selected_id), None)
                if selected and selected_id == "B0":
                    selected = {**selected, "candidate_id": cid}
                valid = selected is not None and _matches_winner(selected, {"candidate_id": cid, **optimum})
                check.equal(cid + "." + role + ".winner", True, valid)
                check.equal(cid + "." + role + ".status", "CONDITIONAL", recommendation["status"])
            else:
                check.equal(cid + "." + role + ".unavailable", None, recommendation["scenario_id"])
                check.equal(cid + "." + role + ".status", "UNAVAILABLE", recommendation["status"])
    for row in rows:
        independent = ledger(case, row["candidate_id"], row["result"]["ratio"])
        if row["candidate_id"] is not None:
            ref_candidate = expected_candidates[row["candidate_id"]]
            independent = _boundary_projection(case, row["candidate_id"], ref_candidate, independent)
        _scenario(check, row["scenario_id"], independent, row["result"])
        for metric, path in DELTA_KEYS.items():
            value, base = at(independent, path), at(expected["baseline"], path)
            delta = None if value is None or base is None else F(value) - F(base)
            percent = None if delta is None or F(base) == 0 else delta / abs(F(base)) * 100
            reason = "ZERO_BASELINE" if delta is not None and F(base) == 0 else None
            wanted = {"absolute": value, "delta": delta, "percent_delta": percent, "reason_code": reason}
            for field, number in wanted.items():
                check.equal(f"{row['scenario_id']}.deltas.{metric}.{field}",
                            None if number is None else str(number), row["deltas"][metric][field],
                            numeric=field != "reason_code")
        prefix = f"scenarios.{row['scenario_id']}.result"
        reasons = actual.get("field_reasons", {})
        for product, reference in METRICS.items():
            if at(independent, reference) is not None:
                continue
            reason = None
            if product.startswith("fuel_eu.") or product == "compliance_improvement_tco2e":
                reason = independent["fueleu"]["status"]
            elif product in ("fuel_cost", "model_cost"):
                reason = "PRICE_REQUIRED_FOR_COMPARISON"
            elif product == "eu_ets.eua_cost":
                reason = "EUA_PRICE_NOT_PROVIDED"
            elif product == "reference_adjusted_cost":
                reason = "NOT_DEFINED_AT_CASE_LEVEL" if row["candidate_id"] is None else "COMPLIANCE_VALUE_NOT_PROVIDED"
            # The public reason contract intentionally does not annotate the denominator.
            if reason and product != "fuel_eu.denominator_rwd_mj":
                check.equal(prefix + "." + product + ".reason", reason, reasons.get(prefix + "." + product))
    for name, key in (("cost_minimum", "cost_min_scenario_id"),
                      ("target_cost_minimum", "target_min_cost_scenario_id"),
                      ("max_improvement", "max_improvement_scenario_id")):
        optimum = expected["economics"][name]
        for section in ("economics", "decision_summary"):
            if section == "decision_summary" and not case["request"]["candidates"]:
                check.equal("B0_only.decision_summary", None, actual[section])
                continue
            selected_id = actual[section][key]
            if not optimum["winners"]:
                check.equal(section + "." + key, None, selected_id)
            else:
                selected = next((r for r in rows if r["scenario_id"] == selected_id), None)
                valid = selected is not None and any(_matches_winner(selected, w) for w in optimum["winners"])
                check.equal(section + "." + key + ".independent_winner", True, valid)
    _ranking(check, expected, rows)
    _switches(check, expected, actual, rows)
    _factors(check, case, actual)
    for issue in case["expected_issues"]:
        if issue["code"] not in WARNINGS:
            continue
        # Warning placement differs from blocking issue placement by contract.
        import json
        scope = (actual if issue.get("candidate_id") is None
                 else actual_candidates[issue["candidate_id"]])
        check.equal("nonblocking_warning." + issue["code"], True,
                    issue["code"] in json.dumps(scope))
    return check.result()


def _ranking(check, expected, rows):
    ranking = expected["economics"]["ranking"]
    selected = [r for r in rows if r["current_model_cost_rank"] is not None]
    check.equal("ranking.count", len(ranking), len(selected))
    check.equal("ranking.positions", list(range(1, len(ranking) + 1)),
                sorted(r["current_model_cost_rank"] for r in selected))
    for row in selected:
        matches = [r for r in ranking if r["candidate_id"] == row["candidate_id"]
                   and close(r["ratio"], row["result"]["ratio"])]
        check.equal(row["scenario_id"] + ".rank.eligible", 1, len(matches))
        if matches:
            costs = [F(r["model_cost"]) for r in ranking]
            value = F(matches[0]["model_cost"])
            low = 1 + sum(c < value and not close(c, value) for c in costs)
            high = sum(c < value or close(c, value) for c in costs)
            check.equal(row["scenario_id"] + ".rank.cost_order", True,
                        low <= row["current_model_cost_rank"] <= high)


def _switches(check, expected, actual, rows):
    economics = expected["economics"]
    intervals = economics["intervals"]
    # Boundary-only ties at V=0 are not changes between two nonempty intervals.
    transitions = [(left, right) for left, right in zip(intervals, intervals[1:])
                   if left["winners"] != right["winners"]]
    switches = actual["economics"]["switch_points"]
    check.equal("switch_points.count", len(transitions), len(switches))
    line_map = {line["id"]: line for line in economics["lines"]}
    row_map = {row["scenario_id"]: row for row in rows}
    for index, (left, right) in enumerate(transitions):
        if index >= len(switches):
            break
        switch = switches[index]
        check.equal(f"switch[{index}].value", right["lower"], switch["value_star"], numeric=True)
        for direction, interval in (("from", left), ("to", right)):
            selected = row_map.get(switch[direction + "_scenario_id"])
            valid = selected is not None and any(
                selected["candidate_id"] == line_map[identifier]["candidate_id"]
                and close(selected["result"]["ratio"], line_map[identifier]["ratio"])
                for identifier in interval["winners"])
            check.equal(f"switch[{index}].{direction}.interval_winner", True, valid)
        value = F(right["lower"])
        for interval, direction in ((left, "from"), (right, "to")):
            probe = ((F(interval["lower"]) + value) / 2 if direction == "from"
                     else value + 1 if interval["upper"] is None
                     else (value + F(interval["upper"])) / 2)
            selected = row_map.get(switch[direction + "_scenario_id"])
            if selected:
                match = next((line for line in economics["lines"]
                              if line["candidate_id"] == selected["candidate_id"]
                              and close(line["ratio"], selected["result"]["ratio"])), None)
                if match:
                    objective = F(match["cost"]) - probe * F(match["improvement"])
                    best = min(F(line["cost"]) - probe * F(line["improvement"]) for line in economics["lines"])
                    check.equal(f"switch[{index}].{direction}.probe", str(best), str(objective), numeric=True)


def _factors(check, case, actual):
    factors = [case["snapshot"]["baseline"], *(
        case["snapshot"]["candidates"][c["candidateId"]] for c in case["request"]["candidates"]
        if c["candidateId"] in case["snapshot"]["candidates"])]
    traces = actual["provenance"]["factor_resolutions"]
    check.equal("factor_trace_count", len(factors), len(traces))
    fields = {"path_id": "path_id", "lcv": "lcv_mj_per_g", "co2": "cf_co2_g_per_g",
              "ch4": "cf_ch4_g_per_g", "n2o": "cf_n2o_g_per_g", "slip": "cslip_percent",
              "rwd": "rwd", "methane": "methane_slip_applicable", "mode": "wt_t_mode",
              "qualification": "qualification_status", "equipment_id": "equipment_id",
              "factor_status": "factor_status"}
    for index, (factor, trace) in enumerate(zip(factors, traces)):
        for reference, product in fields.items():
            check.equal(f"factors[{index}].{product}", factor[reference], trace["factor"][product],
                        numeric=reference in ("lcv", "co2", "ch4", "n2o", "slip", "rwd"))
        wtt = F(factor["wtt"])
        if factor["mode"] == "BIO_E" and factor.get("e") is not None:
            wtt = F(factor["e"]) - F(factor["co2"]) / F(factor["lcv"])
        elif factor["mode"] == "RFNBO_E" and factor.get("e") is not None:
            wtt = F(factor["e"]) - F(factor["eu"])
        check.equal(f"factors[{index}].wtt", str(wtt), trace["factor"]["wt_t_g_per_mj"], numeric=True)
        for source in factor.get("source_ids", []):
            check.equal(f"factors[{index}].source.{source}", True, source in trace["source_ids"])
    components = [case["request"]["baseline"], *(
        c for c in case["request"]["candidates"] if c["candidateId"] in case["snapshot"]["candidates"])]
    for index, (component, trace) in enumerate(zip(components, traces)):
        evidence = component.get("sourceEvidence", {})
        actual_evidence = {item["field_name"]: item for item in trace["factor"]["source_evidence"]}
        for field, entry in evidence.items():
            record = actual_evidence.get(field)
            check.equal(f"evidence[{index}].{field}.present", True, record is not None)
            if record:
                for input_key, output_key in (("sourceId", "source_id"), ("unit", "unit"),
                                              ("sourceType", "source_type"), ("verificationStatus", "verification_status")):
                    check.equal(f"evidence[{index}].{field}.{output_key}", entry[input_key], record[output_key])
