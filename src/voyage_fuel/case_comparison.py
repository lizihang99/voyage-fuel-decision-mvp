"""Pure cross-candidate projections over calculated voyage results."""

from __future__ import annotations

from decimal import Decimal
from itertools import combinations
from fractions import Fraction
from .numerics import decimal_ratio

from .contracts import (
    CaseEconomicsResult,
    CaseScenario,
    CaseValueSwitchPoint,
    CandidateResult,
    ConditionalRecommendation,
    DecisionSummary,
    MetricDelta,
)
from .models import ScenarioResult


HUNDRED = Decimal("100")
ZERO = Decimal("0")
ONE = Decimal("1")


def metric_delta(value: Decimal | None, baseline: Decimal | None) -> MetricDelta:
    """Project an absolute value into an unrounded change relative to B0."""
    if value is None or baseline is None:
        return MetricDelta(absolute=value, delta=None, percent_delta=None)
    delta = value - baseline
    if baseline == Decimal("0"):
        return MetricDelta(value, delta, None, "ZERO_BASELINE")
    return MetricDelta(value, delta, delta / abs(baseline) * HUNDRED)


def _metric_values(scenario: ScenarioResult) -> dict[str, Decimal | None]:
    ets = scenario.eu_ets
    fuel_eu = scenario.fuel_eu
    return {
        "ratio": scenario.ratio,
        "baseline_mass_tonnes": scenario.baseline_mass_tonnes,
        "candidate_mass_tonnes": scenario.candidate_mass_tonnes,
        "physical_energy_mj": scenario.physical_energy_mj,
        "fuel_cost": scenario.fuel_cost,
        "ets_raw_co2_t": ets.raw_co2_t,
        "ets_raw_ch4_t": ets.raw_ch4_t,
        "ets_raw_n2o_t": ets.raw_n2o_t,
        "ets_mrv_raw_co2e_t": ets.mrv_raw_co2e_t,
        "ets_co2e_pre_scope_t": ets.ets_co2e_pre_scope_t,
        "euas_required": ets.euas_required,
        "eua_cost": ets.eua_cost,
        "model_cost": scenario.model_cost,
        "fueleu_scoped_energy_mj": fuel_eu.scoped_energy_mj,
        "fueleu_denominator_rwd_mj": fuel_eu.denominator_rwd_mj,
        "fueleu_wtt_intensity_g_per_mj": fuel_eu.wt_t_intensity_g_per_mj,
        "fueleu_ttw_intensity_g_per_mj": fuel_eu.tt_w_intensity_g_per_mj,
        "fueleu_ghgi_actual_g_per_mj": fuel_eu.ghgi_actual_g_per_mj,
        "fueleu_target_g_per_mj": fuel_eu.target_g_per_mj,
        "fueleu_compliance_balance_g": fuel_eu.compliance_balance_g,
        "fueleu_compliance_balance_t": fuel_eu.compliance_balance_t,
        "fueleu_indicative_penalty_eur": fuel_eu.indicative_penalty_eur,
        "compliance_improvement_tco2e": scenario.compliance_improvement_tco2e,
        "reference_adjusted_cost": scenario.reference_adjusted_cost,
    }


def _scenario_id(candidate_id: str, ratio: Decimal) -> str:
    return f"{candidate_id}@{format(ratio.normalize(), 'f')}"


def build_case_scenarios(
    baseline: ScenarioResult,
    candidates: tuple[CandidateResult, ...],
) -> tuple[CaseScenario, ...]:
    """Deduplicate B0 and attach deltas without invoking any calculation kernel."""
    baseline_values = _metric_values(baseline)
    rows: list[CaseScenario] = [
        CaseScenario(
            scenario_id="B0",
            candidate_id=None,
            calculation_status=("COMPARABLE" if baseline.model_cost is not None else "CALCULABLE"),
            result=baseline,
            deltas={key: metric_delta(value, value) for key, value in baseline_values.items()},
        )
    ]
    for candidate in candidates:
        if candidate.voyage_result is None:
            continue
        for scenario in candidate.voyage_result.scenarios:
            if scenario.ratio == Decimal("0"):
                continue
            values = _metric_values(scenario)
            rows.append(CaseScenario(
                scenario_id=_scenario_id(candidate.candidate_id, scenario.ratio),
                candidate_id=candidate.candidate_id,
                calculation_status=candidate.calculation_status,
                result=scenario,
                deltas={
                    key: metric_delta(value, baseline_values[key])
                    for key, value in values.items()
                },
            ))

    eligible = sorted(
        (
            row for row in rows
            if row.calculation_status == "COMPARABLE"
            and row.result.constraint_status == "FEASIBLE"
            and row.result.model_cost is not None
        ),
        key=lambda row: (row.result.model_cost, row.scenario_id),
    )
    ranks = {row.scenario_id: index for index, row in enumerate(eligible, start=1)}
    return tuple(
        CaseScenario(
            scenario_id=row.scenario_id,
            candidate_id=row.candidate_id,
            calculation_status=row.calculation_status,
            result=row.result,
            deltas=row.deltas,
            current_model_cost_rank=ranks.get(row.scenario_id),
        )
        for row in rows
    )


