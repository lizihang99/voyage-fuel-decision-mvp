"""JSON boundary for validating the calculation kernel without a web framework."""

import json
from dataclasses import asdict, is_dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from .calculator import calculate_voyage
from .contracts import CandidateInput, DecisionCaseInput, DecisionCaseResult, ParsedDecisionCase
from .custom_factors import resolve_custom_factor
from .factors import resolve_factor
from .issues import issue_from_exception
from .models import FuelComponent, VoyageInput


def _strict_bool(value: Any, *, field: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"MISSING_REQUIRED_FACTOR: {field} must be a boolean")
    return value


def parse_component(payload: Mapping[str, Any]) -> FuelComponent:
    """Parse a fuel component using decimal-safe factor resolution."""
    if not isinstance(payload, Mapping):
        raise ValueError("MISSING_REQUIRED_FACTOR: component must be an object")
    qualification = str(payload.get("qualificationStatus", "NOT_DEMONSTRATED"))
    e_value = payload.get("e")
    eu_value = payload.get("eu")
    cslip = payload.get("cslip")
    verified_wt = payload.get("verifiedWtT")
    path_id = str(payload["pathId"])
    custom = _strict_bool(payload.get("custom", False), field="custom")
    if not custom:
        try:
            factor = resolve_factor(
                path_id, qualification_status=qualification,
                e_value=None if e_value is None else Decimal(str(e_value)),
                eu_value=None if eu_value is None else Decimal(str(eu_value)),
                cslip_percent=None if cslip is None else Decimal(str(cslip)),
                verified_wt_t=None if verified_wt is None else Decimal(str(verified_wt)),
            )
        except KeyError:
            custom = True
    if custom:
        factor = resolve_custom_factor(payload)
    return FuelComponent(
        factor=factor,
        price_per_tonne=None if payload.get("pricePerTonne") is None else Decimal(str(payload["pricePerTonne"])),
        eligible_biomass_fraction=Decimal(str(payload.get("eligibleBiomassFraction", "0"))),
        qualification_status=str(payload.get("qualificationStatus", "NOT_DEMONSTRATED")),
    )


# Kept private alias for compatibility with callers that imported this module internals.
_component = parse_component


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
        baseline_component=parse_component(baseline),
        baseline_mass_tonnes=Decimal(str(baseline["massTonnes"])),
        candidate_component=parse_component(candidate),
        eua_price_per_tco2e=None if eua_price is None else Decimal(str(eua_price)),
        specified_blend_ratios=tuple(Decimal(str(value)) for value in payload.get("specifiedBlendRatios", ())),
        max_blend_ratio=Decimal(str(payload.get("maxBlendRatio", "1"))),
        candidate_allows_pure_use=_strict_bool(
            payload.get("candidateAllowsPureUse", False), field="candidateAllowsPureUse"
        ),
        candidate_supply_tonnes=(
            None if payload.get("candidateSupplyTonnes") is None
            else Decimal(str(payload["candidateSupplyTonnes"]))
        ),
        incremental_budget=(
            None if payload.get("incrementalBudget") is None
            else Decimal(str(payload["incrementalBudget"]))
        ),
        compliance_improvement_value=(
            None if payload.get("complianceImprovementValue") is None
            else Decimal(str(payload["complianceImprovementValue"]))
        ),
    )


def _decimal(value: Any, *, field: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"MISSING_REQUIRED_FACTOR: {field} must be numeric")
    try:
        return Decimal(str(value))
    except Exception as error:
        raise ValueError(f"MISSING_REQUIRED_FACTOR: {field} must be numeric") from error


