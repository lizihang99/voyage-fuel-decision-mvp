"""Independent reference model. No imports from the application under test.

Inputs are normalized component properties, not outputs from its solvers.
Mass-space HiGHS LP and exact rational vertex enumeration share the constraint
definition but use different solution algorithms. Neither uses closed-form
production blend thresholds.
"""
from fractions import Fraction as F
from scipy.optimize import linprog


def unit_properties(fuel, year):
    """Independent ledger per tonne: MJ/t, gCO2eq/t, reward MJ/t, tETS/t."""
    lcv = F(fuel["lcv"]) * 1000000
    slip = F(fuel["slip"]) / 100
    burned = 1 - slip
    co2, ch4, n2o = (F(fuel[k]) for k in ("co2", "ch4", "n2o"))
    ets = burned * co2
    if year >= 2026:
        ets += 28 * (burned * ch4 + slip) + 265 * burned * n2o
    numerator = lcv * F(fuel["wtt"]) + 1000000 * (
        burned * (co2 + 25 * ch4 + 298 * n2o) + slip * 25)
    denominator = lcv * F(fuel["rwd"])
    return lcv, numerator, denominator, ets


def normalized(case):
    lb, nb, db, qb = unit_properties(case["baseline"], case["year"])
    lc, nc, dc, qc = unit_properties(case["candidate"], case["year"])
    k = F(case["scope"]) * F(case["surrender"])
    def cost(f, q):
        return None if f["price"] is None or case["eua"] is None else (
            F(f["price"]) + F(case["eua"]) * k * q)
    return dict(lb=lb, lc=lc, gb=nb / db, gc=nc / dc,
                rb=db / lb, rc=dc / lc, kb=cost(case["baseline"], qb),
                kc=cost(case["candidate"], qc), mass=case["mass"], cap=case["cap"],
                supply=case["supply"], budget=case["budget"],
                target="85.6904" if case["year"] == 2030 else "89.3368")


def ledger(case, ratio, *, candidate_price=None, eua_price=None):
    """Solve the energy and ratio equalities in exact mass units."""
    x = F(ratio)
    lb, nb, db, qb = unit_properties(case["baseline"], case["year"])
    lc, nc, dc, qc = unit_properties(case["candidate"], case["year"])
    energy = F(case["mass"]) * lb
    total = energy / ((1 - x) * lb + x * lc)
    u, v = total * (1 - x), total * x
    pb = case["baseline"]["price"]
    pc = case["candidate"]["price"] if candidate_price is None else candidate_price
    pe = case["eua"] if eua_price is None else eua_price
    k = F(case["scope"]) * F(case["surrender"])
    cost = None if (pb is None and u != 0) or (pc is None and v != 0) or pe is None else (
        u * F(pb or 0) + v * F(pc or 0) + (u * qb + v * qc) * k * F(pe))
    ghgi = (u * nb + v * nc) / (u * db + v * dc)
    applicable = case["year"] != 2024 and case["fueleu_scope"] not in (None, "0")
    target = F("85.6904" if case["year"] == 2030 else "89.3368")
    balance = (target - ghgi) * energy * F(case["fueleu_scope"]) / 1000000 if applicable else None
    return dict(baseline_mass=u, candidate_mass=v, cost=cost, ghgi=ghgi,
                balance=balance, euas=(u * qb + v * qc) * k)


def problem(case, target=False, constrained=True):
    p = {k: None if v is None else F(v) for k, v in case.items()}
    energy = (F(1), p["lc"] / p["lb"])
    a, b = [(-F(1), F(0)), (F(0), -F(1))], [F(0), F(0)]
    if constrained:
        a.append((-p["cap"], 1 - p["cap"]))
        b.append(F(0))
        if p["supply"] is not None:
            a.append((F(0), F(1)))
            b.append(p["supply"] / p["mass"])
        if p["budget"] is not None and p["kb"] is not None and p["kc"] is not None:
            a.append((p["kb"], p["kc"]))
            b.append(p["kb"] + p["budget"] / p["mass"])
    d = (p["rb"], energy[1] * p["rc"])
    n = (p["gb"] * d[0], p["gc"] * d[1])
    if target:
        a.append((n[0] - p["target"] * d[0], n[1] - p["target"] * d[1]))
        b.append(F(0))
    return p, energy, a, b, n, d


