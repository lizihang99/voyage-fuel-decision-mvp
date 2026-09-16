"""Economic thresholds and FuelEU compliance-value sensitivity analysis."""

from dataclasses import replace
from decimal import Decimal
from itertools import combinations
from fractions import Fraction
from typing import Optional, Sequence

from .constraints import _unit_ets_tco2e
from .numerics import decimal_ratio, exact_unit_n_d
from .models import (
    EuaBreakEvenResult,
    EconomicsResult,
    FuelComponent,
    ScenarioResult,
    ScopeRates,
    ValueSwitchPoint,
)


ZERO = Decimal("0")
ONE = Decimal("1")
TONNES_TO_GRAMS = Decimal("1000000")


def calculate_candidate_break_even_price(
    report_year: int,
    baseline: FuelComponent,
    candidate: FuelComponent,
    scope: ScopeRates,
    eua_price_per_tco2e: Optional[Decimal],
) -> Optional[Decimal]:
    """Return the candidate price at which any positive blend ties B0."""
    if (baseline.price_per_tonne is None or candidate.price_per_tonne is None
            or eua_price_per_tco2e is None):
        return None
    lb = baseline.factor.lcv_mj_per_g
    lc = candidate.factor.lcv_mj_per_g
    qb = _unit_ets_tco2e(report_year, baseline, scope)
    qc = _unit_ets_tco2e(report_year, candidate, scope)
    kappa = scope.eu_ets_effective_rate
    return (lc / lb) * (baseline.price_per_tonne + eua_price_per_tco2e * kappa * qb) - eua_price_per_tco2e * kappa * qc


def calculate_eua_break_even_price(
    report_year: int,
    baseline: FuelComponent,
    candidate: FuelComponent,
    scope: ScopeRates,
) -> EuaBreakEvenResult:
    """Return a non-negative EUA price threshold and its mathematical status."""
    if baseline.price_per_tonne is None or candidate.price_per_tonne is None:
        return EuaBreakEvenResult(None, "PRICE_REQUIRED_FOR_COMPARISON")
    lb = baseline.factor.lcv_mj_per_g
    lc = candidate.factor.lcv_mj_per_g
    qb = _unit_ets_tco2e(report_year, baseline, scope)
    qc = _unit_ets_tco2e(report_year, candidate, scope)
    ratio = lc / lb
    numerator = ratio * baseline.price_per_tonne - candidate.price_per_tonne
    denominator = scope.eu_ets_effective_rate * (qc - ratio * qb)
    if numerator == ZERO and denominator == ZERO:
        return EuaBreakEvenResult(None, "ALL_PRICES_TIE")
    if denominator == ZERO:
        return EuaBreakEvenResult(None, "NO_FINITE_POINT")
    value = numerator / denominator
    if value < ZERO:
        return EuaBreakEvenResult(None, "NEGATIVE_THRESHOLD")
    return EuaBreakEvenResult(value, "FINITE_NON_NEGATIVE")


def compliance_improvement_tco2e(
    scenario: ScenarioResult,
    baseline_scenario: ScenarioResult,
) -> Optional[Decimal]:
    """Return CB(s)-CB(B0) in tonnes CO2e, preserving null applicability."""
    scenario_balance = scenario.fuel_eu.compliance_balance_t
    baseline_balance = baseline_scenario.fuel_eu.compliance_balance_t
    if scenario_balance is None or baseline_balance is None:
        return None
    return scenario_balance - baseline_balance


def _adjusted_cost(scenario: ScenarioResult, value: Optional[Decimal]) -> Optional[Decimal]:
    improvement = scenario.compliance_improvement_tco2e
    if value is None or scenario.model_cost is None or improvement is None:
        return None
    return scenario.model_cost - value * improvement


def _winner(
    lines: Sequence[tuple[Decimal, Fraction, Fraction]], value: Fraction,
) -> tuple[Decimal, Fraction, Fraction]:
    return min(lines, key=lambda line: (line[1] - value * line[2], line[0]))


def calculate_value_switch_points(
    scenarios: Sequence[ScenarioResult],
    exact_coefficients: Optional[dict[Decimal, tuple[Fraction, Fraction]]] = None,
) -> tuple[ValueSwitchPoint, ...]:
    """Return only intersections where the global lower envelope changes winner."""
    lines = [
        (scenario.ratio, *(exact_coefficients[scenario.ratio]
                          if exact_coefficients and scenario.ratio in exact_coefficients else
                          (Fraction(scenario.model_cost), Fraction(scenario.compliance_improvement_tco2e))))
        for scenario in scenarios
        if scenario.constraint_status == "FEASIBLE"
        and scenario.model_cost is not None
        and scenario.compliance_improvement_tco2e is not None
    ]
    if len(lines) < 2:
        return ()
    intersections: dict[Fraction, set[tuple[Decimal, Decimal]]] = {}
    for left, right in combinations(lines, 2):
        slope_delta = left[2] - right[2]
        cost_delta = left[1] - right[1]
        if slope_delta == ZERO:
            continue
        value = cost_delta / slope_delta
        if value < ZERO:
            continue
        intersections.setdefault(value, set()).add((left[0], right[0]))
    if not intersections:
        return ()
    ordered = sorted(intersections)
    transitions: list[ValueSwitchPoint] = []
    for index, value in enumerate(ordered):
        previous = Fraction(0) if index == 0 else ordered[index - 1]
        following = None if index + 1 == len(ordered) else ordered[index + 1]
        left_probe = (previous + value) / 2 if index else Fraction(0)
        right_probe = value + 1 if following is None else (value + following) / 2
        left_winner = _winner(lines, left_probe)[0]
        right_winner = _winner(lines, right_probe)[0]
        if left_winner == right_winner:
            continue
        # A tie at the intersection can involve more than two lines. Pick the
        # actual envelope winners on either side, then report the switch once.
        transitions.append(ValueSwitchPoint(left_winner, right_winner, decimal_ratio(value)))
    return tuple(transitions)