def _decimal_sequence(value: Any, *, field: str) -> tuple[Decimal, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ValueError(f"INVALID_BLEND_RATIO: {field} must be an array")
    return tuple(_decimal(item, field=f"{field}[{index}]") for index, item in enumerate(value))


def _parse_candidate(payload: Mapping[str, Any]) -> CandidateInput:
    candidate_id = payload.get("candidateId")
    if not isinstance(candidate_id, str):
        raise ValueError("INVALID_CANDIDATE_ID: candidateId is required")
    return CandidateInput(
        candidate_id=candidate_id,
        component=parse_component(payload),
        specified_blend_ratios=_decimal_sequence(
            payload.get("specifiedBlendRatios", ()), field="specifiedBlendRatios"
        ),
        max_blend_ratio=_decimal(payload.get("maxBlendRatio", "1"), field="maxBlendRatio"),
        allows_pure_use=_strict_bool(
            payload.get("candidateAllowsPureUse", payload.get("allowsPureUse", False)),
            field="candidateAllowsPureUse",
        ),
        supply_tonnes=(
            None if payload.get("candidateSupplyTonnes") is None
            else _decimal(payload["candidateSupplyTonnes"], field="candidateSupplyTonnes")
        ),
        incremental_budget=(
            None if payload.get("incrementalBudget") is None
            else _decimal(payload["incrementalBudget"], field="incrementalBudget")
        ),
        compliance_improvement_value=(
            None if payload.get("complianceImprovementValue") is None
            else _decimal(payload["complianceImprovementValue"], field="complianceImprovementValue")
        ),
    )


def _case_issue(error: Exception, field: str) -> ParsedDecisionCase:
    return ParsedDecisionCase(request=None, issues=(issue_from_exception(error, scope="CASE", field=field),))


def parse_decision_case(payload: str | Mapping[str, Any]) -> ParsedDecisionCase:
    """Parse a case request while isolating invalid candidate entries."""
    try:
        decoded = json.loads(payload) if isinstance(payload, str) else payload
    except (TypeError, json.JSONDecodeError) as error:
        return _case_issue(error, "payload")
    if not isinstance(decoded, Mapping):
        return _case_issue(ValueError("MISSING_REQUIRED_FACTOR: JSON root must be an object"), "payload")

    try:
        confirmation_value = decoded.get("adjacentValidPortOfCallConfirmed", False)
        if type(confirmation_value) is not bool:
            raise ValueError(
                "PORT_OF_CALL_CONFIRMATION_REQUIRED: adjacent Port of Call confirmation must be a boolean"
            )
        confirmation = confirmation_value
        if not confirmation:
            raise ValueError(
                "PORT_OF_CALL_CONFIRMATION_REQUIRED: adjacent Port of Call confirmation is required"
            )
        report_year = decoded["reportYear"]
        if type(report_year) is not int:
            raise ValueError("INVALID_YEAR: reportYear must be an integer")
        baseline = decoded.get("baseline")
        if not isinstance(baseline, Mapping):
            raise ValueError("MISSING_REQUIRED_FACTOR: baseline must be an object")
        candidates_payload = decoded.get("candidates")
        if not isinstance(candidates_payload, (list, tuple)):
            raise ValueError("MISSING_REQUIRED_FACTOR: candidates must be an array")
        candidate_ids = [
            item.get("candidateId")
            for item in candidates_payload
            if isinstance(item, Mapping) and isinstance(item.get("candidateId"), str)
        ]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("DUPLICATE_CANDIDATE_ID: candidateId values must be unique")
        baseline_component = parse_component(baseline)
        baseline_mass = _decimal(baseline["massTonnes"], field="baseline.massTonnes")
        eua_price = decoded.get("euaPricePerTCO2e")
        eua_price_decimal = None if eua_price is None else _decimal(eua_price, field="euaPricePerTCO2e")
    except (InvalidOperation, KeyError, TypeError, ValueError) as error:
        field = "baseline" if "baseline" in str(error).lower() else "case"
        return _case_issue(error, field)

    candidates = []
    issues = []
    for index, candidate_payload in enumerate(candidates_payload):
        candidate_id = (
            candidate_payload.get("candidateId")
            if isinstance(candidate_payload, Mapping) and isinstance(candidate_payload.get("candidateId"), str)
            else None
        )
        try:
            if not isinstance(candidate_payload, Mapping):
                raise ValueError("INVALID_CANDIDATE_ID: candidate must be an object")
            candidates.append(_parse_candidate(candidate_payload))
        except (InvalidOperation, KeyError, TypeError, ValueError) as error:
            issues.append(
                issue_from_exception(
                    error,
                    scope="CANDIDATE",
                    field=f"candidates[{index}]",
                    candidate_id=candidate_id,
                    component=(
                        str(candidate_payload.get("pathId"))
                        if isinstance(candidate_payload, Mapping) and candidate_payload.get("pathId") is not None
                        else None
                    ),
                )
            )

    try:
        request = DecisionCaseInput(
            report_year=report_year,
            departure_port=str(decoded["departurePort"]),
            arrival_port=str(decoded["arrivalPort"]),
            adjacent_valid_port_of_call_confirmed=confirmation,
            currency=decoded["currency"],
            baseline_component=baseline_component,
            baseline_mass_tonnes=baseline_mass,
            eua_price_per_tco2e=eua_price_decimal,
            candidates=tuple(candidates),
        )
    except (InvalidOperation, KeyError, TypeError, ValueError) as error:
        return _case_issue(error, "case")
    return ParsedDecisionCase(request=request, issues=tuple(issues))


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


def decision_case_result_to_dict(result: DecisionCaseResult) -> dict[str, Any]:
    """Convert a decision-case result into JSON-compatible primitive values."""
    converted = _json_value(result)
    if not isinstance(converted, dict):
        raise TypeError("result must be a DecisionCaseResult")
    return converted


def calculate_voyage_json(payload: str | Mapping[str, Any]) -> str:
    decoded = json.loads(payload) if isinstance(payload, str) else payload
    if not isinstance(decoded, Mapping):
        raise ValueError("JSON root must be an object")
    return json.dumps(_json_value(calculate_voyage(_request(decoded))), ensure_ascii=False, separators=(",", ":"))
