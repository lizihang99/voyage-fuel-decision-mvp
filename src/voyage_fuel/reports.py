"""Deterministic CSV export for raw voyage calculation results."""

import csv
import io
from decimal import Decimal
from pathlib import Path
from typing import Any

from .contracts import DecisionCaseResult
from .formatting import DisplayConfig
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
    "factor_source_id", "factor_field", "factor_value", "verification_status", "issue_code", "issue_scope",
    "issue_field", "issue_blocking", "issue_message", "value_star", "eu_ets_reason", "fuel_eu_reason",
    "eu_ets_scope_rate", "eu_ets_surrender_rate", "fuel_eu_scope_rate",
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
                "value_currency": result.currency if metric_units.get(metric_name) == "case_currency" else "",
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
        rows.append(row)
    for candidate in result.candidate_results:
        if candidate.voyage_result is None or candidate.voyage_result.economics is None:
            continue
        for point in candidate.voyage_result.economics.switch_points:
            row = _case_base(result, "switch_point")
            row.update({"candidate_id": candidate.candidate_id, "from_scenario_id": f"{candidate.candidate_id}@{format(point.from_ratio.normalize(), 'f')}", "to_scenario_id": f"{candidate.candidate_id}@{format(point.to_ratio.normalize(), 'f')}", "value_star": _text(point.value_star), "unit": "case_currency", "value_currency": result.currency})
            rows.append(row)
    for trace in getattr(provenance, "factor_resolutions", ()) or ():
        factor = trace.factor
        evidence = getattr(factor, "source_evidence", ()) or ()
        if not evidence:
            evidence = (None,)
        for item in evidence:
            row = _case_base(result, "factor_evidence")
            row.update({
                "requested_path_id": _text(trace.requested_path_id), "resolved_path_id": _text(trace.resolved_path_id),
                "resolution_reason": _text(trace.resolution_reason), "qualification_status": _text(trace.qualification_status),
                "factor_status": _text(trace.factor_status), "factor_source_id": _text(getattr(item, "source_id", "")),
                "factor_field": _text(getattr(item, "field_name", "")), "factor_value": "",
                "unit": _text(getattr(item, "unit", "")),
                "verification_status": _text(getattr(item, "verification_status", "")),
            })
            rows.append(row)
    for issue in result.issues + tuple(issue for candidate in result.candidate_results for issue in candidate.issues):
        row = _case_base(result, "issue")
        row.update({"candidate_id": _text(issue.candidate_id), "issue_code": issue.code, "issue_scope": issue.scope, "issue_field": issue.field, "issue_blocking": str(issue.blocking).lower(), "issue_message": issue.message})
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