def exact_economic_coefficients(
    report_year: int, baseline: FuelComponent, candidate: FuelComponent,
    scope: ScopeRates, eua_price: Optional[Decimal], energy_mj: Decimal,
    ratios: Sequence[Decimal],
) -> dict[Decimal, tuple[Fraction, Fraction]]:
    """Preserve shared-model collinearity before projecting amounts to Decimal.

Rounding each scenario's cost/improvement independently can manufacture tiny
winning intervals in an exactly collinear set. Derive the lines from common
inputs; standalone comparison functions still compare supplied coefficients.
"""
    if (baseline.price_per_tonne is None or candidate.price_per_tonne is None or eua_price is None
            or report_year == 2024 or not scope.fuel_eu_scope_rate):
        return {}
    lb, lc = Fraction(baseline.factor.lcv_mj_per_g), Fraction(candidate.factor.lcv_mj_per_g)
    nb, db = exact_unit_n_d(baseline)
    nc, dc = exact_unit_n_d(candidate)
    pe, k = Fraction(eua_price), Fraction(scope.eu_ets_effective_rate)
    kb = Fraction(baseline.price_per_tonne) + pe * k * Fraction(_unit_ets_tco2e(report_year, baseline, scope))
    kc = Fraction(candidate.price_per_tonne) + pe * k * Fraction(_unit_ets_tco2e(report_year, candidate, scope))
    energy = Fraction(energy_mj)
    result = {}
    for ratio in ratios:
        x = Fraction(ratio)
        mass = energy / ((1 - x) * lb + x * lc) / 1000000
        ghgi = ((1 - x) * nb + x * nc) / ((1 - x) * db + x * dc)
        improvement = (nb / db - ghgi) * energy * Fraction(scope.fuel_eu_scope_rate) / 1000000
        result[ratio] = (mass * ((1 - x) * kb + x * kc), improvement)
    return result


def build_economics(
    *,
    report_year: int,
    baseline: FuelComponent,
    candidate: FuelComponent,
    scope: ScopeRates,
    eua_price_per_tco2e: Optional[Decimal],
    scenarios: Sequence[ScenarioResult],
    comparison_value: Optional[Decimal],
) -> tuple[EconomicsResult, tuple[ScenarioResult, ...]]:
    """Attach sensitivity values to scenarios and calculate economic summaries."""
    if comparison_value is not None and comparison_value < ZERO:
        raise ValueError("compliance_improvement_value must be non-negative")
    if not scenarios:
        raise ValueError("at least one scenario is required")
    baseline_scenario = min(scenarios, key=lambda scenario: scenario.ratio)
    enriched: list[ScenarioResult] = []
    for scenario in scenarios:
        improvement = compliance_improvement_tco2e(scenario, baseline_scenario)
        enriched.append(replace(
            scenario,
            compliance_improvement_tco2e=improvement,
            reference_adjusted_cost=_adjusted_cost(
                replace(scenario, compliance_improvement_tco2e=improvement), comparison_value,
            ),
        ))
    enriched_tuple = tuple(enriched)
    comparable = tuple(
        scenario for scenario in enriched_tuple
        if scenario.constraint_status == "FEASIBLE" and scenario.model_cost is not None
    )
    sorted_ratios = tuple(scenario.ratio for scenario in sorted(comparable, key=lambda scenario: (scenario.model_cost, scenario.ratio)))
    cost_min_ratio = sorted_ratios[0] if sorted_ratios else None
    pc = calculate_candidate_break_even_price(
        report_year, baseline, candidate, scope, eua_price_per_tco2e,
    )
    pe_result = calculate_eua_break_even_price(report_year, baseline, candidate, scope)
    pe_value = pe_result.value if eua_price_per_tco2e is not None else None
    pe_status = pe_result.status if eua_price_per_tco2e is not None else "PRICE_REQUIRED_FOR_COMPARISON"
    warnings: list[str] = []
    if not comparable or pc is None:
        warnings.append("PRICE_REQUIRED_FOR_COMPARISON")
    if comparison_value is not None and not any(
        scenario.compliance_improvement_tco2e is not None for scenario in enriched_tuple
    ):
        warnings.append("TARGET_NOT_APPLICABLE")
    status = "COMPARABLE" if comparable and pc is not None else "CALCULABLE"
    return EconomicsResult(
        comparison_status=status,
        pc_break_even=pc,
        pe_break_even=pe_value,
        pe_break_even_status=pe_status,
        comparison_value=comparison_value,
        cost_min_ratio=cost_min_ratio,
        cost_sorted_ratios=sorted_ratios,
        switch_points=calculate_value_switch_points(enriched_tuple, exact_economic_coefficients(
            report_year, baseline, candidate, scope, eua_price_per_tco2e,
            baseline_scenario.physical_energy_mj, [s.ratio for s in enriched_tuple])),
        warning_codes=tuple(dict.fromkeys(warnings)),
    ), enriched_tuple
