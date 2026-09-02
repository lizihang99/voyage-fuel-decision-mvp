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


class _InputError(ValueError):
    """Expected JSON-boundary validation failure with its exact input path."""

    def __init__(self, code: str, field: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.field = field


_STRUCTURED_ERROR_CODES = frozenset({
    "INVALID_CSLIP",
    "INVALID_RWD",
    "INVALID_EMISSION_FACTOR",
    "INVALID_BIOMASS_FRACTION",
    "RFNBO_E_EXCEEDS_LIMIT",
})


def _as_input_error(error: Exception, field: str) -> _InputError:
    """Keep an explicit domain error code at the JSON boundary."""
    if isinstance(error, _InputError):
        return error
    message = str(error).strip()
    code = message.partition(":")[0]
    if code not in _STRUCTURED_ERROR_CODES:
        code = "MISSING_REQUIRED_FACTOR"
    return _InputError(code, field, message)


def _strict_bool(value: Any, *, field: str) -> bool:
    if type(value) is not bool:
        raise _InputError("MISSING_REQUIRED_FACTOR", field, f"{field} must be a boolean")
    return value


def parse_component(payload: Mapping[str, Any], *, report_year: int | None = None) -> FuelComponent:
    """Parse a fuel component using decimal-safe factor resolution."""
    return _parse_component(payload, field_prefix="", report_year=report_year)


def _parse_component(payload: Mapping[str, Any], *, field_prefix: str,
                     report_year: int | None = None) -> FuelComponent:
    def field(name: str) -> str:
        return f"{field_prefix}.{name}" if field_prefix else name

    if not isinstance(payload, Mapping):
        raise _InputError("MISSING_REQUIRED_FACTOR", field_prefix or "component", "component must be an object")
    qualification = str(payload.get("qualificationStatus", "NOT_DEMONSTRATED")).strip().upper()
    e_value = payload.get("e")
    eu_value = payload.get("eu")
    cslip = payload.get("cslip")
    verified_wt = payload.get("verifiedWtT")
    if "pathId" not in payload:
        raise _InputError("MISSING_REQUIRED_FACTOR", field("pathId"), "pathId is required")
    path_id = str(payload["pathId"])
    custom = _strict_bool(payload.get("custom", False), field=field("custom"))
    if not custom:
        try:
            factor = resolve_factor(
                path_id, qualification_status=qualification,
                e_value=None if e_value is None else Decimal(str(e_value)),
                eu_value=None if eu_value is None else Decimal(str(eu_value)),
                cslip_percent=None if cslip is None else Decimal(str(cslip)),
                verified_wt_t=None if verified_wt is None else Decimal(str(verified_wt)),
                report_year=report_year,
            )
        except KeyError:
            custom = True
        except (InvalidOperation, TypeError, ValueError) as error:
            raise _as_input_error(error, field("pathId")) from error
    if custom:
        try:
            factor = resolve_custom_factor(payload, report_year=report_year)
        except (AssertionError, InvalidOperation, KeyError, TypeError, ValueError) as error:
            raise _as_input_error(error, field("pathId")) from error
    try:
        return FuelComponent(
            factor=factor,
            price_per_tonne=(
                None if payload.get("pricePerTonne") is None
                else _decimal(payload["pricePerTonne"], field=field("pricePerTonne"))
            ),
            eligible_biomass_fraction=_decimal(
                payload.get("eligibleBiomassFraction", "0"), field=field("eligibleBiomassFraction")
            ),
            qualification_status=qualification,
        )
    except (InvalidOperation, TypeError, ValueError) as error:
        if isinstance(error, _InputError):
            raise
        raise _InputError("MISSING_REQUIRED_FACTOR", field("pathId"), str(error)) from error


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
        raise _InputError("MISSING_REQUIRED_FACTOR", field, f"{field} must be numeric")
    try:
        return Decimal(str(value))
    except Exception as error:
        raise _InputError("MISSING_REQUIRED_FACTOR", field, f"{field} must be numeric") from error


def _decimal_sequence(value: Any, *, field: str) -> tuple[Decimal, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise _InputError("INVALID_BLEND_RATIO", field, f"{field} must be an array")
    return tuple(_decimal(item, field=f"{field}[{index}]") for index, item in enumerate(value))


def _parse_candidate(payload: Mapping[str, Any], *, field_prefix: str,
                     report_year: int | None = None) -> CandidateInput:
    candidate_id = payload.get("candidateId")
    if not isinstance(candidate_id, str):
        raise _InputError("INVALID_CANDIDATE_ID", f"{field_prefix}.candidateId", "candidateId is required")
    specified_ratios = _decimal_sequence(
        payload.get("specifiedBlendRatios", ()), field=f"{field_prefix}.specifiedBlendRatios"
    )
    max_blend_ratio = _decimal(
        payload.get("maxBlendRatio", "1"), field=f"{field_prefix}.maxBlendRatio"
    )
    if not Decimal("0") <= max_blend_ratio <= Decimal("1"):
        raise _InputError(
            "INVALID_BLEND_RATIO", f"{field_prefix}.maxBlendRatio", "maxBlendRatio must be between zero and one"
        )
    for index, ratio in enumerate(specified_ratios):
        if not Decimal("0") <= ratio <= max_blend_ratio:
            raise _InputError(
                "INVALID_BLEND_RATIO",
                f"{field_prefix}.specifiedBlendRatios[{index}]",
                "specifiedBlendRatios must be within maxBlendRatio",
            )
    supply_tonnes = (
        None if payload.get("candidateSupplyTonnes") is None
        else _decimal(payload["candidateSupplyTonnes"], field=f"{field_prefix}.candidateSupplyTonnes")
    )
    incremental_budget = (
        None if payload.get("incrementalBudget") is None
        else _decimal(payload["incrementalBudget"], field=f"{field_prefix}.incrementalBudget")
    )
    compliance_improvement_value = (
        None if payload.get("complianceImprovementValue") is None
        else _decimal(
            payload["complianceImprovementValue"], field=f"{field_prefix}.complianceImprovementValue"
        )
    )
    for name, value in (
        ("candidateSupplyTonnes", supply_tonnes),
        ("incrementalBudget", incremental_budget),
        ("complianceImprovementValue", compliance_improvement_value),
    ):
        if value is not None and value < Decimal("0"):
            raise _InputError(
                "INVALID_CANDIDATE_CONSTRAINT", f"{field_prefix}.{name}", f"{name} must be non-negative"
            )
    return CandidateInput(
        candidate_id=candidate_id,
        component=_parse_component(payload, field_prefix=field_prefix, report_year=report_year),
        specified_blend_ratios=specified_ratios,
        max_blend_ratio=max_blend_ratio,
        allows_pure_use=_strict_bool(
            payload.get("candidateAllowsPureUse", payload.get("allowsPureUse", False)),
            field=f"{field_prefix}.candidateAllowsPureUse",
        ),
        supply_tonnes=supply_tonnes,
        incremental_budget=incremental_budget,
        compliance_improvement_value=compliance_improvement_value,
    )


def _case_issue(error: Exception, field: str) -> ParsedDecisionCase:
    return ParsedDecisionCase(request=None, issues=(issue_from_exception(error, scope="CASE", field=field),))


def _error_field(error: Exception, fallback: str) -> str:
    return error.field if isinstance(error, _InputError) else fallback


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
            raise _InputError(
                "PORT_OF_CALL_CONFIRMATION_REQUIRED",
                "adjacentValidPortOfCallConfirmed",
                "adjacent Port of Call confirmation must be a boolean",
            )
        confirmation = confirmation_value
        if not confirmation:
            raise _InputError(
                "PORT_OF_CALL_CONFIRMATION_REQUIRED",
                "adjacentValidPortOfCallConfirmed",
                "adjacent Port of Call confirmation is required",
            )
        if "reportYear" not in decoded or type(decoded["reportYear"]) is not int:
            raise _InputError("INVALID_YEAR", "reportYear", "reportYear must be an integer")
        report_year = decoded["reportYear"]
        if not 2024 <= report_year <= 2030:
            raise _InputError("INVALID_YEAR", "reportYear", "reportYear must be from 2024 through 2030")
        baseline = decoded.get("baseline")
        if not isinstance(baseline, Mapping):
            raise _InputError("MISSING_REQUIRED_FACTOR", "baseline", "baseline must be an object")
        candidates_payload = decoded.get("candidates")
        if not isinstance(candidates_payload, (list, tuple)):
            raise _InputError("MISSING_REQUIRED_FACTOR", "candidates", "candidates must be an array")
        if not candidates_payload:
            raise _InputError("MISSING_REQUIRED_FACTOR", "candidates", "at least one candidate is required")
        candidate_ids = [
            item.get("candidateId")
            for item in candidates_payload
            if isinstance(item, Mapping) and isinstance(item.get("candidateId"), str)
        ]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise _InputError("DUPLICATE_CANDIDATE_ID", "candidates", "candidateId values must be unique")
        baseline_component = _parse_component(baseline, field_prefix="baseline", report_year=report_year)
        if "massTonnes" not in baseline:
            raise _InputError("INVALID_BASELINE_MASS", "baseline.massTonnes", "massTonnes is required")
        baseline_mass = _decimal(baseline["massTonnes"], field="baseline.massTonnes")
        if baseline_mass <= Decimal("0"):
            raise _InputError("INVALID_BASELINE_MASS", "baseline.massTonnes", "massTonnes must be positive")
        eua_price = decoded.get("euaPricePerTCO2e")
        eua_price_decimal = None if eua_price is None else _decimal(eua_price, field="euaPricePerTCO2e")
        if eua_price_decimal is not None and eua_price_decimal < Decimal("0"):
            raise _InputError("INVALID_EUA_PRICE", "euaPricePerTCO2e", "eua price must be non-negative")
        if not isinstance(decoded.get("currency"), str) or not decoded["currency"].strip():
            raise _InputError("INVALID_CURRENCY", "currency", "currency is required")
        for field in ("departurePort", "arrivalPort"):
            if not isinstance(decoded.get(field), str) or not decoded[field].strip():
                raise _InputError("INVALID_PORT_CODE", field, f"{field} is required")
    except (InvalidOperation, KeyError, TypeError, ValueError) as error:
        return _case_issue(error, _error_field(error, "baseline"))

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
                raise _InputError("INVALID_CANDIDATE_ID", f"candidates[{index}]", "candidate must be an object")
            candidates.append(
                _parse_candidate(candidate_payload, field_prefix=f"candidates[{index}]", report_year=report_year)
            )
        except (AssertionError, InvalidOperation, KeyError, TypeError, ValueError) as error:
            issues.append(
                issue_from_exception(
                    error,
                    scope="CANDIDATE",
                    field=_error_field(error, f"candidates[{index}]"),
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
        case_issue = issue_from_exception(error, scope="CASE", field=_error_field(error, "currency"))
        if candidates_payload and not candidates:
            return ParsedDecisionCase(request=None, issues=tuple(issues))
        return ParsedDecisionCase(request=None, issues=(*issues, case_issue))
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
