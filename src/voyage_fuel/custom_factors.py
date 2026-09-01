"""Validated custom fuel-factor parsing with field-level evidence."""

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from .models import EvidenceRecord, FuelFactor


ZERO = Decimal("0")
ONE = Decimal("1")
TWO = Decimal("2")
MAX_RFNBO_E = Decimal("28.2")
VERIFIED = "VERIFIED"


def _blocked(message: str) -> ValueError:
    return ValueError(f"BLOCKED: {message}")


def _decimal(payload: Mapping[str, Any], name: str, *, allow_na: bool = False) -> Decimal | None:
    if name not in payload or payload[name] is None:
        raise _blocked(f"custom factor field {name} is required")
    value = payload[name]
    if allow_na and isinstance(value, str) and value.strip().upper() == "NA":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise _blocked(f"invalid decimal field {name}") from exc


def _evidence_records(payload: Mapping[str, Any], required: tuple[str, ...]) -> tuple[tuple[EvidenceRecord, ...], bool]:
    raw = payload.get("sourceEvidence")
    if not isinstance(raw, Mapping):
        raise _blocked("sourceEvidence must be an object")
    records: list[EvidenceRecord] = []
    all_verified = True
    for field in required:
        entries = raw.get(field)
        if isinstance(entries, Mapping):
            entries = [entries]
        if not isinstance(entries, (list, tuple)) or not entries:
            raise _blocked(f"sourceEvidence missing field {field}")
        for entry in entries:
            if not isinstance(entry, Mapping):
                raise _blocked(f"sourceEvidence entry for {field} must be an object")
            source_id = str(entry.get("sourceId", "")).strip()
            source_type = str(entry.get("sourceType", "")).strip()
            unit = str(entry.get("unit", "")).strip()
            verification = str(entry.get("verificationStatus", "")).strip().upper()
            if not source_id or not source_type or not unit or not verification:
                raise _blocked(f"sourceEvidence incomplete for {field}")
            if verification not in {"VERIFIED", "ESTIMATED", "ASSUMED", "SA", "RC"}:
                raise _blocked(f"unsupported verificationStatus for {field}")
            all_verified = all_verified and verification == VERIFIED
            records.append(EvidenceRecord(field, source_id, source_type, unit, verification))
    return tuple(records), all_verified


def _require_units(records: tuple[EvidenceRecord, ...]) -> None:
    expected = {
        "lcv": {"mj/gfuel", "mj/g", "mj per gfuel"},
        "wtT": {"gco2eq/mj"},
        "E": {"gco2eq/mj"},
        "eu": {"gco2eq/mj"},
        "cfCO2": {"gghg/gfuel", "gco2/gfuel"},
        "cfCH4": {"gghg/gfuel", "gch4/gfuel"},
        "cfN2O": {"gghg/gfuel", "gn2o/gfuel"},
        "cslip": {"%", "percent"},
        "csfCO2": {"gghg/gfuel", "gco2/gfuel"},
        "csfCH4": {"gghg/gfuel", "gch4/gfuel"},
        "csfN2O": {"gghg/gfuel", "gn2o/gfuel"},
        "rwd": {"ratio"},
        "methaneSlipApplicable": {"boolean", "bool"},
        "eligibleBiomassFraction": {"fraction", "ratio"},
    }
    for record in records:
        allowed = expected.get(record.field_name)
        if allowed and record.unit.lower().replace(" ", "") not in {unit.replace(" ", "") for unit in allowed}:
            raise _blocked(f"unsupported unit for sourceEvidence field {record.field_name}")


