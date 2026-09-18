"""Case-level orchestration over the single-voyage calculation kernel."""

from __future__ import annotations

from decimal import Decimal
import re

from .calculator import calculate_voyage
from .contracts import (
    CandidateInput,
    CandidateResult,
    DecisionCaseInput,
    DecisionCaseResult,
    Issue,
    ParsedDecisionCase,
)
from .issues import issue_from_exception
from .models import ScenarioResult, VoyageInput
from .case_comparison import (
    build_case_economics,
    build_case_scenarios,
    build_decision_summary,
    build_recommendations,
)
from .economics import exact_economic_coefficients
from .ports import calculate_scope_rates
from .provenance import FactorResolutionTrace, ResultProvenance, deduplicate_source_ids


_DOMAIN_PREFIXES = (
    "Port not found",
    "Invalid UN/LOCODE",
    "Supported reporting years",
    "Unsupported reporting year",
    "Unsupported FuelEU year",
    "Cslip required",
    "FuelEU denominator",
    "mass_tonnes",
    "baseline_mass_tonnes",
    "weighted LCV",
)
_DOMAIN_CODES = frozenset({
    "INVALID_YEAR",
    "INVALID_PORT_CODE",
    "PORT_NOT_FOUND",
    "PORT_OF_CALL_CONFIRMATION_REQUIRED",
    "INVALID_BASELINE_MASS",
    "INVALID_LCV",
    "INVALID_BLEND_RATIO",
    "MISSING_REQUIRED_FACTOR",
    "INVALID_CSLIP",
    "INVALID_RWD",
    "INVALID_EMISSION_FACTOR",
    "INVALID_BIOMASS_FRACTION",
    "RFNBO_E_EXCEEDS_LIMIT",
    "PRICE_REQUIRED_FOR_COMPARISON",
    "BUDGET_UNAVAILABLE_WITHOUT_PRICES",
    "TARGET_NOT_APPLICABLE",
    "TARGET_NO_SOLUTION",
    "TARGET_UNREACHABLE_UNDER_CONSTRAINTS",
    "ZERO_BASELINE",
    "DUPLICATE_CANDIDATE_ID",
    "INVALID_CANDIDATE_ID",
    "INVALID_CANDIDATE_CONSTRAINT",
    "INVALID_CURRENCY",
    "INVALID_EUA_PRICE",
})


def _is_domain_error(error: ValueError) -> bool:
    message = str(error).strip()
    code = message.partition(":")[0]
    return code in _DOMAIN_CODES or message.startswith(_DOMAIN_PREFIXES)


def _candidate_issue(error: ValueError, candidate: CandidateInput) -> Issue:
    return issue_from_exception(
        error,
        scope="CANDIDATE",
        field="candidate",
        candidate_id=candidate.candidate_id,
        component=candidate.component.factor.path_id,
    )


def _case_issue(error: ValueError, field: str = "case") -> Issue:
    return issue_from_exception(error, scope="CASE", field=field)


def _voyage_input(request: DecisionCaseInput, candidate: CandidateInput) -> VoyageInput:
    return VoyageInput(
        report_year=request.report_year,
        departure_port=request.departure_port,
        arrival_port=request.arrival_port,
        baseline_component=request.baseline_component,
        baseline_mass_tonnes=request.baseline_mass_tonnes,
        candidate_component=candidate.component,
        eua_price_per_tco2e=request.eua_price_per_tco2e,
        specified_blend_ratios=candidate.specified_blend_ratios,
        max_blend_ratio=candidate.max_blend_ratio,
        candidate_allows_pure_use=candidate.allows_pure_use,
        candidate_supply_tonnes=candidate.supply_tonnes,
        incremental_budget=candidate.incremental_budget,
        compliance_improvement_value=candidate.compliance_improvement_value,
    )


def calculate_baseline_scenario(request: DecisionCaseInput) -> ScenarioResult:
    """Calculate the shared B0 row once using the case baseline component."""
    baseline_candidate = CandidateInput(
        candidate_id="__baseline__",
        component=request.baseline_component,
        max_blend_ratio=Decimal("0"),
    )
    voyage = calculate_voyage(_voyage_input(request, baseline_candidate))
    return voyage.scenarios[0]


