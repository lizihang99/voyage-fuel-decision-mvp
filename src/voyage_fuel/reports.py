"""Deterministic CSV export for raw voyage calculation results."""

import csv
import io
from html import escape
from decimal import Decimal
from pathlib import Path
from typing import Any

from .contracts import CaseScenario, DecisionCaseResult
from .formatting import DisplayConfig, format_for_display
from .models import ScenarioResult, VoyageResult


CSV_COLUMNS = (
    "record_type",
    "ratio",
    "baseline_mass_tonnes",
    "candidate_mass_tonnes",
    "physical_energy_mj",
    "fuel_cost",
    "model_cost",
    "execution_status",
    "constraint_status",
    "ets_raw_co2_t",
    "ets_raw_ch4_t",
    "ets_raw_n2o_t",
    "ets_co2e_pre_scope_t",
    "euas_required",
    "eua_cost",
    "included_gases",
    "fuel_eu_status",
    "scoped_energy_mj",
    "ghgi_actual_g_per_mj",
    "target_g_per_mj",
    "compliance_balance_t",
    "indicative_penalty_eur",
    "compliance_improvement_tco2e",
    "reference_adjusted_cost",
    "max_blend_ratio",
    "candidate_supply_tonnes",
    "incremental_budget",
    "x_budget",
    "x_supply",
    "x_cap",
    "target_status",
    "x_target_min_unconstrained",
    "x_target_min",
    "x_target_min_cost",
    "x_max_improvement",
    "x_cost_min",
    "comparison_status",
    "pc_break_even",
    "pe_break_even",
    "pe_break_even_status",
    "comparison_value",
    "cost_min_ratio",
    "cost_sorted_ratios",
    "warning_codes",
    "from_ratio",
    "to_ratio",
    "value_star",
    "baseline_path_id",
    "candidate_path_id",
    "baseline_factor_status",
    "candidate_factor_status",
    "baseline_qualification_status",
    "candidate_qualification_status",
    "baseline_evidence_ids",
    "candidate_evidence_ids",
)


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def _display(value: Any, places: int = 6) -> str:
    if value is None:
        return "-"
    if isinstance(value, Decimal):
        return f"{value:.{places}f}"
    return str(value)


def _base_row(record_type: str) -> dict[str, str]:
    return {column: "" for column in CSV_COLUMNS} | {"record_type": record_type}


def _scenario_row(scenario: ScenarioResult) -> dict[str, str]:
    row = _base_row("scenario")
    row.update({
        "ratio": _text(scenario.ratio),
        "baseline_mass_tonnes": _text(scenario.baseline_mass_tonnes),
        "candidate_mass_tonnes": _text(scenario.candidate_mass_tonnes),
        "physical_energy_mj": _text(scenario.physical_energy_mj),
        "fuel_cost": _text(scenario.fuel_cost),
        "model_cost": _text(scenario.model_cost),
        "execution_status": scenario.execution_status,
        "constraint_status": scenario.constraint_status,
        "ets_raw_co2_t": _text(scenario.eu_ets.raw_co2_t),
        "ets_raw_ch4_t": _text(scenario.eu_ets.raw_ch4_t),
        "ets_raw_n2o_t": _text(scenario.eu_ets.raw_n2o_t),
        "ets_co2e_pre_scope_t": _text(scenario.eu_ets.ets_co2e_pre_scope_t),
        "euas_required": _text(scenario.eu_ets.euas_required),
        "eua_cost": _text(scenario.eu_ets.eua_cost),
        "included_gases": ";".join(scenario.eu_ets.included_gases),
        "fuel_eu_status": scenario.fuel_eu.status,
        "scoped_energy_mj": _text(scenario.fuel_eu.scoped_energy_mj),
        "ghgi_actual_g_per_mj": _text(scenario.fuel_eu.ghgi_actual_g_per_mj),
        "target_g_per_mj": _text(scenario.fuel_eu.target_g_per_mj),
        "compliance_balance_t": _text(scenario.fuel_eu.compliance_balance_t),
        "indicative_penalty_eur": _text(scenario.fuel_eu.indicative_penalty_eur),
        "compliance_improvement_tco2e": _text(scenario.compliance_improvement_tco2e),
        "reference_adjusted_cost": _text(scenario.reference_adjusted_cost),
    })
    return row


def voyage_result_to_csv(result: VoyageResult) -> str:
    """Serialize a result using fixed columns and lossless Decimal text."""
    rows = [_scenario_row(scenario) for scenario in result.scenarios]
    if result.baseline_factor is not None or result.candidate_factor is not None:
        for row in rows:
            row.update({
                "baseline_path_id": _text(result.baseline_factor.path_id if result.baseline_factor else None),
                "candidate_path_id": _text(result.candidate_factor.path_id if result.candidate_factor else None),
                "baseline_factor_status": _text(result.baseline_factor.factor_status if result.baseline_factor else None),
                "candidate_factor_status": _text(result.candidate_factor.factor_status if result.candidate_factor else None),
                "baseline_qualification_status": _text(result.baseline_qualification_status),
                "candidate_qualification_status": _text(result.candidate_qualification_status),
                "baseline_evidence_ids": ";".join(e.source_id for e in (result.baseline_factor.source_evidence if result.baseline_factor else ())),
                "candidate_evidence_ids": ";".join(e.source_id for e in (result.candidate_factor.source_evidence if result.candidate_factor else ())),
            })
    if result.constraints is not None:
        constraints = result.constraints
        row = _base_row("constraints")
        row.update({
            "max_blend_ratio": _text(constraints.max_blend_ratio),
            "candidate_supply_tonnes": _text(constraints.candidate_supply_tonnes),
            "incremental_budget": _text(constraints.incremental_budget),
            "x_budget": _text(constraints.x_budget),
            "x_supply": _text(constraints.x_supply),
            "x_cap": _text(constraints.x_cap),
            "target_status": constraints.target_status,
            "x_target_min_unconstrained": _text(constraints.x_target_min_unconstrained),
            "x_target_min": _text(constraints.x_target_min),
            "x_target_min_cost": _text(constraints.x_target_min_cost),
            "x_max_improvement": _text(constraints.x_max_improvement),
            "x_cost_min": _text(constraints.x_cost_min),
            "warning_codes": ";".join(constraints.warning_codes),
        })
        rows.append(row)
    if result.economics is not None:
        economics = result.economics
        row = _base_row("economics")
        row.update({
            "comparison_status": economics.comparison_status,
            "pc_break_even": _text(economics.pc_break_even),
            "pe_break_even": _text(economics.pe_break_even),
            "pe_break_even_status": economics.pe_break_even_status,
            "comparison_value": _text(economics.comparison_value),
            "cost_min_ratio": _text(economics.cost_min_ratio),
            "cost_sorted_ratios": ";".join(_text(ratio) for ratio in economics.cost_sorted_ratios),
            "warning_codes": ";".join(economics.warning_codes),
        })
        rows.append(row)
        for point in economics.switch_points:
            switch = _base_row("switch_point")
            switch.update({
                "from_ratio": _text(point.from_ratio),
                "to_ratio": _text(point.to_ratio),
                "value_star": _text(point.value_star),
            })
            rows.append(switch)

    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def write_voyage_csv(result: VoyageResult, path: str | Path) -> Path:
    """Write the deterministic CSV export and return its resolved path."""
    target = Path(path)
    target.write_text(voyage_result_to_csv(result), encoding="utf-8", newline="")
    return target