def resolve_custom_factor(payload: Mapping[str, Any]) -> FuelFactor:
    """Parse a complete custom path; no built-in defaults are applied."""
    if not isinstance(payload, Mapping):
        raise _blocked("custom factor must be an object")
    path_id = str(payload.get("pathId", "")).strip()
    equipment_id = str(payload.get("equipmentId", "")).strip()
    if not path_id or not equipment_id:
        raise _blocked("pathId and equipmentId are required")
    mode = str(payload.get("wtTMode", "")).strip().upper()
    if mode not in {"STATIC", "BIO_E", "RFNBO_E", "CERTIFIED"}:
        raise _blocked("wtTMode must be explicit and supported")
    methane = payload.get("methaneSlipApplicable")
    if not isinstance(methane, bool):
        raise _blocked("methaneSlipApplicable must be an explicit boolean")

    lcv = _decimal(payload, "lcv")
    assert lcv is not None
    if lcv <= ZERO:
        raise _blocked("lcv must be positive")
    cf_co2 = _decimal(payload, "cfCO2", allow_na=True)
    cf_ch4 = _decimal(payload, "cfCH4", allow_na=True)
    cf_n2o = _decimal(payload, "cfN2O", allow_na=True)
    cslip = _decimal(payload, "cslip", allow_na=True)
    if cslip is not None and not ZERO <= cslip <= Decimal("100"):
        raise ValueError(f"INVALID_CSLIP: {path_id}")
    if methane and cslip is None:
        raise _blocked("cslip is required when methaneSlipApplicable is true")
    if not methane and cslip is not None and cslip != ZERO:
        raise ValueError(f"INVALID_CSLIP: non-methane custom path {path_id}")

    rwd = _decimal(payload, "rwd")
    assert rwd is not None
    if rwd not in {ONE, TWO}:
        raise _blocked("rwd must be 1 or 2")

    required = ["lcv", "cfCO2", "cfCH4", "cfN2O", "cslip", "methaneSlipApplicable", "rwd"]
    if mode in {"STATIC", "CERTIFIED"}:
        wt_t = _decimal(payload, "wtT")
        required.append("wtT")
    elif mode == "BIO_E":
        e_value = _decimal(payload, "E")
        assert e_value is not None and cf_co2 is not None
        wt_t = e_value - cf_co2 / lcv
        required.append("E")
    else:
        e_value = _decimal(payload, "E")
        eu_value = _decimal(payload, "eu")
        assert e_value is not None and eu_value is not None
        if e_value > MAX_RFNBO_E:
            raise ValueError(f"RFNBO_E_EXCEEDS_LIMIT: {path_id}")
        wt_t = e_value - eu_value
        required.extend(("E", "eu"))
    if wt_t is None:
        raise _blocked("WtT formula did not produce a value")

    if cslip is not None and cslip > ZERO:
        csf_co2 = _decimal(payload, "csfCO2")
        csf_ch4 = _decimal(payload, "csfCH4")
        csf_n2o = _decimal(payload, "csfN2O")
        required.extend(("csfCO2", "csfCH4", "csfN2O"))
    else:
        csf_co2 = csf_ch4 = csf_n2o = ZERO

    eligible_fraction = _decimal(payload, "eligibleBiomassFraction")
    assert eligible_fraction is not None
    if not ZERO <= eligible_fraction <= ONE:
        raise _blocked("eligibleBiomassFraction must be between 0 and 1")
    required.append("eligibleBiomassFraction")
    records, all_verified = _evidence_records(payload, tuple(dict.fromkeys(required)))
    _require_units(records)
    factor_status = "VERIFIED" if all_verified else "ESTIMATED"
    na_fields = tuple(name for name, value in (
        ("cf_co2_g_per_g", cf_co2), ("cf_ch4_g_per_g", cf_ch4),
        ("cf_n2o_g_per_g", cf_n2o), ("cslip_percent", cslip),
    ) if value is None)
    return FuelFactor(
        path_id=path_id,
        lcv_mj_per_g=lcv,
        wt_t_g_per_mj=wt_t,
        cf_co2_g_per_g=cf_co2 or ZERO,
        cf_ch4_g_per_g=cf_ch4 or ZERO,
        cf_n2o_g_per_g=cf_n2o or ZERO,
        rwd=rwd,
        cslip_percent=cslip,
        methane_slip_applicable=methane,
        factor_status=factor_status,
        csf_co2_g_per_g=csf_co2 or ZERO,
        csf_ch4_g_per_g=csf_ch4 or ZERO,
        csf_n2o_g_per_g=csf_n2o or ZERO,
        na_fields=na_fields,
        cslip_semantics="NA" if cslip is None else ("VERIFIED" if all_verified else "SA"),
        source_evidence=records,
    )