def _baseline_matches(left: ScenarioResult, right: ScenarioResult) -> bool:
    """Compare B0 quantities that must be common before case-level deduplication.

    Candidate price availability can make a single-voyage B0 fuel-cost field
    unknown even at ratio zero. That remains a candidate economic-status
    concern, while the shared physical and compliance baseline is valid.
    """
    return (
        left.ratio == right.ratio
        and left.baseline_mass_tonnes == right.baseline_mass_tonnes
        and left.candidate_mass_tonnes == right.candidate_mass_tonnes
        and left.physical_energy_mj == right.physical_energy_mj
        and (
            left.eu_ets.raw_co2_t == right.eu_ets.raw_co2_t
            and left.eu_ets.raw_ch4_t == right.eu_ets.raw_ch4_t
            and left.eu_ets.raw_n2o_t == right.eu_ets.raw_n2o_t
            and left.eu_ets.mrv_raw_co2e_t == right.eu_ets.mrv_raw_co2e_t
            and left.eu_ets.included_gases == right.eu_ets.included_gases
            and left.eu_ets.ets_co2e_pre_scope_t == right.eu_ets.ets_co2e_pre_scope_t
            and left.eu_ets.euas_required == right.eu_ets.euas_required
            and left.eu_ets.eua_cost == right.eu_ets.eua_cost
        )
        and left.fuel_eu == right.fuel_eu
    )


def _candidate_status(voyage: VoyageInput, result) -> str:
    if (
        voyage.baseline_component.price_per_tonne is not None
        and voyage.candidate_component.price_per_tonne is not None
        and voyage.eua_price_per_tco2e is not None
        and result.economics is not None
        and result.economics.comparison_status == "COMPARABLE"
    ):
        return "COMPARABLE"
    return "CALCULABLE"


def _component_trace(component) -> FactorResolutionTrace:
    """Project the immutable factor resolved at the input boundary into a trace."""
    factor = component.factor
    return FactorResolutionTrace(
        requested_path_id=factor.requested_path_id or factor.path_id,
        resolved_path_id=factor.path_id,
        resolution_reason=factor.resolution_reason or "DIRECT_RESOLUTION",
        qualification_status=factor.qualification_status or component.qualification_status.upper(),
        factor_status=factor.factor_status,
        factor=factor,
        source_ids=tuple(dict.fromkeys(e.source_id for e in factor.source_evidence)),
        eligible_biomass_fraction=component.eligible_biomass_fraction,
    )


def _result_provenance(request: DecisionCaseInput | None) -> ResultProvenance:
    """Collect only resolution-boundary facts available for this result."""
    if request is None:
        return ResultProvenance(
            departure=None,
            arrival=None,
            eu_ets_reason=None,
            fuel_eu_reason=None,
            eu_ets_geographic_rate=None,
            eu_ets_surrender_rate=None,
            fuel_eu_rate=None,
            eu_ets_effective_rate=None,
            factor_resolutions=(),
            source_ids=(),
            status="UNAVAILABLE",
        )

    factor_traces = [_component_trace(request.baseline_component)]
    factor_traces.extend(_component_trace(candidate.component) for candidate in request.candidates)
    source_ids = [source_id for trace in factor_traces for source_id in trace.source_ids]
    try:
        scope = calculate_scope_rates(request.report_year, request.departure_port, request.arrival_port)
    except ValueError:
        return ResultProvenance(
            departure=None,
            arrival=None,
            eu_ets_reason=None,
            fuel_eu_reason=None,
            eu_ets_geographic_rate=None,
            eu_ets_surrender_rate=None,
            fuel_eu_rate=None,
            eu_ets_effective_rate=None,
            factor_resolutions=tuple(factor_traces),
            source_ids=deduplicate_source_ids(source_ids),
            status="PARTIAL",
        )

    for port in (scope.departure_port, scope.arrival_port):
        if port is not None:
            source_ids.extend(port.rule_source_id.split(";"))
    return ResultProvenance(
        departure=scope.departure_port,
        arrival=scope.arrival_port,
        eu_ets_reason=scope.eu_ets_reason,
        fuel_eu_reason=scope.fuel_eu_reason,
        eu_ets_geographic_rate=scope.eu_ets_scope_rate,
        eu_ets_surrender_rate=scope.eu_ets_surrender_rate,
        fuel_eu_rate=scope.fuel_eu_scope_rate,
        eu_ets_effective_rate=scope.eu_ets_effective_rate,
        factor_resolutions=tuple(factor_traces),
        source_ids=deduplicate_source_ids(source_ids),
    )