# Case export intentionally has its own schema so the legacy voyage schema above
# remains byte-compatible for existing consumers.
CASE_CSV_COLUMNS = (
    "record_type", "report_year", "departure_port", "arrival_port", "currency",
    "candidate_id", "scenario_id", "calculation_status", "execution_status",
    "constraint_status", "rank", "recommendation_id", "condition", "recommendation_status",
    "reason", "assumptions", "from_scenario_id", "to_scenario_id", "from_candidate_id",
    "to_candidate_id", "metric_name", "absolute", "delta", "percent_delta", "reason_code",
    "unit", "value_currency", "penalty_currency", "source_ids", "calculation_spec_version",
    "fuel_factor_version", "port_rule_version", "port_role", "port_name", "unlocode",
    "eu_ets_identity", "fuel_eu_identity", "port_rule_source_id", "requested_path_id",
    "resolved_path_id", "resolution_reason", "qualification_status", "factor_status",
    "factor_source_id", "factor_source_type", "factor_field", "evidence_field", "factor_value", "verification_status", "issue_code", "issue_scope",
    "issue_field", "component", "issue_component", "issue_blocking", "issue_message", "value_star", "eu_ets_reason", "fuel_eu_reason",
    "eu_ets_scope_rate", "eu_ets_surrender_rate", "fuel_eu_scope_rate",
    "ets_effective_rate", "ets_included_gases", "ets_excluded_gases", "zero_rating_status",
    "ets_scope_by_gas", "mrv_raw_by_gas", "s_ets_geo", "s_ets_surrender", "s_ets_effective",
    "equipment_id", "wt_t_mode", "factor_level",
    "comparison_status",
    "cost_min_scenario_id", "target_min_cost_scenario_id", "max_improvement_scenario_id",
    "decision_type", "recommended_quantity_tonnes", "recommended_blend_ratio",
    "pc_break_even", "pe_break_even", "pe_break_even_status", "comparison_value",
    "cost_min_ratio", "cost_sorted_ratios",
    "max_blend_ratio", "candidate_supply_tonnes", "incremental_budget", "x_budget", "x_supply",
    "x_cap", "target_status", "x_target_min_unconstrained", "x_target_min", "x_target_min_cost",
    "x_max_improvement", "x_cost_min",
    "warning_codes",
)


def _case_base(result: DecisionCaseResult, record_type: str) -> dict[str, str]:
    provenance = result.provenance
    return {
        **{column: "" for column in CASE_CSV_COLUMNS},
        "record_type": record_type,
        "report_year": str(result.report_year),
        "departure_port": result.departure_port,
        "arrival_port": result.arrival_port,
        "currency": result.currency,
        "penalty_currency": "EUR",
        "source_ids": ";".join(getattr(provenance, "source_ids", ()) or ()),
        "calculation_spec_version": _text(getattr(provenance, "calculation_spec_version", "")),
        "fuel_factor_version": _text(getattr(provenance, "fuel_factor_version", "")),
        "port_rule_version": _text(getattr(provenance, "port_rule_version", "")),
    }


def _case_metric_rows(result: DecisionCaseResult) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    metric_units = {
        "ratio": "fraction", "baseline_mass_tonnes": "tonne", "candidate_mass_tonnes": "tonne",
        "physical_energy_mj": "MJ", "fuel_cost": "case_currency", "ets_raw_co2_t": "tCO2",
        "ets_raw_ch4_t": "tCH4", "ets_raw_n2o_t": "tN2O", "ets_mrv_raw_co2e_t": "tCO2e",
        "ets_co2e_pre_scope_t": "tCO2e", "euas_required": "tCO2e", "eua_cost": "case_currency",
        "model_cost": "case_currency", "fueleu_scoped_energy_mj": "MJ", "fueleu_denominator_rwd_mj": "MJ",
        "fueleu_wtt_intensity_g_per_mj": "gCO2e/MJ", "fueleu_ttw_intensity_g_per_mj": "gCO2e/MJ",
        "fueleu_ghgi_actual_g_per_mj": "gCO2e/MJ", "fueleu_target_g_per_mj": "gCO2e/MJ",
        "fueleu_compliance_balance_g": "gCO2e", "fueleu_compliance_balance_t": "tCO2e",
        "fueleu_indicative_penalty_eur": "EUR", "compliance_improvement_tco2e": "tCO2e",
        "reference_adjusted_cost": "case_currency",
    }
    for scenario in result.scenarios:
        for metric_name, delta in scenario.deltas.items():
            row = _case_base(result, "scenario")
            row.update({
                "candidate_id": _text(scenario.candidate_id),
                "scenario_id": scenario.scenario_id,
                "calculation_status": scenario.calculation_status,
                "execution_status": scenario.result.execution_status,
                "constraint_status": scenario.result.constraint_status,
                "rank": _text(scenario.current_model_cost_rank),
                "metric_name": metric_name,
                "absolute": _text(delta.absolute),
                "delta": _text(delta.delta),
                "percent_delta": _text(delta.percent_delta),
                "reason_code": _text(delta.reason_code),
                "unit": metric_units.get(metric_name, ""),
                "value_currency": (
                    "EUR" if metric_name == "fueleu_indicative_penalty_eur"
                    else result.currency if metric_units.get(metric_name) == "case_currency" else ""
                ),
                "ets_effective_rate": _text(scenario.result.eu_ets.s_ets_effective),
                "ets_included_gases": ";".join(scenario.result.eu_ets.included_gases),
                "ets_excluded_gases": ";".join(
                    gas for gas, excluded in (scenario.result.eu_ets.excluded_from_ets_surrender or {}).items()
                    if excluded
                ) or "-",
                "zero_rating_status": ";".join(
                    f"{path}:{status}" for path, status in
                    (scenario.result.eu_ets.zero_rating_status_by_fuel_component or {}).items()
                ),
                "ets_scope_by_gas": ";".join(
                    f"{gas}:{_text(rate)}" for gas, rate in
                    (scenario.result.eu_ets.ets_scope_by_gas or {}).items()
                ),
                "mrv_raw_by_gas": ";".join(
                    f"{gas}:{_text(value)}" for gas, value in
                    (scenario.result.eu_ets.mrv_raw_by_gas or {}).items()
                ),
                "s_ets_geo": _text(scenario.result.eu_ets.s_ets_geo),
                "s_ets_surrender": _text(scenario.result.eu_ets.s_ets_surrender),
                "s_ets_effective": _text(scenario.result.eu_ets.s_ets_effective),
            })
            rows.append(row)
    return rows


