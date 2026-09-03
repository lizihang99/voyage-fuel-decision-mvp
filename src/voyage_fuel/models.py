"""Immutable domain models for the voyage fuel calculation kernel."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")


def as_decimal(value: Decimal | int | str) -> Decimal:
    """Parse numeric input without routing it through binary float."""
    return value if isinstance(value, Decimal) else Decimal(str(value))


@dataclass(frozen=True)
class EvidenceRecord:
    """One source assertion attached to an input factor field."""

    field_name: str
    source_id: str
    source_type: str
    unit: str
    verification_status: str


@dataclass(frozen=True)
class FuelFactor:
    path_id: str
    lcv_mj_per_g: Decimal
    wt_t_g_per_mj: Decimal
    cf_co2_g_per_g: Decimal
    cf_ch4_g_per_g: Decimal
    cf_n2o_g_per_g: Decimal
    rwd: Decimal
    cslip_percent: Optional[Decimal]
    methane_slip_applicable: bool
    factor_status: str
    csf_co2_g_per_g: Decimal = ZERO
    csf_ch4_g_per_g: Decimal = ZERO
    csf_n2o_g_per_g: Decimal = ZERO
    na_fields: tuple[str, ...] = ()
    cslip_semantics: str = "NA"
    source_evidence: tuple[EvidenceRecord, ...] = ()
    requested_path_id: Optional[str] = None
    resolution_reason: Optional[str] = None
    qualification_status: Optional[str] = None
    equipment_id: Optional[str] = None
    wt_t_mode: Optional[str] = None
    factor_level: Optional[str] = None
    biomass_eligible: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "lcv_mj_per_g",
            "wt_t_g_per_mj",
            "cf_co2_g_per_g",
            "cf_ch4_g_per_g",
            "cf_n2o_g_per_g",
            "rwd",
            "csf_co2_g_per_g",
            "csf_ch4_g_per_g",
            "csf_n2o_g_per_g",
        ):
            object.__setattr__(self, field_name, as_decimal(getattr(self, field_name)))
        if self.cslip_percent is not None:
            object.__setattr__(self, "cslip_percent", as_decimal(self.cslip_percent))
        if not self.path_id:
            raise ValueError("path_id is required")
        if self.lcv_mj_per_g <= ZERO:
            raise ValueError("lcv_mj_per_g must be positive")
        if self.rwd <= ZERO:
            raise ValueError("rwd must be positive")
        if self.cslip_percent is not None and not ZERO <= self.cslip_percent <= HUNDRED:
            raise ValueError("cslip_percent must be between 0 and 100")
        object.__setattr__(self, "na_fields", tuple(self.na_fields))
        object.__setattr__(self, "source_evidence", tuple(self.source_evidence))


@dataclass(frozen=True)
class FuelDefinition:
    """Catalog metadata used to resolve a path into a calculable factor."""

    path_id: str
    equipment_id: str
    factor_level: str
    wt_t_mode: str
    lcv_mj_per_g: Optional[Decimal]
    wt_t_g_per_mj: Optional[Decimal]
    cf_co2_g_per_g: Optional[Decimal]
    cf_ch4_g_per_g: Optional[Decimal]
    cf_n2o_g_per_g: Optional[Decimal]
    cslip_percent: Optional[Decimal]
    rwd: Decimal
    fallback_path_id: Optional[str] = None
    category: str = ""
    cslip_required: bool = False
    methane_slip_applicable: bool = False
    default_e_g_per_mj: Optional[Decimal] = None
    default_eu_g_per_mj: Optional[Decimal] = None
    default_lcv_mj_per_g: Optional[Decimal] = None
    default_wt_t_g_per_mj: Optional[Decimal] = None
    default_cf_co2_g_per_g: Optional[Decimal] = None
    default_cf_ch4_g_per_g: Optional[Decimal] = None
    default_cf_n2o_g_per_g: Optional[Decimal] = None
    default_cslip_percent: Optional[Decimal] = None
    biomass_eligible: bool = False
    # Fields explicitly sourced from a default snapshot. This stays distinct
    # from values auto-filled from the formal catalog in __post_init__.
    default_fields: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        for name in (
            "lcv_mj_per_g", "wt_t_g_per_mj", "cf_co2_g_per_g", "cf_ch4_g_per_g",
            "cf_n2o_g_per_g", "cslip_percent", "rwd", "default_lcv_mj_per_g",
            "default_wt_t_g_per_mj", "default_cf_co2_g_per_g", "default_cf_ch4_g_per_g",
            "default_cf_n2o_g_per_g", "default_cslip_percent",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, as_decimal(value))
        for default_name, formal_name in (
            ("default_lcv_mj_per_g", "lcv_mj_per_g"),
            ("default_wt_t_g_per_mj", "wt_t_g_per_mj"),
            ("default_cf_co2_g_per_g", "cf_co2_g_per_g"),
            ("default_cf_ch4_g_per_g", "cf_ch4_g_per_g"),
            ("default_cf_n2o_g_per_g", "cf_n2o_g_per_g"),
            ("default_cslip_percent", "cslip_percent"),
        ):
            if getattr(self, default_name) is None and getattr(self, formal_name) is not None:
                object.__setattr__(self, default_name, getattr(self, formal_name))


@dataclass(frozen=True)
class FuelComponent:
    factor: FuelFactor
    price_per_tonne: Optional[Decimal]
    eligible_biomass_fraction: Decimal = ZERO
    qualification_status: str = "NOT_DEMONSTRATED"

    def __post_init__(self) -> None:
        if self.price_per_tonne is not None:
            object.__setattr__(self, "price_per_tonne", as_decimal(self.price_per_tonne))
            if self.price_per_tonne < ZERO:
                raise ValueError("price_per_tonne must be non-negative")
        object.__setattr__(self, "eligible_biomass_fraction", as_decimal(self.eligible_biomass_fraction))
        if not ZERO <= self.eligible_biomass_fraction <= ONE:
            raise ValueError("eligible_biomass_fraction must be between 0 and 1")
        if self.eligible_biomass_fraction != ZERO and not self.factor.biomass_eligible:
            raise ValueError("INVALID_BIOMASS_FRACTION: fuel path cannot claim eligible biomass")
        if self.qualification_status.upper() in {"NOT_DEMONSTRATED", "INELIGIBLE"} and self.eligible_biomass_fraction != ZERO:
            raise ValueError("INVALID_BIOMASS_FRACTION: qualification does not permit eligible biomass")


@dataclass(frozen=True)
class FuelAmount:
    component: FuelComponent
    mass_tonnes: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "mass_tonnes", as_decimal(self.mass_tonnes))
        if self.mass_tonnes < ZERO:
            raise ValueError("mass_tonnes must be non-negative")


@dataclass(frozen=True)
class ScopeRates:
    eu_ets_scope_rate: Decimal
    eu_ets_surrender_rate: Decimal
    eu_ets_effective_rate: Decimal
    fuel_eu_scope_rate: Optional[Decimal]
    fuel_eu_applicable: bool
    departure_port: object | None = None
    arrival_port: object | None = None
    eu_ets_reason: str | None = None
    fuel_eu_reason: str | None = None

    @property
    def departure(self) -> object | None:
        return self.departure_port

    @property
    def arrival(self) -> object | None:
        return self.arrival_port

    @property
    def port_decisions(self) -> tuple[object | None, object | None]:
        return (self.departure_port, self.arrival_port)

    def __post_init__(self) -> None:
        for field_name in (
            "eu_ets_scope_rate",
            "eu_ets_surrender_rate",
            "eu_ets_effective_rate",
        ):
            object.__setattr__(self, field_name, as_decimal(getattr(self, field_name)))
        if self.fuel_eu_scope_rate is not None:
            object.__setattr__(self, "fuel_eu_scope_rate", as_decimal(self.fuel_eu_scope_rate))


@dataclass(frozen=True)
class EtsResult:
    raw_co2_t: Decimal
    raw_ch4_t: Decimal
    raw_n2o_t: Decimal
    mrv_raw_co2e_t: Decimal
    included_gases: tuple[str, ...]
    ets_co2e_pre_scope_t: Decimal
    euas_required: Decimal
    eua_cost: Optional[Decimal]
    mrv_raw_by_gas: dict[str, Decimal] | None = None
    ets_scope_by_gas: dict[str, Decimal] | None = None
    excluded_from_ets_surrender: dict[str, bool] | None = None
    s_ets_geo: Decimal = ZERO
    s_ets_surrender: Decimal = ZERO
    s_ets_effective: Decimal = ZERO
    zero_rating_status_by_fuel_component: dict[str, str] | None = None


@dataclass(frozen=True)
class EtsFuelComponentStatus:
    path_id: str
    qualification_status: str
    eligible_biomass_fraction: Decimal
    zero_rating_status: str


@dataclass(frozen=True)
class FuelEuResult:
    status: str
    physical_energy_mj: Decimal
    scoped_energy_mj: Decimal
    denominator_rwd_mj: Optional[Decimal]
    wt_t_intensity_g_per_mj: Optional[Decimal]
    tt_w_intensity_g_per_mj: Optional[Decimal]
    ghgi_actual_g_per_mj: Optional[Decimal]
    target_g_per_mj: Optional[Decimal]
    compliance_balance_g: Optional[Decimal]
    compliance_balance_t: Optional[Decimal]
    indicative_penalty_eur: Optional[Decimal]


@dataclass(frozen=True)
class VoyageInput:
    report_year: int
    departure_port: str
    arrival_port: str
    baseline_component: FuelComponent
    baseline_mass_tonnes: Decimal
    candidate_component: FuelComponent
    eua_price_per_tco2e: Optional[Decimal]
    specified_blend_ratios: tuple[Decimal, ...] = ()
    max_blend_ratio: Decimal = ONE
    candidate_allows_pure_use: bool = False
    candidate_supply_tonnes: Optional[Decimal] = None
    incremental_budget: Optional[Decimal] = None
    compliance_improvement_value: Optional[Decimal] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "baseline_mass_tonnes", as_decimal(self.baseline_mass_tonnes))
        object.__setattr__(self, "max_blend_ratio", as_decimal(self.max_blend_ratio))
        if self.candidate_supply_tonnes is not None:
            object.__setattr__(self, "candidate_supply_tonnes", as_decimal(self.candidate_supply_tonnes))
        if self.incremental_budget is not None:
            object.__setattr__(self, "incremental_budget", as_decimal(self.incremental_budget))
        if self.compliance_improvement_value is not None:
            object.__setattr__(self, "compliance_improvement_value", as_decimal(self.compliance_improvement_value))
        object.__setattr__(
            self,
            "specified_blend_ratios",
            tuple(as_decimal(ratio) for ratio in self.specified_blend_ratios),
        )
        if self.baseline_mass_tonnes <= ZERO:
            raise ValueError("baseline_mass_tonnes must be positive")
        if not ZERO <= self.max_blend_ratio <= ONE:
            raise ValueError("max_blend_ratio must be between 0 and 1")
        if self.candidate_supply_tonnes is not None and self.candidate_supply_tonnes < ZERO:
            raise ValueError("candidate_supply_tonnes must be non-negative")
        if self.incremental_budget is not None and self.incremental_budget < ZERO:
            raise ValueError("incremental_budget must be non-negative")
        if self.compliance_improvement_value is not None and self.compliance_improvement_value < ZERO:
            raise ValueError("compliance_improvement_value must be non-negative")
        if any(not ZERO <= ratio <= self.max_blend_ratio for ratio in self.specified_blend_ratios):
            raise ValueError("specified_blend_ratios must be within max_blend_ratio")
        if self.eua_price_per_tco2e is not None:
            object.__setattr__(self, "eua_price_per_tco2e", as_decimal(self.eua_price_per_tco2e))
            if self.eua_price_per_tco2e < ZERO:
                raise ValueError("eua_price_per_tco2e must be non-negative")


@dataclass(frozen=True)
class ScenarioResult:
    ratio: Decimal
    baseline_mass_tonnes: Decimal
    candidate_mass_tonnes: Decimal
    physical_energy_mj: Decimal
    fuel_cost: Optional[Decimal]
    eu_ets: EtsResult
    fuel_eu: FuelEuResult
    model_cost: Optional[Decimal]
    execution_status: str
    constraint_status: str = "FEASIBLE"
    compliance_improvement_tco2e: Optional[Decimal] = None
    reference_adjusted_cost: Optional[Decimal] = None


@dataclass(frozen=True)
class VoyageResult:
    report_year: int
    departure_port: str
    arrival_port: str
    baseline_energy_mj: Decimal
    scope_rates: ScopeRates
    scenarios: tuple[ScenarioResult, ...]
    constraints: Optional["ConstraintResult"] = None
    economics: Optional["EconomicsResult"] = None
    baseline_factor: Optional[FuelFactor] = None
    candidate_factor: Optional[FuelFactor] = None
    baseline_qualification_status: Optional[str] = None
    candidate_qualification_status: Optional[str] = None


@dataclass(frozen=True)
class ConstraintResult:
    """Continuous blend bounds and FuelEU target search results."""

    max_blend_ratio: Decimal
    candidate_supply_tonnes: Optional[Decimal]
    incremental_budget: Optional[Decimal]
    x_budget: Optional[Decimal]
    x_supply: Optional[Decimal]
    x_cap: Decimal
    target_status: str
    x_target_min_unconstrained: Optional[Decimal]
    x_target_min: Optional[Decimal]
    x_target_min_cost: Optional[Decimal]
    x_max_improvement: Optional[Decimal]
    x_cost_min: Optional[Decimal]
    warning_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class EuaBreakEvenResult:
    value: Optional[Decimal]
    status: str


@dataclass(frozen=True)
class ValueSwitchPoint:
    from_ratio: Decimal
    to_ratio: Decimal
    value_star: Decimal


@dataclass(frozen=True)
class EconomicsResult:
    comparison_status: str
    pc_break_even: Optional[Decimal]
    pe_break_even: Optional[Decimal]
    pe_break_even_status: str
    comparison_value: Optional[Decimal]
    cost_min_ratio: Optional[Decimal]
    cost_sorted_ratios: tuple[Decimal, ...]
    switch_points: tuple[ValueSwitchPoint, ...]
    warning_codes: tuple[str, ...] = ()
