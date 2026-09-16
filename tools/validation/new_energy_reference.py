"""Test-only business expectations; no imports from the application.

The reference solves in mass space with exact rational vertices and HiGHS,
not with the application's ratio thresholds or list of generated scenarios.
Synthetic factors below are arithmetic fixtures, not approved fuel data.
"""
from fractions import Fraction as F

from c_layer_oracle import ledger, normalized, solve


def hand_case(price="1000", supply=None):
    return {
        "id": "clean", "year": 2026, "scope": ".5", "surrender": "1",
        "fueleu_scope": ".5", "mass": "100", "cap": ".6", "supply": supply,
        "budget": None, "eua": "80",
        "baseline": {
            "lcv": ".04", "wtt": "25", "co2": "3", "ch4": "0", "n2o": "0",
            "slip": "0", "rwd": "1", "price": "600",
        },
        "candidate": {
            "lcv": ".04", "wtt": "35", "co2": "1", "ch4": "0", "n2o": "0",
            "slip": "0", "rwd": "1", "price": price,
        },
    }


def business_values(case, ratio):
    book = ledger(case, ratio)
    masses = (book["baseline_mass"], book["candidate_mass"])
    prices = (case["baseline"]["price"], case["candidate"]["price"])
    fuel_cost = None if any(m and p is None for m, p in zip(masses, prices)) else sum(
        (m * F(p or 0) for m, p in zip(masses, prices)), F(0)
    )
    eua_cost = None if case["eua"] is None else book["euas"] * F(case["eua"])
    balance = book["balance"]
    ghgi = book["ghgi"] if balance is not None else None
    penalty = (
        -balance * 1000000 * 2400 / (ghgi * 41000)
        if balance is not None and balance < 0 else None
    )
    return {
        "ratio": F(ratio),
        "baseline_mass_tonnes": masses[0],
        "candidate_mass_tonnes": masses[1],
        "physical_energy_mj": F(case["mass"]) * F(case["baseline"]["lcv"]) * 1000000,
        "euas": book["euas"],
        "fuel_cost": fuel_cost,
        "eua_cost": eua_cost,
        "model_cost": None if fuel_cost is None or eua_cost is None else fuel_cost + eua_cost,
        "fueleu_ghgi_actual_g_per_mj": ghgi,
        "fueleu_compliance_balance_t": balance,
        "fueleu_indicative_penalty_eur": penalty,
    }


def business_deltas(case, ratio):
    baseline = business_values(case, 0)
    values = business_values(case, ratio)
    return {
        key: None if value is None or baseline[key] is None else value - baseline[key]
        for key, value in values.items()
    }


def optimal_references(case):
    applicable = case["year"] != 2024 and case["fueleu_scope"] not in (None, "0")
    refs = {}
    for mode in ("cost", "target_cost", "improvement"):
        if mode != "cost" and not applicable:
            refs[mode] = None
        else:
            refs[mode] = solve(normalized(case), mode)
    return refs


def custom_payload(cases):
    """Encode synthetic STATIC fixtures as documented API inputs, not results."""
    first = cases[0]

    def component(fuel, path):
        if fuel["rwd"] != "1":
            raise ValueError("STATIC API fixtures cannot use RFNBO rewards")
        fields = {
            "lcv": ("MJ/gFuel", fuel["lcv"]), "wtT": ("gCO2eq/MJ", fuel["wtt"]),
            "cfCO2": ("gGHG/gFuel", fuel["co2"]), "cfCH4": ("gGHG/gFuel", fuel["ch4"]),
            "cfN2O": ("gGHG/gFuel", fuel["n2o"]),
            "cslip": ("%", "NA"), "methaneSlipApplicable": ("boolean", False),
            "rwd": ("ratio", "1"), "eligibleBiomassFraction": ("fraction", "0"),
        }
        return {
            "custom": True, "pathId": path, "equipmentId": "CROSS_TEST",
            "wtTMode": "STATIC", "pricePerTonne": fuel["price"],
            "qualificationStatus": "NOT_DEMONSTRATED",
            **{key: value for key, (_, value) in fields.items()},
            "sourceEvidence": {
                key: [{
                    "sourceId": "SYNTHETIC-CROSS-TEST", "sourceType": "TEST",
                    "unit": unit, "verificationStatus": "ESTIMATED",
                }]
                for key, (unit, _) in fields.items()
            },
        }

    return {
        "reportYear": first["year"], "departurePort": "CNSHG", "arrivalPort": "NLRTM",
        "adjacentValidPortOfCallConfirmed": True, "currency": "EUR",
        "baseline": {**component(first["baseline"], "CROSS_BASE"), "massTonnes": first["mass"]},
        "euaPricePerTCO2e": first["eua"],
        "candidates": [
            {
                **component(case["candidate"], "CROSS_" + case["id"]),
                "candidateId": case["id"], "maxBlendRatio": case["cap"],
                "candidateSupplyTonnes": case["supply"], "incrementalBudget": case["budget"],
                "candidateAllowsPureUse": True, "specifiedBlendRatios": [],
            }
            for case in cases
        ],
    }
