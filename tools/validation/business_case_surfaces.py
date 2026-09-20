"""Export projections checked against the independent synthetic-case ledger.

No production calculation, report, or formatting helpers are imported here.
``actual`` supplies scenario identity/ratio mapping only, never expected values.
PDF assertions target labelled table rows at the default display precision.
"""

import csv
from decimal import Decimal, localcontext
from fractions import Fraction
import io
import re


# Public CSV metric -> independent ledger path, PDF label, display precision.
METRICS = {
    "ratio": ("ratio", None, 4),
    "baseline_mass_tonnes": ("physical.baseline_mass_t", "Baseline fuel mass", 3),
    "candidate_mass_tonnes": ("physical.candidate_mass_t", "Candidate fuel mass", 3),
    "physical_energy_mj": ("physical.energy_mj", "Physical energy", 3),
    "fuel_cost": ("costs.fuel", "Fuel cost", 2),
    "ets_raw_co2_t": ("ets.raw_by_gas_t.CO2", "CO2", 6),
    "ets_raw_ch4_t": ("ets.raw_by_gas_t.CH4", "CH4", 6),
    "ets_raw_n2o_t": ("ets.raw_by_gas_t.N2O", "N2O", 6),
    "ets_mrv_raw_co2e_t": ("ets.raw_co2e_t", "MRV raw CO2e", 6),
    "ets_co2e_pre_scope_t": ("ets.pre_scope_co2e_t", "EU ETS CO2e before scope", 6),
    "euas_required": ("ets.euas", "EUAs required", 6),
    "eua_cost": ("costs.eua", "EUA cost", 2),
    "model_cost": ("costs.model", "Model cost", 2),
    "fueleu_scoped_energy_mj": ("fueleu.scoped_energy_mj", "FuelEU scoped energy", 3),
    "fueleu_denominator_rwd_mj": ("fueleu.denominator_mj", "FuelEU RWD denominator", 3),
    "fueleu_wtt_intensity_g_per_mj": ("fueleu.wtt_intensity", "WtT", 4),
    "fueleu_ttw_intensity_g_per_mj": ("fueleu.ttw_intensity", "TtW", 4),
    "fueleu_ghgi_actual_g_per_mj": ("fueleu.ghgi", "GHGI", 4),
    "fueleu_target_g_per_mj": ("fueleu.target", "Target", 4),
    "fueleu_compliance_balance_g": ("fueleu.balance_g", "Compliance balance (g)", 6),
    "fueleu_compliance_balance_t": ("fueleu.balance_t", "Compliance balance", 6),
    "fueleu_indicative_penalty_eur": ("fueleu.penalty_eur", "Indicative penalty equivalent", 2),
    "compliance_improvement_tco2e": ("improvement", "Compliance improvement", 6),
    "reference_adjusted_cost": ("costs.reference_adjusted", "Reference-adjusted cost", 2),
}
DECISIONS = {
    "fuel_cost_delta": ("fuel_cost", 1),
    "eua_cost_savings": ("eua_cost", -1),
    "model_cost_delta": ("model_cost", 1),
    "fueleu_ghgi_delta": ("fueleu_ghgi_actual_g_per_mj", 1),
    "fueleu_balance_delta": ("fueleu_compliance_balance_t", 1),
    "fueleu_penalty_delta": ("fueleu_indicative_penalty_eur", 1),
}


def _get(book, path):
    for part in path.split("."):
        book = book[part]
    return book


def _fraction(value):
    return None if value is None else Fraction(value)


def _near(left, right):
    return abs(left - right) <= max(Fraction(1, 10**8), abs(right) / 10**18)


def _metrics(book, baseline):
    values = {}
    for key, (path, _, _) in METRICS.items():
        if path == "improvement":
            value, base = book["fueleu"]["balance_t"], baseline["fueleu"]["balance_t"]
            values[key] = None if value is None or base is None else Fraction(value) - Fraction(base)
        else:
            values[key] = _fraction(_get(book, path))
    return values


def _delta(value, baseline):
    if value is None or baseline is None:
        return value, None, None, ""
    change = value - baseline
    if baseline == 0:
        return value, change, None, "ZERO_BASELINE"
    return value, change, change / abs(baseline) * 100, ""


