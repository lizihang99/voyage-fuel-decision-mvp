"""EU ETS and FuelEU emission primitives."""

from decimal import Decimal
from typing import Optional, Sequence

from .models import EtsResult, FuelAmount, FuelEuResult, ScopeRates


GRAMS_PER_TONNE = Decimal("1000000")
ETS_GWP_CH4 = Decimal("28")
ETS_GWP_N2O = Decimal("265")
FUELEU_GWP_CH4 = Decimal("25")
FUELEU_GWP_N2O = Decimal("298")
FUELEU_REFERENCE = Decimal("91.16")
TONNES_TO_GRAMS = Decimal("1000000")


def calculate_eu_ets(
    year: int,
    amounts: Sequence[FuelAmount],
    scope: ScopeRates,
    eua_price_per_tco2e: Optional[Decimal],
) -> EtsResult:
    co2_g = Decimal("0")
    ch4_g = Decimal("0")
    n2o_g = Decimal("0")
    zero_rating_status: dict[str, str] = {}
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
        qualification = amount.component.qualification_status.upper()
        if eligible > Decimal("0") and factor.biomass_eligible and qualification in {"ASSUMED_ELIGIBLE", "VERIFIED_ELIGIBLE"}:
            zero_rating_status[factor.path_id] = "ZERO_RATED"
        elif factor.biomass_eligible and qualification not in {"ASSUMED_ELIGIBLE", "VERIFIED_ELIGIBLE"}:
            zero_rating_status[factor.path_id] = "ZERO_RATING_NOT_VERIFIED"
        elif factor.biomass_eligible:
            zero_rating_status[factor.path_id] = "NOT_ZERO_RATED"
        else:
            zero_rating_status[factor.path_id] = "NOT_ZERO_RATED"
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
    mrv_raw_by_gas = {"CO2": co2_t, "CH4": ch4_t, "N2O": n2o_t}
    excluded_from_ets_surrender = {
        gas: gas not in included_gases for gas in ("CO2", "CH4", "N2O")
    }
    ets_scope_by_gas = {
        gas: (scope.eu_ets_effective_rate if gas in included_gases else Decimal("0"))
        for gas in ("CO2", "CH4", "N2O")
    }
    return EtsResult(
        raw_co2_t=co2_t,
        raw_ch4_t=ch4_t,
        raw_n2o_t=n2o_t,
        mrv_raw_co2e_t=raw_co2e_t,
        included_gases=included_gases,
        ets_co2e_pre_scope_t=pre_scope,
        euas_required=euas,
        eua_cost=eua_cost,
        mrv_raw_by_gas=mrv_raw_by_gas,
        ets_scope_by_gas=ets_scope_by_gas,
        excluded_from_ets_surrender=excluded_from_ets_surrender,
        s_ets_geo=scope.eu_ets_scope_rate,
        s_ets_surrender=scope.eu_ets_surrender_rate,
        s_ets_effective=scope.eu_ets_effective_rate,
        zero_rating_status_by_fuel_component=zero_rating_status,
    )


def _fueleu_target(year: int) -> Optional[Decimal]:
    if year in range(2025, 2030):
        return Decimal("89.3368")
    if year == 2030:
        return Decimal("85.6904")
    return None


def _ttw_mass_eq(amount: FuelAmount) -> Decimal:
    factor = amount.component.factor
    combustion_eq = (
        factor.cf_co2_g_per_g
        + FUELEU_GWP_CH4 * factor.cf_ch4_g_per_g
        + FUELEU_GWP_N2O * factor.cf_n2o_g_per_g
    )
    if factor.methane_slip_applicable:
        if factor.cslip_percent is None:
            raise ValueError(f"Cslip required for methane-slip path: {factor.path_id}")
        p = factor.cslip_percent / Decimal("100")
    else:
        p = Decimal("0")
    slip_eq = (
        factor.csf_co2_g_per_g
        + FUELEU_GWP_CH4 * factor.csf_ch4_g_per_g
        + FUELEU_GWP_N2O * factor.csf_n2o_g_per_g
    )
    return (Decimal("1") - p) * combustion_eq + p * slip_eq


def calculate_fueleu(
    year: int,
    amounts: Sequence[FuelAmount],
    fuel_eu_scope_rate: Optional[Decimal],
) -> FuelEuResult:
    physical_energy = Decimal("0")
    denominator_rwd = Decimal("0")
    wt_t_numerator = Decimal("0")
    tt_w_numerator = Decimal("0")
    for amount in amounts:
        mass_g = amount.mass_tonnes * GRAMS_PER_TONNE
        factor = amount.component.factor
        physical_energy += mass_g * factor.lcv_mj_per_g
        denominator_rwd += mass_g * factor.lcv_mj_per_g * factor.rwd
        wt_t_numerator += mass_g * factor.lcv_mj_per_g * factor.wt_t_g_per_mj
        tt_w_numerator += mass_g * _ttw_mass_eq(amount)

    if year == 2024 or fuel_eu_scope_rate is None:
        return FuelEuResult(
            status="NOT_YET_APPLICABLE" if year == 2024 else "NOT_APPLICABLE",
            physical_energy_mj=physical_energy,
            scoped_energy_mj=Decimal("0"),
            denominator_rwd_mj=None,
            wt_t_intensity_g_per_mj=None,
            tt_w_intensity_g_per_mj=None,
            ghgi_actual_g_per_mj=None,
            target_g_per_mj=None,
            compliance_balance_g=None,
            compliance_balance_t=None,
            indicative_penalty_eur=None,
        )

    scope = fuel_eu_scope_rate
    scoped_energy = physical_energy * scope
    if scope == Decimal("0"):
        return FuelEuResult(
            status="OUT_OF_SCOPE",
            physical_energy_mj=physical_energy,
            scoped_energy_mj=Decimal("0"),
            denominator_rwd_mj=None,
            wt_t_intensity_g_per_mj=None,
            tt_w_intensity_g_per_mj=None,
            ghgi_actual_g_per_mj=None,
            target_g_per_mj=None,
            compliance_balance_g=None,
            compliance_balance_t=None,
            indicative_penalty_eur=None,
        )
    if denominator_rwd <= Decimal("0"):
        raise ValueError("FuelEU denominator must be positive")
    wt_t_intensity = wt_t_numerator / denominator_rwd
    tt_w_intensity = tt_w_numerator / denominator_rwd
    ghgi = wt_t_intensity + tt_w_intensity
    target = _fueleu_target(year)
    if target is None:
        raise ValueError(f"Unsupported FuelEU year: {year}")
    balance_g = (target - ghgi) * scoped_energy
    status = "SURPLUS_ESTIMATE" if balance_g > 0 else "DEFICIT_ESTIMATE" if balance_g < 0 else "ON_TARGET_ESTIMATE"
    penalty = None
    if balance_g < 0:
        penalty = abs(balance_g) / (ghgi * Decimal("41000")) * Decimal("2400")
    return FuelEuResult(
        status=status,
        physical_energy_mj=physical_energy,
        scoped_energy_mj=scoped_energy,
        denominator_rwd_mj=denominator_rwd,
        wt_t_intensity_g_per_mj=wt_t_intensity,
        tt_w_intensity_g_per_mj=tt_w_intensity,
        ghgi_actual_g_per_mj=ghgi,
        target_g_per_mj=target,
        compliance_balance_g=balance_g,
        compliance_balance_t=balance_g / TONNES_TO_GRAMS,
        indicative_penalty_eur=penalty,
    )
