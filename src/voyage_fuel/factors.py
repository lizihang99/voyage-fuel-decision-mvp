"""Built-in fuel catalog and factor resolution helpers."""

from decimal import Decimal
from dataclasses import replace
from typing import Optional

from .models import EvidenceRecord, FuelDefinition, FuelFactor
from .provenance import FactorResolutionTrace


def _definition(path_id: str, equipment_id: str, level: str, mode: str, lcv: str,
                wt_t: Optional[str], co2: Optional[str], ch4: Optional[str], n2o: Optional[str], *,
                cslip: Optional[str] = None, rwd: str = "1", fallback: Optional[str] = None,
                cslip_required: bool = False, methane_slip: bool = False,
                default_e: Optional[str] = None, default_eu: Optional[str] = None,
                default_lcv: Optional[str] = None, default_wt_t: Optional[str] = None,
                default_co2: Optional[str] = None, default_ch4: Optional[str] = None,
                default_n2o: Optional[str] = None, default_cslip: Optional[str] = None) -> FuelDefinition:
    return FuelDefinition(
        path_id=path_id, equipment_id=equipment_id, factor_level=level, wt_t_mode=mode,
        lcv_mj_per_g=Decimal(lcv), wt_t_g_per_mj=None if wt_t is None else Decimal(wt_t),
        cf_co2_g_per_g=None if co2 is None else Decimal(co2),
        cf_ch4_g_per_g=None if ch4 is None else Decimal(ch4),
        cf_n2o_g_per_g=None if n2o is None else Decimal(n2o),
        cslip_percent=None if cslip is None else Decimal(cslip), rwd=Decimal(rwd),
        fallback_path_id=fallback, cslip_required=cslip_required,
        methane_slip_applicable=methane_slip,
        default_e_g_per_mj=None if default_e is None else Decimal(default_e),
        default_eu_g_per_mj=None if default_eu is None else Decimal(default_eu),
        default_lcv_mj_per_g=None if default_lcv is None else Decimal(default_lcv),
        default_wt_t_g_per_mj=None if default_wt_t is None else Decimal(default_wt_t),
        default_cf_co2_g_per_g=None if default_co2 is None else Decimal(default_co2),
        default_cf_ch4_g_per_g=None if default_ch4 is None else Decimal(default_ch4),
        default_cf_n2o_g_per_g=None if default_n2o is None else Decimal(default_n2o),
        default_cslip_percent=None if default_cslip is None else Decimal(default_cslip),
    )


_DEFINITIONS: dict[str, FuelDefinition] = {}


def _add(definition: FuelDefinition) -> None:
    _DEFINITIONS[definition.path_id] = definition


