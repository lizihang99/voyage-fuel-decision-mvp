"""Deterministic coverage matrix; synthetic inputs only, no product imports."""
from copy import deepcopy
from itertools import product
import random

from c_layer_inputs import decimal, fuel
from new_energy_reference import hand_case
from fractions import Fraction as F


SEED = 20260916


def expanded_cases():
    cases = []

    def add(category, label, **changes):
        case = hand_case()
        case.update(changes, id=f"NE-{len(cases) + 1:03d}", category=category, label=label)
        cases.append(case)

    for price in ("0", "100", "679.99", "680", "680.01", "1000", "100000"):
        add("price_reversal", "candidate price " + price,
            candidate={**hand_case()["candidate"], "price": price})
    for eua in ("0", "1", "399.99", "400", "400.01", "10000"):
        add("carbon_price_reversal", "EUA " + eua, eua=eua)

    for lb, lc in product((".005", ".02", ".04", ".05", ".12"), repeat=2):
        add("energy_density", f"LCV {lb}/{lc}",
            baseline=fuel(lb, "100", "600", "3"),
            candidate=fuel(lc, "60", "1000", "1"))
    for mass in (".000001", ".1", "1", "100", "10000", "10000000"):
        add("voyage_scale", "mass " + mass, mass=mass)
    for cap in ("0", ".0000000001", ".01", ".26658", ".6", ".9999999999", "1"):
        add("blend_endpoints", "cap " + cap, cap=cap)

    for field, threshold in (("cap", ".26658"), ("supply", "26.658"), ("budget", "8530.56")):
        for step in ("-.0000001", "-.00000000000000000001", "0", ".00000000000000000001", ".0000001"):
            add("target_boundary", f"{field} target {step}",
                **{field: decimal(F(threshold) + F(step))})
    for cap, supply, budget in product((".1", ".4"), ("10", "40"), ("3200", "12800")):
        add("simultaneous_constraints", f"cap={cap} supply={supply} budget={budget}",
            cap=cap, supply=supply, budget=budget)
    for field in ("supply", "budget"):
        for price in ("500", "680", "1000"):
            add("zero_constraint", f"{field}=0 price={price}", **{
                field: "0", "candidate": {**hand_case()["candidate"], "price": price},
            })

    for year, scope in product(range(2024, 2031), ("0", ".5", "1")):
        add("year_scope", f"year={year} scope={scope}", year=year, scope=scope,
            surrender={2024: ".4", 2025: ".7"}.get(year, "1"),
            fueleu_scope=None if year == 2024 else scope)
    for year, slip in product((2025, 2026, 2030), ("0", ".00000001", "3.1", "99", "100")):
        candidate = fuel(".05", "60", "500", "2.75")
        candidate.update(slip=slip, ch4=".00005", n2o=".00018")
        add("methane_year", f"year={year} slip={slip}", year=year,
            surrender=".7" if year == 2025 else "1", candidate=candidate)
    for rb, rc, lc in product(("1", "2"), ("1", "2"), (".02", ".05")):
        add("reward_denominator", f"rwd={rb}/{rc} lc={lc}",
            baseline=fuel(".04", "100", "600", "3", rb),
            candidate=fuel(lc, "60", "1000", "1", rc))
    for gb, gc in product(("60", "89.3368", "100"), repeat=2):
        add("target_topology", f"GHGI={gb}/{gc}", cap="1",
            baseline=fuel(".04", gb, "600", "3"),
            candidate=fuel(".04", gc, "500", "1"))
    for missing, budget in product(("candidate", "eua"), (None, "0", "5000")):
        case = hand_case()
        if missing == "candidate":
            case["candidate"]["price"] = None
        else:
            case["eua"] = None
        add("missing_prices", f"missing={missing} budget={budget}",
            candidate=case["candidate"], eua=case["eua"], budget=budget)

    rng = random.Random(SEED)
    for index in range(120):
        year = rng.choice((2024, 2025, 2026, 2029, 2030))
        scope = rng.choice(("0", ".5", "1"))
        candidate = fuel(rng.choice((".01", ".02", ".04", ".05", ".12")),
                         str(rng.randint(10, 150)), str(rng.randint(0, 3000)),
                         rng.choice(("0", "1", "2.75", "3")), rng.choice(("1", "2")))
        candidate.update(slip=rng.choice(("0", ".5", "3.1")),
                         ch4=rng.choice(("0", ".00005")), n2o=rng.choice(("0", ".00018")))
        add("seeded_combinations", f"seed={SEED} draw={index + 1}", year=year,
            scope=scope, surrender={2024: ".4", 2025: ".7"}.get(year, "1"),
            fueleu_scope=None if year == 2024 else scope,
            mass=rng.choice(("1", "100", "10000")),
            baseline=fuel(rng.choice((".02", ".04", ".05")), str(rng.randint(50, 130)),
                          str(rng.randint(0, 1200)), rng.choice(("1", "3"))),
            candidate=candidate, cap=rng.choice((".01", ".1", ".5", "1")),
            supply=rng.choice((None, "0", "5", "200")),
            budget=rng.choice((None, "0", "100", "10000")),
            eua=rng.choice(("0", "10", "80", "400", "1000")))
    return cases


def expanded_portfolios():
    rng = random.Random(SEED + 1)
    portfolios = []
    for index in range(40):
        size = (2, 3, 5, 8)[index % 4]
        baseline = fuel(".04", rng.choice(("80", "89.3368", "100")), "600", "3")
        cases = []
        for j in range(size):
            case = hand_case()
            case.update(
                id=f"P{index + 1:02d}C{j + 1}", baseline=deepcopy(baseline),
                candidate=fuel(rng.choice((".02", ".04", ".05")), str(rng.randint(20, 130)),
                               str(rng.randint(100, 1600)), rng.choice(("1", "3"))),
                cap=rng.choice((".1", ".3", ".6", "1")),
                supply=rng.choice((None, "0", "10", "100")),
                budget=rng.choice((None, "0", "1000", "10000")),
            )
            cases.append(case)
        portfolios.append(cases)
    return portfolios
