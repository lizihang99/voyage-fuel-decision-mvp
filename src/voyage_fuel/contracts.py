"""Immutable contracts for multi-candidate voyage decision cases."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping

from .models import (
    ONE,
    ZERO,
    FuelComponent,
    ScenarioResult,
    VoyageResult,
    as_decimal,
)


@dataclass(frozen=True)
class Issue:
    code: str
    scope: str
    field: str
    blocking: bool
    message: str
    candidate_id: str | None = None
    scenario_id: str | None = None
    component: str | None = None


@dataclass(frozen=True)
class CandidateInput:
    candidate_id: str
    component: FuelComponent
    specified_blend_ratios: tuple[Decimal, ...] = ()
    max_blend_ratio: Decimal = ONE
    allows_pure_use: bool = False
    supply_tonnes: Decimal | None = None
    incremental_budget: Decimal | None = None
    compliance_improvement_value: Decimal | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_id, str) or not self.candidate_id.strip():
            raise ValueError("INVALID_CANDIDATE_ID: candidate_id is required")
        object.__setattr__(self, "max_blend_ratio", as_decimal(self.max_blend_ratio))
        object.__setattr__(
            self,
            "specified_blend_ratios",
            tuple(as_decimal(ratio) for ratio in self.specified_blend_ratios),
        )
        for field_name in (
            "supply_tonnes",
            "incremental_budget",
            "compliance_improvement_value",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, as_decimal(value))
        if not ZERO <= self.max_blend_ratio <= ONE:
            raise ValueError("INVALID_BLEND_RATIO: max_blend_ratio must be between zero and one")
        if any(not ZERO <= ratio <= self.max_blend_ratio for ratio in self.specified_blend_ratios):
            raise ValueError("INVALID_BLEND_RATIO: specified_blend_ratios must be within max_blend_ratio")
        if any(
            getattr(self, field_name) is not None and getattr(self, field_name) < ZERO
            for field_name in (
                "supply_tonnes",
                "incremental_budget",
                "compliance_improvement_value",
            )
        ):
            raise ValueError("INVALID_CANDIDATE_CONSTRAINT: candidate constraints must be non-negative")

    def scenario_id(self, ratio: Decimal) -> str:
        canonical = format(as_decimal(ratio).normalize(), "f")
        return f"{self.candidate_id}@{canonical}"


@dataclass(frozen=True)
class DecisionCaseInput:
    report_year: int
    departure_port: str
    arrival_port: str
    adjacent_valid_port_of_call_confirmed: bool
    currency: str
    baseline_component: FuelComponent
    baseline_mass_tonnes: Decimal
    eua_price_per_tco2e: Decimal | None
    candidates: tuple[CandidateInput, ...]

    def __post_init__(self) -> None:
        if type(self.report_year) is not int or not 2024 <= self.report_year <= 2030:
            raise ValueError("INVALID_YEAR: report_year must be an integer from 2024 through 2030")
        object.__setattr__(self, "baseline_mass_tonnes", as_decimal(self.baseline_mass_tonnes))
        object.__setattr__(self, "candidates", tuple(self.candidates))
        if self.eua_price_per_tco2e is not None:
            object.__setattr__(self, "eua_price_per_tco2e", as_decimal(self.eua_price_per_tco2e))
        if not self.adjacent_valid_port_of_call_confirmed:
            raise ValueError("PORT_OF_CALL_CONFIRMATION_REQUIRED: adjacent Port of Call confirmation is required")
        if not isinstance(self.currency, str) or not self.currency.strip():
            raise ValueError("INVALID_CURRENCY: currency is required")
        if self.baseline_mass_tonnes <= ZERO:
            raise ValueError("INVALID_BASELINE_MASS: baseline_mass_tonnes must be positive")
        if self.eua_price_per_tco2e is not None and self.eua_price_per_tco2e < ZERO:
            raise ValueError("INVALID_EUA_PRICE: eua_price_per_tco2e must be non-negative")
        if not self.candidates:
            raise ValueError("MISSING_REQUIRED_FACTOR: at least one candidate is required")
        candidate_ids = tuple(candidate.candidate_id for candidate in self.candidates)
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("DUPLICATE_CANDIDATE_ID: candidate_id values must be unique")


@dataclass(frozen=True)
class ParsedDecisionCase:
    request: DecisionCaseInput | None
    issues: tuple[Issue, ...]


@dataclass(frozen=True)
class CandidateResult:
    candidate_id: str
    calculation_status: str
    voyage_result: VoyageResult | None
    issues: tuple[Issue, ...]


@dataclass(frozen=True)
class MetricDelta:
    absolute: Decimal | None
    delta: Decimal | None
    percent_delta: Decimal | None
    reason_code: str | None = None


@dataclass(frozen=True)
class ConditionalRecommendation:
    recommendation_id: str
    condition: str
    scenario_id: str | None
    reason: str
    assumptions: tuple[str, ...]
    status: str
    from_scenario_id: str | None = None
    to_scenario_id: str | None = None
    from_candidate_id: str | None = None
    to_candidate_id: str | None = None
    value_star: Decimal | None = None


@dataclass(frozen=True)
class CaseScenario:
    scenario_id: str
    candidate_id: str | None
    calculation_status: str
    result: ScenarioResult
    deltas: Mapping[str, MetricDelta]
    current_model_cost_rank: int | None = None


@dataclass(frozen=True)
class DecisionCaseResult:
    report_year: int
    departure_port: str
    arrival_port: str
    currency: str
    baseline_scenario: ScenarioResult | None
    candidate_results: tuple[CandidateResult, ...]
    scenarios: tuple[CaseScenario, ...]
    recommendations: tuple[ConditionalRecommendation, ...]
    issues: tuple[Issue, ...]
    provenance: object | None = None
