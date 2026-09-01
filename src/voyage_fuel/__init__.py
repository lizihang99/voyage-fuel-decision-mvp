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
from .contracts import (
    CandidateInput,
    CandidateResult,
    CaseScenario,
    ConditionalRecommendation,
    DecisionCaseInput,
    DecisionCaseResult,
    Issue,
    MetricDelta,
    ParsedDecisionCase,
)
from .json_io import (
    calculate_voyage_json,
    decision_case_result_to_dict,
    parse_component,
    parse_decision_case,
)
from .issues import issue_from_exception
from .case_calculator import (
    calculate_baseline_scenario,
    calculate_decision_case,
    calculate_parsed_decision_case,
)
from .case_comparison import build_case_scenarios, build_recommendations, metric_delta
from .constraints import calculate_constraints, calculate_minimum_target_ratio
from .economics import (
    build_economics,
    calculate_candidate_break_even_price,
    calculate_eua_break_even_price,
    calculate_value_switch_points,
    compliance_improvement_tco2e,
)
from .reports import voyage_result_to_csv, write_voyage_csv, voyage_result_to_pdf, write_voyage_pdf
from .custom_factors import resolve_custom_factor
from .factors import builtin_path_ids, get_definition, get_builtin_factor, resolve_factor
from .factors import resolve_factor_trace, resolve_factor_with_trace
from .provenance import (
    CALCULATION_SPEC_VERSION,
    FUEL_FACTOR_VERSION,
    PORT_RULE_VERSION,
    FactorResolutionTrace,
    PortDecision,
    ResultProvenance,
)

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
    "CandidateInput",
    "CandidateResult",
    "CaseScenario",
    "ConditionalRecommendation",
    "DecisionCaseInput",
    "DecisionCaseResult",
    "Issue",
    "MetricDelta",
    "ParsedDecisionCase",
    "calculate_voyage_json",
    "decision_case_result_to_dict",
    "issue_from_exception",
    "calculate_baseline_scenario",
    "calculate_decision_case",
    "calculate_parsed_decision_case",
    "build_case_scenarios",
    "build_recommendations",
    "metric_delta",
    "parse_component",
    "parse_decision_case",
    "calculate_constraints",
    "calculate_minimum_target_ratio",
    "build_economics",
    "calculate_candidate_break_even_price",
    "calculate_eua_break_even_price",
    "calculate_value_switch_points",
    "compliance_improvement_tco2e",
    "voyage_result_to_csv",
    "write_voyage_csv",
    "voyage_result_to_pdf",
    "write_voyage_pdf",
    "resolve_custom_factor",
    "builtin_path_ids",
    "get_definition",
    "get_builtin_factor",
    "resolve_factor",
    "resolve_factor_trace",
    "resolve_factor_with_trace",
    "PortDecision",
    "FactorResolutionTrace",
    "ResultProvenance",
    "CALCULATION_SPEC_VERSION",
    "FUEL_FACTOR_VERSION",
    "PORT_RULE_VERSION",
]