# Values are copied from the factor-library tables; formulas are resolved at runtime.
for definition in (
    _definition("HFO", "HFO", "A", "STATIC", "0.0405", "13.5", "3.114", "0.00005", "0.00018"),
    _definition("LFO", "LFO", "A", "STATIC", "0.041", "13.2", "3.151", "0.00005", "0.00018"),
    _definition("MDO", "MDO", "A", "STATIC", "0.0427", "14.4", "3.206", "0.00005", "0.00018"),
    _definition("MGO", "MGO", "A", "STATIC", "0.0427", "14.4", "3.206", "0.00005", "0.00018"),
    _definition("LNG_OTTO_MEDIUM_SPEED", "LNG_OTTO_MS", "A", "STATIC", "0.0491", "18.5", "2.750", "0", "0.00011", cslip="3.1", methane_slip=True),
    _definition("LNG_OTTO_SLOW_SPEED", "LNG_OTTO_SS", "A", "STATIC", "0.0491", "18.5", "2.750", "0", "0.00011", cslip="1.7", methane_slip=True),
    _definition("LNG_DIESEL_SLOW_SPEED", "LNG_DIESEL_SS", "A", "STATIC", "0.0491", "18.5", "2.750", "0", "0.00011", cslip="0.2", methane_slip=True),
    _definition("LNG_LBSI", "LNG_LBSI", "A", "STATIC", "0.0491", "18.5", "2.750", "0", "0.00011", cslip="2.6", methane_slip=True),
    _definition("METHANOL_NG", "METHANOL_NG", "A", "STATIC", "0.0199", "31.3", "1.375", "0.00005", "0.00018"),
    _definition("H2_NG_FC", "H2_NG_FC", "A", "STATIC", "0.12", "132", "0", "0", None, default_n2o="0"),
    _definition("H2_NG_ICE", "H2_NG_ICE", "A", "STATIC", "0.12", "132", "0", "0", "0.00018"),
    _definition("LPG_PROPANE", "LPG_PROPANE", "B", "STATIC", "0.046", "7.8", "3.000", "0.00005", "0.00018", cslip_required=True, default_cslip="0"),
    _definition("LPG_BUTANE", "LPG_BUTANE", "B", "STATIC", "0.046", "7.8", "3.030", "0.00005", "0.00018", cslip_required=True, default_cslip="0"),
    _definition("NH3_NG_FC", "NH3_NG_FC", "B", "STATIC", "0.0186", "121", "0", "0.00005", "0.00018", cslip_required=True, default_cslip="0"),
    _definition("NH3_NG_ICE", "NH3_NG_ICE", "B", "STATIC", "0.0186", "121", "0", "0.00005", "0.00018", cslip_required=True, default_cslip="0"),
    _definition("BIOETHANOL", "BIOETHANOL", "B", "BIO_E", "0.027", None, "1.913", "0.00005", "0.00018", default_lcv="0.02685", default_wt_t="20", default_cslip="0"),
    _definition("BIODIESEL", "BIODIESEL", "B", "BIO_E", "0.037", None, "2.834", "0.00005", "0.00018", default_lcv="0.037", default_wt_t="20", default_cslip="0"),
    _definition("HVO", "HVO", "B", "BIO_E", "0.044", None, "3.115", "0.00005", "0.00018", default_lcv="0.044", default_wt_t="15", default_cslip="0"),
    _definition("BIOLNG_OTTO_MS", "BIOLNG_OTTO_MS", "B", "BIO_E", "0.050", None, "2.750", "0", "0.00011", cslip="3.1", methane_slip=True, default_lcv="0.0491", default_wt_t="10", default_cslip="3.1"),
    _definition("BIOLNG_OTTO_SS", "BIOLNG_OTTO_SS", "B", "BIO_E", "0.050", None, "2.750", "0", "0.00011", cslip="1.7", methane_slip=True, default_lcv="0.0491", default_wt_t="10", default_cslip="1.7"),
    _definition("BIOLNG_DIESEL_SS", "BIOLNG_DIESEL_SS", "B", "BIO_E", "0.050", None, "2.750", "0", "0.00011", cslip="0.2", methane_slip=True, default_lcv="0.0491", default_wt_t="10", default_cslip="0.2"),
    _definition("BIOLNG_LBSI", "BIOLNG_LBSI", "B", "BIO_E", "0.050", None, "2.750", "0", "0.00011", cslip="2.6", methane_slip=True, default_lcv="0.0491", default_wt_t="10", default_cslip="2.6"),
    _definition("BIOMETHANOL", "BIOMETHANOL", "B", "BIO_E", "0.020", None, "1.375", "0.00005", "0.00018", default_lcv="0.01986", default_wt_t="18", default_cslip="0"),
    _definition("BIOH2_FC", "BIOH2_FC", "B", "CERTIFIED", "0.120", None, "0", "0", "0", default_lcv="0.120", default_wt_t="25", default_cslip="0"),
    _definition("BIOH2_ICE", "BIOH2_ICE", "B", "CERTIFIED", "0.120", None, "0", "0", "0.00018", default_lcv="0.120", default_wt_t="25", default_n2o="0.00002", default_cslip="0"),
    _definition("UCO_FAME", "UCO_FAME", "B", "BIO_E", "0.037", None, "2.834", "0.00005", "0.00018", default_e="14.9", default_lcv="0.037", default_cslip="0"),
    _definition("E_DIESEL", "E_DIESEL", "B", "RFNBO_E", "0.0427", None, "3.206", "0.00005", "0.00018", fallback="MDO", default_e="28.2", default_eu="73.2", default_wt_t="3", default_cslip="0"),
    _definition("E_METHANOL", "E_METHANOL", "B", "RFNBO_E", "0.0199", None, "1.375", "0.00005", "0.00018", fallback="METHANOL_NG", default_e="28.2", default_eu="68.9", default_wt_t="3", default_cslip="0"),
    _definition("E_LNG_OTTO_MEDIUM_SPEED", "E_LNG_OTTO_MS", "B", "RFNBO_E", "0.0491", None, "2.750", "0", "0.00011", cslip="3.1", methane_slip=True, fallback="LNG_OTTO_MEDIUM_SPEED", default_e="28.2", default_eu="56.2", default_wt_t="2", default_cslip="3.1"),
    _definition("E_LNG_OTTO_SLOW_SPEED", "E_LNG_OTTO_SS", "B", "RFNBO_E", "0.0491", None, "2.750", "0", "0.00011", cslip="1.7", methane_slip=True, fallback="LNG_OTTO_SLOW_SPEED", default_e="28.2", default_eu="56.2", default_wt_t="2", default_cslip="1.7"),
    _definition("E_LNG_DIESEL_SLOW_SPEED", "E_LNG_DIESEL_SS", "B", "RFNBO_E", "0.0491", None, "2.750", "0", "0.00011", cslip="0.2", methane_slip=True, fallback="LNG_DIESEL_SLOW_SPEED", default_e="28.2", default_eu="56.2", default_wt_t="2", default_cslip="0.2"),
    _definition("E_LNG_LBSI", "E_LNG_LBSI", "B", "RFNBO_E", "0.0491", None, "2.750", "0", "0.00011", cslip="2.6", methane_slip=True, fallback="LNG_LBSI", default_e="28.2", default_eu="56.2", default_wt_t="2", default_cslip="2.6"),
    _definition("E_H2_FC", "E_H2_FC", "B", "RFNBO_E", "0.120", None, "0", "0", "0", fallback="H2_NG_FC", default_e="28.2", default_eu="0", default_wt_t="1", default_cslip="0"),
    _definition("E_H2_ICE", "E_H2_ICE", "B", "RFNBO_E", "0.120", None, "0", "0", "0.00018", fallback="H2_NG_ICE", default_e="28.2", default_eu="0", default_wt_t="1", default_n2o="0.00002", default_cslip="0"),
    _definition("E_NH3_FC", "E_NH3_FC", "B", "RFNBO_E", "0.0186", None, "0", "0.00005", "0.00018", fallback="NH3_NG_FC", cslip_required=True, default_e="28.2", default_eu="0", default_wt_t="2", default_ch4="0", default_n2o="0.0001", default_cslip="0"),
    _definition("E_NH3_ICE", "E_NH3_ICE", "B", "RFNBO_E", "0.0186", None, "0", "0.00005", "0.00018", fallback="NH3_NG_ICE", cslip_required=True, default_e="28.2", default_eu="0", default_wt_t="2", default_ch4="0", default_n2o="0.0005", default_cslip="0"),
):
    _add(definition)


