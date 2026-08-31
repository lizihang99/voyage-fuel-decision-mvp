"""JSON boundary for validating the calculation kernel without a web framework."""

import json
from dataclasses import asdict, is_dataclass
from decimal import Decimal
from typing import Any, Mapping

from .calculator import calculate_voyage
from .factors import get_builtin_factor
from .models import FuelComponent, VoyageInput


def _component(payload: Mapping[str, Any]) -> FuelComponent:
    return FuelComponent(
        factor=get_builtin_factor(payload["pathId"]),
        price_per_tonne=None if payload.get("pricePerTonne") is None else Decimal(str(payload["pricePerTonne"])),
        eligible_biomass_fraction=Decimal(str(payload.get("eligibleBiomassFraction", "0"))),
        qualification_status=str(payload.get("qualificationStatus", "NOT_DEMONSTRATED")),
    )


def _request(payload: Mapping[str, Any]) -> VoyageInput:
    baseline = payload.get("baseline")
    candidate = payload.get("candidate")
    if not isinstance(baseline, Mapping) or not isinstance(candidate, Mapping):
        raise ValueError("baseline and candidate objects are required")
    eua_price = payload.get("euaPricePerTCO2e")
    return VoyageInput(
        report_year=int(payload["reportYear"]),
        departure_port=str(payload["departurePort"]),
        arrival_port=str(payload["arrivalPort"]),
        baseline_component=_component(baseline),
        baseline_mass_tonnes=Decimal(str(baseline["massTonnes"])),
        candidate_component=_component(candidate),
        eua_price_per_tco2e=None if eua_price is None else Decimal(str(eua_price)),
        specified_blend_ratios=tuple(Decimal(str(value)) for value in payload.get("specifiedBlendRatios", ())),
        max_blend_ratio=Decimal(str(payload.get("maxBlendRatio", "1"))),
        candidate_allows_pure_use=bool(payload.get("candidateAllowsPureUse", False)),
    )


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if is_dataclass(value):
        return {key: _json_value(item) for key, item in asdict(value).items()}
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    return value


def calculate_voyage_json(payload: str | Mapping[str, Any]) -> str:
    decoded = json.loads(payload) if isinstance(payload, str) else payload
    if not isinstance(decoded, Mapping):
        raise ValueError("JSON root must be an object")
    return json.dumps(_json_value(calculate_voyage(_request(decoded))), ensure_ascii=False, separators=(",", ":"))