def vertices(energy, a, b):
    points = set()
    for row, bound in zip(a, b):
        det = energy[0] * row[1] - energy[1] * row[0]
        if not det:
            continue
        u = (row[1] - energy[1] * bound) / det
        v = (energy[0] * bound - row[0]) / det
        if all(r[0] * u + r[1] * v <= z for r, z in zip(a, b)):
            points.add((u, v))
    return points


def solve(case, mode, constrained=True):
    """Return exact optimum and independent HiGHS optimum/diagnostics."""
    p, e, a, b, n, d = problem(case, mode.startswith("target"), constrained)
    if mode in ("cost", "target_cost") and (p["kb"] is None or p["kc"] is None):
        return dict(exact_ratio=None, solver_ratio=None, unavailable="MISSING_PRICE")
    if mode in ("cost", "target_cost"):
        c = (p["kb"], p["kc"])
    elif mode == "cap":
        c = (F(0), -F(1))
    else:
        c = (F(0), F(1))
    points = vertices(e, a, b)

    def objective(pt):
        u, v = pt
        if mode == "improvement":
            return (n[0] * u + n[1] * v) / (d[0] * u + d[1] * v)
        return c[0] * u + c[1] * v

    point = min(points, key=lambda pt: (objective(pt), pt[1] / sum(pt))) if points else None
    if mode == "improvement":
        # Charnes-Cooper: w = original masses / denominator, t = 1/denominator.
        aa = [[row[0], row[1], -bound] for row, bound in zip(a, b)]
        bb = [F(0)] * len(a)
        eq, rhs = [[e[0], e[1], -F(1)], [d[0], d[1], F(0)]], [F(0), F(1)]
        cc = [n[0], n[1], F(0)]
    else:
        aa, bb, eq, rhs, cc = a, b, [e], [F(1)], c
    # Scale each row; do not change mathematical feasible region.
    scaled_a, scaled_b = [], []
    for row, bound in zip(aa, bb):
        scale = max(F(1), abs(bound), *(abs(x) for x in row))
        scaled_a.append([float(x / scale) for x in row])
        scaled_b.append(float(bound / scale))
    cscale = max(F(1), *(abs(x) for x in cc))
    lp = linprog(
        [float(x / cscale) for x in cc], A_ub=scaled_a, b_ub=scaled_b,
        A_eq=[[float(x) for x in row] for row in eq],
        b_eq=[float(x) for x in rhs], bounds=(0, None), method="highs",
        options={"primal_feasibility_tolerance": 1e-9,
                 "dual_feasibility_tolerance": 1e-9},
    )
    return {
        "exact_ratio": None if point is None else point[1] / sum(point),
        "exact_masses_normalized": point,
        "exact_objective": None if point is None else objective(point),
        "solver_ratio": None if not lp.success else float(lp.x[1] / (lp.x[0] + lp.x[1])),
        "solver_status": int(lp.status), "solver_message": lp.message,
        "solver_eq_residual": None if not lp.success else lp.eqlin.residual.tolist(),
        "solver_min_inequality_slack": None if not lp.success else float(min(lp.ineqlin.residual)),
    }


def envelope(lines):
    """Exact winning intervals from ALL simultaneous pairwise inequalities.

Each tuple is (id, intercept, improvement); no production intersection probing.
Zero-width ties do not constitute a winning interval. Ties at V=0 are retained
as a possible boundary transition according to lexical representative ID.
"""
    intervals = []
    for name, cost, improvement in lines:
        lo, hi = F(0), None
        possible = True
        for other, other_cost, other_improvement in lines:
            delta_c, delta_i = cost - other_cost, improvement - other_improvement
            if delta_i == 0:
                if delta_c > 0 or (delta_c == 0 and name > other):
                    possible = False
                    break
            elif delta_i > 0:
                lo = max(lo, delta_c / delta_i)
            else:
                bound = delta_c / delta_i
                hi = bound if hi is None else min(hi, bound)
        if possible and (hi is None or hi > lo):
            intervals.append((lo, hi, name))
    intervals.sort(key=lambda x: (x[0], x[2]))
    transitions = []
    if intervals:
        start = min(lines, key=lambda line: (line[1], line[0]))[0]
        if start != intervals[0][2]:
            transitions.append((F(0), start, intervals[0][2]))
    for left, right in zip(intervals, intervals[1:]):
        if left[2] != right[2]:
            transitions.append((right[0], left[2], right[2]))
    return transitions
