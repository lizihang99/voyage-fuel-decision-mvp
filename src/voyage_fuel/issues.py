"""Conversion of calculation-boundary failures into structured issues."""

from __future__ import annotations

from .contracts import Issue


_KNOWN_CODES = frozenset({
    "INVALID_YEAR",
    "INVALID_PORT_CODE",
    "PORT_NOT_FOUND",
    "PORT_OF_CALL_CONFIRMATION_REQUIRED",
    "INVALID_BASELINE_MASS",
    "INVALID_LCV",
    "INVALID_BLEND_RATIO",
    "MISSING_REQUIRED_FACTOR",
    "INVALID_CSLIP",
    "INVALID_RWD",
    "INVALID_EMISSION_FACTOR",
    "INVALID_BIOMASS_FRACTION",
    "RFNBO_E_EXCEEDS_LIMIT",
    "PRICE_REQUIRED_FOR_COMPARISON",
    "BUDGET_UNAVAILABLE_WITHOUT_PRICES",
    "TARGET_NOT_APPLICABLE",
    "TARGET_NO_SOLUTION",
    "TARGET_UNREACHABLE_UNDER_CONSTRAINTS",
    "ZERO_BASELINE",
    "DUPLICATE_CANDIDATE_ID",
    "INVALID_CANDIDATE_ID",
    "INVALID_CANDIDATE_CONSTRAINT",
    "INVALID_CURRENCY",
    "INVALID_EUA_PRICE",
    "PORT_NOT_FOUND",
    "INCONSISTENT_BASELINE",
})


def issue_from_exception(
    error: Exception,
    *,
    scope: str,
    field: str,
    candidate_id: str | None = None,
    component: str | None = None,
) -> Issue:
    """Map a boundary exception to an explicit issue owned by the kernel."""
    message = str(error).strip() or "Invalid calculation input."
    code = message.partition(":")[0]
    if message.startswith("Port not found"):
        code = "PORT_NOT_FOUND"
    elif message.startswith("Invalid UN/LOCODE"):
        code = "INVALID_PORT_CODE"
    if code not in _KNOWN_CODES:
        code = "MISSING_REQUIRED_FACTOR"
    return Issue(
        code=code,
        scope=scope,
        field=field,
        blocking=True,
        message=message,
        candidate_id=candidate_id,
        component=component,
    )