_ALIASES = {
    "LNG_OTTO_MS": "LNG_OTTO_MEDIUM_SPEED", "LNG_OTTO_SS": "LNG_OTTO_SLOW_SPEED",
    "LNG_DIESEL_SS": "LNG_DIESEL_SLOW_SPEED", "E_LNG_OTTO_MS": "E_LNG_OTTO_MEDIUM_SPEED",
    "E_LNG_OTTO_SS": "E_LNG_OTTO_SLOW_SPEED", "E_LNG_DIESEL_SS": "E_LNG_DIESEL_SLOW_SPEED",
}


def _key(path_id: str) -> str:
    return _ALIASES.get(str(path_id).strip().upper(), str(path_id).strip().upper())


def builtin_path_ids() -> tuple[str, ...]:
    return tuple(_DEFINITIONS)


def get_definition(path_id: str) -> FuelDefinition:
    key = _key(path_id)
    if key not in _DEFINITIONS:
        raise KeyError(f"Unsupported built-in fuel path: {path_id}")
    return _DEFINITIONS[key]


def _factor_from_definition(definition: FuelDefinition, status: str, wt_t: Decimal, *, use_defaults: bool = False) -> FuelFactor:
    def selected(default: Optional[Decimal], formal: Optional[Decimal]) -> Optional[Decimal]:
        return default if use_defaults and default is not None else formal

    lcv = selected(definition.default_lcv_mj_per_g, definition.lcv_mj_per_g)
    if lcv is None:
        raise ValueError(f"BLOCKED: LCV required for {definition.path_id}")
    cslip = selected(
        definition.default_cslip_percent if (definition.methane_slip_applicable or definition.cslip_required) else None,
        definition.cslip_percent,
    )
    if cslip is None and definition.cslip_percent is None:
        cslip_semantics = "RC" if definition.cslip_required else "NA"
    elif status == "VERIFIED":
        cslip_semantics = "VERIFIED"
    elif definition.methane_slip_applicable and cslip is not None:
        cslip_semantics = "FIXED"
    elif status == "ESTIMATED" and cslip is not None and definition.default_cslip_percent is not None:
        cslip_semantics = "SA"
    else:
        cslip_semantics = "FIXED"
    na_fields = tuple(
        name for name, value in (
            ("cf_co2_g_per_g", definition.cf_co2_g_per_g),
            ("cf_ch4_g_per_g", definition.cf_ch4_g_per_g),
            ("cf_n2o_g_per_g", definition.cf_n2o_g_per_g),
            ("cslip_percent", None if not definition.cslip_required else Decimal("0")),
        ) if value is None
    )
    return FuelFactor(
        path_id=definition.path_id, lcv_mj_per_g=lcv, wt_t_g_per_mj=wt_t,
        cf_co2_g_per_g=selected(definition.default_cf_co2_g_per_g, definition.cf_co2_g_per_g) or Decimal("0"),
        cf_ch4_g_per_g=selected(definition.default_cf_ch4_g_per_g, definition.cf_ch4_g_per_g) or Decimal("0"),
        cf_n2o_g_per_g=selected(definition.default_cf_n2o_g_per_g, definition.cf_n2o_g_per_g) or Decimal("0"), rwd=definition.rwd,
        cslip_percent=cslip,
        methane_slip_applicable=definition.methane_slip_applicable, factor_status=status,
        csf_ch4_g_per_g=Decimal("1") if definition.methane_slip_applicable else Decimal("0"),
        na_fields=na_fields,
        cslip_semantics=cslip_semantics,
        source_evidence=(EvidenceRecord(
            field_name="catalog",
            source_id=f"FACTOR-CATALOG:{definition.path_id}",
            source_type="BUILTIN_CATALOG",
            unit="factor",
            verification_status="VERIFIED",
        ),),
    )


