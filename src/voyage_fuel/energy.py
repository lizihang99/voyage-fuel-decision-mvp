"""Energy-conserving mass blending and fuel cost calculations."""

from decimal import Decimal
from typing import Optional

from .models import FuelComponent, FuelFactor, as_decimal


GRAMS_PER_TONNE = Decimal("1000000")
ZERO = Decimal("0")
ONE = Decimal("1")


def baseline_energy_mj(mass_tonnes: Decimal, factor: FuelFactor) -> Decimal:
    mass = as_decimal(mass_tonnes)
    if mass <= ZERO:
        raise ValueError("mass_tonnes must be positive")
    return mass * GRAMS_PER_TONNE * factor.lcv_mj_per_g


def blend_masses_tonnes(
    baseline_energy_mj: Decimal,
    baseline: FuelComponent,
    candidate: FuelComponent,
    ratio: Decimal,
) -> tuple[Decimal, Decimal]:
    energy = as_decimal(baseline_energy_mj)
    blend_ratio = as_decimal(ratio)
    if energy <= ZERO:
        raise ValueError("baseline_energy_mj must be positive")
    if not ZERO <= blend_ratio <= ONE:
        raise ValueError("ratio must be between 0 and 1")

    weighted_lcv = (
        (ONE - blend_ratio) * baseline.factor.lcv_mj_per_g
        + blend_ratio * candidate.factor.lcv_mj_per_g
    )
    if weighted_lcv <= ZERO:
        raise ValueError("weighted LCV must be positive")

    total_mass_g = energy / weighted_lcv
    return (
        total_mass_g * (ONE - blend_ratio) / GRAMS_PER_TONNE,
        total_mass_g * blend_ratio / GRAMS_PER_TONNE,
    )


def fuel_cost(mass_tonnes: Decimal, component: FuelComponent) -> Optional[Decimal]:
    if component.price_per_tonne is None:
        return None
    return as_decimal(mass_tonnes) * component.price_per_tonne


def sum_known_costs(*costs: Optional[Decimal]) -> Optional[Decimal]:
    if any(cost is None for cost in costs):
        return None
    return sum((as_decimal(cost) for cost in costs), ZERO)
