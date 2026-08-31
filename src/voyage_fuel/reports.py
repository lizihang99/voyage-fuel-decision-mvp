"""Deterministic CSV export for raw voyage calculation results."""

import csv
import io
from decimal import Decimal
from pathlib import Path
from typing import Any

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
)


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return format(value, "f")
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
