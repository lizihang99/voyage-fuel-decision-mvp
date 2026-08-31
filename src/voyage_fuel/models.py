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

    def __post_init__(self) -> None:
        for name in ("lcv_mj_per_g", "wt_t_g_per_mj", "cf_co2_g_per_g", "cf_ch4_g_per_g", "cf_n2o_g_per_g", "cslip_percent", "rwd"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, as_decimal(value))


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

    def __post_init__(self) -> None:
        object.__setattr__(self, "baseline_mass_tonnes", as_decimal(self.baseline_mass_tonnes))
        object.__setattr__(self, "max_blend_ratio", as_decimal(self.max_blend_ratio))
        object.__setattr__(
            self,
            "specified_blend_ratios",
            tuple(as_decimal(ratio) for ratio in self.specified_blend_ratios),
        )
        if self.baseline_mass_tonnes <= ZERO:
            raise ValueError("baseline_mass_tonnes must be positive")
        if not ZERO <= self.max_blend_ratio <= ONE:
            raise ValueError("max_blend_ratio must be between 0 and 1")
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


@dataclass(frozen=True)
class VoyageResult:
    baseline_energy_mj: Decimal
    scope_rates: ScopeRates
    scenarios: tuple[ScenarioResult, ...]
