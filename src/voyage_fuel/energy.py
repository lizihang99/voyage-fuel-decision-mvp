"""Energy-conserving mass blending and fuel cost calculations."""

from decimal import Decimal
from typing import Optional

from .models import FuelComponent, FuelFactor, as_decimal
from .numerics import decimal_ratio, exact_product, exact_complement
from fractions import Fraction


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

    exact_ratio = Fraction(blend_ratio)
    exact_lcv = ((1 - exact_ratio) * Fraction(baseline.factor.lcv_mj_per_g)
                 + exact_ratio * Fraction(candidate.factor.lcv_mj_per_g))
    # One finite common total; multiply both fractions exactly so their mass
    # ratio remains precisely the requested decimal, even at a target boundary.
    total_mass_tonnes = decimal_ratio(Fraction(energy) / exact_lcv / 1000000)
    return (
        exact_product(total_mass_tonnes, exact_complement(blend_ratio)),
        exact_product(total_mass_tonnes, blend_ratio),
    )


def fuel_cost(mass_tonnes: Decimal, component: FuelComponent) -> Optional[Decimal]:
    if component.price_per_tonne is None:
        return None
    return as_decimal(mass_tonnes) * component.price_per_tonne


def sum_known_costs(*costs: Optional[Decimal]) -> Optional[Decimal]:
    if any(cost is None for cost in costs):
        return None
    return sum((as_decimal(cost) for cost in costs), ZERO)
