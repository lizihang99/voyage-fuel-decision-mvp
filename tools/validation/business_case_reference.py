"""Independent, exact oracle for frozen single-voyage business cases.

Authority: calculation SPEC sections 6-13 and 15, fuel-factor specification,
and the documented 2026-09-17 pure-use / unverified-budget safety contract.
No production modules, solvers, factor catalogues, or fixtures are imported.

Public functions return JSON-compatible trees. Numbers are reduced rational
strings (integers omit "/1"); None always means unavailable, not numeric zero.
``ledger`` accepts an exact actual-response ratio for a fresh scenario check.

Optimization intersects the physical-energy line in (baseline tonnes,
candidate tonnes) space with each half-plane boundary, then evaluates every
feasible vertex. It deliberately does not use the production ratio formulae.
Pure-use permission is a reporting restriction: an excluded endpoint can be
an unattained infimum, never a fabricated 1-epsilon recommendation.
Optimum mathematical_ratio / mathematical_ratio_interval describe the closed
mass-space geometry with unverified budget planes omitted. representative_ratio
is separately gated by permission and budget assurance. constraints'
x_max_improvement exposes the mathematical physical bound, not a recommendation.

Validation boundary: snapshots are independently prepared, already normalized
factor/scope inputs. This oracle does not certify their provenance or redo
catalogue lookup or qualification fallback. Request-level issue classes are
derived independently from the public request contract; metadata issues are
only compared with that derivation and are never used as expected output.

Report interpretation: SPEC 11.2's final definition makes xTargetMin the
constrained target intersection's lower bound. That is the point included by
11.6. The independently named unconstrained minimum remains visible in target
and constraints metadata when unreachable; it is not an automatic report point.
"""

from decimal import Decimal
from fractions import Fraction
from itertools import combinations


MU = Fraction(1_000_000)
ZERO = Fraction(0)
ONE = Fraction(1)
EXECUTION = "EXECUTION_CONDITIONS_PENDING"
PRICE_REASON = "PRICE_REQUIRED_FOR_COMPARISON"
BUDGET_REASON = "BUDGET_UNAVAILABLE_WITHOUT_PRICES"
NONBLOCKING_CODES = frozenset({
    PRICE_REASON, BUDGET_REASON, "ZERO_BASELINE", "TARGET_NOT_APPLICABLE",
    "TARGET_NO_SOLUTION", "TARGET_UNREACHABLE_UNDER_CONSTRAINTS",
})


def _case_blocked(issues):
    return any(issue["scope"] == "CASE" and issue["code"] not in NONBLOCKING_CODES
               for issue in issues)


def _issue(code, scope, candidate_id=None):
    return {"code": code, "scope": scope, "candidate_id": candidate_id}


def _issue_key(issue):
    return (issue["scope"], issue.get("candidate_id") or "", issue["code"])


def _candidate_error(case, candidate):
    """Derive a candidate-level blocker from request fields, without the product."""
    request = case["request"]
    candidate_id = candidate.get("candidateId")
    if candidate.get("candidateAllowsPureUse") is False:
        if any(rational(ratio) == ONE for ratio in candidate.get("specifiedBlendRatios", [])):
            return "INVALID_BLEND_RATIO"
    if not candidate.get("custom"):
        # A non-custom path without a normalized snapshot has no complete
        # independently declared factor and must remain locally blocked.
        if candidate_id not in case.get("snapshot", {}).get("candidates", {}):
            return "MISSING_REQUIRED_FACTOR"
        return None

    evidence = candidate.get("sourceEvidence")
    mode = candidate.get("wtTMode")
    required = ["lcv", "cfCO2", "cfCH4", "cfN2O", "cslip",
                "methaneSlipApplicable", "rwd", "eligibleBiomassFraction"]
    if mode == "STATIC":
        required.append("wtT")
    elif mode in ("BIO_E", "RFNBO_E"):
        required.append("E")
    if mode == "RFNBO_E":
        required.append("eu")
    if not isinstance(evidence, dict) or any(field not in evidence for field in required):
        return "MISSING_REQUIRED_FACTOR"
    if any(field not in candidate for field in required):
        return "MISSING_REQUIRED_FACTOR"
    expected_units = {
        "lcv": "MJ/gFuel", "cfCO2": "gGHG/gFuel", "cfCH4": "gGHG/gFuel",
        "cfN2O": "gGHG/gFuel", "cslip": "%", "methaneSlipApplicable": "boolean",
        "rwd": "ratio", "eligibleBiomassFraction": "fraction",
        "wtT": "gCO2eq/MJ", "E": "gCO2eq/MJ", "eu": "gCO2eq/MJ",
    }
    if any(not isinstance(evidence[field], dict)
           or evidence[field].get("unit") != expected_units[field] for field in required):
        return "MISSING_REQUIRED_FACTOR"
    for field in ("cfCO2", "cfCH4", "cfN2O"):
        if rational(candidate[field]) < ZERO:
            return "INVALID_EMISSION_FACTOR"
    slip = candidate.get("cslip")
    if slip not in (None, "NA"):
        slip_value = rational(slip)
        if slip_value < ZERO or slip_value > 100:
            return "INVALID_CSLIP"
        if not candidate.get("methaneSlipApplicable") and slip_value != ZERO:
            return "INVALID_CSLIP"
    if int(request["reportYear"]) == 2024 and rational(candidate.get("rwd") or "1") == 2:
        return "MISSING_REQUIRED_FACTOR"
    if mode == "RFNBO_E" and rational(candidate.get("E") or "0") > rational("28.2"):
        return "RFNBO_E_EXCEEDS_LIMIT"
    if candidate_id not in case.get("snapshot", {}).get("candidates", {}):
        return "MISSING_REQUIRED_FACTOR"
    return None


