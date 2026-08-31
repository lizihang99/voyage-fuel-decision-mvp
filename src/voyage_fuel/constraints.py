"""Continuous blend constraint and FuelEU target calculations."""

from decimal import Decimal
from typing import Optional

from .emissions import calculate_eu_ets, _ttw_mass_eq, _fueleu_target
from .models import ConstraintResult, FuelAmount, FuelComponent, ScopeRates


ZERO = Decimal("0")
ONE = Decimal("1")
GRAMS_PER_TONNE = Decimal("1000000")


def _unit_ets_tco2e(
    year: int, component: FuelComponent, scope: ScopeRates,
) -> Decimal:
    result = calculate_eu_ets(
        year, (FuelAmount(component, ONE),), scope, None,
    )
    if scope.eu_ets_effective_rate == ZERO:
        return ZERO
    return result.euas_required / scope.eu_ets_effective_rate


def _unit_n_d(component: FuelComponent) -> tuple[Decimal, Decimal]:
    amount = FuelAmount(component, ONE)
    factor = component.factor
    n = factor.lcv_mj_per_g * factor.wt_t_g_per_mj + _ttw_mass_eq(amount)
    d = factor.lcv_mj_per_g * factor.rwd
    return n, d


def _ratio_for_budget(
    baseline_mass: Decimal, baseline_lcv: Decimal, candidate_lcv: Decimal,
    omega: Decimal, budget: Optional[Decimal],
) -> Optional[Decimal]:
    if budget is None:
        return ONE
    if omega <= ZERO:
        return ONE
    delta_100 = baseline_mass * omega / candidate_lcv
    if budget >= delta_100:
        return ONE
    denominator = baseline_mass * omega - budget * (candidate_lcv - baseline_lcv)
    if denominator <= ZERO:
        return ONE
    return budget * baseline_lcv / denominator


def _ratio_for_supply(
    baseline_mass: Decimal, baseline_lcv: Decimal, candidate_lcv: Decimal,
    supply: Optional[Decimal],
) -> Optional[Decimal]:
    if supply is None:
        return ONE
    if supply < ZERO:
        raise ValueError("candidate_supply_tonnes must be non-negative")
    baseline_energy = baseline_mass * GRAMS_PER_TONNE * baseline_lcv
    candidate_mass_100 = baseline_energy / (candidate_lcv * GRAMS_PER_TONNE)
    if supply >= candidate_mass_100:
        return ONE
    denominator = baseline_mass * baseline_lcv - supply * (candidate_lcv - baseline_lcv)
    if denominator <= ZERO:
        return ONE
    return supply * baseline_lcv / denominator


def calculate_minimum_target_ratio(
    report_year: int,
    baseline: FuelComponent,
    candidate: FuelComponent,
    fuel_eu_scope_rate: Optional[Decimal],
    x_cap: Decimal,
) -> tuple[str, Optional[Decimal], Optional[Decimal]]:
    """Return status, unconstrained minimum, and constrained minimum ratio."""
    target = _fueleu_target(report_year)
    if report_year == 2024 or fuel_eu_scope_rate is None or fuel_eu_scope_rate == ZERO or target is None:
        return "TARGET_NOT_APPLICABLE", None, None
    n_b, d_b = _unit_n_d(baseline)
    n_c, d_c = _unit_n_d(candidate)
    h_b = n_b - target * d_b
    h_c = n_c - target * d_c
    if h_b <= ZERO:
        unconstrained = ZERO
    elif h_c > ZERO:
        return "TARGET_NO_SOLUTION", None, None
    elif h_c == ZERO:
        unconstrained = ONE
    else:
        unconstrained = h_b / (h_b - h_c)
    if unconstrained > x_cap:
        return "TARGET_UNREACHABLE_UNDER_CONSTRAINTS", unconstrained, None
    return "TARGET_REACHABLE", unconstrained, unconstrained