def _case_adjusted_cost(row: CaseScenario, value: Decimal) -> Decimal:
    improvement = row.result.compliance_improvement_tco2e or ZERO
    return row.result.model_cost - value * improvement  # type: ignore[operator]


def calculate_case_value_switch_points(
    scenarios: tuple[CaseScenario, ...],
    exact_coefficients: dict[str, tuple[Fraction, Fraction]] | None = None,
) -> tuple[CaseValueSwitchPoint, ...]:
    """Return only lower-envelope switches across all case scenarios."""
    eligible = tuple(
        row for row in scenarios
        if row.result.constraint_status == "FEASIBLE"
        and row.result.model_cost is not None
        and row.result.compliance_improvement_tco2e is not None
    )
    if len(eligible) < 2:
        return ()
    def coefficients(row):
        if exact_coefficients and row.scenario_id in exact_coefficients:
            return exact_coefficients[row.scenario_id]
        return Fraction(row.result.model_cost), Fraction(row.result.compliance_improvement_tco2e)

    intersections: set[Fraction] = set()
    for left, right in combinations(eligible, 2):
        left_cost, left_improvement = coefficients(left)
        right_cost, right_improvement = coefficients(right)
        slope_delta = left_improvement - right_improvement
        cost_delta = left_cost - right_cost
        if slope_delta == ZERO:
            continue
        value = cost_delta / slope_delta
        if value >= ZERO:
            intersections.add(value)
    if not intersections:
        return ()

    ordered = sorted(intersections)
    transitions: list[CaseValueSwitchPoint] = []

    def winner(value: Fraction) -> CaseScenario:
        return min(eligible, key=lambda row: (
            coefficients(row)[0] - value * coefficients(row)[1],
            row.scenario_id))

    for index, value in enumerate(ordered):
        previous = Fraction(0) if index == 0 else ordered[index - 1]
        following = None if index + 1 == len(ordered) else ordered[index + 1]
        left_probe = (previous + value) / 2 if index else Fraction(0)
        right_probe = value + 1 if following is None else (value + following) / 2
        left_winner = winner(left_probe)
        right_winner = winner(right_probe)
        if left_winner.scenario_id == right_winner.scenario_id:
            continue
        transitions.append(CaseValueSwitchPoint(
            from_scenario_id=left_winner.scenario_id,
            to_scenario_id=right_winner.scenario_id,
            from_candidate_id=left_winner.candidate_id,
            to_candidate_id=right_winner.candidate_id,
            value_star=decimal_ratio(value),
        ))
    return tuple(transitions)


def build_case_economics(
    scenarios: tuple[CaseScenario, ...],
    exact_coefficients: dict[str, tuple[Fraction, Fraction]] | None = None,
) -> CaseEconomicsResult:
    """Summarize cross-candidate winners without recalculating scenarios."""
    priced = tuple(
        row for row in scenarios
        if row.result.constraint_status == "FEASIBLE" and row.result.model_cost is not None
    )
    cost_min = min(priced, key=lambda row: (row.result.model_cost, row.scenario_id)) if priced else None
    target_candidates = tuple(
        row for row in priced
        if row.result.fuel_eu.target_g_per_mj is not None
        and row.result.fuel_eu.compliance_balance_g is not None
        and row.result.fuel_eu.compliance_balance_g >= ZERO
    )
    target_min = min(target_candidates, key=lambda row: (row.result.model_cost, row.scenario_id)) if target_candidates else None
    improvement_candidates = tuple(
        row for row in scenarios
        if row.result.constraint_status == "FEASIBLE"
        and row.result.compliance_improvement_tco2e is not None
    )
    max_improvement = max(
        improvement_candidates,
        key=lambda row: (row.result.compliance_improvement_tco2e, row.scenario_id),
    ) if improvement_candidates else None
    return CaseEconomicsResult(
        comparison_status="COMPARABLE" if priced else "CALCULABLE",
        cost_min_scenario_id=cost_min.scenario_id if cost_min else None,
        target_min_cost_scenario_id=target_min.scenario_id if target_min else None,
        max_improvement_scenario_id=max_improvement.scenario_id if max_improvement else None,
        switch_points=calculate_case_value_switch_points(scenarios, exact_coefficients),
    )