def derive_issues(case):
    """Independently classify request errors and nonblocking data warnings."""
    request = case["request"]
    if "adjacentValidPortOfCallConfirmed" in request \
            and request["adjacentValidPortOfCallConfirmed"] is not True:
        return [_issue("PORT_OF_CALL_CONFIRMATION_REQUIRED", "CASE")]
    year = request.get("reportYear")
    if type(year) is not int or not 2024 <= year <= 2030:
        return [_issue("INVALID_YEAR", "CASE")]
    baseline = request.get("baseline")
    if not isinstance(baseline, dict):
        return [_issue("MISSING_REQUIRED_FACTOR", "CASE")]
    try:
        baseline_mass = rational(baseline.get("massTonnes"))
    except (TypeError, ValueError, ZeroDivisionError):
        return [_issue("INVALID_BASELINE_MASS", "CASE")]
    if baseline_mass <= ZERO:
        return [_issue("INVALID_BASELINE_MASS", "CASE")]
    eua_price = request.get("euaPricePerTCO2e")
    if eua_price is not None and rational(eua_price) < ZERO:
        return [_issue("INVALID_EUA_PRICE", "CASE")]
    candidates = request.get("candidates")
    if not isinstance(candidates, list):
        return [_issue("MISSING_REQUIRED_FACTOR", "CASE")]
    ids = [candidate.get("candidateId") for candidate in candidates if isinstance(candidate, dict)]
    if len(ids) != len(set(ids)):
        return [_issue("DUPLICATE_CANDIDATE_ID", "CASE")]

    issues = []
    if baseline.get("pricePerTonne") is None or eua_price is None:
        issues.append(_issue(PRICE_REASON, "CASE"))
    for candidate in candidates:
        candidate_id = candidate.get("candidateId")
        error = _candidate_error(case, candidate)
        if error:
            issues.append(_issue(error, "CANDIDATE", candidate_id))
            continue
        if candidate.get("pricePerTonne") is None:
            issues.append(_issue(PRICE_REASON, "CANDIDATE", candidate_id))
        if candidate.get("incrementalBudget") is not None and any((
            baseline.get("pricePerTonne") is None,
            candidate.get("pricePerTonne") is None,
            eua_price is None,
        )):
            issues.append(_issue(BUDGET_REASON, "CANDIDATE", candidate_id))
    return sorted(issues, key=_issue_key)


def reviewed_issues(case):
    """Derive issues and, for frozen business cases, verify reviewed metadata."""
    derived = derive_issues(case)
    if case.get("synthetic") is True:
        declared = sorted((dict(issue) for issue in case.get("expected_issues", [])),
                          key=_issue_key)
        if declared != derived:
            raise ValueError(
                f"{case.get('id')}: expected_issues differ from independent derivation: "
                f"declared={declared!r}, derived={derived!r}"
            )
        expected_status = 422 if _case_blocked(derived) else 200
        if case.get("expected_http_status") != expected_status:
            raise ValueError(f"{case.get('id')}: expected HTTP status differs from independent derivation")
    return derived


def rational(value):
    """Parse exact decimal/rational values, explicitly rejecting binary floats."""
    if isinstance(value, (float, bool)) or value is None:
        raise TypeError("An exact decimal string, Fraction, Decimal or integer is required")
    return Fraction(value)