def _decision_summary_selections(result: DecisionCaseResult) -> list[tuple[str, CaseScenario]]:
    """Keep each recommendation role even when several select the same scenario."""
    summary = result.decision_summary
    scenarios = {row.scenario_id: row for row in result.scenarios}
    baseline_id = summary.baseline_scenario_id if summary else "B0"
    selections = [("BASELINE", scenarios[baseline_id])] if baseline_id in scenarios else []
    if summary is not None:
        selections.extend(
            (recommendation.recommendation_id, scenarios[recommendation.scenario_id])
            for recommendation in result.recommendations
            if recommendation.scenario_id in scenarios
        )
    return selections


def _decision_summary_rows(result: DecisionCaseResult) -> list[dict[str, str]]:
    summary = result.decision_summary
    if summary is None:
        return []
    rows: list[dict[str, str]] = []
    metrics = (
        ("fuel_cost_delta", "fuel_cost", "case_currency", False),
        ("eua_cost_savings", "eua_cost", "case_currency", True),
        ("model_cost_delta", "model_cost", "case_currency", False),
        ("fueleu_ghgi_delta", "fueleu_ghgi_actual_g_per_mj", "gCO2e/MJ", False),
        ("fueleu_balance_delta", "fueleu_compliance_balance_t", "tCO2e", False),
        ("fueleu_penalty_delta", "fueleu_indicative_penalty_eur", "EUR", False),
    )
    for decision_type, scenario in _decision_summary_selections(result):
        scenario_id = scenario.scenario_id
        deltas = summary.scenario_deltas.get(scenario_id, {})
        for metric_name, source_metric, unit, negate in metrics:
            delta = deltas.get(source_metric)
            row = _case_base(result, "decision_summary")
            row.update({
                "candidate_id": _text(scenario.candidate_id),
                "scenario_id": scenario_id,
                "decision_type": decision_type,
                "recommended_quantity_tonnes": _text(scenario.result.candidate_mass_tonnes),
                "recommended_blend_ratio": _text(scenario.result.ratio),
                "metric_name": metric_name,
                "absolute": _text(delta.absolute if delta else None),
                "delta": _text(
                    delta.delta.copy_negate() if delta and negate and delta.delta
                    else delta.delta if delta else None
                ),
                "percent_delta": _text(
                    delta.percent_delta.copy_negate() if delta and negate and delta.percent_delta
                    else delta.percent_delta if delta else None
                ),
                "reason_code": _text(delta.reason_code if delta else None),
                "unit": unit,
                "value_currency": result.currency if unit == "case_currency" else "",
            })
            rows.append(row)
    return rows


