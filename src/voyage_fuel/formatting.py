"""Presentation-only display precision shared by page and report layers."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class DisplayConfig:
    """Decimal places for rendered values; never used by calculation code."""

    fuel_mass_decimals: int = 3
    energy_decimals: int = 3
    ratio_decimals: int = 4
    scope_rate_decimals: int = 2
    intensity_decimals: int = 4
    gas_decimals: int = 6
    price_decimals: int = 2
    factor_decimals: int = 9

    # Short aliases make the config convenient for UI callers while retaining
    # explicit names in serialized settings.
    @property
    def fuel_mass(self) -> int:
        return self.fuel_mass_decimals

    @property
    def mass_decimals(self) -> int:
        return self.fuel_mass_decimals

    @property
    def ratios(self) -> int:
        return self.ratio_decimals

    @property
    def scope_rates(self) -> int:
        return self.scope_rate_decimals

    @property
    def ghgi_decimals(self) -> int:
        return self.intensity_decimals

    @property
    def prices_decimals(self) -> int:
        return self.price_decimals

    def __post_init__(self) -> None:
        for name in (
            "fuel_mass_decimals", "energy_decimals", "ratio_decimals",
            "scope_rate_decimals", "intensity_decimals", "gas_decimals",
            "price_decimals", "factor_decimals",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")


_ALIASES = {
    "mass": "fuel_mass_decimals", "fuel_mass": "fuel_mass_decimals",
    "energy": "energy_decimals", "energy_gj": "energy_decimals", "ratio": "ratio_decimals",
    "scope_rate": "scope_rate_decimals", "scope": "scope_rate_decimals",
    "ghgi": "intensity_decimals", "wt_t": "intensity_decimals",
    "ttw": "intensity_decimals", "tt_w": "intensity_decimals",
    "target": "intensity_decimals", "intensity": "intensity_decimals",
    "gas": "gas_decimals", "eua": "gas_decimals", "compliance": "gas_decimals",
    "price": "price_decimals", "cost": "price_decimals", "penalty": "price_decimals",
    "factor": "factor_decimals",
}


def format_for_display(value: Any, kind: str | DisplayConfig = "generic", config: DisplayConfig | str | None = None) -> str:
    """Render a value according to *config* without mutating or recalculating it.

    ``ratio`` and ``scope_rate`` are stored as fractions and rendered as
    percentage points. Other values are rendered in their supplied unit.
    Decimal output is intentionally fixed-point and factors omit insignificant
    trailing zeroes.
    """
    # Accept both format_for_display(value, kind, config) and the natural
    # format_for_display(value, config, kind) ordering for UI integrations.
    if isinstance(kind, DisplayConfig):
        kind, config = (config if isinstance(config, str) else "generic"), kind
    if isinstance(config, str):
        kind, config = config, None
    if value is None:
        return ""
    if not isinstance(value, Decimal):
        return str(value)
    config = config or DisplayConfig()
    normalized_kind = str(kind).lower()
    field_name = _ALIASES.get(normalized_kind)
    places = getattr(config, field_name, 6) if field_name else 6
    if normalized_kind in {"ratio", "scope_rate", "scope"}:
        rendered = value * Decimal("100")
    elif normalized_kind in {"energy", "energy_gj"}:
        # Domain energy values are stored in MJ; display specification uses GJ.
        rendered = value / Decimal("1000")
    else:
        rendered = value
    text = format(rendered, f".{places}f")
    if normalized_kind == "factor":
        text = text.rstrip("0").rstrip(".")
    return text
