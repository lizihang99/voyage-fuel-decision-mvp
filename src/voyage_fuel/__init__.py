"""Python implementation of the voyage fuel decision calculation kernel."""

from decimal import getcontext


# Keep the process context above the specification's 34 significant digits.
getcontext().prec = max(getcontext().prec, 50)

from .models import (
    EtsResult,
    ConstraintResult,
    EuaBreakEvenResult,
    EconomicsResult,
    FuelAmount,
    FuelComponent,
    FuelEuResult,
    FuelFactor,
    ScenarioResult,
    ScopeRates,
    VoyageInput,
    VoyageResult,
    ValueSwitchPoint,
)
from .json_io import calculate_voyage_json
from .constraints import calculate_constraints, calculate_minimum_target_ratio
from .economics import (
    build_economics,
    calculate_candidate_break_even_price,
    calculate_eua_break_even_price,
    calculate_value_switch_points,
    compliance_improvement_tco2e,
)
from .factors import builtin_path_ids, get_definition, get_builtin_factor, resolve_factor

__all__ = [
    "EtsResult",
    "ConstraintResult",
    "EuaBreakEvenResult",
    "EconomicsResult",
    "FuelAmount",
    "FuelComponent",
    "FuelEuResult",
    "FuelFactor",
    "ScenarioResult",
    "ScopeRates",
    "VoyageInput",
    "VoyageResult",
    "ValueSwitchPoint",
    "calculate_voyage_json",
    "calculate_constraints",
    "calculate_minimum_target_ratio",
    "build_economics",
    "calculate_candidate_break_even_price",
    "calculate_eua_break_even_price",
    "calculate_value_switch_points",
    "compliance_improvement_tco2e",
    "builtin_path_ids",
    "get_definition",
    "get_builtin_factor",
    "resolve_factor",
]
