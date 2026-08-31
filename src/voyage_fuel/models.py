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
