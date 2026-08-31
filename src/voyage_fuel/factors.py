"""First-release built-in fuel factors.

The full 36-path catalog remains governed by the factor-library specification;
this slice registers only the paths needed by the initial calculation vectors.
"""

from decimal import Decimal

from .models import FuelFactor


def _factor(
    path_id: str,
    lcv: str,
    wt_t: str,
    co2: str,
    ch4: str = "0.00005",
    n2o: str = "0.00018",
) -> FuelFactor:
    return FuelFactor(
        path_id=path_id,
        lcv_mj_per_g=Decimal(lcv),
        wt_t_g_per_mj=Decimal(wt_t),
        cf_co2_g_per_g=Decimal(co2),
        cf_ch4_g_per_g=Decimal(ch4),
        cf_n2o_g_per_g=Decimal(n2o),
        rwd=Decimal("1"),
        cslip_percent=None,
        methane_slip_applicable=False,
        factor_status="FIXED",
    )


_FACTORS = {
    "MDO": _factor("MDO", "0.0427", "14.4", "3.206"),
    "MGO": _factor("MGO", "0.0427", "14.4", "3.206"),
    "HFO": _factor("HFO", "0.0405", "13.5", "3.114"),
    "UCO_FAME": FuelFactor(
        path_id="UCO_FAME",
        lcv_mj_per_g=Decimal("0.037"),
        wt_t_g_per_mj=Decimal("14.9") - Decimal("2.834") / Decimal("0.037"),
        cf_co2_g_per_g=Decimal("2.834"),
        cf_ch4_g_per_g=Decimal("0.00005"),
        cf_n2o_g_per_g=Decimal("0.00018"),
        rwd=Decimal("1"),
        cslip_percent=None,
        methane_slip_applicable=False,
        factor_status="FIXED",
    ),
}


def get_builtin_factor(path_id: str) -> FuelFactor:
    """Return a registered factor or fail without inventing a placeholder."""
    normalized = str(path_id).strip().upper()
    try:
        return _FACTORS[normalized]
    except KeyError as exc:
        raise KeyError(f"Unsupported first-slice fuel path: {path_id}") from exc


def builtin_path_ids() -> tuple[str, ...]:
    return tuple(_FACTORS)