def decision_case_to_csv(result: DecisionCaseResult, display_config: DisplayConfig | None = None) -> str:
    """Serialize a completed decision case without invoking calculation code.

    ``display_config`` is accepted for a shared API with visual reports, but
    raw CSV values deliberately ignore it to preserve auditability and bytes.
    """
    if not isinstance(result, DecisionCaseResult):
        raise TypeError("result must be a DecisionCaseResult")
    rows: list[dict[str, str]] = []
    provenance = result.provenance
    case = _case_base(result, "case")
    case["calculation_status"] = "CALCULABLE" if result.baseline_scenario is not None else "BLOCKED"
    case.update({
        "eu_ets_reason": _text(getattr(provenance, "eu_ets_reason", "")),
        "fuel_eu_reason": _text(getattr(provenance, "fuel_eu_reason", "")),
        "eu_ets_scope_rate": _text(getattr(provenance, "eu_ets_geographic_rate", None)),
        "eu_ets_surrender_rate": _text(getattr(provenance, "eu_ets_surrender_rate", None)),
        "fuel_eu_scope_rate": _text(getattr(provenance, "fuel_eu_rate", None)),
        "ets_effective_rate": _text(getattr(provenance, "eu_ets_effective_rate", None)),
        "unit": "scope_rate",
    })
    rows.append(case)
    for role, port in (("departure", getattr(provenance, "departure", None)), ("arrival", getattr(provenance, "arrival", None))):
        if port is None:
            continue
        row = _case_base(result, "port")
        row.update({
            "port_role": role, "port_name": _text(port.port_name), "unlocode": _text(port.unlocode),
            "eu_ets_identity": _text(port.eu_ets_identity), "fuel_eu_identity": _text(port.fuel_eu_identity),
                "port_rule_source_id": _text(port.rule_source_id),
            "unit": "scope_rate", "absolute": _text(getattr(provenance, "eu_ets_geographic_rate", None)),
            "eu_ets_reason": _text(getattr(provenance, "eu_ets_reason", "")),
            "fuel_eu_reason": _text(getattr(provenance, "fuel_eu_reason", "")),
            "eu_ets_scope_rate": _text(getattr(provenance, "eu_ets_geographic_rate", None)),
            "eu_ets_surrender_rate": _text(getattr(provenance, "eu_ets_surrender_rate", None)),
            "fuel_eu_scope_rate": _text(getattr(provenance, "fuel_eu_rate", None)),
        })
        rows.append(row)
    rows.extend(_case_metric_rows(result))
    rows.extend(_decision_summary_rows(result))
    for candidate in result.candidate_results:
        row = _case_base(result, "constraints")
        row["candidate_id"] = candidate.candidate_id
        if candidate.voyage_result is None or candidate.voyage_result.constraints is None:
            row["calculation_status"] = candidate.calculation_status
            row["warning_codes"] = ";".join(issue.code for issue in candidate.issues)
        else:
            constraints = candidate.voyage_result.constraints
            row.update({
                "calculation_status": candidate.calculation_status,
                "max_blend_ratio": _text(constraints.max_blend_ratio),
                "candidate_supply_tonnes": _text(constraints.candidate_supply_tonnes),
                "incremental_budget": _text(constraints.incremental_budget),
                "x_budget": _text(constraints.x_budget), "x_supply": _text(constraints.x_supply),
                "x_cap": _text(constraints.x_cap), "target_status": constraints.target_status,
                "x_target_min_unconstrained": _text(constraints.x_target_min_unconstrained),
                "x_target_min": _text(constraints.x_target_min),
                "x_target_min_cost": _text(constraints.x_target_min_cost),
                "x_max_improvement": _text(constraints.x_max_improvement),
                "x_cost_min": _text(constraints.x_cost_min),
                "warning_codes": ";".join(constraints.warning_codes),
            })
        rows.append(row)
    if result.economics is not None:
        economics = result.economics
        row = _case_base(result, "economics")
        row.update({
            "comparison_status": economics.comparison_status,
            "cost_min_scenario_id": _text(economics.cost_min_scenario_id),
            "target_min_cost_scenario_id": _text(economics.target_min_cost_scenario_id),
            "max_improvement_scenario_id": _text(economics.max_improvement_scenario_id),
        })
        rows.append(row)
        for point in economics.switch_points:
            switch = _case_base(result, "switch_point")
            switch.update({
                "from_scenario_id": point.from_scenario_id,
                "to_scenario_id": point.to_scenario_id,
                "from_candidate_id": _text(point.from_candidate_id),
                "to_candidate_id": _text(point.to_candidate_id),
                "value_star": _text(point.value_star),
                "unit": "case_currency", "value_currency": result.currency,
            })
            rows.append(switch)
    for recommendation in result.recommendations:
        row = _case_base(result, "recommendation")
        row.update({
            "recommendation_id": recommendation.recommendation_id, "condition": recommendation.condition,
            "scenario_id": _text(recommendation.scenario_id), "recommendation_status": recommendation.status,
            "reason": recommendation.reason, "assumptions": ";".join(recommendation.assumptions),
            "from_scenario_id": _text(recommendation.from_scenario_id), "to_scenario_id": _text(recommendation.to_scenario_id),
            "from_candidate_id": _text(recommendation.from_candidate_id), "to_candidate_id": _text(recommendation.to_candidate_id),
            "value_star": _text(recommendation.value_star),
        })
        if recommendation.value_star is not None:
            row["unit"] = "case_currency"
            row["value_currency"] = result.currency
        rows.append(row)
    for trace in getattr(provenance, "factor_resolutions", ()) or ():
        factor = trace.factor
        evidence = getattr(factor, "source_evidence", ()) or ()
        if not evidence:
            evidence = (None,)
        evidence_fields = {
            "lcv": ("lcv_mj_per_g", "MJ/g"), "wtT": ("wt_t_g_per_mj", "g/MJ"),
            "cfCO2": ("cf_co2_g_per_g", "g/g"), "cfCH4": ("cf_ch4_g_per_g", "g/g"),
            "cfN2O": ("cf_n2o_g_per_g", "g/g"), "rwd": ("rwd", "fraction"),
            "E": ("e_g_per_mj", "g/MJ"), "eu": ("eu_g_per_mj", "g/MJ"),
            "cslip": ("cslip_percent", "%"), "csfCO2": ("csf_co2_g_per_g", "g/g"),
            "csfCH4": ("csf_ch4_g_per_g", "g/g"), "csfN2O": ("csf_n2o_g_per_g", "g/g"),
            "methaneSlipApplicable": ("methane_slip_applicable", "boolean"),
            # Keep the existing factor_field label stable; the value comes
            # from the component trace rather than the path capability flag.
            "eligibleBiomassFraction": ("biomass_eligible", "fraction"),
        }
        for item in evidence:
            mapped = evidence_fields.get(getattr(item, "field_name", ""))
            if mapped is None:
                continue
            field_name, field_unit = mapped
            value = (
                getattr(trace, "eligible_biomass_fraction", None)
                if item is not None and item.field_name == "eligibleBiomassFraction"
                else getattr(factor, field_name, None)
            )
            if value is None:
                continue
            row = _case_base(result, "factor_evidence")
            row.update({
                "requested_path_id": _text(trace.requested_path_id), "resolved_path_id": _text(trace.resolved_path_id),
                "resolution_reason": _text(trace.resolution_reason), "qualification_status": _text(trace.qualification_status),
                "factor_status": _text(trace.factor_status), "factor_source_id": _text(getattr(item, "source_id", "")),
                "factor_source_type": _text(getattr(item, "source_type", "")),
                "factor_field": field_name, "evidence_field": getattr(item, "field_name", field_name), "factor_value": _text(value),
                "unit": _text(getattr(item, "unit", field_unit)),
                "verification_status": _text(getattr(item, "verification_status", "")),
                "equipment_id": _text(getattr(factor, "equipment_id", None)),
                "wt_t_mode": _text(getattr(factor, "wt_t_mode", None)),
                "factor_level": _text(getattr(factor, "factor_level", None)),
            })
            rows.append(row)
    all_issues = result.issues + tuple(issue for candidate in result.candidate_results for issue in candidate.issues)
    seen_issues = set()
    for issue in all_issues:
        identity = (issue.code, issue.scope, issue.field, issue.candidate_id, issue.scenario_id, issue.component, issue.blocking, issue.message)
        if identity in seen_issues:
            continue
        seen_issues.add(identity)
        row = _case_base(result, "issue")
        row.update({
            "candidate_id": _text(issue.candidate_id), "scenario_id": _text(issue.scenario_id),
            "issue_code": issue.code, "issue_scope": issue.scope, "issue_field": issue.field,
            "component": _text(issue.component), "issue_component": _text(issue.component),
            "issue_blocking": str(issue.blocking).lower(),
            "issue_message": issue.message,
        })
        rows.append(row)
    # Keep the record-type vocabulary stable for consumers even when an
    # optional section has no entries in a particular case.
    present_types = {row["record_type"] for row in rows}
    for record_type in ("recommendation", "switch_point", "factor_evidence", "issue"):
        if record_type not in present_types:
            rows.append(_case_base(result, record_type))
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CASE_CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def write_decision_case_csv(result: DecisionCaseResult, path: str | Path, display_config: DisplayConfig | None = None) -> Path:
    target = Path(path)
    target.write_text(decision_case_to_csv(result, display_config), encoding="utf-8", newline="")
    return target


