"""Immutable provenance contracts for calculation results."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable


CALCULATION_SPEC_VERSION = "2026-08-07"
FUEL_FACTOR_VERSION = "2026-08-31-audit"
PORT_RULE_VERSION = "2026-07-23"


@dataclass(frozen=True)
class PortDecision:
    """Formal port-table identity used when determining scope."""

    unlocode: str
    port_name: str
    eu_ets_identity: str
    fuel_eu_identity: str
    rule_source_id: str
    source_version: str

    @property
    def eu_ets_status(self) -> str:
        return self.eu_ets_identity

    @property
    def fuel_eu_status(self) -> str:
        return self.fuel_eu_identity


@dataclass(frozen=True)
class FactorResolutionTrace:
    """The requested factor path and the boundary resolution decision."""

    requested_path_id: str
    resolved_path_id: str
    resolution_reason: str
    qualification_status: str
    factor_status: str
    factor: object
    source_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResultProvenance:
    """Provenance carried by each decision-case result."""

    departure: PortDecision | None
    arrival: PortDecision | None
    eu_ets_reason: str | None
    fuel_eu_reason: str | None
    eu_ets_geographic_rate: Decimal | None
    eu_ets_surrender_rate: Decimal | None
    fuel_eu_rate: Decimal | None
    factor_resolutions: tuple[FactorResolutionTrace, ...]
    source_ids: tuple[str, ...]
    status: str = "AVAILABLE"
    calculation_spec_version: str = CALCULATION_SPEC_VERSION
    fuel_factor_version: str = FUEL_FACTOR_VERSION
    port_rule_version: str = PORT_RULE_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "factor_resolutions", tuple(self.factor_resolutions))
        object.__setattr__(self, "source_ids", tuple(dict.fromkeys(str(item) for item in self.source_ids if item)))
        if self.eu_ets_geographic_rate is not None:
            object.__setattr__(self, "eu_ets_geographic_rate", Decimal(str(self.eu_ets_geographic_rate)))
        if self.eu_ets_surrender_rate is not None:
            object.__setattr__(self, "eu_ets_surrender_rate", Decimal(str(self.eu_ets_surrender_rate)))
        if self.fuel_eu_rate is not None:
            object.__setattr__(self, "fuel_eu_rate", Decimal(str(self.fuel_eu_rate)))

    @property
    def port_decisions(self) -> tuple[PortDecision | None, PortDecision | None]:
        return (self.departure, self.arrival)

    @property
    def factor_traces(self) -> tuple[FactorResolutionTrace, ...]:
        return self.factor_resolutions

    @property
    def source_id_collection(self) -> tuple[str, ...]:
        return self.source_ids


def deduplicate_source_ids(values: Iterable[str]) -> tuple[str, ...]:
    """Return source IDs in first-seen order without duplicates."""
    return tuple(dict.fromkeys(str(value) for value in values if str(value).strip()))
