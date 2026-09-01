"""Port identity loading and the first-release scope-rate rules."""

import csv
import re
from pathlib import Path
from typing import Mapping, Optional

from .models import ScopeRates
from .provenance import PortDecision


PORT_COLUMNS = (
    "unlocode",
    "portName",
    "countryCode",
    "territoryType",
    "territoryName",
    "euEtsStatus",
    "fuelEuStatus",
    "ruleSourceId",
    "sourceVersion",
)
EXPECTED_STATUSES = {
    "EU_MEMBER": ("IN_SCOPE", "IN_SCOPE"),
    "EU_MEMBER_SPECIAL": ("IN_SCOPE", "IN_SCOPE"),
    "OMR": ("IN_SCOPE", "OMR"),
    "EEA_NO_IS": ("IN_SCOPE", "THIRD_COUNTRY"),
    "OCT": ("THIRD_COUNTRY", "THIRD_COUNTRY"),
    "SVALBARD": ("THIRD_COUNTRY", "THIRD_COUNTRY"),
    "FAROE_ISLANDS": ("THIRD_COUNTRY", "THIRD_COUNTRY"),
    "THIRD_COUNTRY": ("THIRD_COUNTRY", "THIRD_COUNTRY"),
}
DEFAULT_PORT_TABLE_PATH = (
    Path(__file__).resolve().parents[2]
    / "官方参考资料"
    / "港口基础数据"
    / "UNLOCODE_2025-1_港口制度身份清单.csv"
)


def _normalize_unlocode(value: str) -> str:
    normalized = re.sub(r"[\s/-]", "", str(value or "").strip().upper())
    if not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{3}", normalized):
        raise ValueError(f"Invalid UN/LOCODE: {value or ''}")
    return normalized


def load_port_table(path: Optional[str | Path] = None) -> dict[str, dict[str, str]]:
    resolved = Path(path) if path is not None else DEFAULT_PORT_TABLE_PATH
    with resolved.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != PORT_COLUMNS:
            raise ValueError(f"Unexpected port table columns: {reader.fieldnames}")
        table: dict[str, dict[str, str]] = {}
        for row_number, row in enumerate(reader, start=2):
            code = _normalize_unlocode(row.get("unlocode", ""))
            territory_type = row.get("territoryType", "")
            expected = EXPECTED_STATUSES.get(territory_type)
            valid = (
                expected is not None
                and row.get("countryCode") == code[:2]
                and bool(row.get("portName"))
                and (row.get("euEtsStatus"), row.get("fuelEuStatus")) == expected
                and "PORT-02" in (row.get("ruleSourceId", "").split(";"))
                and bool(row.get("sourceVersion"))
            )
            if not valid:
                raise ValueError(f"Invalid port identity row {row_number}: {code}")
            if code in table:
                raise ValueError(f"Duplicate UN/LOCODE in formal table: {code}")
            table[code] = dict(row, unlocode=code)
    return table


def _matrix_rate(statuses: tuple[str, str]) -> tuple[object, str]:
    from decimal import Decimal

    if any(status not in {"IN_SCOPE", "THIRD_COUNTRY"} for status in statuses):
        raise ValueError(f"Unsupported port status combination: {statuses}")
    count = sum(status == "IN_SCOPE" for status in statuses)
    if count == 2:
        return Decimal("1"), "BOTH_IN_SCOPE"
    if count == 1:
        return Decimal("0.5"), "ONE_IN_SCOPE"
    return Decimal("0"), "BOTH_THIRD_COUNTRY"


def calculate_scope_rates(
    year: int,
    departure_port: str,
    arrival_port: str,
    table: Optional[Mapping[str, Mapping[str, str]]] = None,
) -> ScopeRates:
    from decimal import Decimal

    if not isinstance(year, int) or not 2024 <= year <= 2030:
        raise ValueError(f"Supported reporting years are 2024-2030: {year}")
    ports = table if table is not None else load_port_table()
    departure_code = _normalize_unlocode(departure_port)
    arrival_code = _normalize_unlocode(arrival_port)
    try:
        departure = ports[departure_code]
        arrival = ports[arrival_code]
    except KeyError as exc:
        raise ValueError(f"Port not found in formal table: {exc.args[0]}") from exc

    ets_scope, ets_reason = _matrix_rate((departure["euEtsStatus"], arrival["euEtsStatus"]))
    surrender = Decimal("0.4") if year == 2024 else Decimal("0.7") if year == 2025 else Decimal("1")
    fuel_eu_scope = None
    fuel_eu_applicable = year >= 2025
    fuel_eu_reason = None
    if fuel_eu_applicable:
        if "OMR" in (departure["fuelEuStatus"], arrival["fuelEuStatus"]):
            fuel_eu_scope = Decimal("0.5")
            fuel_eu_reason = "ONE_IN_SCOPE"
        else:
            fuel_eu_scope, fuel_eu_reason = _matrix_rate((departure["fuelEuStatus"], arrival["fuelEuStatus"]))
    departure_decision = PortDecision(
        unlocode=departure["unlocode"],
        port_name=departure["portName"],
        eu_ets_identity=departure["euEtsStatus"],
        fuel_eu_identity=departure["fuelEuStatus"],
        rule_source_id=departure["ruleSourceId"],
        source_version=departure["sourceVersion"],
    )
    arrival_decision = PortDecision(
        unlocode=arrival["unlocode"],
        port_name=arrival["portName"],
        eu_ets_identity=arrival["euEtsStatus"],
        fuel_eu_identity=arrival["fuelEuStatus"],
        rule_source_id=arrival["ruleSourceId"],
        source_version=arrival["sourceVersion"],
    )
    return ScopeRates(
        eu_ets_scope_rate=ets_scope,
        eu_ets_surrender_rate=surrender,
        eu_ets_effective_rate=ets_scope * surrender,
        fuel_eu_scope_rate=fuel_eu_scope,
        fuel_eu_applicable=fuel_eu_applicable,
        departure_port=departure_decision,
        arrival_port=arrival_decision,
        eu_ets_reason=ets_reason,
        fuel_eu_reason=fuel_eu_reason,
    )