def get_builtin_factor(path_id: str) -> FuelFactor:
    return resolve_factor(path_id)


def _validated_cslip(definition: FuelDefinition, cslip_percent: Optional[Decimal], status: str) -> FuelDefinition:
    if cslip_percent is None:
        if definition.cslip_required and status == "VERIFIED":
            raise ValueError(f"BLOCKED: recognized Cslip required for {definition.path_id}")
        return definition
    cslip = Decimal(str(cslip_percent))
    if not Decimal("0") <= cslip <= Decimal("100"):
        raise ValueError(f"INVALID_CSLIP: {definition.path_id}")
    if not definition.methane_slip_applicable and cslip != Decimal("0"):
        raise ValueError(f"INVALID_CSLIP: non-methane path {definition.path_id}")
    return replace(definition, cslip_percent=cslip)


def _resolve_factor(path_id: str, qualification_status: str = "NOT_DEMONSTRATED",
                   e_value: Optional[Decimal] = None, eu_value: Optional[Decimal] = None,
                   cslip_percent: Optional[Decimal] = None, verified_wt_t: Optional[Decimal] = None,
                   report_year: Optional[int] = None) -> FuelFactor:
    definition = get_definition(path_id)
    status = str(qualification_status).upper()
    if status not in {"NOT_DEMONSTRATED", "ASSUMED_ELIGIBLE", "VERIFIED_ELIGIBLE", "INELIGIBLE"}:
        raise ValueError(f"BLOCKED: unsupported qualification status {qualification_status}")
    if definition.wt_t_mode == "RFNBO_E":
        if status in {"NOT_DEMONSTRATED", "INELIGIBLE"}:
            return _resolve_factor(
                definition.fallback_path_id or "", "NOT_DEMONSTRATED", report_year=report_year
            )
        if report_year is not None and not 2025 <= report_year <= 2033:
            raise ValueError("BLOCKED: rwd=2 is only valid for qualified RFNBO from 2025 through 2033")
        if status == "VERIFIED_ELIGIBLE" and (e_value is None or eu_value is None):
            raise ValueError(f"BLOCKED: verified RFNBO requires E and eu for {definition.path_id}")
        e = Decimal(str(e_value)) if e_value is not None else definition.default_e_g_per_mj
        eu = Decimal(str(eu_value)) if eu_value is not None else definition.default_eu_g_per_mj
        if e is None or eu is None:
            raise ValueError(f"BLOCKED: RFNBO requires E and eu for {definition.path_id}")
        if e > Decimal("28.2"):
            raise ValueError(f"BLOCKED: RFNBO E exceeds 28.2 for {definition.path_id}")
        if cslip_percent is None and status != "VERIFIED_ELIGIBLE" and (definition.methane_slip_applicable or definition.cslip_required):
            cslip_percent = definition.default_cslip_percent
        resolved = _validated_cslip(definition, cslip_percent, "VERIFIED" if status == "VERIFIED_ELIGIBLE" else "ESTIMATED")
        resolved_factor = _factor_from_definition(
            resolved,
            "VERIFIED" if status == "VERIFIED_ELIGIBLE" else "ESTIMATED",
            e - eu,
            use_defaults=False,
        )
        return replace(resolved_factor,
            cf_co2_g_per_g=resolved.cf_co2_g_per_g or Decimal("0"), cf_ch4_g_per_g=resolved.cf_ch4_g_per_g or Decimal("0"),
            cf_n2o_g_per_g=resolved.cf_n2o_g_per_g or Decimal("0"), rwd=Decimal("2"),
        )
    if definition.wt_t_mode == "CERTIFIED":
        if status == "VERIFIED_ELIGIBLE" and verified_wt_t is None:
            raise ValueError(f"BLOCKED: verified WtT required for {definition.path_id}")
        if verified_wt_t is not None:
            status_out = "VERIFIED" if status == "VERIFIED_ELIGIBLE" else "ESTIMATED"
            resolved = _validated_cslip(definition, cslip_percent, status_out)
            return _factor_from_definition(resolved, status_out, Decimal(str(verified_wt_t)), use_defaults=False)
        if definition.default_wt_t_g_per_mj is None and definition.default_e_g_per_mj is None:
            raise ValueError(f"BLOCKED: certified WtT required for {definition.path_id}")
        if cslip_percent is None and (definition.methane_slip_applicable or definition.cslip_required):
            cslip_percent = definition.default_cslip_percent
        resolved = _validated_cslip(definition, cslip_percent, "ESTIMATED")
        default_wt = definition.default_wt_t_g_per_mj or definition.default_e_g_per_mj
        return _factor_from_definition(resolved, "ESTIMATED", default_wt, use_defaults=True)
    if definition.wt_t_mode == "BIO_E":
        if status == "VERIFIED_ELIGIBLE" and e_value is None:
            raise ValueError(f"BLOCKED: verified biofuel requires E for {definition.path_id}")
        status_out = "VERIFIED" if status == "VERIFIED_ELIGIBLE" and e_value is not None else "ESTIMATED"
        if e_value is None:
            if cslip_percent is None and (definition.methane_slip_applicable or definition.cslip_required):
                cslip_percent = definition.default_cslip_percent
            resolved = _validated_cslip(definition, cslip_percent, status_out)
            if definition.path_id == "UCO_FAME":
                if definition.default_e_g_per_mj is None:
                    raise ValueError(f"BLOCKED: biofuel E required for {definition.path_id}")
                wt_t = definition.default_e_g_per_mj - (definition.cf_co2_g_per_g or Decimal("0")) / (definition.lcv_mj_per_g or Decimal("1"))
            elif definition.default_wt_t_g_per_mj is not None:
                wt_t = definition.default_wt_t_g_per_mj
            else:
                raise ValueError(f"BLOCKED: biofuel default WtT required for {definition.path_id}")
            return _factor_from_definition(resolved, status_out, wt_t, use_defaults=True)
        e = Decimal(str(e_value))
        resolved = _validated_cslip(definition, cslip_percent, status_out)
        if resolved.lcv_mj_per_g is None:
            raise ValueError(f"BLOCKED: LCV required for {definition.path_id}")
        return _factor_from_definition(
            resolved,
            status_out,
            e - (resolved.cf_co2_g_per_g or Decimal("0")) / resolved.lcv_mj_per_g,
            use_defaults=False,
        )
    if definition.wt_t_g_per_mj is None:
        raise ValueError(f"BLOCKED: WtT required for {definition.path_id}")
    if status == "VERIFIED_ELIGIBLE" and definition.cslip_required and cslip_percent is None:
        raise ValueError(f"BLOCKED: recognized Cslip required for {definition.path_id}")
    verified = verified_wt_t is not None or (
        status == "VERIFIED_ELIGIBLE" and definition.cslip_required and cslip_percent is not None
    )
    status_out = "VERIFIED" if verified else ("FIXED" if definition.factor_level == "A" else "ESTIMATED")
    if cslip_percent is None and not verified and (definition.methane_slip_applicable or definition.cslip_required):
        cslip_percent = definition.default_cslip_percent
    resolved = _validated_cslip(definition, cslip_percent, "VERIFIED" if verified else "ESTIMATED")
    wt_t = Decimal(str(verified_wt_t)) if verified_wt_t is not None else definition.wt_t_g_per_mj
    if wt_t is None:
        raise ValueError(f"BLOCKED: WtT required for {definition.path_id}")
    return _factor_from_definition(resolved, status_out, wt_t, use_defaults=not verified)


