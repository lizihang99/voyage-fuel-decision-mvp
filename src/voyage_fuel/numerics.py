"""Exact decision arithmetic with Decimal projections at API boundaries."""
from decimal import Decimal, getcontext, localcontext, ROUND_HALF_EVEN
from fractions import Fraction


def decimal_ratio(value: Fraction, *, rounding=ROUND_HALF_EVEN) -> Decimal:
    """Project without converting through float; direction protects feasible bounds."""
    with localcontext() as ctx:
        ctx.rounding = rounding
        return Decimal(value.numerator) / Decimal(value.denominator)


def exact_product(*values: Decimal) -> Decimal:
    """Multiply finite decimals without losing mass-ratio digits."""
    with localcontext() as ctx:
        ctx.prec = max(getcontext().prec, sum(len(v.as_tuple().digits) for v in values) + 2)
        result = Decimal(1)
        for value in values:
            result *= value
        return result


def exact_complement(value: Decimal) -> Decimal:
    """1-value may need more significant digits than value (e.g. 1-1e-60)."""
    with localcontext() as ctx:
        ctx.prec = max(getcontext().prec, len(value.as_tuple().digits),
                       -value.as_tuple().exponent + 1) + 2
        return Decimal(1) - value


def exact_unit_n_d(component) -> tuple[Fraction, Fraction]:
    """FuelEU numerator per mass and rewarded energy, using exact input decimals."""
    f = component.factor
    if f.methane_slip_applicable and f.cslip_percent is None:
        raise ValueError(f"Cslip required for methane-slip path: {f.path_id}")
    slip = Fraction(f.cslip_percent) / 100 if f.methane_slip_applicable else Fraction(0)
    combustion = Fraction(f.cf_co2_g_per_g) + 25 * Fraction(f.cf_ch4_g_per_g) + 298 * Fraction(f.cf_n2o_g_per_g)
    unburned = Fraction(f.csf_co2_g_per_g) + 25 * Fraction(f.csf_ch4_g_per_g) + 298 * Fraction(f.csf_n2o_g_per_g)
    lcv = Fraction(f.lcv_mj_per_g)
    return (lcv * Fraction(f.wt_t_g_per_mj) + (1 - slip) * combustion + slip * unburned,
            lcv * Fraction(f.rwd))
