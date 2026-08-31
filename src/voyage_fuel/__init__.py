"""Python implementation of the voyage fuel decision calculation kernel."""

from decimal import getcontext


# Keep the process context above the specification's 34 significant digits.
getcontext().prec = max(getcontext().prec, 50)

from .models import (
    EtsResult,
    FuelAmount,
    FuelComponent,
    FuelEuResult,
    FuelFactor,
    ScenarioResult,
    ScopeRates,
    VoyageInput,
    VoyageResult,
)
from .json_io import calculate_voyage_json
from .factors import builtin_path_ids, get_definition, get_builtin_factor, resolve_factor

__all__ = [
    "EtsResult",
    "FuelAmount",
    "FuelComponent",
    "FuelEuResult",
    "FuelFactor",
    "ScenarioResult",
    "ScopeRates",
    "VoyageInput",
    "VoyageResult",
    "calculate_voyage_json",
    "builtin_path_ids",
    "get_definition",
    "get_builtin_factor",
    "resolve_factor",
]