def build_decision_summary(
    scenarios: tuple[CaseScenario, ...],
    economics: CaseEconomicsResult | None,
) -> DecisionSummary | None:
    """Project business metrics from already-calculated case results."""
    if not scenarios or economics is None:
        return None
    business_metrics = (
        "fuel_cost",
        "eua_cost",
        "model_cost",
        "fueleu_ghgi_actual_g_per_mj",
        "fueleu_compliance_balance_t",
        "fueleu_indicative_penalty_eur",
    )
    return DecisionSummary(
        baseline_scenario_id="B0",
        cost_min_scenario_id=economics.cost_min_scenario_id,
        target_min_cost_scenario_id=economics.target_min_cost_scenario_id,
        max_improvement_scenario_id=economics.max_improvement_scenario_id,
        scenario_deltas={
            scenario.scenario_id: {
                metric: scenario.deltas[metric]
                for metric in business_metrics
                if metric in scenario.deltas
            }
            for scenario in scenarios
        },
    )


def _scenario_for_ratio(
    scenarios: tuple[CaseScenario, ...], candidate_id: str, ratio: Decimal | None,
) -> CaseScenario | None:
    if ratio is None:
        return None
    if ratio == Decimal("0"):
        return next((row for row in scenarios if row.scenario_id == "B0"), None)
    return next(
        (row for row in scenarios if row.candidate_id == candidate_id and row.result.ratio == ratio),
        None,
    )


def _unavailable(
    recommendation_id: str, condition: str, reason: str, *assumptions: str,
) -> ConditionalRecommendation:
    return ConditionalRecommendation(
        recommendation_id=recommendation_id,
        condition=condition,
        scenario_id=None,
        reason=reason,
        assumptions=tuple(dict.fromkeys(assumptions)),
        status="UNAVAILABLE",
    )


def _candidate_assumptions(candidate: CandidateResult) -> tuple[str, ...]:
    return ("EXECUTION_CONDITIONS_PENDING", candidate.calculation_status)


def _candidate_recommendation(
    recommendation_id: str,
    condition: str,
    candidate: CandidateResult,
    scenarios: tuple[CaseScenario, ...],
    ratio: Decimal | None,
    target_status: str,
) -> ConditionalRecommendation:
    if candidate.voyage_result is None:
        return _unavailable(recommendation_id, condition, "CANDIDATE_BLOCKED", "CANDIDATE_BLOCKED")
    if target_status != "TARGET_REACHABLE":
        assumptions = [target_status, *_candidate_assumptions(candidate)]
        if candidate.calculation_status != "COMPARABLE":
            assumptions.insert(1, "PRICE_REQUIRED_FOR_COMPARISON")
        return _unavailable(recommendation_id, condition, target_status, *assumptions)
    if candidate.calculation_status != "COMPARABLE":
        return _unavailable(
            recommendation_id, condition, "PRICE_REQUIRED_FOR_COMPARISON",
            "PRICE_REQUIRED_FOR_COMPARISON", *_candidate_assumptions(candidate),
        )
    scenario = _scenario_for_ratio(scenarios, candidate.candidate_id, ratio)
    if scenario is None or scenario.result.constraint_status != "FEASIBLE":
        return _unavailable(recommendation_id, condition, "SCENARIO_UNAVAILABLE", *_candidate_assumptions(candidate))
    balance = scenario.result.fuel_eu.compliance_balance_g
    if balance is None or balance < ZERO:
        return _unavailable(recommendation_id, condition, "TARGET_NOT_SATISFIED", *_candidate_assumptions(candidate))
    return ConditionalRecommendation(
        recommendation_id=recommendation_id,
        condition=condition,
        scenario_id=scenario.scenario_id,
        reason="CONSTRAINT_RESULT",
        assumptions=_candidate_assumptions(candidate),
        status="CONDITIONAL",
    )