def encode(value):
    """Recursively freeze exact numbers without consulting Decimal precision."""
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, (Fraction, Decimal, int)):
        number = rational(value)
        return (str(number.numerator) if number.denominator == 1
                else f"{number.numerator}/{number.denominator}")
    if isinstance(value, dict):
        return {key: encode(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [encode(item) for item in value]
    raise TypeError(f"Unsupported reference-output type: {type(value).__name__}")


def _optional(value):
    return None if value is None else rational(value)


def _factor(snapshot):
    f = dict(snapshot)
    for key in ("lcv", "wtt", "co2", "ch4", "n2o", "rwd", "biomass"):
        f[key] = rational(snapshot[key]) if snapshot[key] is not None else ZERO
    if f["lcv"] <= 0:
        raise ValueError("Frozen factor LCV must be positive")
    if f["rwd"] <= 0:
        raise ValueError("Frozen factor RWD must be positive")
    f["p"] = rational(snapshot["slip"]) / 100 if snapshot["slip"] is not None else ZERO
    if snapshot["mode"] == "BIO_E" and snapshot.get("e") is not None:
        f["wtt"] = rational(snapshot["e"]) - f["co2"] / f["lcv"]
    elif snapshot["mode"] == "RFNBO_E" and snapshot.get("e") is not None:
        f["wtt"] = rational(snapshot["e"]) - rational(snapshot["eu"])
    f["combustion_eq"] = f["co2"] + 25 * f["ch4"] + 298 * f["n2o"]
    default_ch4 = ONE if snapshot["methane"] else ZERO
    f["slip_eq"] = (
        rational(snapshot.get("csf_co2", ZERO))
        + 25 * rational(snapshot.get("csf_ch4", default_ch4))
        + 298 * rational(snapshot.get("csf_n2o", ZERO))
    )
    f["ttw_mass_eq"] = (1 - f["p"]) * f["combustion_eq"] + f["p"] * f["slip_eq"]
    f["n"] = f["lcv"] * f["wtt"] + f["ttw_mass_eq"]
    f["d"] = f["lcv"] * f["rwd"]
    burn = 1 - f["p"] if f["methane"] else ONE
    f["gas"] = {
        "CO2": burn * f["co2"] * (1 - f["biomass"]),
        "CH4": burn * f["ch4"] + (f["p"] if f["methane"] else ZERO),
        "N2O": burn * f["n2o"],
    }
    return f


def _context(case, candidate_id=None):
    request = case["request"]
    snapshot = case["snapshot"]
    candidate = None
    if candidate_id is not None:
        candidate = next(
            (c for c in request.get("candidates", []) if c["candidateId"] == candidate_id),
            None,
        )
        if candidate is None or candidate_id not in snapshot["candidates"]:
            raise ValueError(f"Candidate has no frozen factor: {candidate_id}")
    year = int(request["reportYear"])
    baseline = request["baseline"]
    b = _factor(snapshot["baseline"])
    c = _factor(snapshot["candidates"][candidate_id]) if candidate is not None else b
    scope = snapshot["scope"]
    geo, surrender = rational(scope["geo"]), rational(scope["surrender"])
    fuel_scope = _optional(scope["fueleu"])
    target = None if year == 2024 else rational("85.6904" if year == 2030 else "89.3368")
    mass = rational(baseline["massTonnes"])
    pb = _optional(baseline.get("pricePerTonne"))
    pc = _optional(candidate.get("pricePerTonne")) if candidate is not None else pb
    pe = _optional(request.get("euaPricePerTCO2e"))
    complete = all(p is not None for p in (pb, pc, pe))
    included = ["CO2"] if year < 2026 else ["CO2", "CH4", "N2O"]

    def ets_unit(f):
        return sum(f["gas"][g] * {"CO2": 1, "CH4": 28, "N2O": 265}[g]
                   for g in included)

    return {
        "request": request, "candidate": candidate, "candidate_id": candidate_id,
        "b": b, "c": c, "mass": mass, "energy_t": mass * b["lcv"],
        "geo": geo, "surrender": surrender, "effective": geo * surrender,
        "fuel_scope": fuel_scope, "target": target, "year": year,
        "applicable": year != 2024 and fuel_scope is not None and fuel_scope > 0,
        "pb": pb, "pc": pc, "pe": pe, "complete": complete,
        "included": included, "qb": ets_unit(b), "qc": ets_unit(c),
        "allows_pure": candidate.get(
            "candidateAllowsPureUse", candidate.get("allowsPureUse", False)
        ) if candidate else True,
    }


def _masses(ctx, ratio):
    total = ctx["energy_t"] / ((1 - ratio) * ctx["b"]["lcv"] + ratio * ctx["c"]["lcv"])
    return (total * (1 - ratio), total * ratio)


def _ratio(vertex):
    return vertex[1] / sum(vertex)


def _unit_costs(ctx):
    if not ctx["complete"]:
        return None
    return (ctx["pb"] + ctx["pe"] * ctx["effective"] * ctx["qb"],
            ctx["pc"] + ctx["pe"] * ctx["effective"] * ctx["qc"])


def _vertices(ctx, planes):
    """Enumerate intersections a*Mb+b*Mc<=limit with Lb*Mb+Lc*Mc=E."""
    lb, lc, energy = ctx["b"]["lcv"], ctx["c"]["lcv"], ctx["energy_t"]
    points = set()
    for a, b, limit in planes:
        determinant = lb * b - lc * a
        if determinant == 0:
            continue
        mb = (energy * b - lc * limit) / determinant
        mc = (lb * limit - energy * a) / determinant
        if all(aa * mb + bb * mc <= cc for aa, bb, cc in planes):
            points.add((mb, mc))
    return sorted(points, key=_ratio)


def _target_plane(ctx):
    return (ctx["b"]["n"] - ctx["target"] * ctx["b"]["d"],
            ctx["c"]["n"] - ctx["target"] * ctx["c"]["d"], ZERO)


def _geometry(ctx):
    candidate = ctx["candidate"] or {}
    simplex = [(-ONE, ZERO, ZERO), (ZERO, -ONE, ZERO)]
    cap = rational(candidate.get("maxBlendRatio") or "1")
    # An explicitly supplied zero must not be treated as a missing cap.
    if candidate.get("maxBlendRatio") is not None:
        cap = rational(candidate["maxBlendRatio"])
    planes = simplex + [(-cap, 1 - cap, ZERO)]
    supply = _optional(candidate.get("candidateSupplyTonnes"))
    budget = _optional(candidate.get("incrementalBudget"))
    x_supply, x_budget = ONE, ONE
    if supply is not None:
        supply_plane = (ZERO, ONE, supply)
        supply_vertices = _vertices(ctx, simplex + [supply_plane])
        x_supply = max(map(_ratio, supply_vertices))
        planes.append(supply_plane)
    budget_status = "NOT_PROVIDED"
    costs = _unit_costs(ctx)
    if budget is not None:
        if costs is None:
            x_budget, budget_status = None, "UNVERIFIED"
        else:
            budget_status = "VERIFIED"
            budget_plane = (*costs, ctx["mass"] * costs[0] + budget)
            budget_vertices = _vertices(ctx, simplex + [budget_plane])
            x_budget = max(map(_ratio, budget_vertices))
            planes.append(budget_plane)
    vertices = _vertices(ctx, planes)
    x_cap = max(map(_ratio, vertices))
    unconstrained_target, constrained_target = [], []
    if ctx["applicable"]:
        target_plane = _target_plane(ctx)
        unconstrained_target = _vertices(ctx, simplex + [target_plane])
        constrained_target = _vertices(ctx, planes + [target_plane])
    return {
        "x_budget": x_budget, "x_supply": x_supply, "x_cap": x_cap,
        "budget_status": budget_status, "planes": planes, "vertices": vertices,
        "unconstrained_target": unconstrained_target,
        "constrained_target": constrained_target,
    }


def _constraint_state(ctx, geo, ratio, masses):
    if ratio == 1 and not ctx["allows_pure"]:
        return "CONSTRAINT_INFEASIBLE"
    if any(a * masses[0] + b * masses[1] > limit for a, b, limit in geo["planes"]):
        return "CONSTRAINT_INFEASIBLE"
    if ratio > 0 and geo["budget_status"] == "UNVERIFIED":
        return "CONSTRAINT_UNVERIFIED"
    return "CONSTRAINT_FEASIBLE"


def _component(f, mass, role):
    grams = mass * MU
    unburned = grams * f["p"] if f["methane"] else ZERO
    biomass = f["biomass"]
    zero_status = (
        "ESTIMATED_ASSUMED_ELIGIBLE" if biomass and f["qualification"] == "ASSUMED_ELIGIBLE"
        else "VERIFIED_ELIGIBLE" if biomass and f["qualification"] == "VERIFIED_ELIGIBLE"
        else "FOSSIL_TREATMENT"
    )
    return {
        "role": role, "path_id": f["path_id"], "equipment_id": f["equipment_id"],
        "mass_t": mass, "mass_g": grams, "energy_mj": grams * f["lcv"],
        "unburned_mass_g": unburned, "burned_mass_g": grams - unburned,
        "lcv": f["lcv"], "wtt": f["wtt"], "rwd": f["rwd"],
        "slip_percent": _optional(f["slip"]), "slip_fraction": f["p"],
        "methane": f["methane"], "biomass": biomass,
        "combustion_eq": f["combustion_eq"], "slip_eq": f["slip_eq"],
        "ttw_mass_eq": f["ttw_mass_eq"],
        "effective_co2_factor": f["co2"] * (1 - biomass),
        "raw_by_gas_t": {g: mass * amount for g, amount in f["gas"].items()},
        "wtt_numerator_g": grams * f["lcv"] * f["wtt"],
        "ttw_numerator_g": grams * f["ttw_mass_eq"],
        "denominator_mj": grams * f["d"],
        "factor_status": f["factor_status"], "qualification": f["qualification"],
        "zero_rating_status": zero_status, "mode": f["mode"],
        "source_ids": list(f.get("source_ids", [])),
    }


def _raw_ledger(ctx, ratio):
    mb, mc = _masses(ctx, ratio)
    components = [
        _component(f, mass, role)
        for f, mass, role in [(ctx["b"], mb, "BASELINE"), (ctx["c"], mc, "CANDIDATE")]
        if mass > 0
    ]
    gases = {g: sum(c["raw_by_gas_t"][g] for c in components)
             for g in ("CO2", "CH4", "N2O")}
    raw_co2e = gases["CO2"] + 28 * gases["CH4"] + 265 * gases["N2O"]
    pre_scope = gases["CO2"] if ctx["year"] < 2026 else raw_co2e
    scope_gases = {
        g: gases[g] * ctx["geo"] if g in ctx["included"] else ZERO for g in gases
    }
    euas = pre_scope * ctx["effective"]
    d = sum(c["denominator_mj"] for c in components)
    n_wtt = sum(c["wtt_numerator_g"] for c in components)
    n_ttw = sum(c["ttw_numerator_g"] for c in components)
    energy = ctx["energy_t"] * MU
    reasons = {}
    if ctx["applicable"]:
        ghgi = (n_wtt + n_ttw) / d
        scoped_energy = energy * ctx["fuel_scope"]
        balance = (ctx["target"] * d - n_wtt - n_ttw) * scoped_energy / d
        penalty = -balance * 2400 / (ghgi * 41000) if balance < 0 else ZERO
        classification = ("SURPLUS_ESTIMATE" if balance > 0 else "DEFICIT_ESTIMATE"
                          if balance < 0 else "ON_TARGET_ESTIMATE")
        fuel_status = "VOYAGE_PROPORTIONAL_ESTIMATE"
        wtt_intensity, ttw_intensity = n_wtt / d, n_ttw / d
    else:
        fuel_status = "NOT_YET_APPLICABLE" if ctx["year"] == 2024 else "OUT_OF_SCOPE"
        ghgi = balance = penalty = classification = wtt_intensity = ttw_intensity = None
        scoped_energy = ZERO
        for field in ("ghgi", "balance_g", "balance_t", "penalty_eur", "classification",
                      "wtt_intensity", "ttw_intensity", "target", "denominator_mj"):
            reasons[f"fueleu.{field}"] = fuel_status
    fuel = ZERO
    for mass, price in [(mb, ctx["pb"]), (mc, ctx["pc"])]:
        if mass and price is None:
            fuel = None
            break
        if mass:
            fuel += mass * price
    eua_cost = None if ctx["pe"] is None else euas * ctx["pe"]
    model = None if fuel is None or eua_cost is None else fuel + eua_cost
    for field, amount in (("fuel", fuel), ("eua", eua_cost), ("model", model)):
        if amount is None:
            reasons["costs." + field] = PRICE_REASON
    states = {c["factor_status"] for c in components}
    factor_status = ("ESTIMATED" if "ESTIMATED" in states else "VERIFIED"
                     if "VERIFIED" in states else "FIXED")
    return {
        "candidate_id": ctx["candidate_id"], "ratio": ratio,
        "status": "COMPARABLE" if ctx["complete"] else "CALCULABLE",
        "factor_status": factor_status, "execution_status": EXECUTION,
        "components": components,
        "physical": {"baseline_mass_t": mb, "candidate_mass_t": mc,
                     "total_mass_t": mb + mc, "energy_mj": energy},
        "ets": {
            "raw_by_gas_t": gases, "raw_co2e_t": raw_co2e,
            "included_gases": ctx["included"],
            "excluded_from_surrender": [g for g in gases if g not in ctx["included"]],
            "pre_scope_co2e_t": pre_scope, "geo_co2e_t": pre_scope * ctx["geo"],
            "scope_by_gas_t": scope_gases, "geo": ctx["geo"],
            "surrender": ctx["surrender"], "effective": ctx["effective"], "euas": euas,
        },
        "fueleu": {
            "status": fuel_status, "target": ctx["target"] if ctx["applicable"] else None,
            "denominator_mj": d if ctx["applicable"] else None,
            "wtt_numerator_g": n_wtt, "ttw_numerator_g": n_ttw,
            "wtt_intensity": wtt_intensity, "ttw_intensity": ttw_intensity,
            "ghgi": ghgi, "scoped_energy_mj": scoped_energy,
            "balance_g": balance, "balance_t": None if balance is None else balance / MU,
            "classification": classification, "penalty_eur": penalty,
        },
        "costs": {"fuel": fuel, "eua": eua_cost, "model": model},
        "null_reasons": reasons,
    }


def _measurements(scenario):
    return {
        "fuel_cost": scenario["costs"]["fuel"], "eua_cost": scenario["costs"]["eua"],
        "model_cost": scenario["costs"]["model"], "euas": scenario["ets"]["euas"],
        "ghgi": scenario["fueleu"]["ghgi"], "balance_t": scenario["fueleu"]["balance_t"],
        "penalty_eur": scenario["fueleu"]["penalty_eur"],
        "co2_t": scenario["ets"]["raw_by_gas_t"]["CO2"],
        "ch4_t": scenario["ets"]["raw_by_gas_t"]["CH4"],
        "n2o_t": scenario["ets"]["raw_by_gas_t"]["N2O"],
        "raw_co2e_t": scenario["ets"]["raw_co2e_t"],
    }


def _scenario(case, ctx, ratio, geometry=None):
    if ratio < 0 or ratio > 1 or (ctx["candidate_id"] is None and ratio != 0):
        raise ValueError("ratio must be in [0,1]; B0 requires ratio=0")
    result = _raw_ledger(ctx, ratio)
    base = _raw_ledger(_context(case), ZERO)
    geometry = geometry or _geometry(ctx)
    result["constraint_status"] = _constraint_state(ctx, geometry, ratio, _masses(ctx, ratio))
    result["warnings"] = []
    if not ctx["complete"]:
        result["warnings"].append(PRICE_REASON)
    if geometry["budget_status"] == "UNVERIFIED":
        result["warnings"].append(BUDGET_REASON)
    values, base_values = _measurements(result), _measurements(base)
    deltas, percents = {}, {}
    for field, value in values.items():
        baseline = base_values[field]
        if value is None or baseline is None:
            reason = PRICE_REASON if field.endswith("cost") else result["fueleu"]["status"]
            deltas[field] = percents[field] = None
            result["null_reasons"][f"deltas.{field}"] = reason
            result["null_reasons"][f"percent_deltas.{field}"] = reason
        else:
            deltas[field] = value - baseline
            percents[field] = None if baseline == 0 else deltas[field] / abs(baseline) * 100
            if baseline == 0:
                result["null_reasons"][f"percent_deltas.{field}"] = "ZERO_BASELINE"
    result["deltas"], result["percent_deltas"] = deltas, percents
    eua_delta = deltas["eua_cost"]
    result["costs"]["eua_savings"] = None if eua_delta is None else -eua_delta
    if eua_delta is None:
        result["null_reasons"]["costs.eua_savings"] = PRICE_REASON
    value = (ctx["candidate"] or {}).get(
        "complianceImprovementValue", ctx["request"].get("complianceImprovementValue")
    )
    if value is None or result["costs"]["model"] is None or deltas["balance_t"] is None:
        result["costs"]["reference_adjusted"] = None
        result["null_reasons"]["costs.reference_adjusted"] = (
            "COMPLIANCE_VALUE_NOT_PROVIDED" if value is None else PRICE_REASON
            if result["costs"]["model"] is None else "TARGET_NOT_APPLICABLE"
        )
    else:
        result["costs"]["reference_adjusted"] = (
            result["costs"]["model"] - rational(value) * deltas["balance_t"]
        )
    for index, component in enumerate(result["components"]):
        if component["slip_percent"] is None:
            result["null_reasons"][f"components.{index}.slip_percent"] = "NOT_APPLICABLE"
    return result


def ledger(case, candidate_id, ratio):
    """Recompute a complete scenario at an exact returned ratio, including deltas."""
    if _case_blocked(reviewed_issues(case)):
        raise ValueError("A blocking case-level issue forbids reference calculations")
    return encode(_scenario(case, _context(case, candidate_id), rational(ratio)))


def _target_result(ctx, geo):
    free, constrained = geo["unconstrained_target"], geo["constrained_target"]
    if not ctx["applicable"]:
        status, reason = "NOT_APPLICABLE", "TARGET_NOT_APPLICABLE"
    elif not free:
        status, reason = "NO_SOLUTION", "TARGET_NO_SOLUTION"
    elif not constrained:
        status, reason = "UNREACHABLE", "TARGET_UNREACHABLE_UNDER_CONSTRAINTS"
    else:
        status, reason = "REACHABLE", None
    return {
        "status": status, "reason": reason,
        "unconstrained_low": _ratio(free[0]) if free else None,
        "unconstrained_high": _ratio(free[-1]) if free else None,
        "constrained_low": _ratio(constrained[0]) if constrained else None,
        "constrained_high": _ratio(constrained[-1]) if constrained else None,
    }


def _unavailable(reason):
    return {"status": "UNAVAILABLE", "reason": reason, "objective": None,
            "representative_ratio": None, "ratio_interval": None,
            "mathematical_ratio": None, "mathematical_ratio_interval": None,
            "upper_inclusive": False, "attained": False}


def _optimize(ctx, geo, vertices, kind, target):
    if kind in ("cost", "target_cost") and not ctx["complete"]:
        return _unavailable(PRICE_REASON)
    if kind != "cost" and not ctx["applicable"]:
        return _unavailable("TARGET_NOT_APPLICABLE")
    if not vertices:
        return _unavailable(target["reason"] or "TARGET_UNREACHABLE_UNDER_CONSTRAINTS")
    costs = _unit_costs(ctx)
    base_g = ctx["b"]["n"] / ctx["b"]["d"]

    def objective(vertex):
        mb, mc = vertex
        if kind == "max_improvement":
            ghgi = (mb * ctx["b"]["n"] + mc * ctx["c"]["n"]) / (
                mb * ctx["b"]["d"] + mc * ctx["c"]["d"]
            )
            return (base_g - ghgi) * ctx["energy_t"] * ctx["fuel_scope"]
        return mb * costs[0] + mc * costs[1]

    scores = [(objective(vertex), _ratio(vertex)) for vertex in vertices]
    best = (max if kind == "max_improvement" else min)(score for score, _ in scores)
    ratios = sorted(ratio for score, ratio in scores if score == best)
    low, high = ratios[0], ratios[-1]
    attained = ctx["allows_pure"] or low < 1
    result = {
        "status": "AVAILABLE" if attained else "UNAVAILABLE",
        "reason": None if attained else "PURE_USE_NOT_ALLOWED",
        "objective": best, "representative_ratio": low if attained else None,
        "ratio_interval": [low, high],
        "mathematical_ratio": low, "mathematical_ratio_interval": [low, high],
        "upper_inclusive": ctx["allows_pure"] or high < 1, "attained": attained,
    }
    if geo["budget_status"] == "UNVERIFIED" and high > 0:
        # A tied B0 remains recommendable; no positive ratio gets budget assurance.
        if low == 0:
            result["ratio_interval"] = [ZERO, ZERO]
            result["upper_inclusive"] = True
        else:
            result.update(status="UNAVAILABLE", reason=BUDGET_REASON,
                          representative_ratio=None, attained=False)
    return result


def _break_even(ctx):
    if not ctx["complete"]:
        empty = {"status": "UNAVAILABLE", "value": None, "reason": PRICE_REASON}
        return {"candidate_price": dict(empty), "eua_price": dict(empty)}
    scale = ctx["c"]["lcv"] / ctx["b"]["lcv"]
    price = scale * (ctx["pb"] + ctx["pe"] * ctx["effective"] * ctx["qb"]) - (
        ctx["pe"] * ctx["effective"] * ctx["qc"]
    )
    fuel = {"status": "FINITE_NON_NEGATIVE" if price >= 0 else "NEGATIVE_THRESHOLD",
            "value": price}
    numerator = scale * ctx["pb"] - ctx["pc"]
    denominator = ctx["effective"] * (ctx["qc"] - scale * ctx["qb"])
    if ctx["effective"] == 0:
        eua = {"status": "EUA_PRICE_IRRELEVANT", "value": None}
    elif denominator == 0:
        eua = {"status": "ALL_PRICES_TIED" if numerator == 0 else "NO_FINITE_THRESHOLD",
               "value": None}
    else:
        threshold = numerator / denominator
        eua = {"status": "FINITE_NON_NEGATIVE" if threshold >= 0 else "NEGATIVE_THRESHOLD",
               "value": threshold if threshold >= 0 else None}
    return {"candidate_price": fuel, "eua_price": eua}


def _candidate(case, ctx):
    geo = _geometry(ctx)
    target = _target_result(ctx, geo)
    optima = {
        "cost": _optimize(ctx, geo, geo["vertices"], "cost", target),
        "target_cost": _optimize(ctx, geo, geo["constrained_target"], "target_cost", target),
        "max_improvement": _optimize(ctx, geo, geo["vertices"], "max_improvement", target),
    }
    points = {}

    def add(ratio, role):
        if ratio is not None and (ratio != 1 or ctx["allows_pure"]):
            points.setdefault(ratio, set()).add(role)

    add(ZERO, "B0")
    add(ONE, "B100")
    for ratio in ctx["candidate"].get("specifiedBlendRatios", []):
        add(rational(ratio), "SPECIFIED")
    add(geo["x_cap"], "CAP")
    if ctx["candidate"].get("incrementalBudget") is not None:
        add(geo["x_budget"], "BUDGET_BOUNDARY")
    if ctx["candidate"].get("candidateSupplyTonnes") is not None:
        add(geo["x_supply"], "SUPPLY_BOUNDARY")
    # SPEC 11.2 defines xTargetMin=xTargetLow after intersection with [0,xCap].
    # Its separately displayed unconstrained minimum is not a 11.6 report point.
    add(target["constrained_low"], "TARGET_MIN")
    add(optima["target_cost"]["representative_ratio"], "TARGET_MIN_COST")
    add(optima["max_improvement"]["representative_ratio"], "MAX_IMPROVEMENT")
    issues = [dict(i) for i in reviewed_issues(case)
              if i.get("candidate_id") == ctx["candidate_id"]]
    constraints = {key: geo[key] for key in ("x_budget", "x_supply", "x_cap", "budget_status")}
    constraints["x_max_improvement"] = optima["max_improvement"]["mathematical_ratio"]
    constraints["x_target_min_unconstrained"] = target["unconstrained_low"]
    constraints["vertices"] = [
        {"baseline_mass_t": mb, "candidate_mass_t": mc, "ratio": _ratio((mb, mc))}
        for mb, mc in geo["vertices"]
    ]
    return {
        "status": "COMPARABLE" if ctx["complete"] else "CALCULABLE", "issues": issues,
        "report_points": [
            {"ratio": ratio, "roles": sorted(roles), "scenario": _scenario(case, ctx, ratio, geo)}
            for ratio, roles in sorted(points.items())
        ],
        "constraints": constraints, "target": target, "optima": optima,
        "break_even": _break_even(ctx),
    }


def envelope(lines):
    """Exact lower envelope of cost - V*improvement for V>=0.

    Pair intersections merely partition the domain. Winners are evaluated in
    every open interval; hidden intersections are removed and adjacent equal
    winner intervals are merged. Boundary-only ties remain in switch_points.
    """
    exact = [(line["id"], rational(line["cost"]), rational(line["improvement"]))
             for line in lines]
    if not exact:
        return {"switch_points": [], "intervals": []}

    def winners(value):
        prices = [(identifier, cost - value * improvement)
                  for identifier, cost, improvement in exact]
        minimum = min(price for _, price in prices)
        return sorted(identifier for identifier, price in prices if price == minimum)

    cuts = {ZERO}
    for (_, cost_a, improvement_a), (_, cost_b, improvement_b) in combinations(exact, 2):
        if improvement_a != improvement_b:
            intersection = (cost_a - cost_b) / (improvement_a - improvement_b)
            if intersection >= 0:
                cuts.add(intersection)
    cuts = sorted(cuts)
    raw_intervals = []
    for index, low in enumerate(cuts):
        high = cuts[index + 1] if index + 1 < len(cuts) else None
        probe = low + 1 if high is None else (low + high) / 2
        raw_intervals.append({"lower": low, "upper": high, "winners": winners(probe)})
    switches = []
    for index, cut in enumerate(cuts):
        at_cut = winners(cut)
        left = raw_intervals[index - 1]["winners"] if index else raw_intervals[0]["winners"]
        right = raw_intervals[index]["winners"]
        if left != right or at_cut != left or at_cut != right:
            switches.append({"value": cut, "winners": at_cut})
    intervals = []
    for interval in raw_intervals:
        if intervals and intervals[-1]["winners"] == interval["winners"]:
            intervals[-1]["upper"] = interval["upper"]
        else:
            intervals.append(dict(interval))
    return encode({"switch_points": switches, "intervals": intervals})


def _global_optimum(options, maximize=False, reason="NO_COMPARABLE_SCENARIOS"):
    valid = [(candidate_id, option) for candidate_id, option in options
             if option["status"] == "AVAILABLE"]
    open_limits = [(candidate_id, option) for candidate_id, option in options
                   if option["reason"] == "PURE_USE_NOT_ALLOWED" and option["objective"] is not None]
    if not valid and not open_limits:
        return {"status": "UNAVAILABLE", "reason": reason, "objective": None, "winners": []}
    best = (max if maximize else min)(
        option["objective"] for _, option in valid + open_limits
    )
    if not any(option["objective"] == best for _, option in valid):
        return {"status": "UNAVAILABLE", "reason": "PURE_USE_NOT_ALLOWED",
                "objective": best, "winners": []}
    return {"status": "AVAILABLE", "reason": None, "objective": best,
            "winners": [{"candidate_id": cid, **option} for cid, option in valid
                        if option["objective"] == best]}


def _baseline_option(objective):
    return {
        "status": "AVAILABLE", "reason": None, "objective": objective,
        "representative_ratio": ZERO, "ratio_interval": [ZERO, ZERO],
        "mathematical_ratio": ZERO, "mathematical_ratio_interval": [ZERO, ZERO],
        "upper_inclusive": True, "attained": True,
    }


def _economics(baseline, candidates):
    cost_options, target_options, improvement_options = [], [], []
    baseline_cost = baseline["costs"]["model"]
    baseline_balance = baseline["fueleu"]["balance_t"]
    comparable = baseline["status"] == "COMPARABLE"
    if comparable:
        cost_options.append((None, _baseline_option(baseline_cost)))
        if baseline_balance is not None and baseline_balance >= 0:
            target_options.append((None, _baseline_option(baseline_cost)))
    if baseline_balance is not None:
        improvement_options.append((None, _baseline_option(ZERO)))
    reports = [(None, ZERO, baseline)]
    for cid, candidate in candidates.items():
        if candidate["status"] == "BLOCKED":
            continue
        cost_options.append((cid, candidate["optima"]["cost"]))
        target_options.append((cid, candidate["optima"]["target_cost"]))
        improvement_options.append((cid, candidate["optima"]["max_improvement"]))
        reports.extend((cid, p["ratio"], p["scenario"])
                       for p in candidate["report_points"] if p["ratio"] != 0)
    ranking, lines = [], []
    for cid, ratio, scenario in reports:
        if scenario["status"] != "COMPARABLE" or scenario["constraint_status"] != "CONSTRAINT_FEASIBLE":
            continue
        ranking.append({"candidate_id": cid, "ratio": ratio,
                        "model_cost": scenario["costs"]["model"]})
        if scenario["deltas"]["balance_t"] is not None:
            lines.append({
                "id": "B0" if cid is None else f"{cid}@{encode(ratio)}",
                "candidate_id": cid, "ratio": ratio, "cost": scenario["costs"]["model"],
                "improvement": scenario["deltas"]["balance_t"],
            })
    ranking.sort(key=lambda row: (row["model_cost"], row["candidate_id"] or "", row["ratio"]))
    sensitivity = envelope(lines)
    reason = "TARGET_NOT_APPLICABLE" if baseline_balance is None else "NO_FEASIBLE_TARGET"
    return {
        "ranking": ranking,
        "cost_minimum": _global_optimum(cost_options),
        "target_cost_minimum": _global_optimum(target_options, reason=reason),
        "max_improvement": _global_optimum(improvement_options, maximize=True, reason=reason),
        "lines": lines, **sensitivity,
    }


def calculate_reference(case):
    """Calculate the case exclusively from request inputs and frozen factors.

    Expected issues define prevalidated blocking boundaries. Missing candidate
    snapshots are blocked; a blocking case-scoped issue prevents B0 calculation.
    SPEC 13.2 warnings and target-search outcomes do not block calculations.
    Scenario warnings are also derived independently from the supplied inputs.
    """
    issues = reviewed_issues(case)
    if _case_blocked(issues):
        return {
            "id": case["id"], "status": "BLOCKED", "issues": issues,
            "baseline": None, "candidates": {}, "economics": None,
        }
    baseline = _scenario(case, _context(case), ZERO)
    candidates = {}
    for candidate in case["request"].get("candidates", []):
        cid = candidate["candidateId"]
        local_issues = [issue for issue in issues if issue.get("candidate_id") == cid]
        local_blockers = [
            issue for issue in local_issues if issue["code"] not in NONBLOCKING_CODES
        ]
        if local_blockers:
            candidates[cid] = {"status": "BLOCKED", "issues": local_blockers, "report_points": []}
        elif cid not in case["snapshot"]["candidates"]:
            raise ValueError(f"Missing snapshot requires an independently derived issue: {cid}")
        else:
            candidates[cid] = _candidate(case, _context(case, cid))
    status = ("COMPARABLE" if baseline["status"] == "COMPARABLE"
              and all(c["status"] in ("COMPARABLE", "BLOCKED") for c in candidates.values())
              else "CALCULABLE")
    return encode({
        "id": case["id"], "status": status, "issues": issues, "baseline": baseline,
        "candidates": candidates, "economics": _economics(baseline, candidates),
    })