def resolve_factor(path_id: str, qualification_status: str = "NOT_DEMONSTRATED",
                   e_value: Optional[Decimal] = None, eu_value: Optional[Decimal] = None,
                   cslip_percent: Optional[Decimal] = None,
                   verified_wt_t: Optional[Decimal] = None,
                   report_year: Optional[int] = None) -> FuelFactor:
    """Compatibility resolver returning only the resolved factor."""
    requested = _key(path_id)
    qualification = str(qualification_status).upper()
    factor = _resolve_factor(
        path_id,
        qualification_status=qualification,
        e_value=e_value,
        eu_value=eu_value,
        cslip_percent=cslip_percent,
        verified_wt_t=verified_wt_t,
        report_year=report_year,
    )
    reason = (
        "RFNBO_QUALIFICATION_NOT_DEMONSTRATED"
        if factor.path_id != requested and qualification in {"NOT_DEMONSTRATED", "INELIGIBLE"}
        else "FALLBACK_PATH" if factor.path_id != requested else "DIRECT_RESOLUTION"
    )
    return replace(
        factor,
        requested_path_id=requested,
        resolution_reason=reason,
        qualification_status=qualification,
    )


def resolve_factor_trace(path_id: str, qualification_status: str = "NOT_DEMONSTRATED",
                        e_value: Optional[Decimal] = None, eu_value: Optional[Decimal] = None,
                        cslip_percent: Optional[Decimal] = None,
                        verified_wt_t: Optional[Decimal] = None,
                        report_year: Optional[int] = None) -> FactorResolutionTrace:
    """Resolve a factor while retaining the requested-to-resolved path decision."""
    factor = resolve_factor(
        path_id,
        qualification_status=qualification_status,
        e_value=e_value,
        eu_value=eu_value,
        cslip_percent=cslip_percent,
        verified_wt_t=verified_wt_t,
        report_year=report_year,
    )
    requested = factor.requested_path_id or _key(path_id)
    qualification = factor.qualification_status or str(qualification_status).upper()
    resolved = factor.path_id
    reason = factor.resolution_reason or "DIRECT_RESOLUTION"
    source_ids = tuple(dict.fromkeys(e.source_id for e in factor.source_evidence))
    return FactorResolutionTrace(
        requested_path_id=requested,
        resolved_path_id=resolved,
        resolution_reason=reason,
        qualification_status=qualification,
        factor_status=factor.factor_status,
        factor=factor,
        source_ids=source_ids,
    )


# Explicit long-form alias for callers discovering the trace API by name.
resolve_factor_with_trace = resolve_factor_trace