def _display(value, places=6, scale=1):
    if value is None:
        return "-"
    with localcontext() as context:
        context.prec = 80
        value = Fraction(value) * Fraction(scale)
        number = Decimal(value.numerator) / Decimal(value.denominator)
        rendered = format(number, f".{places}f")
    return rendered[1:] if rendered.startswith("-") and Decimal(rendered) == 0 else rendered


def _compact(text):
    # A mathematically zero target can carry a signed rounding residue.
    text = re.sub(r"(?<![\d.])-0\.0+(?!\d)", lambda m: m.group()[1:], text)
    return "".join(text.split())


def _pdf_text(pdf_bytes):
    from pypdf import PdfReader
    return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf_bytes)).pages)


def _section(text, heading, next_heading):
    if heading not in text:
        return ""
    return text.split(heading, 1)[1].split(next_heading, 1)[0]


def _constraint(book):
    return {
        "CONSTRAINT_FEASIBLE": "FEASIBLE",
    }.get(book["constraint_status"], book["constraint_status"])


def _calculation_status(case, candidate_id, values):
    if candidate_id is None:
        return "COMPARABLE" if values["model_cost"] is not None else "CALCULABLE"
    candidate = next(c for c in case["request"]["candidates"] if c["candidateId"] == candidate_id)
    priced = all(v is not None for v in (
        case["request"]["baseline"].get("pricePerTonne"),
        candidate.get("pricePerTonne"), case["request"].get("euaPricePerTCO2e"),
    ))
    return "COMPARABLE" if priced else "CALCULABLE"


class _Checks:
    def __init__(self):
        self.assertions = 0
        self.differences = []

    def equal(self, path, observed, expected):
        self.assertions += 1
        if observed != expected:
            self.differences.append({"path": path, "expected": expected, "actual": observed})

    def numeric(self, path, observed, expected):
        self.assertions += 1
        if expected is None:
            valid = observed == ""
        else:
            try:
                # Raw CSV must be finite decimal text, not a reference fraction.
                parsed = Decimal(observed)
                valid = parsed.is_finite() and _near(Fraction(parsed), expected)
            except (ValueError, ArithmeticError, TypeError):
                valid = False
        if not valid:
            self.differences.append({
                "path": path, "expected": None if expected is None else str(expected),
                "actual": observed,
            })

    def contains(self, path, text, row):
        self.equal(path, _compact(row) in _compact(text), True)

    def result(self):
        return {"assertions": self.assertions, "differences": self.differences}


def _null_fields(values, book, candidate_id, case):
    """Public nullable-field paths/reasons derived from input and reference state."""
    reasons = {}
    for key in ("fuel_cost", "model_cost"):
        if values[key] is None:
            reasons[key] = "PRICE_REQUIRED_FOR_COMPARISON"
    if values["eua_cost"] is None:
        reasons["eu_ets.eua_cost"] = "EUA_PRICE_NOT_PROVIDED"
    for metric, field in (
        ("fueleu_wtt_intensity_g_per_mj", "wt_t_intensity_g_per_mj"),
        ("fueleu_ttw_intensity_g_per_mj", "tt_w_intensity_g_per_mj"),
        ("fueleu_ghgi_actual_g_per_mj", "ghgi_actual_g_per_mj"),
        ("fueleu_target_g_per_mj", "target_g_per_mj"),
        ("fueleu_compliance_balance_g", "compliance_balance_g"),
        ("fueleu_compliance_balance_t", "compliance_balance_t"),
        ("fueleu_indicative_penalty_eur", "indicative_penalty_eur"),
    ):
        if values[metric] is None:
            reasons["fuel_eu." + field] = book["fueleu"]["status"]
    if values["compliance_improvement_tco2e"] is None:
        reasons["compliance_improvement_tco2e"] = book["fueleu"]["status"]
    if values["reference_adjusted_cost"] is None:
        candidate = next((c for c in case["request"]["candidates"]
                          if c["candidateId"] == candidate_id), {})
        reasons["reference_adjusted_cost"] = (
            "NOT_DEFINED_AT_CASE_LEVEL" if candidate_id is None else
            "COMPLIANCE_VALUE_NOT_PROVIDED" if candidate.get("complianceImprovementValue") is None
            else book["fueleu"]["status"]
        )
    return reasons