def _maximum_compliance_improvement_recommendation(
    candidate: CandidateResult,
    scenarios: tuple[CaseScenario, ...],
    ratio: Decimal | None,
    target_status: str,
) -> ConditionalRecommendation:
    recommendation_id = f"MAX_COMPLIANCE_IMPROVEMENT:{candidate.candidate_id}"
    condition = "FUELEU_MAX_COMPLIANCE_IMPROVEMENT"
    if candidate.voyage_result is None:
        return _unavailable(recommendation_id, condition, "CANDIDATE_BLOCKED", "CANDIDATE_BLOCKED")
    scenario = _scenario_for_ratio(scenarios, candidate.candidate_id, ratio)
    assumptions = (*_candidate_assumptions(candidate), target_status)
    if scenario is None or scenario.result.constraint_status != "FEASIBLE":
        return _unavailable(recommendation_id, condition, "SCENARIO_UNAVAILABLE", *assumptions)
    return ConditionalRecommendation(
        recommendation_id=recommendation_id,
        condition=condition,
        scenario_id=scenario.scenario_id,
        reason="CONSTRAINT_RESULT",
        assumptions=(*assumptions, scenario.result.constraint_status),
        status="CONDITIONAL",
    )


def build_recommendations(
    scenarios: tuple[CaseScenario, ...],
    candidates: tuple[CandidateResult, ...],
    exact_coefficients: dict[str, tuple[Fraction, Fraction]] | None = None,
) -> tuple[ConditionalRecommendation, ...]:
    """Build conditional result records from existing constraints and economics."""
    recommendations: list[ConditionalRecommendation] = []
    ranked = tuple(row for row in scenarios if row.current_model_cost_rank is not None)
    if ranked:
        winner = min(ranked, key=lambda row: row.current_model_cost_rank or 0)
        recommendations.append(ConditionalRecommendation(
            recommendation_id="CURRENT_MODEL_COST_MIN",
            condition="CURRENT_MODEL_COST",
            scenario_id=winner.scenario_id,
            reason="MODEL_COST_MINIMUM",
            assumptions=("EXECUTION_CONDITIONS_PENDING", "FEASIBLE", "COMPARABLE"),
            status="CONDITIONAL",
        ))
    else:
        recommendations.append(_unavailable(
            "CURRENT_MODEL_COST_MIN", "CURRENT_MODEL_COST", "PRICE_REQUIRED_FOR_COMPARISON",
            "PRICE_REQUIRED_FOR_COMPARISON",
        ))

    for candidate in candidates:
        voyage = candidate.voyage_result
        if voyage is None or voyage.constraints is None:
            recommendations.extend((
                _unavailable(f"TARGET_MIN_COST:{candidate.candidate_id}", "FUELEU_TARGET", "CANDIDATE_BLOCKED", "CANDIDATE_BLOCKED"),
                _unavailable(f"MAX_COMPLIANCE_IMPROVEMENT:{candidate.candidate_id}", "FUELEU_COMPLIANCE_IMPROVEMENT", "CANDIDATE_BLOCKED", "CANDIDATE_BLOCKED"),
            ))
            continue
        constraints = voyage.constraints
        recommendations.append(_candidate_recommendation(
            f"TARGET_MIN_COST:{candidate.candidate_id}", "FUELEU_TARGET_MINIMUM_COST", candidate,
            scenarios, constraints.x_target_min_cost, constraints.target_status,
        ))
        recommendations.append(_maximum_compliance_improvement_recommendation(
            candidate, scenarios, constraints.x_max_improvement, constraints.target_status,
        ))

    switches = calculate_case_value_switch_points(scenarios, exact_coefficients)
    for index, point in enumerate(switches, start=1):
        prefix = point.to_candidate_id or point.from_candidate_id or "B0"
        recommendations.append(ConditionalRecommendation(
            recommendation_id=f"REFERENCE_ADJUSTED_COST_SWITCH:{prefix}:{index}",
            condition="REFERENCE_ADJUSTED_COST_SENSITIVITY",
            scenario_id=None,
            reason="LOWER_ENVELOPE_SWITCH",
            assumptions=("EXECUTION_CONDITIONS_PENDING", "REFERENCE_VALUE_SENSITIVITY"),
            status="CONDITIONAL",
            from_scenario_id=point.from_scenario_id,
            to_scenario_id=point.to_scenario_id,
            from_candidate_id=point.from_candidate_id,
            to_candidate_id=point.to_candidate_id,
            value_star=point.value_star,
        ))
    return tuple(recommendations)