def _invalid_candidate_results(initial_issues: tuple[Issue, ...]) -> tuple[CandidateResult, ...]:
    """Project parser-rejected candidates back into stable candidate rows."""
    indexed: list[tuple[int, Issue]] = []
    for issue in initial_issues:
        if issue.scope != "CANDIDATE":
            continue
        match = re.search(r"candidates\[(\d+)\]", issue.field)
        indexed.append((int(match.group(1)) if match else 10**9, issue))
    return tuple(
        CandidateResult(
            candidate_id=issue.candidate_id or f"candidates[{index}]",
            calculation_status="BLOCKED",
            voyage_result=None,
            issues=(issue,),
        )
        for index, issue in sorted(indexed, key=lambda item: item[0])
    )


def _issue_index(issue: Issue) -> int | None:
    match = re.search(r"candidates\[(\d+)\]", issue.field)
    return int(match.group(1)) if match else None


def _result_field_reasons(
    request: DecisionCaseInput,
    candidate_results: tuple[CandidateResult, ...],
    scenarios,
) -> dict[str, str]:
    """Explain key nullable public fields without changing calculation values."""
    reasons: dict[str, str] = {}
    candidate_inputs = {candidate.candidate_id: candidate for candidate in request.candidates}

    for row in scenarios:
        prefix = f"scenarios.{row.scenario_id}.result"
        result = row.result
        if result.fuel_cost is None:
            reasons[f"{prefix}.fuel_cost"] = "PRICE_REQUIRED_FOR_COMPARISON"
        if result.model_cost is None:
            reasons[f"{prefix}.model_cost"] = "PRICE_REQUIRED_FOR_COMPARISON"
        if result.eu_ets.eua_cost is None:
            reasons[f"{prefix}.eu_ets.eua_cost"] = "EUA_PRICE_NOT_PROVIDED"
        fuel_eu_reason = result.fuel_eu.status
        for field_name in (
            "wt_t_intensity_g_per_mj", "tt_w_intensity_g_per_mj",
            "ghgi_actual_g_per_mj", "target_g_per_mj", "compliance_balance_g",
            "compliance_balance_t", "indicative_penalty_eur",
        ):
            if getattr(result.fuel_eu, field_name) is None:
                reasons[f"{prefix}.fuel_eu.{field_name}"] = fuel_eu_reason
        if result.compliance_improvement_tco2e is None:
            reasons[f"{prefix}.compliance_improvement_tco2e"] = fuel_eu_reason
        if result.reference_adjusted_cost is None:
            candidate_input = candidate_inputs.get(row.candidate_id) if row.candidate_id else None
            if candidate_input is None:
                reference_reason = "NOT_DEFINED_AT_CASE_LEVEL"
            elif candidate_input.compliance_improvement_value is None:
                reference_reason = "COMPLIANCE_VALUE_NOT_PROVIDED"
            else:
                reference_reason = fuel_eu_reason
            reasons[f"{prefix}.reference_adjusted_cost"] = reference_reason
        for metric_name, delta in row.deltas.items():
            if delta.percent_delta is None and delta.reason_code:
                reasons[f"scenarios.{row.scenario_id}.deltas.{metric_name}.percent_delta"] = delta.reason_code

    for candidate in candidate_results:
        voyage = candidate.voyage_result
        prefix = f"candidate_results.{candidate.candidate_id}"
        if voyage is None:
            reasons[f"{prefix}.voyage_result"] = "BLOCKED"
            continue
        economics = voyage.economics
        if economics is not None:
            if economics.pc_break_even is None:
                reasons[f"{prefix}.economics.pc_break_even"] = (
                    economics.warning_codes[0] if economics.warning_codes
                    else "PRICE_REQUIRED_FOR_COMPARISON"
                )
            if economics.pe_break_even is None:
                reasons[f"{prefix}.economics.pe_break_even"] = economics.pe_break_even_status
            if economics.comparison_value is None:
                reasons[f"{prefix}.economics.comparison_value"] = "NOT_PROVIDED"
        constraints = voyage.constraints
        candidate_input = candidate_inputs.get(candidate.candidate_id)
        if constraints is None or candidate_input is None:
            continue
        if constraints.candidate_supply_tonnes is None:
            reasons[f"{prefix}.constraints.candidate_supply_tonnes"] = "NOT_PROVIDED"
        if constraints.incremental_budget is None:
            reasons[f"{prefix}.constraints.incremental_budget"] = "NOT_PROVIDED"
        if constraints.x_supply is None:
            reasons[f"{prefix}.constraints.x_supply"] = "NOT_PROVIDED"
        if constraints.x_budget is None:
            reasons[f"{prefix}.constraints.x_budget"] = (
                "NOT_PROVIDED" if candidate_input.incremental_budget is None
                else "BUDGET_UNAVAILABLE_WITHOUT_PRICES"
            )
        for field_name in ("x_target_min_unconstrained", "x_target_min", "x_max_improvement"):
            if getattr(constraints, field_name) is None:
                reasons[f"{prefix}.constraints.{field_name}"] = constraints.target_status
        if constraints.x_target_min_cost is None:
            reasons[f"{prefix}.constraints.x_target_min_cost"] = (
                constraints.target_status
                if constraints.target_status != "TARGET_REACHABLE"
                else "PRICE_REQUIRED_FOR_COMPARISON"
            )
        if constraints.x_cost_min is None:
            reasons[f"{prefix}.constraints.x_cost_min"] = "PRICE_REQUIRED_FOR_COMPARISON"
    return reasons