def calculate_constraints(
    *,
    report_year: int,
    baseline_mass_tonnes: Decimal,
    baseline: FuelComponent,
    candidate: FuelComponent,
    scope: ScopeRates,
    candidate_supply_tonnes: Optional[Decimal],
    incremental_budget: Optional[Decimal],
    max_blend_ratio: Decimal,
    eua_price_per_tco2e: Optional[Decimal] = None,
    baseline_energy_mj: Optional[Decimal] = None,
) -> ConstraintResult:
    """Calculate all continuous blend bounds without enumerating ratios."""
    if baseline_mass_tonnes <= ZERO:
        raise ValueError("baseline_mass_tonnes must be positive")
    if not ZERO <= max_blend_ratio <= ONE:
        raise ValueError("max_blend_ratio must be between 0 and 1")
    if incremental_budget is not None and incremental_budget < ZERO:
        raise ValueError("incremental_budget must be non-negative")
    if candidate_supply_tonnes is not None and candidate_supply_tonnes < ZERO:
        raise ValueError("candidate_supply_tonnes must be non-negative")

    lb = baseline.factor.lcv_mj_per_g
    lc = candidate.factor.lcv_mj_per_g
    warnings: list[str] = []
    kb = kc = None
    if (baseline.price_per_tonne is None or candidate.price_per_tonne is None
            or eua_price_per_tco2e is None):
        if incremental_budget is not None:
            warnings.append("BUDGET_UNAVAILABLE_WITHOUT_PRICES")
    else:
        qb = _unit_ets_tco2e(report_year, baseline, scope)
        qc = _unit_ets_tco2e(report_year, candidate, scope)
        pe = eua_price_per_tco2e
        kb = baseline.price_per_tonne + pe * scope.eu_ets_effective_rate * qb
        kc = candidate.price_per_tonne + pe * scope.eu_ets_effective_rate * qc

    x_budget: Optional[Decimal] = None
    omega: Optional[Decimal] = None
    if kb is not None and kc is not None:
        omega = lb * kc - lc * kb
        x_budget = _ratio_for_budget(baseline_mass_tonnes, lb, lc, omega, incremental_budget)
    elif incremental_budget is None:
        x_budget = ONE

    x_supply = _ratio_for_supply(baseline_mass_tonnes, lb, lc, candidate_supply_tonnes)
    bounds = [ONE, max_blend_ratio]
    if x_budget is not None:
        bounds.append(x_budget)
    if x_supply is not None:
        bounds.append(x_supply)
    x_cap = min(bounds)

    target_status, x_target_unconstrained, x_target = calculate_minimum_target_ratio(
        report_year, baseline, candidate, scope.fuel_eu_scope_rate, x_cap,
    )
    if target_status != "TARGET_REACHABLE":
        warnings.append(target_status)
    x_target_cost = None
    x_cost_min = None
    if omega is not None:
        x_cost_min = ZERO if omega >= ZERO else x_cap
        if x_target is not None:
            x_target_cost = x_target if omega >= ZERO else x_cap

    x_max_improvement: Optional[Decimal]
    if x_target_unconstrained is None or target_status == "TARGET_NOT_APPLICABLE":
        x_max_improvement = None
    else:
        n_b, d_b = _unit_n_d(baseline)
        n_c, d_c = _unit_n_d(candidate)
        psi = n_c * d_b - n_b * d_c
        x_max_improvement = x_cap if psi < ZERO else ZERO

    return ConstraintResult(
        max_blend_ratio=max_blend_ratio,
        candidate_supply_tonnes=candidate_supply_tonnes,
        incremental_budget=incremental_budget,
        x_budget=x_budget,
        x_supply=x_supply,
        x_cap=x_cap,
        target_status=target_status,
        x_target_min_unconstrained=x_target_unconstrained,
        x_target_min=x_target,
        x_target_min_cost=x_target_cost,
        x_max_improvement=x_max_improvement,
        x_cost_min=x_cost_min,
        warning_codes=tuple(dict.fromkeys(warnings)),
    )