def validate_exports(case, expected, actual, csv_text, pdf_bytes):
    """Check default-precision exports against independent reference expectations.

    Returns JSON-safe assertion counts and structured differences. This sidecar
    does not validate API calculations, global optimizer choices, or report
    visual layout; those are separate runner/browser responsibilities.
    """
    from tools.validation.business_case_reference import ledger

    checks = _Checks()
    baseline = expected.get("baseline")
    if baseline is None:
        # A case-level block cannot create an exportable result snapshot.
        checks.equal("csv.blocked.no_export", csv_text in ("", None), True)
        checks.equal("pdf.blocked.no_export", pdf_bytes in (b"", None), True)
        return checks.result()
    try:
        reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")))
        rows = list(reader)
        checks.equal("csv.header", {
            "record_type", "scenario_id", "metric_name", "absolute", "delta",
            "percent_delta", "reason_code", "calculation_status", "constraint_status",
        }.issubset(reader.fieldnames or []), True)
    except (csv.Error, TypeError, AttributeError) as exc:
        checks.equal("csv.parse", type(exc).__name__, "valid CSV")
        rows = []
    try:
        pdf_text = _pdf_text(pdf_bytes)
    except Exception as exc:
        checks.equal("pdf.parse", type(exc).__name__, "valid PDF")
        pdf_text = ""

    changes = _section(pdf_text, "Absolute and relative-to-B0 changes", "Concrete switch points")
    comparison = _section(pdf_text, "Scenario comparison (fuel mass and energy)",
                          "EU ETS gas scope and zero-rating status")
    nullable = _section(pdf_text, "Nullable field reasons", "Factor evidence and resolution")
    constraint_pdf = _section(pdf_text, "Constraints and thresholds", "Candidate economic thresholds")
    switch_pdf = _section(pdf_text, "Concrete switch points",
                          "FuelEU metrics and changes relative to B0")
    recommendation_pdf = _section(
        pdf_text, "Conclusions and conditional recommendations",
        "Scenario comparison (fuel mass and energy)",
    )
    case_rows = [r for r in rows if r.get("record_type") == "case"]
    checks.equal("csv.case.count", len(case_rows), 1)
    if case_rows:
        checks.equal("csv.case.status", case_rows[0].get("calculation_status"),
                     "CALCULABLE" if baseline else "BLOCKED")
        for column, key in (
            ("report_year", "reportYear"), ("departure_port", "departurePort"),
            ("arrival_port", "arrivalPort"), ("currency", "currency"),
        ):
            checks.equal("csv.case." + column, case_rows[0].get(column),
                         str(case["request"][key]))
        scope = case["snapshot"]["scope"]
        for column, value in (
            ("eu_ets_scope_rate", scope["geo"]),
            ("eu_ets_surrender_rate", scope["surrender"]),
            ("fuel_eu_scope_rate", scope["fueleu"]),
            ("ets_effective_rate", Fraction(scope["geo"]) * Fraction(scope["surrender"])),
        ):
            checks.numeric("csv.case." + column, case_rows[0].get(column), _fraction(value))
    base_values = _metrics(baseline, baseline)
    identity = {}
    for row in actual.get("scenarios", []):
        sid, cid = row["scenario_id"], row.get("candidate_id")
        ratio = row["result"]["ratio"]
        checks.equal(f"identity.{sid}.unique", sid in identity, False)
        identity[sid] = (cid, ratio)
    checks.equal("identity.B0", identity.get("B0"), (None, "0"))
    identity.setdefault("B0", (None, "0"))

    def allowed_scenario_ids(optimum, candidate_id=None):
        if optimum.get("status") != "AVAILABLE":
            return []
        allowed = []
        winners = optimum.get("winners") or [{
            "candidate_id": candidate_id,
            "representative_ratio": optimum.get("representative_ratio"),
            "ratio_interval": optimum.get("ratio_interval"),
        }]
        for winner in winners:
            interval = winner.get("ratio_interval")
            representative = winner.get("representative_ratio")
            for sid, (cid, ratio) in identity.items():
                value = Fraction(ratio)
                if interval is not None:
                    low, high = map(Fraction, interval)
                    inside = low - Fraction(1, 10**30) <= value <= high + Fraction(1, 10**30)
                else:
                    inside = representative is not None and _near(value, Fraction(representative))
                if not inside:
                    continue
                expected_candidate = winner.get("candidate_id", candidate_id)
                if value == 0 or cid == expected_candidate:
                    allowed.append(sid)
        return sorted(set(allowed))

    csv_ids = {r.get("scenario_id") for r in rows if r.get("record_type") == "scenario"}
    checks.equal("csv.scenario_ids", sorted(csv_ids), sorted(identity))
    frozen = {}
    for candidate_id, candidate in expected.get("candidates", {}).items():
        for point in candidate.get("report_points", []):
            if Fraction(point["ratio"]) == 0:
                continue
            matches = [sid for sid, (cid, ratio) in identity.items()
                       if cid == candidate_id
                       and abs(Fraction(ratio) - Fraction(point["ratio"])) <= Fraction(1, 10**20)]
            checks.equal(f"identity.reference.{candidate_id}@{point['ratio']}", len(matches), 1)
            if len(matches) == 1:
                frozen[matches[0]] = point["scenario"]

    expected_books = {}
    for sid, (candidate_id, ratio) in identity.items():
        if candidate_id is not None and candidate_id not in case["snapshot"]["candidates"]:
            checks.equal(f"identity.{sid}.candidate", candidate_id, "independently calculable candidate")
            continue
        book = baseline if candidate_id is None else frozen.get(sid)
        if book is None:
            book = ledger(case, candidate_id, ratio)
        values = _metrics(book, baseline)
        expected_books[sid] = (book, values)
        status = _calculation_status(case, candidate_id, values)
        constraint = _constraint(book)
        for key, (_, label, places) in METRICS.items():
            found = [r for r in rows if r.get("record_type") == "scenario"
                     and r.get("scenario_id") == sid and r.get("metric_name") == key]
            path = f"csv.scenarios.{sid}.{key}"
            checks.equal(path + ".count", len(found), 1)
            absolute, delta, percent, reason = _delta(values[key], base_values[key])
            if found:
                record = found[0]
                for field, value in (("absolute", absolute), ("delta", delta), ("percent_delta", percent)):
                    checks.numeric(path + "." + field, record.get(field), value)
                for field, wanted in (
                    ("reason_code", reason), ("calculation_status", status),
                    ("constraint_status", constraint), ("candidate_id", candidate_id or ""),
                    ("execution_status", "EXECUTION_CONDITIONS_PENDING"),
                    ("ets_included_gases", ";".join(book["ets"]["included_gases"])),
                ):
                    checks.equal(path + "." + field, record.get(field), wanted)
            if label:
                scale = Fraction(1, 1000) if key in (
                    "physical_energy_mj", "fueleu_scoped_energy_mj", "fueleu_denominator_rwd_mj"
                ) else 1
                expected_row = sid + label + _display(absolute, places, scale) + _display(delta, places, scale)
                expected_row += _display(percent) + ("%" if percent is not None else "")
                checks.contains(f"pdf.scenarios.{sid}.{key}", changes, expected_row)
            if reason:
                public_path = f"scenarios.{sid}.deltas.{key}.percent_delta"
                found_reasons = [r.get("reason_code") for r in rows
                                 if r.get("record_type") == "field_reason" and r.get("metric_name") == public_path]
                checks.equal(f"csv.reasons.{public_path}", found_reasons, [reason])
                checks.contains(f"pdf.reasons.{public_path}", nullable, public_path + reason)

        numeric_row = "".join(_display(values[key], places, scale) for key, places, scale in (
            ("ratio", 4, 100), ("baseline_mass_tonnes", 3, 1),
            ("candidate_mass_tonnes", 3, 1), ("physical_energy_mj", 3, Fraction(1, 1000)),
            ("fuel_cost", 2, 1), ("model_cost", 2, 1),
            ("ets_raw_co2_t", 6, 1), ("ets_raw_ch4_t", 6, 1), ("ets_raw_n2o_t", 6, 1),
            ("euas_required", 6, 1), ("eua_cost", 2, 1),
        ))
        checks.contains(f"pdf.comparison.{sid}", comparison,
                        sid + (candidate_id or "B0") + numeric_row
                        + status + "/" + constraint + "/EXECUTION_CONDITIONS_PENDING")
        for field, reason in _null_fields(values, book, candidate_id, case).items():
            public_path = f"scenarios.{sid}.result.{field}"
            found = [r.get("reason_code") for r in rows
                     if r.get("record_type") == "field_reason" and r.get("metric_name") == public_path]
            checks.equal(f"csv.reasons.{public_path}", found, [reason])
            checks.contains(f"pdf.reasons.{public_path}", nullable, public_path + reason)

    decision_rows = [r for r in rows if r.get("record_type") == "decision_summary"]
    groups = {}
    for row in decision_rows:
        groups.setdefault((row.get("decision_type"), row.get("scenario_id")), []).append(row)
    if case["request"].get("candidates"):
        checks.equal("csv.decisions.baseline.present", ("BASELINE", "B0") in groups, True)
    expected_groups = {}
    if case["request"].get("candidates"):
        expected_groups["BASELINE"] = {"B0"}
    if case["request"].get("candidates"):
        for role, optimum in (("CURRENT_MODEL_COST_MIN", expected["economics"]["cost_minimum"]),):
            allowed = allowed_scenario_ids(optimum)
            if allowed:
                expected_groups[role] = set(allowed)
    for candidate_id, candidate in expected.get("candidates", {}).items():
        if candidate["status"] == "BLOCKED":
            continue
        for role, key in (("TARGET_MIN_COST:" + candidate_id, "target_cost"),
                          ("MAX_COMPLIANCE_IMPROVEMENT:" + candidate_id, "max_improvement")):
            allowed = allowed_scenario_ids(candidate["optima"][key], candidate_id)
            if allowed:
                expected_groups[role] = set(allowed)
    for role, allowed in expected_groups.items():
        checks.equal(
            "csv.decisions.required." + role,
            any(group_role == role and sid in allowed for group_role, sid in groups),
            True,
        )
    for (role, sid), records in groups.items():
        checks.equal(f"csv.decisions.{role}.{sid}.metrics",
                     sorted(r.get("metric_name", "") for r in records), sorted(DECISIONS))
    for row in decision_rows:
        sid, key = row.get("scenario_id"), row.get("metric_name")
        path = f"csv.decisions.{row.get('decision_type')}.{sid}.{key}"
        checks.equal(path + ".known", sid in expected_books and key in DECISIONS, True)
        if sid not in expected_books or key not in DECISIONS:
            continue
        _, values = expected_books[sid]
        source, sign = DECISIONS[key]
        absolute, delta, percent, reason = _delta(values[source], base_values[source])
        for field, value in (
            ("absolute", absolute), ("delta", None if delta is None else delta * sign),
            ("percent_delta", None if percent is None else percent * sign),
            ("recommended_quantity_tonnes", values["candidate_mass_tonnes"]),
            ("recommended_blend_ratio", values["ratio"]),
        ):
            checks.numeric(path + "." + field, row.get(field), value)
        checks.equal(path + ".reason", row.get("reason_code"), reason)

    for candidate_id, candidate in expected.get("candidates", {}).items():
        constraint_rows = [r for r in rows if r.get("record_type") == "constraints"
                           and r.get("candidate_id") == candidate_id]
        checks.equal(f"csv.constraints.{candidate_id}.count", len(constraint_rows), 1)
        if candidate["status"] == "BLOCKED":
            if constraint_rows:
                checks.equal(f"csv.constraints.{candidate_id}.status",
                             constraint_rows[0].get("calculation_status"), "BLOCKED")
            checks.contains(f"pdf.constraints.{candidate_id}.blocked", constraint_pdf,
                            candidate_id + "------BLOCKED----")
            checks.equal(f"csv.blocked.{candidate_id}.scenarios",
                         [sid for sid, (cid, _) in identity.items() if cid == candidate_id], [])
        elif constraint_rows:
            for field in ("x_budget", "x_supply", "x_cap", "x_target_min_unconstrained"):
                checks.numeric(f"csv.constraints.{candidate_id}.{field}",
                               constraint_rows[0].get(field),
                               _fraction(candidate["constraints"][field]))

    economics_rows = [r for r in rows if r.get("record_type") == "economics"]
    checks.equal("csv.economics.count", len(economics_rows), 1)
    if economics_rows:
        row = economics_rows[0]
        checks.equal("csv.economics.comparison_status", row.get("comparison_status"),
                     expected["baseline"]["status"])
        for field, key in (
            ("cost_min_scenario_id", "cost_minimum"),
            ("target_min_cost_scenario_id", "target_cost_minimum"),
            ("max_improvement_scenario_id", "max_improvement"),
        ):
            allowed = allowed_scenario_ids(expected["economics"][key])
            actual_id = row.get(field) or None
            checks.equal("csv.economics." + field + ".winner",
                         actual_id in allowed if allowed else actual_id is None, True)

    for candidate_id, candidate in expected.get("candidates", {}).items():
        economics = [r for r in rows if r.get("record_type") == "candidate_economics"
                     and r.get("candidate_id") == candidate_id]
        if candidate["status"] == "BLOCKED":
            checks.equal(f"csv.candidate_economics.{candidate_id}.blocked", economics, [])
            continue
        checks.equal(f"csv.candidate_economics.{candidate_id}.count", len(economics), 1)
        if not economics:
            continue
        row = economics[0]
        break_even = candidate["break_even"]
        checks.numeric(f"csv.candidate_economics.{candidate_id}.pc_break_even",
                       row.get("pc_break_even"), _fraction(break_even["candidate_price"]["value"]))
        checks.numeric(f"csv.candidate_economics.{candidate_id}.pe_break_even",
                       row.get("pe_break_even"), _fraction(break_even["eua_price"]["value"]))
        status = {
            "ALL_PRICES_TIED": "ALL_PRICES_TIE",
            "NO_FINITE_THRESHOLD": "NO_FINITE_POINT",
            "EUA_PRICE_IRRELEVANT": "NO_FINITE_POINT",
            "UNAVAILABLE": "PRICE_REQUIRED_FOR_COMPARISON",
        }.get(break_even["eua_price"]["status"], break_even["eua_price"]["status"])
        checks.equal(f"csv.candidate_economics.{candidate_id}.pe_status",
                     row.get("pe_break_even_status"), status)
        cost_optimum = candidate["optima"]["cost"]
        checks.numeric(f"csv.candidate_economics.{candidate_id}.cost_min_ratio",
                       row.get("cost_min_ratio"),
                       None if cost_optimum["representative_ratio"] is None
                       else _fraction(cost_optimum["representative_ratio"]))

    expected_switches = expected["economics"]["switch_points"]
    switch_rows = [r for r in rows if r.get("record_type") == "switch_point"
                   and r.get("value_star") not in (None, "")]
    checks.equal("csv.switch_points.count", len(switch_rows), len(expected_switches))
    for index, expected_switch in enumerate(expected_switches):
        matches = [r for r in switch_rows
                   if r.get("value_star") not in (None, "")
                   and _near(Fraction(r["value_star"]), Fraction(expected_switch["value"]))]
        checks.equal(f"csv.switch_points.{index}.present", len(matches), 1)
        if matches:
            row = matches[0]
            left = expected["economics"]["intervals"][index]["winners"]
            right = expected["economics"]["intervals"][index + 1]["winners"]
            from_candidates = {line.split("@", 1)[0] if line != "B0" else ""
                               for line in left}
            to_candidates = {line.split("@", 1)[0] if line != "B0" else ""
                             for line in right}
            checks.equal(f"csv.switch_points.{index}.from",
                         (row.get("from_candidate_id") or "") in from_candidates, True)
            checks.equal(f"csv.switch_points.{index}.to",
                         (row.get("to_candidate_id") or "") in to_candidates, True)

    recommendations = [r for r in rows if r.get("record_type") == "recommendation"]
    recommendation_index = {}
    for row in recommendations:
        recommendation_index.setdefault(row.get("recommendation_id"), []).append(row)
    known_recommendations = {"CURRENT_MODEL_COST_MIN"}
    for candidate_id, candidate in expected.get("candidates", {}).items():
        known_recommendations.update({
            "TARGET_MIN_COST:" + candidate_id,
            "MAX_COMPLIANCE_IMPROVEMENT:" + candidate_id,
        })
    unknown_recommendations = sorted(
        recommendation_id for recommendation_id in recommendation_index
        if recommendation_id not in ("", None)
        and recommendation_id not in known_recommendations
        and not str(recommendation_id).startswith("REFERENCE_ADJUSTED_COST_SWITCH")
    )
    checks.equal("csv.recommendations.unknown", unknown_recommendations, [])
    if case["request"].get("candidates") \
            and expected["economics"]["cost_minimum"]["status"] == "AVAILABLE":
        rows_for_role = recommendation_index.get("CURRENT_MODEL_COST_MIN", [])
        checks.equal("csv.recommendations.current.count", len(rows_for_role), 1)
        if rows_for_role:
            allowed = allowed_scenario_ids(expected["economics"]["cost_minimum"])
            checks.equal("csv.recommendations.current.winner",
                         rows_for_role[0].get("scenario_id") in allowed, True)
            checks.equal("csv.recommendations.current.status",
                         rows_for_role[0].get("recommendation_status"), "CONDITIONAL")
    for candidate_id, candidate in expected.get("candidates", {}).items():
        if candidate["status"] == "BLOCKED":
            continue
        for role, key in (("TARGET_MIN_COST:" + candidate_id, "target_cost"),
                          ("MAX_COMPLIANCE_IMPROVEMENT:" + candidate_id, "max_improvement")):
            rows_for_role = recommendation_index.get(role, [])
            checks.equal(f"csv.recommendations.{role}.count", len(rows_for_role), 1)
            if not rows_for_role:
                continue
            row = rows_for_role[0]
            optimum = candidate["optima"][key]
            if optimum["status"] == "AVAILABLE":
                allowed = allowed_scenario_ids(optimum, candidate_id)
                checks.equal(f"csv.recommendations.{role}.winner",
                             row.get("scenario_id") in allowed, True)
                checks.equal(f"csv.recommendations.{role}.status",
                             row.get("recommendation_status"), "CONDITIONAL")
            else:
                checks.equal(f"csv.recommendations.{role}.unavailable",
                             row.get("scenario_id") or "", "")
                checks.equal(f"csv.recommendations.{role}.status",
                             row.get("recommendation_status"), "UNAVAILABLE")
    reference_rows = [r for r in recommendations
                      if str(r.get("recommendation_id", "")).startswith("REFERENCE_ADJUSTED_COST_SWITCH")
                      and r.get("value_star") not in (None, "")]
    checks.equal("csv.recommendations.reference_switch.count",
                 len(reference_rows), len(expected_switches))
    expected_switch_values = [Fraction(item["value"]) for item in expected_switches]
    for index, row in enumerate(reference_rows):
        try:
            value = Fraction(row.get("value_star"))
        except (TypeError, ValueError, ZeroDivisionError):
            value = None
        checks.equal(f"csv.recommendations.reference_switch.{index}.value",
                     value is not None
                     and any(_near(value, expected) for expected in expected_switch_values),
                     True)

    for index, expected_switch in enumerate(expected_switches):
        right = expected["economics"]["intervals"][index + 1]["winners"]
        candidates = {line.split("@", 1)[0] if line != "B0" else "-"
                      for line in right}
        checks.contains(f"pdf.switch_points.{index}", switch_pdf,
                        _display(Fraction(expected_switch["value"]), 2))
        checks.equal(f"pdf.switch_points.{index}.candidate",
                     any(candidate in switch_pdf for candidate in candidates), True)
    for role, allowed in expected_groups.items():
        checks.contains("pdf.recommendations." + role, recommendation_pdf, role)
        if role != "BASELINE":
            checks.equal(
                "pdf.recommendations." + role + ".scenario",
                any(sid in _compact(recommendation_pdf) for sid in allowed), True,
            )
    return checks.result()
