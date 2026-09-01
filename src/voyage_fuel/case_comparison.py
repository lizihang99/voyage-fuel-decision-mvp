"""Pure cross-candidate projections over calculated voyage results."""

from __future__ import annotations

from decimal import Decimal
from .contracts import CaseScenario, CandidateResult, ConditionalRecommendation, MetricDelta
from .models import ScenarioResult


HUNDRED = Decimal("100")


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
            calculation_status="CALCULABLE",
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
            if row.candidate_id is not None
            and row.calculation_status == "COMPARABLE"
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
) -> tuple[ConditionalRecommendation, ...]:
    """Build conditional result records from existing constraints and economics."""
    recommendations: list[ConditionalRecommendation] = []
    ranked = tuple(row for row in scenarios if row.current_model_cost_rank is not None)
    incomplete_economics = any(
        candidate.voyage_result is not None and candidate.calculation_status != "COMPARABLE"
        for candidate in candidates
    )
    if ranked and not incomplete_economics:
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

        economics = voyage.economics
        if economics is None:
            continue
        for index, point in enumerate(economics.switch_points, start=1):
            from_row = _scenario_for_ratio(scenarios, candidate.candidate_id, point.from_ratio)
            to_row = _scenario_for_ratio(scenarios, candidate.candidate_id, point.to_ratio)
            if from_row is None or to_row is None:
                continue
            recommendations.append(ConditionalRecommendation(
                recommendation_id=f"REFERENCE_ADJUSTED_COST_SWITCH:{candidate.candidate_id}:{index}",
                condition="REFERENCE_ADJUSTED_COST_SENSITIVITY",
                scenario_id=None,
                reason="LOWER_ENVELOPE_SWITCH",
                assumptions=("EXECUTION_CONDITIONS_PENDING", "REFERENCE_VALUE_SENSITIVITY"),
                status="CONDITIONAL",
                from_scenario_id=from_row.scenario_id,
                to_scenario_id=to_row.scenario_id,
                from_candidate_id=from_row.candidate_id,
                to_candidate_id=to_row.candidate_id,
                value_star=point.value_star,
            ))
    return tuple(recommendations)
