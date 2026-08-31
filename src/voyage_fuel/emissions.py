"""EU ETS and FuelEU emission primitives."""

from decimal import Decimal
from typing import Optional, Sequence

from .models import EtsResult, FuelAmount, ScopeRates


GRAMS_PER_TONNE = Decimal("1000000")
ETS_GWP_CH4 = Decimal("28")
ETS_GWP_N2O = Decimal("265")


def calculate_eu_ets(
    year: int,
    amounts: Sequence[FuelAmount],
    scope: ScopeRates,
    eua_price_per_tco2e: Optional[Decimal],
) -> EtsResult:
    co2_g = Decimal("0")
    ch4_g = Decimal("0")
    n2o_g = Decimal("0")
    for amount in amounts:
        factor = amount.component.factor
        mass_g = amount.mass_tonnes * GRAMS_PER_TONNE
        if factor.methane_slip_applicable:
            if factor.cslip_percent is None:
                raise ValueError(f"Cslip required for methane-slip path: {factor.path_id}")
            non_combusted_g = mass_g * factor.cslip_percent / Decimal("100")
        else:
            non_combusted_g = Decimal("0")
        burned_g = mass_g - non_combusted_g
        eligible = amount.component.eligible_biomass_fraction
        co2_g += burned_g * factor.cf_co2_g_per_g * (Decimal("1") - eligible)
        ch4_g += burned_g * factor.cf_ch4_g_per_g
        n2o_g += burned_g * factor.cf_n2o_g_per_g
        if factor.methane_slip_applicable:
            ch4_g += non_combusted_g

    co2_t = co2_g / GRAMS_PER_TONNE
    ch4_t = ch4_g / GRAMS_PER_TONNE
    n2o_t = n2o_g / GRAMS_PER_TONNE
    raw_co2e_t = co2_t + ETS_GWP_CH4 * ch4_t + ETS_GWP_N2O * n2o_t
    if year in (2024, 2025):
        included_gases = ("CO2",)
        pre_scope = co2_t
    elif year >= 2026:
        included_gases = ("CO2", "CH4", "N2O")
        pre_scope = raw_co2e_t
    else:
        raise ValueError(f"Unsupported reporting year: {year}")
    euas = pre_scope * scope.eu_ets_effective_rate
    eua_cost = None if eua_price_per_tco2e is None else euas * eua_price_per_tco2e
    return EtsResult(
        raw_co2_t=co2_t,
        raw_ch4_t=ch4_t,
        raw_n2o_t=n2o_t,
        mrv_raw_co2e_t=raw_co2e_t,
        included_gases=included_gases,
        ets_co2e_pre_scope_t=pre_scope,
        euas_required=euas,
        eua_cost=eua_cost,
    )