def calculate_decision_case(
    request: DecisionCaseInput | None,
    initial_issues: tuple[Issue, ...] = (),
) -> DecisionCaseResult:
    """Calculate all valid candidates while isolating candidate-local failures."""
    if request is None:
        return DecisionCaseResult(
            report_year=0,
            departure_port="",
            arrival_port="",
            currency="",
            baseline_scenario=None,
            candidate_results=_invalid_candidate_results(initial_issues),
            scenarios=(),
            recommendations=(),
            issues=tuple(initial_issues),
            provenance=_result_provenance(None),
        )
    case_issues = tuple(issue for issue in initial_issues if issue.scope == "CASE")
    candidate_issues = tuple(issue for issue in initial_issues if issue.scope == "CANDIDATE")
    try:
        baseline = calculate_baseline_scenario(request)
    except ValueError as error:
        if not _is_domain_error(error):
            raise
        issue = _case_issue(error, field="departurePort" if "Port" in str(error) else "case")
        return DecisionCaseResult(
            report_year=request.report_year,
            departure_port=request.departure_port,
            arrival_port=request.arrival_port,
            currency=request.currency,
            baseline_scenario=None,
            candidate_results=(),
            scenarios=(),
            recommendations=(),
            issues=(*case_issues, issue, *candidate_issues),
            provenance=_result_provenance(request),
        )

    results: list[CandidateResult] = []
    case_issue_list = list(case_issues)
    for candidate in request.candidates:
        voyage_request = _voyage_input(request, candidate)
        try:
            voyage_result = calculate_voyage(voyage_request)
        except ValueError as error:
            if not _is_domain_error(error):
                raise
            results.append(
                CandidateResult(
                    candidate_id=candidate.candidate_id,
                    calculation_status="BLOCKED",
                    voyage_result=None,
                    issues=(_candidate_issue(error, candidate),),
                )
            )
            continue
        if not voyage_result.scenarios or not _baseline_matches(voyage_result.scenarios[0], baseline):
            issue = Issue(
                code="INCONSISTENT_BASELINE",
                scope="CASE",
                field="baseline",
                blocking=True,
                message="Candidate B0 does not match the shared case baseline.",
                candidate_id=candidate.candidate_id,
                component=candidate.component.factor.path_id,
            )
            return DecisionCaseResult(
                report_year=request.report_year,
                departure_port=request.departure_port,
                arrival_port=request.arrival_port,
                currency=request.currency,
                baseline_scenario=None,
                candidate_results=(),
                scenarios=(),
                recommendations=(),
                issues=(*case_issue_list, issue, *candidate_issues),
                provenance=_result_provenance(request),
            )
        results.append(
            CandidateResult(
                candidate_id=candidate.candidate_id,
                calculation_status=_candidate_status(voyage_request, voyage_result),
                voyage_result=voyage_result,
                issues=(),
            )
        )

    projected_invalid = _invalid_candidate_results(candidate_issues)
    if projected_invalid:
        invalid_indexes = {
            index for index in (_issue_index(issue) for issue in candidate_issues)
            if index is not None
        }
        if invalid_indexes:
            slots = iter(index for index in range(len(results) + len(projected_invalid)) if index not in invalid_indexes)
            ordered: list[CandidateResult | None] = [None] * (len(results) + len(projected_invalid))
            for item in projected_invalid:
                index = _issue_index(item.issues[0])
                if index is not None and index < len(ordered):
                    ordered[index] = item
            for item in results:
                ordered[next(slots)] = item
            results = [item for item in ordered if item is not None]
        else:
            results.extend(projected_invalid)
    candidate_results = tuple(results)
    scenarios = build_case_scenarios(baseline, candidate_results)
    coefficients = {}
    candidate_inputs = {c.candidate_id: c for c in request.candidates}
    for result in candidate_results:
        if result.voyage_result is None:
            continue
        voyage = result.voyage_result
        candidate_input = candidate_inputs[result.candidate_id]
        local = exact_economic_coefficients(
            request.report_year, request.baseline_component, candidate_input.component,
            voyage.scope_rates, request.eua_price_per_tco2e, voyage.baseline_energy_mj,
            [s.ratio for s in voyage.scenarios])
        for ratio, pair in local.items():
            coefficients["B0" if ratio == 0 else candidate_input.scenario_id(ratio)] = pair
    recommendations = (
        build_recommendations(scenarios, candidate_results, coefficients)
        if candidate_results else ()
    )
    economics = build_case_economics(scenarios, coefficients)
    decision_summary = build_decision_summary(scenarios, economics) if candidate_results else None
    provenance = _result_provenance(request)
    return DecisionCaseResult(
        report_year=request.report_year,
        departure_port=request.departure_port,
        arrival_port=request.arrival_port,
        currency=request.currency,
        baseline_scenario=baseline,
        candidate_results=candidate_results,
        scenarios=scenarios,
        recommendations=recommendations,
        issues=(*case_issue_list, *candidate_issues),
        provenance=provenance,
        economics=economics,
        decision_summary=decision_summary,
        field_reasons=_result_field_reasons(request, candidate_results, scenarios),
    )


def calculate_parsed_decision_case(parsed: ParsedDecisionCase) -> DecisionCaseResult:
    """Calculate a parsed case, retaining parser issues in the result."""
    if parsed.request is None:
        case_issue = next((issue for issue in parsed.issues if issue.scope == "CASE"), None)
        return DecisionCaseResult(
            report_year=0,
            departure_port="",
            arrival_port="",
            currency="",
            baseline_scenario=None,
            candidate_results=_invalid_candidate_results(parsed.issues),
            scenarios=(),
            recommendations=(),
            issues=parsed.issues if case_issue is not None else tuple(parsed.issues),
            provenance=_result_provenance(None),
        )
    return calculate_decision_case(parsed.request, initial_issues=parsed.issues)
