"""Versioned, canonical input/expectation storage; no production dependencies."""
import hashlib
import json
from pathlib import Path
import re
from fractions import Fraction

VERSION = "business-reference-v1"
DISCLAIMER = "合成数据，仅用于系统验证和未来示例复用"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def _no_floats(value, path="case"):
    if isinstance(value, float):
        raise ValueError(f"{path}: float forbidden; use decimal strings")
    if isinstance(value, dict):
        for key, item in value.items():
            _no_floats(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _no_floats(item, f"{path}[{index}]")


def validate_case(case):
    case_id = case.get("id", "")
    if not isinstance(case_id, str) or not re.fullmatch(r"[A-D]-[A-Za-z0-9_-]+", case_id):
        raise ValueError("invalid stable case id")
    family = case.get("family")
    if family not in ("A", "B", "C", "D") or not case_id.startswith(family + "-"):
        raise ValueError("invalid family")
    for field in ("name", "purpose", "coverage", "assumptions"):
        if not case.get(field):
            raise ValueError(f"missing metadata: {field}")
    for field in ("name", "purpose"):
        if not isinstance(case[field], str):
            raise ValueError(f"metadata must be a string: {field}")
    for field in ("coverage", "assumptions"):
        if not isinstance(case[field], list) or not all(isinstance(item, str) and item for item in case[field]):
            raise ValueError(f"metadata must be a non-empty list of strings: {field}")
    if case.get("synthetic") is not True or type(case.get("compact")) is not bool:
        raise ValueError("synthetic declaration and compact membership required")
    for field in ("request", "snapshot"):
        if not isinstance(case.get(field), dict):
            raise ValueError(f"missing {field}")
    if not {"reportYear", "baseline", "candidates", "departurePort", "arrivalPort"} <= case["request"].keys():
        raise ValueError("request envelope missing fields")
    if not isinstance(case.get("expected_issues"), list):
        raise ValueError("expected issues required, including empty list")
    valid_scopes = {"CASE", "CANDIDATE"}
    for issue in case["expected_issues"]:
        if not isinstance(issue, dict) or not isinstance(issue.get("code"), str) or not issue["code"]:
            raise ValueError("each expected issue needs a code")
        if issue.get("scope") not in valid_scopes:
            raise ValueError("expected issue scope must be CASE or CANDIDATE")
        if issue["scope"] == "CASE" and issue.get("candidate_id") is not None:
            raise ValueError("case issue cannot have candidate_id")
        if issue["scope"] == "CANDIDATE" and not isinstance(issue.get("candidate_id"), str):
            raise ValueError("candidate issue needs candidate_id")
    if case.get("expected_http_status") not in (200, 422):
        raise ValueError("explicit expected HTTP status required")
    _no_floats(case)
    scope = case["snapshot"].get("scope")
    if not isinstance(scope, dict) or set(scope) != {"geo", "surrender", "fueleu"}:
        raise ValueError("snapshot scope must have geo, surrender and fueleu")
    if not isinstance(case["snapshot"].get("candidates"), dict):
        raise ValueError("candidate snapshots must be an object")
    factors = [case["snapshot"].get("baseline"), *case["snapshot"]["candidates"].values()]
    if any(not isinstance(f, dict) for f in factors):
        raise ValueError("snapshot factors must be objects")
    required = {"path_id", "lcv", "wtt", "co2", "ch4", "n2o", "slip", "methane",
                "rwd", "biomass", "factor_status", "qualification", "mode", "equipment_id"}
    for factor in factors:
        if not required <= factor.keys():
            raise ValueError("normalized factor missing required field")
        for field in ("lcv", "wtt", "co2", "ch4", "n2o", "rwd", "biomass"):
            if not isinstance(factor[field], str):
                raise ValueError(f"normalized factor {field} must be a decimal string")
            number = Fraction(factor[field])
            if field in ("lcv", "rwd") and number <= 0:
                raise ValueError(f"normalized {field} must be positive")
            if field in ("co2", "ch4", "n2o", "biomass") and number < 0:
                raise ValueError(f"normalized {field} must be nonnegative")
            if field == "biomass" and number > 1:
                raise ValueError("biomass exceeds one")
        if factor["slip"] is not None and not 0 <= Fraction(factor["slip"]) <= 100:
            raise ValueError("slip outside 0..100")
        if not isinstance(factor["methane"], bool):
            raise ValueError("normalized factor methane must be boolean")
    return case


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_case(root, case, expected):
    validate_case(case)
    directory = root / case["id"]
    metadata = {k: v for k, v in case.items() if k not in ("request", "snapshot")}
    write_json(directory / "metadata.json", metadata)
    write_json(directory / "request.json", case["request"])
    write_json(directory / "factor-snapshot.json", case["snapshot"])
    write_json(directory / "expected.json", {
        "reference_version": VERSION, "disclaimer": DISCLAIMER,
        "input_sha256": fingerprint(case), "expected_sha256": fingerprint(expected),
        "result": expected,
    })
    return directory


def load_case(path: Path):
    def read(name):
        return json.loads((path / name).read_text(encoding="utf-8"))
    case = {**read("metadata.json"), "request": read("request.json"),
            "snapshot": read("factor-snapshot.json")}
    validate_case(case)
    envelope = read("expected.json")
    if envelope["input_sha256"] != fingerprint(case):
        raise ValueError(f"{case['id']}: input fingerprint mismatch")
    if envelope["expected_sha256"] != fingerprint(envelope["result"]):
        raise ValueError(f"{case['id']}: expected fingerprint mismatch")
    if envelope["reference_version"] != VERSION:
        raise ValueError("reference version mismatch")
    return case
