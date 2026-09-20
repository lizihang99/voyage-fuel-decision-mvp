"""Freeze/verify independent synthetic cases, then exercise kernel/API/exports."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import hashlib

from business_case_schema import DISCLAIMER, fingerprint, write_json

ROOT = Path(__file__).resolve().parents[2]
CASE_ROOT = ROOT / "tests/fixtures/business-cases"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))


def prepare_reference(case_root, *, freeze=False):
    with tempfile.TemporaryDirectory() as temporary:
        output = Path(temporary) / "reference.json"
        command = [sys.executable, "-X", "utf8", str(Path(__file__).with_name("business_case_worker.py")),
                   "--root", str(case_root), "--output", str(output)]
        if freeze:
            command.append("--freeze")
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if completed.returncode:
            raise RuntimeError("Independent stage failed before product invocation:\n" + (completed.stderr or completed.stdout))
        return json.loads(output.read_text(encoding="utf-8"))


def run_business_case_suite(case_root=CASE_ROOT, *, mode="full", exports=True):
    started = time.monotonic()
    reference = prepare_reference(case_root)
    # The entire expected bundle is already calculated and fingerprint-checked.
    from business_case_assertions import validate_product_result
    from voyage_fuel.json_io import parse_decision_case, decision_case_result_to_dict
    from voyage_fuel.case_calculator import calculate_parsed_decision_case
    from voyage_fuel.web import app
    from fastapi.testclient import TestClient
    cases = reference["results"]
    if mode == "compact":
        cases = [entry for entry in cases if entry["case"]["compact"]]
    results = []
    with TestClient(app) as client:
        for entry in cases:
            case, expected = entry["case"], entry["expected"]
            item = {"id": case["id"], "family": case["family"], "compact": case["compact"],
                    "coverage": case["coverage"], "expected_sha256": fingerprint(expected),
                    "checks": {}, "differences": [], "assertions": 0,
                    "csv_exported": False, "pdf_exported": False}
            try:
                parsed = parse_decision_case(case["request"])
                kernel = decision_case_result_to_dict(calculate_parsed_decision_case(parsed))
                item["checks"]["kernel"] = validate_product_result(case, expected, kernel)
                response = client.post("/api/calculate", json=case["request"])
                if response.status_code != case["expected_http_status"]:
                    item["differences"].append({"path": "http_status", "expected": case["expected_http_status"],
                                                "actual": response.status_code})
                actual = response.json()
                item["assertions"] += 1
                item["checks"]["api"] = validate_product_result(case, expected, actual)
                should_export = expected["baseline"] is not None
                if bool(actual.get("result_snapshot_id")) != should_export:
                    item["differences"].append({"path": "snapshot.availability", "expected": should_export,
                                                "actual": bool(actual.get("result_snapshot_id"))})
                item["assertions"] += 1
                if exports and actual.get("result_snapshot_id"):
                    from business_case_surfaces import validate_exports
                    payload = {"resultSnapshotId": actual["result_snapshot_id"]}
                    csv_response = client.post("/api/export/csv", json=payload)
                    pdf_response = client.post("/api/export/pdf", json=payload)
                    item["assertions"] += 2
                    for name, export in (("csv", csv_response), ("pdf", pdf_response)):
                        if export.status_code != 200:
                            item["differences"].append({"path": name + ".status", "expected": 200,
                                                        "actual": export.status_code})
                        item[name + "_exported"] = export.status_code == 200
                    if csv_response.status_code == pdf_response.status_code == 200:
                        item["checks"]["exports"] = validate_exports(
                            case, expected, actual, csv_response.text, pdf_response.content)
                elif exports:
                    from business_case_surfaces import validate_exports
                    item["checks"]["exports"] = validate_exports(case, expected, actual, None, None)
                    for endpoint in ("csv", "pdf"):
                        rejected = client.post("/api/export/" + endpoint, json={})
                        item["assertions"] += 1
                        if rejected.status_code != 409:
                            item["differences"].append({"path": endpoint + ".no_snapshot", "expected": 409,
                                                        "actual": rejected.status_code})
            except Exception as error:
                item["differences"].append({"path": "harness_exception", "actual": repr(error)})
            for name, check in item["checks"].items():
                item["assertions"] += check["assertions"]
                item["differences"].extend({"surface": name, **d} for d in check["differences"])
            item["passed"] = not item["differences"]
            results.append(item)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(), "mode": mode,
        "disclaimer": DISCLAIMER, "reference_production_imports": reference["production_modules_loaded"],
        "family_count": len({r["family"] for r in results}),
        "request_count": len(results), "compact_request_count": sum(r["compact"] for r in results),
        "family_request_counts": {family: sum(r["family"] == family for r in results)
                                  for family in ("A", "B", "C", "D")},
        "parameterized_variant_count": sum(not r["compact"] for r in results),
        "parameterized_variant_definition": "完整自动集中未选入 compact 的独立冻结请求",
        "api_calculation_count": len(results),
        "csv_export_count": sum(r["csv_exported"] for r in results),
        "pdf_export_count": sum(r["pdf_exported"] for r in results),
        "runtime": sys.version,
        "source_sha256": {str(path.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in [*sorted((ROOT / "src/voyage_fuel").rglob("*.py")),
                                       *sorted((ROOT / "src/voyage_fuel/data").glob("*.csv")),
                                       *sorted((ROOT / "src/voyage_fuel/templates").glob("*.html")),
                                       *sorted((ROOT / "src/voyage_fuel/static").glob("*")),
                                       *sorted((ROOT / "tools/validation").glob("business_case_*.py"))]},
        "assertion_count": sum(r["assertions"] for r in results),
        "passed": sum(r["passed"] for r in results), "failed": sum(not r["passed"] for r in results),
        "elapsed_seconds": round(time.monotonic() - started, 3), "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", action="store_true", help="Explicitly rebuild independent expectations")
    parser.add_argument("--mode", choices=("compact", "full"), default="full")
    parser.add_argument("--no-exports", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/validation/business-case-results.json")
    args = parser.parse_args()
    if args.freeze:
        result = prepare_reference(CASE_ROOT, freeze=True)
        print(json.dumps({"frozen_requests": len(result["results"]), "production_imports": []}))
        return
    result = run_business_case_suite(mode=args.mode, exports=not args.no_exports)
    write_json(args.output, result)
    print(json.dumps({k: v for k, v in result.items() if k != "results"}, ensure_ascii=False))
    for item in result["results"]:
        if not item["passed"]:
            print(item["id"], json.dumps(item["differences"][:4], ensure_ascii=False))
    raise SystemExit(1 if result["failed"] else 0)


if __name__ == "__main__":
    main()