def decision_case_to_pdf(
    result: DecisionCaseResult,
    display_config: DisplayConfig | None = None,
) -> bytes:
    """Render an auditable multi-section decision case report.

    The report is a projection only: it never invokes the calculation kernel and
    never mutates ``result``.  ``display_config`` controls presentation precision
    while the CSV serializer continues to expose lossless Decimal strings.
    """
    if not isinstance(result, DecisionCaseResult):
        raise TypeError("result must be a DecisionCaseResult")
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            KeepTogether, LongTable, PageBreak, Paragraph, SimpleDocTemplate,
            Spacer, Table, TableStyle,
        )
    except ImportError as exc:
        raise RuntimeError("reportlab is required for PDF export") from exc

    config = display_config or DisplayConfig()

    def value(item: Any, kind: str = "generic") -> str:
        rendered = format_for_display(item, kind, config)
        return rendered if rendered != "" else "-"

    def text(item: Any) -> str:
        rendered = "-" if item is None or item == "" else str(item)
        return escape(rendered).replace("\n", "<br/>")

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=17, leading=21, spaceAfter=5 * mm,
    ))
    styles.add(ParagraphStyle(
        name="ReportHeading", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=11, leading=14, spaceBefore=4 * mm, spaceAfter=2 * mm,
    ))
    styles.add(ParagraphStyle(
        name="ReportBody", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=8.5, leading=11, alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="ReportCell", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=6.8, leading=8.2, wordWrap="CJK",
    ))
    styles.add(ParagraphStyle(
        name="ReportCellSmall", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=6.1, leading=7.2, wordWrap="CJK",
    ))

    def cell(item: Any, small: bool = False) -> Paragraph:
        return Paragraph(text(item), styles["ReportCellSmall" if small else "ReportCell"])

    def make_table(rows: list[list[Any]], widths: list[float], *, header: bool = True, small: bool = False) -> Table:
        converted = [[cell(item, small=small) if not isinstance(item, Paragraph) else item for item in row] for row in rows]
        table = LongTable(converted, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
        commands = [
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#AAB7C4")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]
        if header:
            commands.extend([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ])
        table.setStyle(TableStyle(commands))
        return table

    story: list[Any] = [Paragraph("Voyage Fuel Decision Report", styles["ReportTitle"])]
    story.append(Paragraph(
        f"Report year: {text(result.report_year)} | Departure: {text(result.departure_port)} | "
        f"Arrival: {text(result.arrival_port)} | Case currency: {text(result.currency)}",
        styles["ReportBody"],
    ))
    story.append(Paragraph(
        "Boundary: voyage-level regulatory estimate for this submitted voyage. "
        "FuelEU indicative penalty equivalent is not a formal annual penalty or annual-limit settlement; "
        "execution conditions remain pending and this report is not a procurement recommendation. "
        "This report does not provide an independent physical lifecycle WtW reduction.",
        styles["ReportBody"],
    ))

    provenance = result.provenance
    story.append(Paragraph("Case boundary and scope", styles["ReportHeading"]))
    departure = getattr(provenance, "departure", None)
    arrival = getattr(provenance, "arrival", None)
    boundary_rows = [["Field", "Value"],
        ["Departure EU ETS identity", text(getattr(departure, "eu_ets_identity", None))],
        ["Arrival EU ETS identity", text(getattr(arrival, "eu_ets_identity", None))],
        ["Departure FuelEU identity", text(getattr(departure, "fuel_eu_identity", None))],
        ["Arrival FuelEU identity", text(getattr(arrival, "fuel_eu_identity", None))],
        ["EU ETS reason", text(getattr(provenance, "eu_ets_reason", None))],
        ["EU ETS geographic scope rate", value(getattr(provenance, "eu_ets_geographic_rate", None), "scope_rate")],
        ["EU ETS surrender rate", value(getattr(provenance, "eu_ets_surrender_rate", None), "scope_rate")],
        ["ETS effective rate", value(getattr(provenance, "eu_ets_effective_rate", None), "scope_rate")],
        ["FuelEU reason", text(getattr(provenance, "fuel_eu_reason", None))],
        ["FuelEU scope rate", value(getattr(provenance, "fuel_eu_rate", None), "scope_rate")],
        ["Source IDs", text("; ".join(getattr(provenance, "source_ids", ()) or ()))],
    ]
    story.append(make_table(boundary_rows, [57 * mm, 113 * mm], small=True))

    story.append(Paragraph("Conclusions and conditional recommendations", styles["ReportHeading"]))
    recommendation_rows = [["ID", "Condition", "Status", "Scenario", "Reason / assumptions"]]
    for recommendation in result.recommendations:
        recommendation_rows.append([
            recommendation.recommendation_id, recommendation.condition, recommendation.status,
            recommendation.scenario_id or "-",
            f"{recommendation.reason}; " + "; ".join(recommendation.assumptions),
        ])
    if len(recommendation_rows) == 1:
        recommendation_rows.append(["-", "-", "-", "-", "No recommendation available"])
    story.append(make_table(recommendation_rows, [38 * mm, 38 * mm, 22 * mm, 32 * mm, 40 * mm], small=True))

    story.append(Paragraph("New energy decision summary", styles["ReportHeading"]))
    decision_rows = [[
        "Decision type", "Candidate", "Recommended quantity (t)", "Blend ratio",
        "Additional fuel cost", "EU ETS cost saving", "Net cost change",
        "FuelEU GHGI change", "FuelEU balance change",
    ]]
    summary = result.decision_summary
    for decision_type, scenario in _decision_summary_selections(result):
        scenario_id = scenario.scenario_id
        deltas = summary.scenario_deltas.get(scenario_id, {}) if summary else {}
        fuel_cost = deltas.get("fuel_cost")
        eua_cost = deltas.get("eua_cost")
        model_cost = deltas.get("model_cost")
        ghgi = deltas.get("fueleu_ghgi_actual_g_per_mj")
        balance = deltas.get("fueleu_compliance_balance_t")
        decision_rows.append([
            decision_type, scenario.candidate_id or "B0",
            value(scenario.result.candidate_mass_tonnes, "fuel_mass"),
            value(scenario.result.ratio, "ratio"),
            value(fuel_cost.delta if fuel_cost else None, "price"),
            value(-eua_cost.delta if eua_cost and eua_cost.delta is not None else None, "price"),
            value(model_cost.delta if model_cost else None, "price"),
            value(ghgi.delta if ghgi else None, "intensity"),
            value(balance.delta if balance else None, "gas"),
        ])
    if len(decision_rows) == 1:
        decision_rows.append(["-", "-", "-", "-", "-", "-", "-", "-", "-"])
    story.append(make_table(
        decision_rows,
        [34*mm, 24*mm, 28*mm, 22*mm, 28*mm, 28*mm, 28*mm, 28*mm, 28*mm],
        small=True,
    ))
    story.append(Paragraph(
        "FuelEU values are voyage-level indicators; recommendation status remains conditional and "
        "EXECUTION_CONDITIONS_PENDING.",
        styles["ReportBody"],
    ))

    story.append(Paragraph("Scenario comparison (fuel mass and energy)", styles["ReportHeading"]))
    scenario_rows = [[
        "Scenario", "Candidate", "Ratio", "Baseline mass (t)", "Candidate mass (t)", "Energy (GJ)", "Fuel cost", "Model cost",
        "CO2 (t)", "CH4 (t)", "N2O (t)", "EUAs", "EUA cost", "Calc / constraint / execution",
    ]]
    for scenario in result.scenarios:
        item = scenario.result
        scenario_rows.append([
            scenario.scenario_id, scenario.candidate_id or "B0", value(item.ratio, "ratio"),
            value(item.baseline_mass_tonnes, "fuel_mass"), value(item.candidate_mass_tonnes, "fuel_mass"),
            value(item.physical_energy_mj, "energy"), value(item.fuel_cost, "price"), value(item.model_cost, "price"),
            value(item.eu_ets.raw_co2_t, "gas"), value(item.eu_ets.raw_ch4_t, "gas"), value(item.eu_ets.raw_n2o_t, "gas"),
            value(item.eu_ets.euas_required, "gas"), value(item.eu_ets.eua_cost, "price"),
            f"{scenario.calculation_status} / {item.constraint_status} / {item.execution_status}",
        ])
    if len(scenario_rows) == 1:
        scenario_rows.append(["-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-"])
    story.append(make_table(scenario_rows, [22*mm, 18*mm, 14*mm, 20*mm, 20*mm, 19*mm, 19*mm, 19*mm, 16*mm, 16*mm, 16*mm, 16*mm, 19*mm, 31*mm], small=True))

    story.append(Paragraph("EU ETS gas scope and zero-rating status", styles["ReportHeading"]))
    ets_rows = [["Scenario", "ETS effective rate", "Included gases", "Excluded gases", "Zero-rating status"]]
    for scenario in result.scenarios:
        ets = scenario.result.eu_ets
        ets_rows.append([
            scenario.scenario_id, value(ets.s_ets_effective, "scope_rate"),
            "; ".join(ets.included_gases),
            "; ".join(gas for gas, excluded in (ets.excluded_from_ets_surrender or {}).items() if excluded) or "-",
            "; ".join(f"{path}: {status}" for path, status in (ets.zero_rating_status_by_fuel_component or {}).items()) or "-",
        ])
    if len(ets_rows) == 1:
        ets_rows.append(["-", "-", "-", "-", "-"])
    story.append(make_table(ets_rows, [42*mm, 28*mm, 35*mm, 35*mm, 58*mm], small=True))

    story.append(Paragraph("Absolute and relative-to-B0 changes", styles["ReportHeading"]))
    change_rows = [["Scenario", "Metric", "Absolute", "Delta", "Relative-to-B0 (%)"]]
    change_metrics = (
        ("baseline_mass_tonnes", "Baseline fuel mass", "fuel_mass"),
        ("candidate_mass_tonnes", "Candidate fuel mass", "fuel_mass"),
        ("physical_energy_mj", "Physical energy", "energy"),
        ("fuel_cost", "Fuel cost", "price"),
        ("ets_raw_co2_t", "CO2", "gas"), ("ets_raw_ch4_t", "CH4", "gas"),
        ("ets_raw_n2o_t", "N2O", "gas"), ("ets_mrv_raw_co2e_t", "MRV raw CO2e", "gas"),
        ("ets_co2e_pre_scope_t", "EU ETS CO2e before scope", "gas"),
        ("euas_required", "EUAs required", "gas"), ("eua_cost", "EUA cost", "price"),
        ("model_cost", "Model cost", "price"),
        ("fueleu_scoped_energy_mj", "FuelEU scoped energy", "energy"),
        ("fueleu_denominator_rwd_mj", "FuelEU RWD denominator", "energy"),
        ("fueleu_wtt_intensity_g_per_mj", "WtT", "intensity"),
        ("fueleu_ttw_intensity_g_per_mj", "TtW", "intensity"),
        ("fueleu_ghgi_actual_g_per_mj", "GHGI", "intensity"),
        ("fueleu_target_g_per_mj", "Target", "intensity"),
        ("fueleu_compliance_balance_g", "Compliance balance (g)", "gas"),
        ("fueleu_compliance_balance_t", "Compliance balance", "gas"),
        ("fueleu_indicative_penalty_eur", "Indicative penalty equivalent", "price"),
        ("compliance_improvement_tco2e", "Compliance improvement", "gas"),
        ("reference_adjusted_cost", "Reference-adjusted cost", "price"),
    )
    for scenario in result.scenarios:
        for metric_name, label, kind in change_metrics:
            delta = scenario.deltas.get(metric_name)
            if delta is not None:
                change_rows.append([scenario.scenario_id, label, value(delta.absolute, kind), value(delta.delta, kind), value(delta.percent_delta, "generic") + ("%" if delta.percent_delta is not None else "")])
    if len(change_rows) == 1:
        change_rows.append(["-", "-", "-", "-", "-"])
    story.append(make_table(change_rows, [40*mm, 35*mm, 38*mm, 38*mm, 46*mm], small=True))

    story.append(Paragraph("Concrete switch points", styles["ReportHeading"]))
    switch_rows = [["Candidate", "From scenario", "To scenario", "Value star (case currency)"]]
    for recommendation in result.recommendations:
        if recommendation.from_scenario_id and recommendation.to_scenario_id:
            switch_rows.append([recommendation.from_candidate_id or recommendation.to_candidate_id or "-", recommendation.from_scenario_id, recommendation.to_scenario_id, value(recommendation.value_star, "price")])
    if len(switch_rows) == 1:
        switch_rows.append(["-", "-", "-", "-"])
    story.append(make_table(switch_rows, [40*mm, 50*mm, 50*mm, 52*mm], small=True))

    story.append(Paragraph("FuelEU metrics and changes relative to B0", styles["ReportHeading"]))
    fueleu_rows = [["Scenario", "WtT (g/MJ)", "TtW (g/MJ)", "GHGI (g/MJ)", "Target (g/MJ)", "Balance (tCO2e)", "Indicative penalty equivalent (EUR)", "Absolute / relative-to-B0"]]
    for scenario in result.scenarios:
        item = scenario.result.fuel_eu
        ghgi_delta = scenario.deltas.get("fueleu_ghgi_actual_g_per_mj")
        fueleu_rows.append([
            scenario.scenario_id, value(item.wt_t_intensity_g_per_mj, "intensity"),
            value(item.tt_w_intensity_g_per_mj, "intensity"), value(item.ghgi_actual_g_per_mj, "intensity"),
            value(item.target_g_per_mj, "intensity"), value(item.compliance_balance_t, "gas"),
            value(item.indicative_penalty_eur, "price"),
            f"GHGI abs {value(ghgi_delta.delta if ghgi_delta else None, 'intensity')}; "
            f"rel {value(ghgi_delta.percent_delta if ghgi_delta else None, 'generic')}%",
        ])
    story.append(make_table(fueleu_rows, [22*mm, 20*mm, 20*mm, 20*mm, 20*mm, 24*mm, 31*mm, 43*mm], small=True))

    story.append(Paragraph("Constraints and thresholds", styles["ReportHeading"]))
    constraints_rows = [["Candidate", "Max blend", "Supply (t)", "Budget", "xBudget", "xSupply", "xCap", "Target status", "Target min", "Target min cost", "Max improvement", "Cost min"]]
    for candidate in result.candidate_results:
        voyage = candidate.voyage_result
        c = voyage.constraints if voyage else None
        if c is None:
            constraints_rows.append([candidate.candidate_id, "-", "-", "-", "-", "-", "-", "BLOCKED", "-", "-", "-", "-"])
            continue
        constraints_rows.append([
            candidate.candidate_id, value(c.max_blend_ratio, "ratio"), value(c.candidate_supply_tonnes, "fuel_mass"),
            value(c.incremental_budget, "price"), value(c.x_budget, "ratio"), value(c.x_supply, "ratio"),
            value(c.x_cap, "ratio"), c.target_status, value(c.x_target_min, "ratio"),
            value(c.x_target_min_cost, "ratio"), value(c.x_max_improvement, "ratio"), value(c.x_cost_min, "ratio"),
        ])
    story.append(make_table(constraints_rows, [24*mm, 17*mm, 19*mm, 19*mm, 15*mm, 15*mm, 15*mm, 24*mm, 19*mm, 23*mm, 22*mm, 18*mm], small=True))

    story.append(Paragraph("Factor evidence and resolution", styles["ReportHeading"]))
    factor_rows = [["Requested path", "Resolved path", "Fallback reason", "Qualification", "Factor status", "Equipment ID", "WtT mode", "Evidence (field/source/type/unit/status/value)"]]
    for trace in getattr(provenance, "factor_resolutions", ()) or ():
        factor = trace.factor
        field_values = {
            "lcv": getattr(factor, "lcv_mj_per_g", None), "wtT": getattr(factor, "wt_t_g_per_mj", None),
            "cfCO2": getattr(factor, "cf_co2_g_per_g", None), "cfCH4": getattr(factor, "cf_ch4_g_per_g", None),
            "cfN2O": getattr(factor, "cf_n2o_g_per_g", None), "rwd": getattr(factor, "rwd", None),
            "E": getattr(factor, "e_g_per_mj", None), "eu": getattr(factor, "eu_g_per_mj", None),
            "cslip": getattr(factor, "cslip_percent", None),
            "methaneSlipApplicable": getattr(factor, "methane_slip_applicable", None),
            "eligibleBiomassFraction": getattr(trace, "eligible_biomass_fraction", Decimal("0")),
        }
        evidence = "; ".join(
            f"{item.field_name}/{item.source_id}/{item.source_type}/{item.unit}/{item.verification_status}/{value(field_values.get(item.field_name), 'factor')}"
            for item in getattr(factor, "source_evidence", ()) or ()
        )
        factor_rows.append([trace.requested_path_id, trace.resolved_path_id, trace.resolution_reason, trace.qualification_status, trace.factor_status, getattr(factor, "equipment_id", None) or "-", getattr(factor, "wt_t_mode", None) or "-", evidence or "-"])
    if len(factor_rows) == 1:
        factor_rows.append(["-", "-", "-", "-", "-", "-", "-", "-", "-"])
    story.append(make_table(factor_rows, [22*mm, 22*mm, 28*mm, 22*mm, 20*mm, 24*mm, 20*mm, 145*mm], small=True))

    story.append(Paragraph("Port evidence", styles["ReportHeading"]))
    port_rows = [["Role", "Port", "UN/LOCODE", "EU ETS identity", "FuelEU identity", "Rule source ID", "Source version"]]
    for role, port in (("Departure", getattr(provenance, "departure", None)), ("Arrival", getattr(provenance, "arrival", None))):
        if port is not None:
            port_rows.append([role, port.port_name, port.unlocode, port.eu_ets_identity, port.fuel_eu_identity, port.rule_source_id, port.source_version])
    if len(port_rows) == 1:
        port_rows.append(["-", "-", "-", "-", "-", "-", "-"])
    story.append(make_table(port_rows, [18*mm, 30*mm, 24*mm, 28*mm, 28*mm, 35*mm, 27*mm], small=True))

    story.append(Paragraph("Issues", styles["ReportHeading"]))
    issue_rows = [["Scope", "Candidate", "Scenario", "Component", "Code", "Field", "Blocking", "Message"]]
    all_issues = result.issues + tuple(issue for candidate in result.candidate_results for issue in candidate.issues)
    seen: set[tuple[Any, ...]] = set()
    for issue in all_issues:
        identity = (issue.code, issue.scope, issue.field, issue.candidate_id, issue.scenario_id, issue.component, issue.blocking, issue.message)
        if identity in seen:
            continue
        seen.add(identity)
        issue_rows.append([issue.scope, issue.candidate_id or "-", issue.scenario_id or "-", issue.component or "-", issue.code, issue.field, str(issue.blocking).lower(), issue.message])
    if len(issue_rows) == 1:
        issue_rows.append(["-", "-", "-", "-", "-", "-", "-", "No issues recorded"])
    story.append(make_table(issue_rows, [17*mm, 25*mm, 31*mm, 25*mm, 27*mm, 31*mm, 18*mm, 35*mm], small=True))

    story.append(Paragraph("Methodology and versions", styles["ReportHeading"]))
    versions = [["Calculation specification version", text(getattr(provenance, "calculation_spec_version", None))],
        ["Fuel factor version", text(getattr(provenance, "fuel_factor_version", None))],
        ["Port rule version", text(getattr(provenance, "port_rule_version", None))],
        ["Calculation status vocabulary", "BLOCKED, CALCULABLE, COMPARABLE"],
        ["Execution status", "EXECUTION_CONDITIONS_PENDING"],
        ["FuelEU limitation", "Voyage-level proportional estimate; indicative EUR equivalent is not an annual legal penalty or annual-limit result."],
        ["Physical WtW limitation", "Independent physical lifecycle WtW reduction is not provided in this MVP."],
        ["Target-min-cost scenario", text(getattr(result.economics, "target_min_cost_scenario_id", None))],
    ]
    story.append(make_table([["Method", "Value"], *versions], [57*mm, 113*mm], small=True))

    output = io.BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=landscape(A4), rightMargin=14 * mm, leftMargin=14 * mm,
        topMargin=13 * mm, bottomMargin=13 * mm, title="Voyage Fuel Decision Report",
        author="voyage-fuel-decision-mvp",
    )
    document.build(story)
    return output.getvalue()


def write_decision_case_pdf(result: DecisionCaseResult, path: str | Path, display_config: DisplayConfig | None = None) -> Path:
    target = Path(path)
    target.write_bytes(decision_case_to_pdf(result, display_config))
    return target


def voyage_result_to_pdf(result: VoyageResult) -> bytes:
    """Render a compact, auditable single-voyage summary without recalculation."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    except ImportError as exc:
        raise RuntimeError("reportlab is required for PDF export") from exc

    output = io.BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm,
        topMargin=14 * mm, bottomMargin=14 * mm, title="Voyage Fuel Decision",
        author="voyage-fuel-decision-mvp",
    )
    styles = getSampleStyleSheet()
    styles["Title"].fontName = "Helvetica-Bold"
    styles["Heading2"].fontName = "Helvetica-Bold"
    styles["BodyText"].fontName = "Helvetica"
    story = [Paragraph("Voyage Fuel Decision", styles["Title"]), Spacer(1, 4 * mm)]
    story.append(Paragraph(
        f"Report year: {result.report_year} | Voyage: {result.departure_port} to {result.arrival_port}",
        styles["BodyText"],
    ))
    story.append(Paragraph("Single-voyage calculation summary; FuelEU values are estimates and execution conditions remain pending.", styles["BodyText"]))
    story.append(Spacer(1, 4 * mm))

    scope = result.scope_rates
    identity = [
        ["Baseline energy (MJ)", _display(result.baseline_energy_mj)],
        ["EU ETS scope / effective rate", f"{_display(scope.eu_ets_scope_rate)} / {_display(scope.eu_ets_effective_rate)}"],
        ["FuelEU scope", _display(scope.fuel_eu_scope_rate)],
        ["Baseline factor", _text(result.baseline_factor.path_id if result.baseline_factor else "")],
        ["Candidate factor", _text(result.candidate_factor.path_id if result.candidate_factor else "")],
        ["Factor status", f"{_text(result.baseline_factor.factor_status if result.baseline_factor else '')} / {_text(result.candidate_factor.factor_status if result.candidate_factor else '')}"],
    ]
    table = Table(identity, colWidths=[58 * mm, 112 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF1F7")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#9AA9B5")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story += [table, Spacer(1, 5 * mm), Paragraph("Scenarios", styles["Heading2"])]
    scenario_rows = [["Ratio", "Candidate mass (t)", "Model cost", "GHGI", "CB (t)", "Status"]]
    for scenario in result.scenarios:
        scenario_rows.append([
            _display(scenario.ratio), _display(scenario.candidate_mass_tonnes), _display(scenario.model_cost, 2),
            _display(scenario.fuel_eu.ghgi_actual_g_per_mj), _display(scenario.fuel_eu.compliance_balance_t),
            scenario.constraint_status,
        ])
    scenario_table = Table(scenario_rows, repeatRows=1, colWidths=[21 * mm, 31 * mm, 31 * mm, 27 * mm, 27 * mm, 30 * mm])
    scenario_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#AAB7C4")),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (-1, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story += [scenario_table, Spacer(1, 5 * mm)]
    if result.constraints is not None:
        c = result.constraints
        story.append(Paragraph("Constraints and economics", styles["Heading2"]))
        summary = [
            ["xCap", _display(c.x_cap), "Target status", c.target_status],
            ["xBudget", _display(c.x_budget), "xSupply", _display(c.x_supply)],
            ["xTargetMin", _display(c.x_target_min), "Cost-min ratio", _display(c.x_cost_min)],
        ]
        if result.economics is not None:
            e = result.economics
            summary.extend([
                ["Pc break-even", _display(e.pc_break_even, 2), "Pe break-even", _display(e.pe_break_even, 2)],
                ["Comparison status", e.comparison_status, "Switch points", str(len(e.switch_points))],
            ])
        summary_table = Table(summary, colWidths=[32 * mm, 53 * mm, 37 * mm, 48 * mm])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF1F7")),
            ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#EAF1F7")),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#9AA9B5")),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
        ]))
        story += [summary_table, Spacer(1, 4 * mm)]
        story.append(Paragraph("Evidence IDs: " + "; ".join(
            e.source_id for factor in (result.baseline_factor, result.candidate_factor) if factor
            for e in factor.source_evidence
        ), styles["BodyText"]))
    document.build(story)
    return output.getvalue()


def write_voyage_pdf(result: VoyageResult, path: str | Path) -> Path:
    target = Path(path)
    target.write_bytes(voyage_result_to_pdf(result))
    return target
